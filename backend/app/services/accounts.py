"""AccountBook —— 账号域的深模块：建号、短信换钥匙（找回/接管）、注销、名片、隐私出口。

策略全部内聚在这里，路由只做参数搬运：
- 建号幂等：同设备 10 分钟内重试直接续接（§5"提交卡住后重试"），并发撞号靠
  phone 唯一索引兜底（§B3 不重复建号）；
- D4 规则：任何短信验证成功 → 作废该账号全部"未验证"钥匙；接管另加全量作废
  （号码回收场景下前主人的已验证钥匙也一并清场，保住评审裁决 A 的强度）；
- D5 规则：接管时只覆盖 B 明确填过的名片字段（带 *_set 显式标志，不做值推断）；
- 密码钥匙（1.6）：逻辑全在 PasswordMixin（services/passwords.py），本文件只留
  接管/注销挂点——接管=密码随全钥匙作废+设密宽限窗，注销=密码随账号消亡；
- 微信钥匙（1.7）：逻辑全在 WechatMixin（services/wechat.py），本文件只留
  建号/验明正身/接管/注销四个挂点——建号顺手绑（弱档）、验明正身绑（正式档，
  顺手档同刻解开）、接管/注销清位；绑定失败静默跳过不拖主流程；
- 快进号补手机号（1.8）：send_code 按 purpose 分支（bind_phone 判定反转——
  有账号当场拒、指路登录页走短信验证）+ bind_phone 动作（收码才落号翻真）；
  redeem 找回复挂验证收编（当前设备登着的快进号上的微信自动迁绑回来）；
- 隐私出口：对外只有昵称+头像；同局加尾号 4 位；本人见全号；已注销统一占位。
  全产品展示他人一律经 view()，别处不得直读 Account。
"""

from __future__ import annotations

import random
import re
from datetime import timedelta
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core import clock, errors
from ..core.logs import audit
from ..db.models import Account
from .cosmetics import by_id, default_dress, dress_fields
from .keys import KeyVault
from .passwords import PasswordMixin
from .sms import SmsGate
from .stats import StatsLedger
from .wechat import WeChatGate, WechatMixin

PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
# 已注销账号的对外占位昵称——跨域单一源（保留名、view() 占位、球局域名单共用）
ANON_NAME = "已注销球友"
RESERVED_NICKNAMES = {ANON_NAME, "平台客服"}
SIGNUP_RESUME_WINDOW = timedelta(minutes=10)
NICKNAME_MAX = 16

Viewer = Literal["self", "same_game", "other"]


def new_account(
    *,
    phone: str | None,
    nickname: str,
    device_marker: str,
    dress_avatar: str | None = None,
    **wechat_cols: Any,
) -> Account:
    """建号行工厂（signup 手填建号与微信快进 _fast_create 同吃）：基础件一处
    定形，注册卡挑的形象与快进支多带的微信列经参数透传——新增带非库默认值的
    账号列时改这里一处，两条建号路不漂。"""
    return Account(
        phone=phone,
        nickname=nickname,
        status="active",
        device_marker=device_marker,
        created_at=clock.now(),
        dress_avatar=dress_avatar,
        **wechat_cols,
    )


def person_view(account: Account | None) -> dict:
    """名单里的一人：昵称+装扮三键（1.1 隐私口径 + 展示位直发）。
    已注销/不存在 → 占位形象穿默认公共款（不读其穿戴列——清空靠 deactivate
    写侧保证，读侧直接兜死更稳）。球局域名单（game_views）与意向列表
    （intents）共用的"对外一个人"形状。"""
    if account is None or account.status != "active":
        return {
            "id": account.id if account else 0,
            "nickname": ANON_NAME,
            **default_dress(),
        }
    return {
        "id": account.id,
        "nickname": account.nickname,
        **dress_fields(account),
    }


