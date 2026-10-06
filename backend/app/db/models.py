"""全域数据表 —— 只有服务层（services/）碰它们，路由不直接查库。

账号域（1.1）accounts / device_keys / phone_codes：
- accounts.phone 带 UNIQUE 且注销时置 NULL：同一个号建不出两个在册账号靠数据库兜底
  （SQLite 多个 NULL 不冲突，手机号"释放后可重新注册"由此成立）。
- device_keys.fingerprint 存钥匙指纹不存原文；verified 标记"发出时是否经短信验证"，
  是 D4 规则（短信验证杀未验证钥匙）的依据。
- phone_codes 一表三用：验证码本体 + 限频计数（60 秒/一天 N 条按行数算，不另建计数表）。

球局域（1.2）games / entries / invites / intents：
- games.state 只有 5 个存储值；locked 之后的"进行中/已结束"是读时派生不落库（技术设计 §2.4）。
- entries 的 Unique(game_id, account_id) 是报名幂等的天然键（并发抢坑由它兜底）。
- intents.invited_at 非空即"已邀"标记（invite 置位、本人改意向清位）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
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
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id"), nullable=False, index=True
    )
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
    purpose: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # recovery/takeover/deactivate
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    ip: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    day: Mapped[str] = mapped_column(String(10), nullable=False)  # 限频按本地日分组
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )  # 用过/作废的时间戳
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organizer_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id"), nullable=False, index=True
    )
    # 局名由前端预览生成提交（后端不产中文文案，契约§2）；可不填
    name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 库内一律 naive 北京墙钟（契约§2：接口进出 ISO 8601 +08:00，服务层负责换算）
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # 截止发布即定死：全部 API 入参表无 deadline 修改入口（不变承诺 3）
    deadline_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    venue_name: Mapped[str] = mapped_column(String(64), nullable=False)
    venue_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    min_players: Mapped[int] = mapped_column(Integer, nullable=False)
    max_players: Mapped[int] = mapped_column(Integer, nullable=False)
    visibility: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # played|public|invite_only
    scoring: Mapped[int] = mapped_column(Integer, nullable=False)
    rotation: Mapped[str] = mapped_column(String(32), nullable=False)
    score_rule: Mapped[str] = mapped_column(String(64), nullable=False)
    manual_lock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 场地号列表（如 ["3号","5号"]）；非空即"已订场"，必打 = manual_lock 或 courts 非空
    courts: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    fee_total: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # 总价整数元；null=未定
    # open 报名中 | locked 成局/已锁 | terminated 未成局 | cancelled 已撤 | pending 待处置（恢复后）
    state: Mapped[str] = mapped_column(
        String(16), default="open", nullable=False, index=True
    )
    # 非空 = 改约解锁标记（锁定局被组织者改时间/地点时置位，到开打时刻重新锁死）
    unlocked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Entry(Base):
    __tablename__ = "entries"
    # 同一人同局只允许一行：报名幂等的天然键，并发抢坑的数据库兜底
    __table_args__ = (UniqueConstraint("game_id", "account_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id"), nullable=False, index=True
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id"), nullable=False, index=True
    )
    bring: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )  # 带的人数 0-3，行大小=1+bring
    joined_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    standing: Mapped[str] = mapped_column(
        String(16), default="formal", nullable=False
    )  # formal|waitlist
    wait_seq: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # 候补次序，仅 waitlist 行有


class Invite(Base):
    __tablename__ = "invites"
    __table_args__ = (
        UniqueConstraint("game_id", "invitee_id"),
    )  # 重复邀请不产生新记录

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id"), nullable=False, index=True
    )
    invitee_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Intent(Base):
    __tablename__ = "intents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 一人一份；时段只存前端词表 key 串不校验词表（防两真值，技术设计 §4）
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id"), unique=True, nullable=False
    )
    slots: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    # 完整可读单词不用缩写（契约§1，mock 的 freq 趁接线换名）
    frequency: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # 非空 = "已邀"标记（invite 置位、本人改意向清位；意向列表排序依据）
    invited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
