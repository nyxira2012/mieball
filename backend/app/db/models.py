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

现场域（2.3）live_state / live_players / live_courts / live_matches / elo_ratings：
- live 域整体与局簿六表并列新建（不并入）：现场是 locked 局之上的"另一本账"，散场封存后
  局簿照旧走自己的派生态，现场表定格当底账。
- 散场时刻只落 games.ended_at 一处（局簿终态锚，derive 吃它出 done）；live_state 不再
  冗余存一份——避免"两列都叫散场时刻"的双真值。
- live_matches 落账即冻结：没有任何 UPDATE 入口（战报不可篡改是积分可信的地基，2.3 §6）。
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
    # 散场时刻（2.3 §4.9）：局簿终态锚——非空即"已结束"，derive 吃它出 done；
    # 现场域另一头的真值（live_state 起止、考勤定格）以此为封存闸
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 终局时刻锚（灰字"当日"以各自的终局时刻记日，次日收走——技术设计 §3）：
    # terminated 死于判定落库时刻（截止判死者=截止时刻、拖过开打的待处置者=开打时刻）；
    # cancelled 死于撤局那一刻。底账留档不删（不变承诺 8），时刻列只记"什么时候死的"。
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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


class LiveState(Base):
    """现场总账头（2.3 技术设计 §2）：每局一行，开了账才有现场。

    total_seq 是全场总号（任何现场写 +1），与各片的 LiveCourt.court_seq 构成两级号
    并发防线（2.3 附录 B1）；round 为全场第几场的轮次计数。scoring 不落本表——
    复用 game 列，全场统一一个分制（2.3 裁决 Q1）。
    """

    __tablename__ = "live_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id"), unique=True, nullable=False
    )
    total_seq: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # rules 四件套快照（scoring 在 game 列）：双打 / 谁下 / 怎么配 / 连庄上限
    doubles: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    down: Mapped[str] = mapped_column(String(8), default="all", nullable=False)
    pairing: Mapped[str] = mapped_column(String(8), default="queue", nullable=False)
    streak_max: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    round: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class LivePlayer(Base):
    """现场名册行（2.3 技术设计 §2）：正式球友一人一行，随行访客也一人一行。

    account_id null = 访客（担保人记 guarantor_account_id）；dropin = 空降进场
    （没报名扫码直入，2.2 §4.4）。考勤时刻真值（arrive_at/left_at）在此列，
    读出按 viewer 分权（2.3 §4.10：组织者与本人可见）。
    """

    __tablename__ = "live_players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id"), nullable=False, index=True
    )
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True
    )
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    guest: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    guarantor_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True
    )
    dropin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # ok|late|left|absent|join（2.2 前端口径）：开账全员 absent，谁报到谁改
    check: Mapped[str] = mapped_column(String(8), default="absent", nullable=False)
    arrive_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    left_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    court_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 'a'/'b'；null = 候场/不在片
    court_side: Mapped[str | None] = mapped_column(String(1), nullable=True)
    skip: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fire: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 候场序（升序即队列序）；null = 场上或不在队
    queue_pos: Mapped[int | None] = mapped_column(Integer, nullable=True)


class LiveCourt(Base):
    """片行（2.3 技术设计 §2）：game+court_no 唯一，一片一行可复用——
    空闲(idle)→在打(playing)→待确认(pending) 状态机在行上循环。

    seq = 该片今天第几场（开新场 +1）；court_seq = 片号（该片记分类写 +1），
    与 LiveState.total_seq 构成两级号。pending_origin 区分待确认窗来源
    （到分自动 'auto' / 提前结算 'manual'，2.3 §4.3/4.4）。
    """

    __tablename__ = "live_courts"
    __table_args__ = (UniqueConstraint("game_id", "court_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id"), nullable=False, index=True
    )
    court_no: Mapped[int] = mapped_column(Integer, nullable=False)
    # idle|playing|pending
    status: Mapped[str] = mapped_column(String(8), default="idle", nullable=False)
    seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sa: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sb: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 撤一分只撤最后一次得分方（2.3 §4.1）：片行自记最后得分方
    last_winner_side: Mapped[str | None] = mapped_column(String(1), nullable=True)
    court_seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # null|auto|manual —— 仅 pending 态有值
    pending_origin: Mapped[str | None] = mapped_column(String(6), nullable=True)


class LiveMatch(Base):
    """战报行（2.3 §4.6）：确认落账即冻结，没有任何修改入口（§6 非目标）。

    winners/losers 为名册行快照 JSON（[{id,name,guest}...]，id 是 LivePlayer.id）；
    elo_rows 结算快照（[{account_id,name,guest,rating_before,rating_after,delta}...]，
    访客行有 delta 展示值但无落账，2.3 裁决访客不进账）。
    """

    __tablename__ = "live_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id"), nullable=False, index=True
    )
    court_no: Mapped[int] = mapped_column(Integer, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    winners: Mapped[list] = mapped_column(JSON, nullable=False)
    losers: Mapped[list] = mapped_column(JSON, nullable=False)
    sa: Mapped[int] = mapped_column(Integer, nullable=False)
    sb: Mapped[int] = mapped_column(Integer, nullable=False)
    # 'a'/'b'
    winner_side: Mapped[str] = mapped_column(String(1), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    elo_rows: Mapped[list] = mapped_column(JSON, nullable=False)


class EloRating(Base):
    """积分账（2.3 技术设计 §2，战力域最小地基）：一人一行。

    rating 默认 1500 = 新人初始等级单一源（2.4 裁决：访客代入同值参与期望计算，
    但访客不入行——只有正式球友有行）。仅 2.3 确认时写；读/榜归战力域册（4.1）。
    """

    __tablename__ = "elo_ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id"), unique=True, nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer, default=1500, nullable=False)
    play: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    win: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
