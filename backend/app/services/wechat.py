"""wechat —— 微信钥匙的通道与策略（网页版公众号钥匙 + 小程序钥匙两把，快进建号
/验证收编/跨端认亲）。

两层，与 sms.py（SmsGate 通道）/ passwords.py（PasswordMixin 策略）同构：
- WeChatGate：微信官方授权的换脸（code→openid+统一编号+昵称+头像）与授权地址
  拼装，含假通道（provider=fake，开发零资质全链可测——凭证即身份号，「|」后可
  带测试昵称、头像 URL、统一编号，后两段可缺省；real 未配 AppID/Secret 时通道
  按 wechat_off 关死，绝不能拿假通道上生产）；小程序端走 jscode2session 换
  (openid, 统一编号)，无画像；绑定凭条的签发与核销（指纹制、10 分钟一次性，
  同钥匙/验证码规矩）。
- WechatMixin：混入 AccountBook 的微信钥匙策略。网页版绑定两档制（verified=
  绑定那一刻手机号是否验过）与 device_keys.verified 完全镜像——验明正身杀
  "顺手绑"，接管/注销/换锁清位；小程序钥匙恒正式绑（静默换号即微信作证）。
  跨端认亲按固定顺序：先本端钥匙、再统一编号、都没有按新人办；钥匙与统一
  编号指向两个账号时各记一笔跨端记号交人工，不换号不并号。
  AccountBook 提供库会话、钥匙库与名片/手机号内部件。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, NamedTuple
from urllib.parse import urlencode

import httpx
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core import clock, errors, security
from ..core.config import Settings
from ..db.models import Account, WechatCrossFlag, WechatPending

# 微信官方端点（网页授权 / OAuth2 换 access_token——本项目只取 openid）
WX_AUTH_URL = "https://open.weixin.qq.com/connect/oauth2/authorize"
WX_TOKEN_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"
WX_USERINFO_URL = "https://api.weixin.qq.com/sns/userinfo"
# 小程序登录凭证换 (openid, unionid)——静默接口，不给昵称头像
WX_JSCODE_URL = "https://api.weixin.qq.com/sns/jscode2session"
# 1.6 §4.12 拍板弹窗确认（snsapi_userinfo）；静默秒认（snsapi_base）留二期评估
WX_SCOPE = "snsapi_userinfo"
# 授权凭证微信侧 5 分钟一次性；绑定凭条与建号续接窗口（SIGNUP_RESUME_WINDOW）同刻度
BIND_TOKEN_TTL = timedelta(minutes=10)

# 微信钥匙列族单一源：source → (openid 列, verified 列|None, bound_at 列)。
# 网页版两档（verified 镜像 device_keys）；小程序静默换号即微信作证、恒正式绑，
# 没有 verified 列。凡按端取列/写列/清列一律走这张表，不许 if source 散落
_KEY_COLS = {
    "h5": ("wechat_openid", "wechat_verified", "wechat_bound_at"),
    "mp": ("wechat_mp_openid", None, "wechat_mp_bound_at"),
}


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

    def exchange(self, code: str) -> tuple[str, str | None, str | None, str | None]:
        """网页授权凭证换 (openid, 统一编号|None, 微信昵称|None, 微信头像URL|None)。
        统一编号只在服务号绑进开放平台后随 token 下发（没绑/存量授权拿不到 →
        None，认亲路自然空转）。凭证侧 5 分钟一次性：过期/用过报可自愈的
        wechat_code_invalid，其余（服务不通/配置错）报 wechat_unavailable。
        画像（昵称+头像）无条件取——认人门与占卡验证每次授权都要顺手刷新微信
        头像；unbound 落卡支取了暂不用（头像只在绑上/建号那一刻落库，「等下一次
        授权」的口径），不为省一趟 userinfo 把通道拆成按需两段。任何抓取失败只回
        None 不拦路。"""
        if not self.real:
            # 假通道：凭证即身份号；「|」后可选携带测试昵称、头像 URL、统一编号
            # （第三、四段可缺省，三段/两段/一段旧格式照旧）
            openid, _, rest = code.partition("|")
            nick, _, rest = rest.partition("|")
            head, _, uni = rest.partition("|")
            return openid, (uni or None), (nick or None), (head or None)
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
                openid, unionid = self._session_from(data)
                nick, head = self._fetch_profile(
                    client,
                    str(data.get("access_token") or ""),
                    openid,
                )
        except errors.ApiError:
            raise
        except Exception:  # noqa: BLE001 - 网络/解析故障统一明示，不静默
            raise errors.wechat_unavailable() from None
        return openid, unionid, nick, head

    def exchange_mp(self, code: str) -> tuple[str, str | None]:
        """小程序登录凭证换 (openid, 统一编号|None)。jscode2session 是静默接口，
        不给昵称头像（名片卡由用户手填/一键带入，画像本端没有）。凭证病与网页版
        同款：无效/用过报 wechat_code_invalid（重点一次即走通），其余按不可用。
        real 下小程序一对密钥未配只把本通道按 wechat_off 关死，不牵连网页版。"""
        if not self.real:
            openid, unionid, _, _ = self.exchange(code)
            return openid, unionid
        if not (self.settings.wechat_mp_app_id and self.settings.wechat_mp_app_secret):
            raise errors.wechat_off()
        try:
            resp = httpx.get(
                WX_JSCODE_URL,
                params={
                    "appid": self.settings.wechat_mp_app_id,
                    "secret": self.settings.wechat_mp_app_secret,
                    "js_code": code,
                    "grant_type": "authorization_code",
                },
                timeout=5.0,
            )
            data = resp.json()
            return self._session_from(data)
        except errors.ApiError:
            raise
        except Exception:  # noqa: BLE001 - 网络/解析故障统一明示，不静默
            raise errors.wechat_unavailable() from None

    def exchange_by_source(
        self, source: str, code: str
    ) -> tuple[str, str | None, str | None, str | None]:
        """按端换 (openid, 统一编号, 微信昵称, 微信头像)：两端各调各的官方接口，
        策略层只见这一种回话形状——小程序端无画像，昵称头像恒 None（头像刷新
        只刷新不抹掉，None 天然空转）。"""
        if source == "mp":
            openid, unionid = self.exchange_mp(code)
            return openid, unionid, None, None
        return self.exchange(code)

    @staticmethod
    def _session_from(data: dict) -> tuple[str, str | None]:
        """token/jscode 两换的共用回话校验（错误码表单源）：40029=凭证无效
        40163=凭证已用过 → 重点一次即走通；其余 errcode 或缺 openid 按不可用。
        统一编号只在应用绑进开放平台后随回话下发（没绑/存量授权拿不到 → None，
        认亲路自然空转）。"""
        errcode = data.get("errcode")
        if errcode in (40029, 40163):
            raise errors.wechat_code_invalid()
        if errcode:
            raise errors.wechat_unavailable()
        openid = data.get("openid")
        if not openid:
            raise errors.wechat_unavailable()
        unionid = data.get("unionid")
        return str(openid), str(unionid) if unionid else None

    def _fetch_profile(
        self, client: httpx.Client, access_token: str, openid: str
    ) -> tuple[str | None, str | None]:
        """snsapi_userinfo 抓微信昵称与头像（scope 已具备）：拿不到/没给一律
        (None, None)，建号路自会走随机名兜底（1.8 §4.2），绝不拖垮授权本身。
        client 由 exchange 传入——与 token 调用共用一条连接。"""
        if not access_token:
            return None, None
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
        except Exception:  # noqa: BLE001 - 画像是锦上添花，任何故障静默放弃
            return None, None
        if data.get("errcode"):
            return None, None
        nick = data.get("nickname")
        head = data.get("headimgurl")
        return (str(nick) if nick else None, str(head) if head else None)

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
        avatar: str | None = None,
        source: str = "h5",
    ) -> WechatLoginOut:
        """认人门（1.7 §4.1/4.2 + 1.8 §4.1~§4.3 + 修订二 + 小程序第二把钥匙）。
        按固定先后顺序找人：先本端钥匙 → 再统一编号认亲（老账号记过同一微信的
        统一编号就直进并顺手绑本端钥匙，正式档）→ 都没有按新人办。
        source="h5"（默认，老契约零变化）走网页版列族，"mp" 走小程序列族
        （恒正式绑）。回话字段义见 WechatLoginOut：
        - "ok"：绑过直进（牢靠绑=验明正身，杀未验证钥匙；凭条照发——换绑顶替的种子）；
          修订二新增一支：快进带号撞在册账号且同机续接窗内 → 进既有账号+微信正式绑；
        - "unbound"：fast=False 的 1.7 原路（登录页找回面落卡分支，4.7 防误快进护栏）；
        - "created"：fast=True 的快进建号（1.8）——微信生而正式绑、不发凭条（绑定一次
          完成）；修订二：卡上手机号没人用则建带号账号，选了头像落档。
        - 快进带号撞占用（异机/过窗）：抛 phone_taken，整体不生效（凭据作废，重点走三出口）。"""
        # 每次授权都取画像：ok 支要顺手刷新微信头像（只刷新不抹掉；小程序端无画像
        # 恒 None 天然空转），昵称仍只在快进路消费
        openid, unionid, wx_nickname, wx_avatar = self.wechat.exchange_by_source(
            source, code
        )
        account = self._active_by_key(source, openid)
        if account is None and unionid:
            # 统一编号认亲：本端钥匙没绑过号，但老账号记过同一微信的统一编号——
            # 直进老账号并把本端钥匙顺手绑上（正式档；老账号其他记录一概不动）
            holders = self._unionid_holders(unionid)
            if holders:
                self._rebind(holders[0], openid, source, verified=True)
                account = holders[0]
        if account is not None:
            # 钥匙命中后核对统一编号：指向另一账号则只记记号不换号（交人工）
            self._cross_check(account, unionid)
            bind_token = self.wechat.issue_bind_token(openid)
            # 列族没有 verified 档（小程序恒正式绑）；网页版沿用原两档
            verified_col = _KEY_COLS[source][1]
            verified = bool(getattr(account, verified_col)) if verified_col else True
            if verified:
                self.keys.revoke_unverified(account.id)
                self.db.commit()
            # 落库随随后 keys.issue 的 commit 带走
            self._refresh_wechat_avatar(account, wx_avatar)
            token = self.keys.issue(account.id, device_marker, verified=verified)
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
            wx_avatar,
            nickname=nickname,
            device_marker=device_marker,
            phone=phone,
            avatar=avatar,
            source=source,
            unionid=unionid,
        )

    def _fast_create(
        self,
        openid: str,
        wx_nickname: str | None,
        wx_avatar: str | None,
        *,
        nickname: str | None,
        device_marker: str,
        phone: str | None = None,
        avatar: str | None = None,
        source: str = "h5",
        unionid: str | None = None,
    ) -> WechatLoginOut:
        """快进建号（1.8 §4.1~§4.3 + 修订二「卡上填过的都算数」）：授权那一刻即
        本人——生而正式绑（§8 裁决 A），绑的是 source 对应端的钥匙列族，统一编号
        有则同刻落档（小程序端画像缺席，头像恒 None 不影响）。手机号两支：没填→
        无号快进号（phone=None，注销预留的空位）；填了没人用→带号建号（两把钥匙
        一步到位）。昵称三优先级：卡上手填（strip 空视同没填）→ 微信昵称过清洗
        规矩（不合格视同拿不到，§4.2）→ 随机名；头像选了落档、没选默认款（与手填
        建号同一条 D2 规矩）。
        原子性（§4.9-3）：账号行 flush（openid/phone 唯一索引撞在此暴露）后由
        keys.issue 的 commit 一并落账，任何失败整体回滚不留半个账号。"""
        # 循环导入（accounts 先 import 本模块）：混入方运行时取用建号模块级件
        from .accounts import (
            _resolve_nickname,
            _validate_public_avatar,
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
                # 续接成立后才改头像：改值随 _rebind 的 commit 落账；若先改再等
                # 发钥匙，占用分支抛 phone_taken 时脏属性挂在会话上，落不落库
                # 全看下游谁碰巧 commit——不赌这个运气
                self._refresh_wechat_avatar(existing, wx_avatar)
                self._rebind(existing, openid, source, verified=True)
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
        # 旧小人列默认件由工厂自置；注册形象落 dress_avatar，微信头像授权即记录；
        # 钥匙列按端取列族（小程序无画像、无两档，verified 列缺席即跳过）
        openid_col, verified_col, bound_col = _KEY_COLS[source]
        wechat_cols: dict[str, Any] = {
            "wechat_avatar": wx_avatar,
            openid_col: openid,
            bound_col: clock.now(),
        }
        if verified_col is not None:
            wechat_cols[verified_col] = True
        if unionid:
            wechat_cols["wechat_unionid"] = unionid
        account = new_account(
            phone=phone,
            nickname=final_name,
            device_marker=device_marker,
            dress_avatar=_validate_public_avatar(avatar),
            **wechat_cols,
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
        迁到 target（正式绑；target 原有微信被顶替覆盖——一个微信只开一扇门），
        原（快进）账号就地解绑搁置，不需要用户再授权一次。幂等：凭条已把同一微信
        绑走时原账号 openid 已清，迁移自然空转（返回 False）。只迁网页版钥匙
        （收编挂点都在网页版名片卡流；小程序钥匙的迁移走统一编号认亲，不在这）。"""
        if current is None or current.id == target.id or not current.wechat_openid:
            return False
        self._rebind(target, current.wechat_openid, "h5", verified=True)
        return True

    def wechat_redeem(
        self,
        *,
        code: str,
        phone: str,
        device_marker: str,
        card: dict[str, Any] | None = None,
        source: str = "h5",
    ) -> tuple[dict, str]:
        """占卡「微信验证进入」（1.7 §4.4/4.5）：只认牢靠绑——微信身份绑定前
        验过手机号，与短信出口同一待遇的接管（1.6 §4.5「效果完全一致」：名片
        并入、全设备钥匙连同密码作废、设密宽限窗）。没绑/绑别处/只是顺手绑，
        各报各的指路错。source 按端认钥匙族：小程序端只认小程序钥匙（小程序
        钥匙恒正式绑，无「顺手绑」档）。"""
        self._check_phone(phone)
        account = self._active_by_phone(phone)
        if account is None:
            raise errors.no_account()
        # 占卡微信验证进入也是一次授权：画像照取，头像顺手刷新（None 不抹已有；
        # 小程序端无画像）
        openid, unionid, _, wx_avatar = self.wechat.exchange_by_source(source, code)
        holder = self._active_by_key(source, openid)
        if holder is None:
            raise errors.wechat_unbound()
        if holder.id != account.id:
            raise errors.wechat_bound_other()
        # 两档判定只在有 verified 列的网页版列族；小程序钥匙生而正式绑
        verified_col = _KEY_COLS[source][1]
        if verified_col is not None and not getattr(account, verified_col):
            raise errors.wechat_binding_weak()
        self.keys.revoke_all(account.id)
        self._wipe_password(account)
        self._merge_card(account, card)
        self._grant_grace(account)
        self._refresh_wechat_avatar(account, wx_avatar)
        # 统一编号核对与 login 路同口径：指向他人只记号、空闲则回填（redeem 也是
        # 一次授权，弃掉编号会让后续认亲少一份线索）
        self._cross_check(account, unionid)
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
        # 凭条只由网页版名片卡流（signup/短信找回/密码验证）消费，小程序端建号
        # 走 fast、占卡走 redeem，都不带凭条——按网页版列族落位
        self._rebind(account, openid, "h5", verified=verified)
        return True

    def _rebind(
        self, target: Account, openid: str, source: str, *, verified: bool
    ) -> None:
        """openid 换位落库的唯一正路（凭条顶替 / 收编 / 统一编号认亲顺手绑共用）：
        按族清旧持有位 → flush → 写 target 列族 → commit。唯一索引下清位与写位之间
        必须 flush 落序——同表两行 UPDATE 按主键序批量执行，持有者主键更大时
        「写新位」会先于「清旧位」撞 openid 唯一索引（生产期偶发、测试难复现）；
        新增换位路径一律走这里，不要再手抄两行换位。"""
        holder = self._active_by_key(source, openid)
        if holder is not None and holder.id != target.id:
            # 顶替=整个微信人搬家（C3 全清）：只族清会留被顶账号另一端钥匙与
            # 统一编号，这个微信换端登录又回旧号——正是 4.13 要防的分裂
            self._clear_binding(holder)
            self.db.flush()
        openid_col, verified_col, bound_col = _KEY_COLS[source]
        setattr(target, openid_col, openid)
        if verified_col is not None:
            setattr(target, verified_col, verified)
        setattr(target, bound_col, clock.now())
        self.db.commit()

    def _refresh_wechat_avatar(self, account: Account, url: str | None) -> None:
        """每次授权顺手刷新微信头像：只刷新不抹掉——拿不到头像（None）别把已有
        记录清了，清了装扮页「微信头像」选项就凭空消失。落库时机交给调用方既有
        的 commit（发钥匙/换绑都会 commit），不为此单付一次磁盘同步。"""
        if url:
            account.wechat_avatar = url

    def _active_by_key(self, source: str, openid: str) -> Account | None:
        openid_col = _KEY_COLS[source][0]
        return self.db.execute(
            select(Account).where(
                getattr(Account, openid_col) == openid, Account.status == "active"
            )
        ).scalar_one_or_none()

    def _unionid_holders(
        self, unionid: str, *, exclude_id: int | None = None
    ) -> list[Account]:
        """活跃账号中记着该统一编号的，按 id 升序：认亲取首位（多个号共记同一
        编号属遗留错位，取最老的在册号先进，残余交人工）；跨端核对取全列排查。"""
        stmt = (
            select(Account)
            .where(Account.wechat_unionid == unionid, Account.status == "active")
            .order_by(Account.id)
        )
        if exclude_id is not None:
            stmt = stmt.where(Account.id != exclude_id)
        return list(self.db.execute(stmt).scalars())

    def _cross_check(self, account: Account, unionid: str | None) -> None:
        """钥匙命中后的统一编号核对：指向另一活跃账号 → 两号各记一笔「跨端绑定
        不一致」（幂等，只记号不换号不并号，交人工裁决）；无冲突且本号没记过 →
        回填（对端日后来登录即凭它认亲直进）。落库随认人门随后的 commit。"""
        if not unionid:
            return
        others = self._unionid_holders(unionid, exclude_id=account.id)
        if others:
            now = clock.now()
            for other in others:
                self._add_cross_flag(account.id, other.id, now)
                self._add_cross_flag(other.id, account.id, now)
            return
        if account.wechat_unionid is None:
            account.wechat_unionid = unionid

    def _add_cross_flag(
        self, account_id: int, other_account_id: int, found_at: datetime
    ) -> None:
        # 幂等：同一对已记过不再叠加也不改时刻（首次发现时刻是人工排查线索）；
        # 人工清掉后再次登录才会重新记
        exists = self.db.execute(
            select(WechatCrossFlag).where(
                WechatCrossFlag.account_id == account_id,
                WechatCrossFlag.other_account_id == other_account_id,
            )
        ).scalar_one_or_none()
        if exists is None:
            self.db.add(
                WechatCrossFlag(
                    account_id=account_id,
                    other_account_id=other_account_id,
                    found_at=found_at,
                )
            )

    def _sweep_weak_binding(self, account: Account) -> None:
        """D4 的微信面：验明正身时解开"顺手绑"（未验手机号的绑定）——冒填者
        建号顺手绑的微信，真主人验证一次即永久失效。牢靠绑与小程序钥匙不动
        （小程序端静默换号即微信作证，生而正式绑、无顺手档）。"""
        if account.wechat_openid and not account.wechat_verified:
            self._clear_binding(account, "h5")

    def _clear_binding(self, account: Account, source: str | None = None) -> None:
        """清位。source 缺省=全清（接管/注销/换绑顶替：两把微信钥匙、统一编号、
        微信头像与跨端记号一并释放，同一微信此后可绑任何账号；头像一并清——
        号码回收场景下新主人不得见/穿前主人的微信头像）。source 给定=只清该端
        钥匙族（D4 解弱绑专属——h5 弱档被验明正身解开，另一端的正式绑与统一
        编号不陪葬）。落库交调用方既有的 commit/flush。"""
        if source is not None:
            self._clear_family(account, source)
            if source == "h5":
                account.wechat_avatar = None
            return
        for family in _KEY_COLS:
            self._clear_family(account, family)
        account.wechat_unionid = None
        account.wechat_avatar = None
        self.db.execute(
            delete(WechatCrossFlag).where(
                or_(
                    WechatCrossFlag.account_id == account.id,
                    WechatCrossFlag.other_account_id == account.id,
                )
            )
        )

    def _clear_family(self, account: Account, source: str) -> None:
        openid_col, verified_col, bound_col = _KEY_COLS[source]
        setattr(account, openid_col, None)
        if verified_col is not None:
            setattr(account, verified_col, False)
        setattr(account, bound_col, None)
