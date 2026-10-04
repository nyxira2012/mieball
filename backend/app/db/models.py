"""账号域的三张表 —— 只有服务层（services/）碰它们，路由不直接查库。

- accounts.phone 带 UNIQUE 且注销时置 NULL：同一个号建不出两个在册账号靠数据库兜底
  （SQLite 多个 NULL 不冲突，手机号"释放后可重新注册"由此成立）。
- device_keys.fingerprint 存钥匙指纹不存原文；verified 标记"发出时是否经短信验证"，
  是 D4 规则（短信验证杀未验证钥匙）的依据。
- phone_codes 一表三用：验证码本体 + 限频计数（60 秒/一天 N 条按行数算，不另建计数表）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .engine import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 在册账号的手机号全局唯一；注销时置 NULL 释放（NULL 不参与唯一约束）
    phone: Mapped[str | None] = mapped_column(String(11), unique=True, nullable=True)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    nickname: Mapped[str] = mapped_column(String(32), nullable=False)
    # Q 版小人六部件配置，JSON 字符串 {"skin":0,"hair":0,"hc":0,"shirt":5,"face":0,"acc":0}
    chibi: Mapped[str] = mapped_column(Text, nullable=False)
    card_bg: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # active=在册；deactivated=已注销（档案匿名化、历史封存）
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    # 建号时用的设备标记：支撑"提交卡住重试"的续接窗口判断
    device_marker: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DeviceKey(Base):
    __tablename__ = "device_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    device_marker: Mapped[str] = mapped_column(String(64), nullable=False)
    # 发出时是否经短信验证：接管/找回的钥匙是 True，报名建号直发的是 False
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PhoneCode(Base):
    __tablename__ = "phone_codes"
    __table_args__ = (
        Index("ix_phone_codes_day_phone", "day", "phone"),
        Index("ix_phone_codes_day_ip", "day", "ip"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str] = mapped_column(String(11), nullable=False)
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)  # recovery/takeover/deactivate
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    ip: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    day: Mapped[str] = mapped_column(String(10), nullable=False)      # 限频按本地日分组
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 用过/作废的时间戳
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