class AccountBook(PasswordMixin, WechatMixin):
    def __init__(self, db: Session, sms: SmsGate, keys: KeyVault, wechat: WeChatGate):
        self.db = db
        self.sms = sms
        self.keys = keys
        self.wechat = wechat

    @classmethod
    def open(cls, db: Session, settings) -> AccountBook:
        # 装配单点：路由依赖与运维脚本都从这取实例，加钥匙通道只改这一处
        # （曾在加第四把微信钥匙时漏改 seed_demo，脚本静默损坏）
        return cls(db, SmsGate(db, settings), KeyVault(db), WeChatGate(db, settings))

    # ---- 建号（4.2：点报名那一刻填名片，建号发钥匙一步完成） ----

    def signup(
        self,
        *,
        phone: str,
        device_marker: str,
        nickname: str | None = None,
        nickname_set: bool = False,
        avatar: str | None = None,
        bind_token: str | None = None,
    ) -> tuple[dict, str, bool]:
        """返回 (本人视图, 钥匙原文, 微信绑没绑上)。手机号已被占用且不可续接时抛
        phone_taken。微信挂点（1.7 §4.2）：带着绑定凭条来的，建号顺手绑（弱档——
        建号不验短信，绑定可靠级别跟着低）；凭条过期/冲突静默跳过，不拖建号。"""

        self._check_phone(phone)
        nickname = _resolve_nickname(nickname if nickname_set else None)
        avatar_id = _validate_public_avatar(avatar)

        existing = self._active_by_phone(phone)
        if existing is not None:
            token = self._resume_or_taken(existing, device_marker)
            bound = self._try_bind(existing, bind_token, verified=False)
            return self.view(existing.id, viewer="self"), token, bound

        account = new_account(
            phone=phone,
            nickname=nickname,
            device_marker=device_marker,
            dress_avatar=avatar_id,
        )
        self.db.add(account)
        try:
            self.db.commit()
        except IntegrityError:
            # 并发同号建号：唯一索引兜底，落败方走占用分支（§B3 不重复建号）
            self.db.rollback()
            existing = self._active_by_phone(phone)
            if existing is None:
                raise
            token = self._resume_or_taken(existing, device_marker)
            bound = self._try_bind(existing, bind_token, verified=False)
            return self.view(existing.id, viewer="self"), token, bound
        # id 在 flush 时已回填（模型无 server 端默认值），view() 又走同库会话——不必 refresh

        bound = self._try_bind(account, bind_token, verified=False)
        token = self.keys.issue(account.id, device_marker, verified=False)
        return self.view(account.id, viewer="self"), token, bound

    # ---- 短信换钥匙（4.4 找回 / 4.5 接管：验证成功即身份裁决） ----

    def redeem(
        self,
        *,
        phone: str,
        code: str,
        purpose: Literal["recovery", "takeover"],
        device_marker: str,
        card: dict[str, Any] | None = None,
        bind_token: str | None = None,
        adopt_from: Account | None = None,
    ) -> tuple[dict, str, bool]:
        """验证通过后发"已验证钥匙"。D4：杀未验证钥匙；接管另杀全部+密码作废。
        D5：接管合并名片。两路都留设密宽限窗（4.8：刚验完短信，设密码不重复发码）。
        微信挂点（1.7 §4.3）：验明正身=正式绑的好时机——凭条在手顺手绑上（顶替换绑）；
        D4 微信面：顺手绑档同刻解开（真主人验证，冒填者的微信即死）。
        验证收编（1.8 §4.5，仅 recovery 支）：adopt_from=当前设备登着的账号（调用方
        静默传 None 可选），它绑着的微信在验证成功后自动迁绑到本账号——凭条先执行、
        收编后且幂等。takeover 不挂：接管语义是清场（1.7），微信登记位一并清。"""
        self._check_phone(phone)
        account = self._active_by_phone(phone)
        if account is None:
            raise errors.no_account()

        self.sms.verify(phone, purpose, code)

        if purpose == "takeover":
            # 前主人/冒填者一律清场（含已验证钥匙——号码回收场景），密码一并作废，
            # 微信登记位一并清（1.7 接管清场），再并入真主人名片
            self.keys.revoke_all(account.id)
            self._wipe_password(account)
            self._clear_binding(account)
            self._merge_card(account, card)
        else:
            self.keys.revoke_unverified(account.id)
            self._sweep_weak_binding(account)
        self._grant_grace(account)
        account.phone_verified = True
        self.db.commit()

        bound = self._try_bind(account, bind_token, verified=True)
        if purpose == "recovery":
            # 收编只挂找回支：接管是清场语义（1.7），微信登记位一并清、不迁绑
            bound = self._adopt_binding(account, adopt_from) or bound
        token = self.keys.issue(account.id, device_marker, verified=True)
        return self.view(account.id, viewer="self"), token, bound

    # ---- 注销（4.6：档案匿名化、手机号释放、历史封存、全钥匙失效） ----

    def deactivate(self, *, account_id: int, phone: str, code: str) -> None:
        account = self._require_active(account_id)
        self._check_phone(phone)
        if account.phone != phone:
            raise errors.phone_mismatch()

        self.sms.verify(phone, "deactivate", code)

        self.keys.revoke_all(account.id)
        self._wipe_password(
            account
        )  # 密码随账号消亡（4.6：重注册是全新账号、无旧密码）
        self._clear_binding(account)  # 微信登记位随账号消亡（1.7 §4.10：释放可再绑）
        account.phone = None  # 释放：同一号将来可注册全新账号（历史不继承）
        account.phone_verified = False
        account.nickname = ANON_NAME
        # 装扮三列随账号消亡一并清空：解锁与穿戴不带入任何新账号（重新注册从零
        # 开始）；历史名单里的注销者由读侧兜默认公共款，微信头像已随上方清位走
        account.dress_avatar = None
        account.dress_back = None
        account.unlocks = None
        account.status = "deactivated"
        account.deactivated_at = clock.now()
        self.db.commit()

    # ---- 发码（发码前先判归属：五用途要号码已有在册账号，bind_phone 相反） ----

    def send_code(
        self, phone: str, purpose: str, ip: str, *, account_id: int | None = None
    ) -> None:
        """bind_phone（1.8 §4.4 快进号补绑）判定反转：既有主路「查无账号不发码」，
        它相反「有账号当场拒」——不透露对方账号，指路登录页走短信验证（验证收编
        会把微信自动绑回老账号）。占用拒照审计账本落一笔（account_id=发码请求者，
        让「要不要立合并功能」有数可查）。"""
        self._check_phone(phone)
        if purpose == "bind_phone":
            if self._active_by_phone(phone) is not None:
                audit(
                    "wechat_bind_phone_taken",
                    account_id=account_id,
                    detail="补绑手机号撞已有账号，指路登录页",
                )
                raise errors.phone_taken_redirect()
        elif self._active_by_phone(phone) is None:
            raise errors.no_account()
        self.sms.send(phone, purpose, ip)

    # ---- 补绑手机号（1.8 §4.4：快进号随时补上手机号，必须收码验证） ----

    def bind_phone(self, *, account_id: int, phone: str, code: str) -> dict:
        """核销 purpose=bind_phone 验证码 → phone 落库 + phone_verified=True（绑定
        记录翻真=既有这一格记号）。发码端已把占用挡在发码时刻；这里只防两步之间
        被人抢注（唯一索引兜底，同判占用指路）。已有手机号的账号核销前即拒——
        换号走 1.6 A1 人工口径。返回最新本人视图。"""
        account = self._require_active(account_id)
        self._check_phone(phone)
        if account.phone is not None:
            # 核销前先挡：已绑号账号凭一张新号验证码自助换根号 = 原号被静默顶掉
            # 释放，被劫持会话 + 攻击者手机号即可持久接管——必须拒
            raise errors.phone_already_bound()
        self.sms.verify(phone, "bind_phone", code)
        account.phone = phone
        account.phone_verified = True
        try:
            self.db.commit()
        except IntegrityError:
            # 发码到确认之间号码被注册：与发码时刻同款占用指路
            self.db.rollback()
            raise errors.phone_taken_redirect() from None
        return self.view(account_id, viewer="self")

    # ---- 认人 / 退出 / 名片 ----

    def by_token(self, token: str) -> Account | None:
        info = self.keys.resolve(token)
        if info is None:
            return None
        account = self._by_id(info.account_id)
        if account is None or account.status != "active":
            return None
        return account

    def logout(self, token: str) -> None:
        """退出登录：只作废这一台的钥匙（服务端作废比只清本机稳，别台不受影响）。"""
        self.keys.revoke(token)

    def update_profile(self, account_id: int, *, nickname: str | None = None) -> dict:
        account = self._require_active(account_id)
        if nickname is not None:
            account.nickname = _resolve_nickname(nickname)
        self.db.commit()
        return self.view(account_id, viewer="self")

    # ---- 隐私出口（唯一对外视图：游客/陌生=昵称+头像，同局+尾号，本人=全号） ----

    def view(self, account_id: int, *, viewer: Viewer) -> dict:
        account = self._by_id(account_id)
        if account is None:
            raise errors.no_account()
        if account.status != "active":
            # 已注销：任何人（含旧设备）都只见占位形象，尾号也不给（dupr 也不给——历史不留痕）
            return {
                "id": account.id,
                "name": ANON_NAME,
                "deactivated": True,
                **default_dress(),
            }
        dupr_card = StatsLedger(self.db).card_flat(account.id)
        out: dict[str, Any] = {
            "id": account.id,
            "name": account.nickname,
            "deactivated": False,
            # 装扮三键：头像值/解析好的素材路径/卡背编号，名片与档案随身份直发
            **dress_fields(account),
            # 设置页/名片卡判"密码未设置/已设置"的唯一依据（1.6 A1）
            "has_password": account.password_hash is not None,
            # 名片主数字 → DUPR（1.4 §6）：六键平铺单一源 card_flat（榜单同吃），
            # 缺行语义=起步分/未定级/0 场
            **dupr_card,
        }
        if viewer in ("self", "same_game") and account.phone:
            out["phone_tail"] = account.phone[-4:]
        if viewer == "self" and account.phone:
            out["phone"] = account.phone
        if viewer == "self":
            # 微信行两态：任一端钥匙在档即「已绑定」（公众号/小程序各记各的，
            # 对球友只报一个「微信已绑定」行；一次性回话旗 wechat_bound 只在发
            # 钥匙那一刻下发，/auth/me 刷新即失——持久态只能从这里出）
            out["wechat_bound"] = (
                account.wechat_openid is not None
                or account.wechat_mp_openid is not None
            )
        return out

    # ---- 内部 ----

    def _active_by_phone(self, phone: str) -> Account | None:
        return self.db.execute(
            select(Account).where(Account.phone == phone, Account.status == "active")
        ).scalar_one_or_none()

    def _by_id(self, account_id: int) -> Account | None:
        return self.db.get(Account, account_id)

    def _require_active(self, account_id: int) -> Account:
        """在册守卫：查无或已注销一律 no_identity（deactivate/update_profile 共用）。"""
        account = self._by_id(account_id)
        if account is None or account.status != "active":
            raise errors.no_identity()
        return account

    def _check_phone(self, phone: str) -> None:
        if not PHONE_RE.fullmatch(phone or ""):
            raise errors.phone_invalid()

    def _merge_card(self, account: Account, card: dict[str, Any] | None) -> None:
        """D5：接管只覆盖本人明确填过的名片字段（不做值推断——头像 None=没挑）。
        短信接管与密码接管（PasswordMixin.redeem_password）共用。"""
        if not card:
            return
        if card.get("nickname_set"):
            account.nickname = _resolve_nickname(str(card.get("nickname") or ""))
        if card.get("avatar") is not None:
            account.dress_avatar = _validate_public_avatar(str(card["avatar"]))

    def _resume_or_taken(self, existing: Account, device_marker: str) -> str:
        """占用分支：同设备且在续接窗口内 → 直接再发一把未验证钥匙续上；否则报占用。"""
        in_window = clock.now() - existing.created_at <= SIGNUP_RESUME_WINDOW
        if in_window and existing.device_marker == device_marker:
            return self.keys.issue(existing.id, device_marker, verified=False)
        raise errors.phone_taken()


