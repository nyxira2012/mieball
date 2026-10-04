"""AccountBook —— 账号域的深模块：建号、短信换钥匙（找回/接管）、注销、名片、隐私出口。

策略全部内聚在这里，路由只做参数搬运：
- 建号幂等：同设备 10 分钟内重试直接续接（§5"提交卡住后重试"），并发撞号靠
  phone 唯一索引兜底（§B3 不重复建号）；
- D4 规则：任何短信验证成功 → 作废该账号全部"未验证"钥匙；接管另加全量作废
  （号码回收场景下前主人的已验证钥匙也一并清场，保住评审裁决 A 的强度）；
- D5 规则：接管时只覆盖 B 明确填过的名片字段（带 *_set 显式标志，不做值推断）；
- 隐私出口：对外只有昵称+小人；同局加尾号 4 位；本人见全号；已注销统一占位。
  全产品展示他人一律经 view()，别处不得直读 Account。
"""
from __future__ import annotations

import json
import random
import re
from datetime import timedelta
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core import clock, errors
from ..db.models import Account
from .keys import KeyVault
from .sms import SmsGate

PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
# 与前端 utils/chibi.ts DRESS_RANGES 同一真值（六部件各自的变体数）
CHIBI_RANGES = {"skin": 4, "hair": 6, "hc": 6, "shirt": 8, "face": 4, "acc": 3}
DEFAULT_CHIBI = {"skin": 0, "hair": 0, "hc": 0, "shirt": 5, "face": 0, "acc": 0}
CARD_BGS = {"neon", "gold", "cyber", "aurora"}
RESERVED_NICKNAMES = {"已注销球友", "平台客服"}
SIGNUP_RESUME_WINDOW = timedelta(minutes=10)
NICKNAME_MAX = 16

Viewer = Literal["self", "same_game", "other"]

_ANON_NAME = "已注销球友"


