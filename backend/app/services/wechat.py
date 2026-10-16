"""wechat —— 微信钥匙的通道与策略（docs/1.7，1.6 §4.12 预留位的点亮册；1.8 快进建号/验证收编）。

两层，与 sms.py（SmsGate 通道）/ passwords.py（PasswordMixin 策略）同构：
- WeChatGate：微信官方网页授权的换脸（code→openid+昵称）与授权地址拼装，含假通道
  （provider=fake，开发零资质全链可测——凭证即身份号，「|」后可带测试昵称；real 未配
  AppID/Secret 时通道按 wechat_off 关死，绝不能拿假通道上生产）；绑定凭条的签发与核销
  （指纹制、10 分钟一次性，同钥匙/验证码规矩）。
- WechatMixin：混入 AccountBook 的微信钥匙策略。绑定两档制（verified=绑定那一刻
  手机号是否验过）与 device_keys.verified 完全镜像——验明正身杀"顺手绑"（D4 的
  微信面），接管/注销/换锁清位；绑定失败（凭条过期/冲突）一律静默跳过不拖垮主流程
  （§6 降级）。1.8 两件：快进建号（fast 支——授权即本人，生而正式绑、手机号欠着、
  昵称三优先级、原子落账）；验证收编 _adopt_binding（登录页验明正身那一刻，当前
  设备登着的快进号上的微信自动迁绑到老账号，不需再授权一次）。
  AccountBook 提供库会话、钥匙库与名片/手机号内部件。
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, NamedTuple
from urllib.parse import urlencode

import httpx
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core import clock, errors, security
from ..core.config import Settings
from ..db.models import Account, WechatPending

# 微信官方端点（网页授权 / OAuth2 换 access_token——本项目只取 openid）
WX_AUTH_URL = "https://open.weixin.qq.com/connect/oauth2/authorize"
WX_TOKEN_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"
WX_USERINFO_URL = "https://api.weixin.qq.com/sns/userinfo"
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

    def exchange(self, code: str, want_profile: bool = False) -> tuple[str, str | None]:
        """授权凭证换 (openid, 微信昵称|None)。凭证侧 5 分钟一次性：过期/用过报
        可自愈的 wechat_code_invalid，其余（服务不通/配置错）报 wechat_unavailable。
        昵称只在快进建号路要（want_profile，1.8 §4.1 snsapi_userinfo 一步）——
        直进/落卡/占卡验证三支拿到即扔，不白付一趟 userinfo 往返；任何抓取失败
        只回 None 不拦路（§4.2）。"""
        if not self.real:
            # 假通道：凭证即身份号；「|」后可选携带测试昵称（1.8 快进测试矩阵用）
            openid, _, nick = code.partition("|")
            return openid, (nick or None)
        if not self._configured():
            raise errors.wechat_off()
        try:
            # 一条连接跑完 token+userinfo 两趟（同主机，省一次 TLS 握手）
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
                errcode = data.get("errcode")
                # 40029=凭证无效 40163=凭证已用过 → 重点一次即走通；其余按不可用
                if errcode in (40029, 40163):
                    raise errors.wechat_code_invalid()
                if errcode:
                    raise errors.wechat_unavailable()
                openid = data.get("openid")
                if not openid:
                    raise errors.wechat_unavailable()
                nick = (
                    self._fetch_nickname(
                        client,
                        str(data.get("access_token") or ""),
                        str(openid),
                    )
                    if want_profile
                    else None
                )
        except errors.ApiError:
            raise
        except Exception:  # noqa: BLE001 - 网络/解析故障统一明示，不静默
            raise errors.wechat_unavailable() from None
        return str(openid), nick

    def _fetch_nickname(
        self, client: httpx.Client, access_token: str, openid: str
    ) -> str | None:
        """snsapi_userinfo 抓微信昵称（scope 已具备）：拿不到/没给一律 None，
        建号路自会走随机名兜底（1.8 §4.2），绝不拖垮授权本身。
        client 由 exchange 传入——与 token 调用共用一条连接。"""
        if not access_token:
            return None
        try:
            resp = client.get(
                WX_USERINFO_URL,
                params={
                    "access_token": access_token,
                    "openid": openid,
                    "lang": "zh_CN",
                },
            )
            data = resp.json()
        except Exception:  # noqa: BLE001 - 昵称是锦上添花，任何故障静默放弃
            return None
        if data.get("errcode"):
            return None
        nick = data.get("nickname")
        return str(nick) if nick else None

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


class WechatLoginOut(NamedTuple):
    """认人门回话（定名字段，位置不随分支变义）：
    - status："ok"（绑过直进）|"unbound"（落卡发凭条）|"created"（快进建号）
    - token/view：ok/created 的会话钥匙与本人视图；unbound 均为 None
    - bind_token：ok/unbound 的绑定凭条；created 不发（绑定一次完成）→ None
    - nickname_random：created 的随机名旗（前端 toast 报名字的判据）；其余 False"""

    status: str
    token: str | None
    view: dict | None
    bind_token: str | None
    nickname_random: bool


class WechatMixin:
    """微信钥匙节：向 AccountBook 只暴露认人门、占卡微信验证与绑定清场钩子。"""

    # 由 AccountBook.__init__ 装配（同 self.keys / self.sms）
    wechat: WeChatGate

    def wechat_login(
        self,
        *,
        code: str,
        device_marker: str,
        fast: bool = False,
        nickname: str | None = None,
        phone: str | None = None,
        chibi: dict[str, Any] | None = None,
        chibi_set: bool = False,
    ) -> WechatLoginOut:
        """认人门（1.7 §4.1/4.2 + 1.8 §4.1~§4.3 + 修订二）。
        回话字段义见 WechatLoginOut：
        - "ok"：绑过直进（牢靠绑=验明正身，杀未验证钥匙；凭条照发——换绑顶替的种子）；
          修订二新增一支：快进带号撞在册账号且同机续接窗内 → 进既有账号+微信正式绑；
        - "unbound"：fast=False 的 1.7 原路（登录页找回面落卡分支，4.7 防误快进护栏）；
        - "created"：fast=True 的快进建号（1.8）——微信生而正式绑、不发凭条（绑定一次
          完成）；修订二：卡上手机号没人用则建带号账号，选了头像落档。
        - 快进带号撞占用（异机/过窗）：抛 phone_taken，整体不生效（凭据作废，重点走三出口）。"""
        # 昵称只在快进路要（fast+未绑才消费）；已绑+fast 的 ok 支多抓一趟就多抓——
        # 换它一分支的简明，不值拆两段通道调用
        openid, wx_nickname = self.wechat.exchange(code, want_profile=fast)
        account = self._active_by_openid(openid)
        if account is not None:
            bind_token = self.wechat.issue_bind_token(openid)
            if account.wechat_verified:
                self.keys.revoke_unverified(account.id)
                self.db.commit()
            token = self.keys.issue(
                account.id, device_marker, verified=account.wechat_verified
            )
            return WechatLoginOut(
                status="ok",
                token=token,
                view=self.view(account.id, viewer="self"),
                bind_token=bind_token,
                nickname_random=False,
            )
        if not fast:
            bind_token = self.wechat.issue_bind_token(openid)
            return WechatLoginOut(
                status="unbound",
                token=None,
                view=None,
                bind_token=bind_token,
                nickname_random=False,
            )
        return self._fast_create(
            openid,
            wx_nickname,
            nickname=nickname,
            device_marker=device_marker,
            phone=phone,
            chibi=chibi,
            chibi_set=chibi_set,
        )

    def _fast_create(
        self,
        openid: str,
        wx_nickname: str | None,
        *,
        nickname: str | None,
        device_marker: str,
        phone: str | None = None,
        chibi: dict[str, Any] | None = None,
        chibi_set: bool = False,
    ) -> WechatLoginOut:
        """快进建号（1.8 §4.1~§4.3 + 修订二「卡上填过的都算数」）：授权那一刻即
        本人——生而正式绑（§8 裁决 A）。手机号两支：没填→无号快进号（phone=None，
        注销预留的空位）；填了没人用→带号建号（两把钥匙一步到位）。昵称三优先级：
        卡上手填（strip 空视同没填）→ 微信昵称过清洗规矩（不合格视同拿不到，§4.2）
        → 随机名；头像选了落档、没选默认小人（与手填建号同一条 D2 规矩）。
        原子性（§4.9-3）：账号行 flush（openid/phone 唯一索引撞在此暴露）后由
        keys.issue 的 commit 一并落账，任何失败整体回滚不留半个账号。"""
        # 循环导入（accounts 先 import 本模块）：混入方运行时取用建号模块级件
        from .accounts import (
            DEFAULT_CHIBI,
            _resolve_nickname,
            _validate_chibi,
            new_account,
            resolve_nickname_report,
        )

        phone = (phone or "").strip() or None
        if phone:
            # 修订二：撞在册账号——同机续接窗内直接进既有账号并把微信正式绑上
            # （授权即本人；与手填建号的续接分支同规），异机/过窗 phone_taken
            # 落三出口（凭据整体作废，不半建）
            self._check_phone(phone)
            existing = self._active_by_phone(phone)
            if existing is not None:
                token = self._resume_or_taken(existing, device_marker)
                self._rebind(existing, openid, verified=True)
                return WechatLoginOut(
                    status="ok",
                    token=token,
                    view=self.view(existing.id, viewer="self"),
                    bind_token=None,
                    nickname_random=False,
                )

        manual = (nickname or "").strip()
        if manual:
            # 手填不合格如实报（与 signup 手填一致），不静默改名
            final_name = _resolve_nickname(manual)
            nickname_random = False
        else:
            # 微信昵称空/清洗不合格 → 落随机名并如实报（判据单一源在 accounts）
            final_name, nickname_random = resolve_nickname_report(wx_nickname)
        chibi_json = json.dumps(_validate_chibi(chibi) if chibi_set else DEFAULT_CHIBI)
        # 建号行基础六件走 accounts.new_account 工厂（手填建号同源），微信三列就地透传
        account = new_account(
            phone=phone,
            nickname=final_name,
            chibi_json=chibi_json,
            device_marker=device_marker,
            wechat_openid=openid,
            wechat_verified=True,
            wechat_bound_at=clock.now(),
        )
        self.db.add(account)
        try:
            self.db.flush()
            token = self.keys.issue(account.id, device_marker, verified=True)
        except IntegrityError:
            # openid/phone 并发撞唯一索引：整体不生效，重点一次即走通
            # （撞号的重试自然落上方占用分支，不在此另设一支）
            self.db.rollback()
            raise errors.wechat_fast_failed() from None
        return WechatLoginOut(
            status="created",
            token=token,
            view=self.view(account.id, viewer="self"),
            bind_token=None,
            nickname_random=nickname_random,
        )

    def _adopt_binding(self, target: Account, current: Account | None) -> bool:
        """验证收编（1.8 §4.5/B1）：当前设备登着的账号绑着微信且 ≠ target → openid
        迁到 target（正式绑；target 原有微信被顶替覆盖——1.7 一个微信只开一扇门），
        原（快进）账号就地解绑搁置，不需要用户再授权一次。幂等：凭条已把同一微信
        绑走时原账号 openid 已清，迁移自然空转（返回 False）。"""
        if current is None or current.id == target.id or not current.wechat_openid:
            return False
        self._rebind(target, current.wechat_openid, verified=True)
        return True

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
        openid, _ = self.wechat.exchange(code)
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
        self._rebind(account, openid, verified=verified)
        return True

    def _rebind(self, target: Account, openid: str, *, verified: bool) -> None:
        """openid 换位落库的唯一正路（_try_bind 顶替 / _adopt_binding 收编共用）：
        清旧持有位 → flush → 写 target 三列 → commit。唯一索引下清位与写位之间
        必须 flush 落序——同表两行 UPDATE 按主键序批量执行，持有者主键更大时
        「写新位」会先于「清旧位」撞 openid 唯一索引（生产期偶发、测试难复现）；
        新增换位路径一律走这里，不要再手抄两行换位。"""
        holder = self._active_by_openid(openid)
        if holder is not None and holder.id != target.id:
            self._clear_binding(holder)
            self.db.flush()
        target.wechat_openid = openid
        target.wechat_verified = verified
        target.wechat_bound_at = clock.now()
        self.db.commit()

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
