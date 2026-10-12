"""wechat —— 微信钥匙的通道与策略（docs/1.7，1.6 §4.12 预留位的点亮册）。

两层，与 sms.py（SmsGate 通道）/ passwords.py（PasswordMixin 策略）同构：
- WeChatGate：微信官方网页授权的换脸（code→openid）与授权地址拼装，含假通道
  （provider=fake，开发零资质全链可测——凭证即身份号；real 未配 AppID/Secret
  时通道按 wechat_off 关死，绝不能拿假通道上生产）；绑定凭条的签发与核销
  （指纹制、10 分钟一次性，同钥匙/验证码规矩）。
- WechatMixin：混入 AccountBook 的微信钥匙策略。绑定两档制（verified=绑定那一刻
  手机号是否验过）与 device_keys.verified 完全镜像——验明正身杀"顺手绑"（D4 的
  微信面），接管/注销/换锁清位；绑定失败（凭条过期/冲突）一律静默跳过不拖垮主流程
  （§6 降级）。AccountBook 提供库会话、钥匙库与名片/手机号内部件。
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..core import clock, errors, security
from ..core.config import Settings
from ..db.models import Account, WechatPending

# 微信官方端点（网页授权 / OAuth2 换 access_token——本项目只取 openid）
WX_AUTH_URL = "https://open.weixin.qq.com/connect/oauth2/authorize"
WX_TOKEN_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"
# 1.6 §4.12 拍板弹窗确认（snsapi_userinfo）；静默秒认（snsapi_base）留二期评估
WX_SCOPE = "snsapi_userinfo"
# 授权凭证微信侧 5 分钟一次性；绑定凭条与建号续接窗口（SIGNUP_RESUME_WINDOW）同刻度
BIND_TOKEN_TTL = timedelta(minutes=10)


class WeChatGate:
    """微信通道：授权地址 / 换 openid / 绑定凭条。策略一概不管（归 WechatMixin）。"""

    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        self.real = settings.wechat_provider == "real"

    def _configured(self) -> bool:
        return bool(self.settings.wechat_app_id and self.settings.wechat_app_secret)

    def build_url(self, redirect_uri: str, state: str) -> str:
        """拼授权地址（前端拿去整页跳转）。假通道把假凭证直接拼进回跳地址，
        开发浏览器里点一下即可走完一圈。"""
        if not self.real:
            sep = "&" if "?" in redirect_uri else "?"
            return f"{redirect_uri}{sep}code=wx_dev&state={state}"
        if not self._configured():
            raise errors.wechat_off()
        params = urlencode(
            {
                "appid": self.settings.wechat_app_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": WX_SCOPE,
                "state": state,
            }
        )
        return f"{WX_AUTH_URL}?{params}#wechat_redirect"

    def exchange(self, code: str) -> str:
        """授权凭证换 openid。微信侧 5 分钟一次性：过期/用过报可自愈的
        wechat_code_invalid，其余（服务不通/配置错）报 wechat_unavailable。"""
        if not self.real:
            return code  # 假通道：凭证即身份号（测试里 code 就是 openid）
        if not self._configured():
            raise errors.wechat_off()
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(
                    WX_TOKEN_URL,
                    params={
                        "appid": self.settings.wechat_app_id,
                        "secret": self.settings.wechat_app_secret,
                        "code": code,
                        "grant_type": "authorization_code",
                    },
                )
            data = resp.json()
        except Exception:  # noqa: BLE001 - 网络/解析故障统一明示，不静默
            raise errors.wechat_unavailable() from None
        errcode = data.get("errcode")
        if errcode:
            # 40029=凭证无效 40163=凭证已用过 → 重点一次即走通；其余按不可用
            if errcode in (40029, 40163):
                raise errors.wechat_code_invalid()
            raise errors.wechat_unavailable()
        openid = data.get("openid")
        if not openid:
            raise errors.wechat_unavailable()
        return str(openid)

    # ---- 绑定凭条（生面孔转名片/验明正身时顺手绑的凭据） ----

    def issue_bind_token(self, openid: str) -> str:
        token = security.new_bind_token()
        now = clock.now()
        self.db.add(
            WechatPending(
                fingerprint=security.bind_fingerprint(token),
                openid=openid,
                expires_at=now + BIND_TOKEN_TTL,
                created_at=now,
            )
        )
        self.db.commit()
        return token

    def take_bind_token(self, token: str) -> str | None:
        """核销：一次性（删行），过期/查无返回 None（调用方静默跳过绑定）。
        顺手清扫全部过期行——凭条表不设清理任务也不积压。"""
        now = clock.now()
        self.db.execute(delete(WechatPending).where(WechatPending.expires_at <= now))
        row = self.db.execute(
            select(WechatPending).where(
                WechatPending.fingerprint == security.bind_fingerprint(token)
            )
        ).scalar_one_or_none()
        if row is None:
            self.db.commit()
            return None
        openid = row.openid
        self.db.delete(row)
        self.db.commit()
        return openid


class WechatMixin:
    """微信钥匙节：向 AccountBook 只暴露认人门、占卡微信验证与绑定清场钩子。"""

    # 由 AccountBook.__init__ 装配（同 self.keys / self.sms）
    wechat: WeChatGate

    def wechat_login(
        self, *, code: str, device_marker: str
    ) -> tuple[str, str, dict | None, str]:
        """认人门（1.7 §4.1/4.2）：绑过直进，生面孔发凭条。
        返回 ("ok", 钥匙, 本人视图, 绑定凭条) 或 ("unbound", 凭条, None, 同一凭条)。
        牢靠绑=验明正身（杀未验证钥匙，与短信/密码同待遇）；顺手绑只发未验证钥匙
        （与建号那把本机记忆同级）。凭条恒发——绑着的微信想搬到别的账号，下一次
        验明正身凭它顶替换绑（4.5 乙的下文）。"""
        openid = self.wechat.exchange(code)
        bind_token = self.wechat.issue_bind_token(openid)
        account = self._active_by_openid(openid)
        if account is None:
            return "unbound", bind_token, None, bind_token
        if account.wechat_verified:
            self.keys.revoke_unverified(account.id)
            self.db.commit()
        token = self.keys.issue(
            account.id, device_marker, verified=account.wechat_verified
        )
        return "ok", token, self.view(account.id, viewer="self"), bind_token

    def wechat_redeem(
        self,
        *,
        code: str,
        phone: str,
        device_marker: str,
        card: dict[str, Any] | None = None,
    ) -> tuple[dict, str]:
        """占卡「微信验证进入」（1.7 §4.4/4.5）：只认牢靠绑——微信身份绑定前
        验过手机号，与短信出口同一待遇的接管（1.6 §4.5「效果完全一致」：名片
        并入、全设备钥匙连同密码作废、设密宽限窗）。没绑/绑别处/只是顺手绑，
        各报各的指路错。"""
        self._check_phone(phone)
        account = self._active_by_phone(phone)
        if account is None:
            raise errors.no_account()
        openid = self.wechat.exchange(code)
        holder = self._active_by_openid(openid)
        if holder is None:
            raise errors.wechat_unbound()
        if holder.id != account.id:
            raise errors.wechat_bound_other()
        if not account.wechat_verified:
            raise errors.wechat_binding_weak()
        self.keys.revoke_all(account.id)
        self._wipe_password(account)
        self._merge_card(account, card)
        self._grant_grace(account)
        self.db.commit()
        token = self.keys.issue(account.id, device_marker, verified=True)
        return self.view(account.id, viewer="self"), token

    # ---- 绑定钩子（signup/redeem/passwords 三处验明正身流挂点调用） ----

    def _try_bind(
        self, account: Account, bind_token: str | None, *, verified: bool
    ) -> bool:
        """凭条顺手绑：凭条过期/已被用——静默跳过（返回 False），绝不拖垮建号/
        找回主流程（1.7 §6 降级裁决）。凭条有效的换绑走**顶替**：这个微信原先
        绑在别的账号上，验证绑上即顶替（旧绑定当场解开，一个微信永远只开一扇门）；
        同账号重绑只升不降（牢靠不因新凭条降回顺手）。"""
        if not bind_token:
            return False
        openid = self.wechat.take_bind_token(bind_token)
        if openid is None:
            return False
        if account.wechat_openid == openid and account.wechat_verified and not verified:
            return False  # 已是牢靠绑，不降档
        holder = self._active_by_openid(openid)
        if holder is not None and holder.id != account.id:
            self._clear_binding(holder)
        account.wechat_openid = openid
        account.wechat_verified = verified
        account.wechat_bound_at = clock.now()
        self.db.commit()
        return True

    def _active_by_openid(self, openid: str) -> Account | None:
        return self.db.execute(
            select(Account).where(
                Account.wechat_openid == openid, Account.status == "active"
            )
        ).scalar_one_or_none()

    def _sweep_weak_binding(self, account: Account) -> None:
        """D4 的微信面：验明正身时解开"顺手绑"（未验手机号的绑定）——冒填者
        建号顺手绑的微信，真主人验证一次即永久失效（1.7 §4.9）。牢靠绑不动。"""
        if account.wechat_openid and not account.wechat_verified:
            self._clear_binding(account)

    def _clear_binding(self, account: Account) -> None:
        """全清位（接管/注销/换锁）：微信号释放，同一微信此后可绑任何账号。"""
        account.wechat_openid = None
        account.wechat_verified = False
        account.wechat_bound_at = None
