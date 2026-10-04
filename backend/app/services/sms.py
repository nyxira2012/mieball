"""SmsGate —— 验证码的深模块：发送（含全部限频与预算熔断）、核销（含次数与过期）。

规格对照（docs/1.1 §B1/§5 出错条目）：
- 60 秒内同一手机号只许重发一条（冷却）；
- 同一手机号一天最多 10 条、同一 IP 一天最多 20 条（防换号刷量）；
- 全站每日总预算（超了明确报"短信暂时发不出"，不静默失败）；
- 6 位码 5 分钟有效、连错 5 次作废、一次性使用；
- 发送器可替换：开发期 console（验证码打进后端日志），上线换真服务商（R1 的抽象）。

限频不另建计数表：phone_codes 一行就是一次发送，按 day 分组数行数即是当日量。
"""
from __future__ import annotations

from datetime import timedelta
from typing import Protocol

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..core import clock, errors, security
from ..core.config import Settings
from ..db.models import PhoneCode

RESEND_COOLDOWN_SECONDS = 60
PHONE_DAILY_LIMIT = 10
IP_DAILY_LIMIT = 20
CODE_TTL_SECONDS = 5 * 60
MAX_ATTEMPTS = 5
PURPOSES = ("recovery", "takeover", "deactivate")


class SmsSender(Protocol):
    def send(self, phone: str, code: str, purpose: str) -> None: ...


class ConsoleSender:
    """开发期假发送器：验证码直接进后端日志（R1：真服务商要执照，先写代码后换弹）。"""

    def send(self, phone: str, code: str, purpose: str) -> None:
        print(f"[sms:console] -> {phone} 验证码 {code}（用途 {purpose}，5 分钟内有效）")


class UnavailableSender:
    """占位真发送器：上线接入服务商时替换本类实现即可，SmsGate 其余不动。"""

    def send(self, phone: str, code: str, purpose: str) -> None:
        raise RuntimeError("real sms sender not wired")


def make_sender(provider: str) -> SmsSender:
    return ConsoleSender() if provider == "console" else UnavailableSender()


class SmsGate:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        self.sender = make_sender(settings.sms_provider)

    # ---- 发码（所有限频都在这条路径上） ----

    def send(self, phone: str, purpose: str, ip: str) -> None:
        if purpose not in PURPOSES:
            raise errors.ApiError(422, "purpose_invalid", "验证码用途不合法")
        now = clock.now()
        day = clock.today_key(now)

        last = self.db.execute(
            select(PhoneCode).where(PhoneCode.phone == phone).order_by(PhoneCode.id.desc()).limit(1)
        ).scalar_one_or_none()
        if last is not None and (now - last.created_at).total_seconds() < RESEND_COOLDOWN_SECONDS:
            retry_after = int(RESEND_COOLDOWN_SECONDS - (now - last.created_at).total_seconds()) or 1
            raise errors.sms_cooldown(retry_after)

        if self._count(day=day, phone=phone) >= PHONE_DAILY_LIMIT:
            raise errors.sms_phone_daily()
        if ip and self._count(day=day, ip=ip) >= IP_DAILY_LIMIT:
            raise errors.sms_ip_daily()
        if self._count(day=day) >= self.settings.sms_daily_budget:
            raise errors.sms_unavailable()

        # 新码作废旧码（同号同用途同时只活一条）
        self.db.execute(
            update(PhoneCode)
            .where(PhoneCode.phone == phone, PhoneCode.purpose == purpose, PhoneCode.used_at.is_(None))
            .values(used_at=now)
        )
        code = security.new_code()
        self.db.add(
            PhoneCode(
                phone=phone,
                purpose=purpose,
                fingerprint=security.code_fingerprint(phone, purpose, code),
                ip=ip or "",
                day=day,
                expires_at=now + timedelta(seconds=CODE_TTL_SECONDS),
                created_at=now,
            )
        )
        self.db.commit()
        try:
            self.sender.send(phone, code, purpose)
        except Exception:  # noqa: BLE001 - 通道故障明示，不静默（§B2）
            raise errors.sms_unavailable() from None

    # ---- 核销 ----

    def verify(self, phone: str, purpose: str, code: str) -> None:
        """核验并一次性消费。不匹配/过期/超次/已用各报各的错，前端提示分流。"""
        row = self.db.execute(
            select(PhoneCode)
            .where(PhoneCode.phone == phone, PhoneCode.purpose == purpose, PhoneCode.used_at.is_(None))
            .order_by(PhoneCode.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            raise errors.sms_code_invalid()
        now = clock.now()
        if now > row.expires_at:
            row.used_at = now
            self.db.commit()
            raise errors.sms_code_expired()
        if row.attempts >= MAX_ATTEMPTS:
            row.used_at = now
            self.db.commit()
            raise errors.sms_code_invalid()
        if row.fingerprint != security.code_fingerprint(phone, purpose, code):
            row.attempts += 1
            self.db.commit()
            remaining = MAX_ATTEMPTS - row.attempts
            if remaining <= 0:
                raise errors.sms_code_invalid()
            raise errors.sms_bad_code(remaining)
        row.used_at = now
        self.db.commit()

    # ---- 内部 ----

    def _count(self, *, day: str, phone: str | None = None, ip: str | None = None) -> int:
        stmt = select(func.count(PhoneCode.id)).where(PhoneCode.day == day)
        if phone is not None:
            stmt = stmt.where(PhoneCode.phone == phone)
        if ip is not None:
            stmt = stmt.where(PhoneCode.ip == ip)
        return int(self.db.execute(stmt).scalar_one())