class AccountBook:
    def __init__(self, db: Session, sms: SmsGate, keys: KeyVault):
        self.db = db
        self.sms = sms
        self.keys = keys

    # ---- 建号（4.2：点报名那一刻填名片，建号发钥匙一步完成） ----

    def signup(
        self,
        *,
        phone: str,
        device_marker: str,
        nickname: str | None = None,
        nickname_set: bool = False,
        chibi: dict[str, Any] | None = None,
        chibi_set: bool = False,
    ) -> tuple[dict, str]:
        """返回 (本人视图, 钥匙原文)。手机号已被占用且不可续接时抛 phone_taken。"""
        _check_phone(phone)
        nickname = _resolve_nickname(nickname if nickname_set else None)
        chibi_json = json.dumps(_validate_chibi(chibi) if chibi_set else DEFAULT_CHIBI)

        existing = self._active_by_phone(phone)
        if existing is not None:
            token = self._resume_or_taken(existing, device_marker)
            return self.view(existing.id, viewer="self"), token

        account = Account(
            phone=phone,
            nickname=nickname,
            chibi=chibi_json,
            status="active",
            device_marker=device_marker,
            created_at=clock.now(),
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
            return self.view(existing.id, viewer="self"), token
        self.db.refresh(account)

        token = self.keys.issue(account.id, device_marker, verified=False)
        return self.view(account.id, viewer="self"), token

    # ---- 短信换钥匙（4.4 找回 / 4.5 接管：验证成功即身份裁决） ----

    def redeem(
        self,
        *,
        phone: str,
        code: str,
        purpose: Literal["recovery", "takeover"],
        device_marker: str,
        card: dict[str, Any] | None = None,
    ) -> tuple[dict, str]:
        """验证通过后发"已验证钥匙"。D4：杀未验证钥匙；接管另杀全部。D5：接管合并名片。"""
        _check_phone(phone)
        account = self._active_by_phone(phone)
        if account is None:
            raise errors.no_account()

        self.sms.verify(phone, purpose, code)

        if purpose == "takeover":
            # 前主人/冒填者一律清场（含已验证钥匙——号码回收场景），再并入真主人名片
            self.keys.revoke_all(account.id)
            if card:
                if card.get("nickname_set"):
                    account.nickname = _resolve_nickname(str(card.get("nickname") or ""))
                if card.get("chibi_set"):
                    account.chibi = json.dumps(_validate_chibi(card.get("chibi")))
        else:
            self.keys.revoke_unverified(account.id)
        account.phone_verified = True
        self.db.commit()

        token = self.keys.issue(account.id, device_marker, verified=True)
        return self.view(account.id, viewer="self"), token

    # ---- 注销（4.6：档案匿名化、手机号释放、历史封存、全钥匙失效） ----

    def deactivate(self, *, account_id: int, phone: str, code: str) -> None:
        account = self._by_id(account_id)
        if account is None or account.status != "active":
            raise errors.no_identity()
        _check_phone(phone)
        if account.phone != phone:
            raise errors.ApiError(422, "phone_mismatch", "请输入本账号的手机号")

        self.sms.verify(phone, "deactivate", code)

        self.keys.revoke_all(account.id)
        account.phone = None  # 释放：同一号将来可注册全新账号（历史不继承）
        account.phone_verified = False
        account.nickname = _ANON_NAME
        account.chibi = json.dumps(DEFAULT_CHIBI)
        account.card_bg = None
        account.status = "deactivated"
        account.deactivated_at = clock.now()
        self.db.commit()

    # ---- 发码（三个用途都要求号码已有在册账号：查无账号不发码，§4.4） ----

    def send_code(self, phone: str, purpose: str, ip: str) -> None:
        _check_phone(phone)
        if self._active_by_phone(phone) is None:
            raise errors.no_account()
        self.sms.send(phone, purpose, ip)

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

    def update_profile(
        self,
        account_id: int,
        *,
        nickname: str | None = None,
        chibi: dict[str, Any] | None = None,
        card_bg: str | None = None,
    ) -> dict:
        account = self._by_id(account_id)
        if account is None or account.status != "active":
            raise errors.no_identity()
        if nickname is not None:
            account.nickname = _resolve_nickname(nickname)
        if chibi is not None:
            account.chibi = json.dumps(_validate_chibi(chibi))
        if card_bg is not None:
            if card_bg not in CARD_BGS:
                raise errors.ApiError(422, "card_bg_invalid", "卡背不合法")
            account.card_bg = card_bg
        self.db.commit()
        return self.view(account_id, viewer="self")

    # ---- 隐私出口（唯一对外视图：游客/陌生=昵称+小人，同局+尾号，本人=全号） ----

    def view(self, account_id: int, *, viewer: Viewer) -> dict:
        account = self._by_id(account_id)
        if account is None:
            raise errors.no_account()
        if account.status != "active":
            # 已注销：任何人（含旧设备）都只见占位形象，尾号也不给
            return {
                "id": account.id,
                "name": _ANON_NAME,
                "chibi": dict(DEFAULT_CHIBI),
                "deactivated": True,
            }
        out: dict[str, Any] = {
            "id": account.id,
            "name": account.nickname,
            "chibi": json.loads(account.chibi),
            "card_bg": account.card_bg,
            "deactivated": False,
        }
        if viewer in ("self", "same_game") and account.phone:
            out["phone_tail"] = account.phone[-4:]
        if viewer == "self" and account.phone:
            out["phone"] = account.phone
        return out

    # ---- 内部 ----

    def _active_by_phone(self, phone: str) -> Account | None:
        return self.db.execute(
            select(Account).where(Account.phone == phone, Account.status == "active")
        ).scalar_one_or_none()

    def _by_id(self, account_id: int) -> Account | None:
        return self.db.get(Account, account_id)

    def _resume_or_taken(self, existing: Account, device_marker: str) -> str:
        """占用分支：同设备且在续接窗口内 → 直接再发一把未验证钥匙续上；否则报占用。"""
        in_window = clock.now() - existing.created_at <= SIGNUP_RESUME_WINDOW
        if in_window and existing.device_marker == device_marker:
            return self.keys.issue(existing.id, device_marker, verified=False)
        raise errors.phone_taken()


def _check_phone(phone: str) -> None:
    if not PHONE_RE.fullmatch(phone or ""):
        raise errors.phone_invalid()


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


def _validate_chibi(chibi: Any) -> dict[str, int]:
    if not isinstance(chibi, dict):
        raise errors.chibi_invalid()
    out: dict[str, int] = {}
    for part, size in CHIBI_RANGES.items():
        v = chibi.get(part, 0)
        if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v < size:
            raise errors.chibi_invalid()
        out[part] = v
    if set(chibi.keys()) - set(CHIBI_RANGES.keys()):
        raise errors.chibi_invalid()
    return out