def _resolve_nickname(raw: str | None) -> str:
    """空/未填 → 默认"球友+四位随机数"；填了则校验（1-16 字、去首尾空格、不占保留名）。"""
    name = (raw or "").strip()
    if not name:
        return f"球友{random.randint(0, 9999):04d}"
    if len(name) > NICKNAME_MAX:
        raise errors.nickname_invalid(f"昵称最多 {NICKNAME_MAX} 个字符")
    if name in RESERVED_NICKNAMES:
        raise errors.nickname_invalid("这个昵称不能用，换一个吧")
    return name


def resolve_nickname_report(raw: str | None) -> tuple[str, bool]:
    """落名并回报是否落了随机名（空昵称与清洗不合格都算）——是否随机由真正
    落名的这一侧说出，调用方不再自己重推一遍判据（wechat._fast_create 消费，
    前端随机名回执 toast 拿的就是这面旗）。"""
    if not (raw or "").strip():
        return _resolve_nickname(None), True
    try:
        return _resolve_nickname(raw), False
    except errors.ApiError:
        return _resolve_nickname(None), True


def _validate_public_avatar(value: str | None) -> str | None:
    """名片卡头像把关（手填建号/微信快进/接管合并三路共用）：注册与占卡界面
    只有公共款可选，其余一律按「查无这件」拒——跨栏编号与荣誉/定制款对这张卡
    而言等于不存在，不区分报错免得给越权试探递话。None=没挑，读侧兜默认。"""
    if value is None:
        return None
    item = by_id(value)
    if item is None or item.kind != "avatar" or item.tier != "common":
        raise errors.cosmetic_not_found()
    return value
