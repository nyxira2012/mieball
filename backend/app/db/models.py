"""全域数据表 —— 只有服务层（services/）碰它们，路由不直接查库。

账号域（1.1）accounts / device_keys / phone_codes：
- accounts.phone 带 UNIQUE 且注销时置 NULL：同一个号建不出两个在册账号靠数据库兜底
  （SQLite 多个 NULL 不冲突，手机号"释放后可重新注册"由此成立）。
- device_keys.fingerprint 存钥匙指纹不存原文；verified 标记"发出时是否经短信验证"，
  是 D4 规则（短信验证杀未验证钥匙）的依据。
- phone_codes 一表三用：验证码本体 + 限频计数（60 秒/一天 N 条按行数算，不另建计数表）。
- 微信钥匙（1.7）：accounts 三列登记位（openid 唯一索引 / verified 镜像钥匙两档 /
  绑定时刻）+ wechat_pendings 绑定凭条（指纹制、10 分钟一次性）。

球局域（1.2）games / entries / invites / intents：
- games.state 只有 5 个存储值；locked 之后的"进行中/已结束"是读时派生不落库（技术设计 §2.4）。
- entries 的 Unique(game_id, account_id) 是报名幂等的天然键（并发抢坑由它兜底）。
- intents.invited_at 非空即"已邀"标记（invite 置位、本人改意向清位）。

账单域（1.3）bills / bill_rows：
- 一场局一份账：bills.game_id unique——出账幂等（散场 end 与补填两个入口竞态/重放）
  靠它兜底，谁先落库谁赢，第二本账建不出来。
- 行不存状态列：说「转了」（paid_at）与点「收」（received_at）是两个时刻，三态由
  两时刻推导（A4：状态是推导不是存储）；display_name 是出账那一刻的定格名，此后
  改名/注销不动这笔账（视图组装时才做「已注销球友」占位转换）。

现场域（2.3）live_state / live_players / live_courts / live_matches / elo_ratings：
- live 域整体与局簿六表并列新建（不并入）：现场是 locked 局之上的"另一本账"，散场封存后
  局簿照旧走自己的派生态，现场表定格当底账。
- 散场时刻只落 games.ended_at 一处（局簿终态锚，derive 吃它出 done）；live_state 不再
  冗余存一份——避免"两列都叫散场时刻"的双真值。
- live_matches 落账即冻结；唯一例外=settle_overwrite 在下一场落账前的窗口内 UPDATE 本行
  （战报不可篡改是积分可信的地基，2.3 §6；窄口由 2026-10-09 裁决③开出）。

战力域（1.4）dupr_ratings / dupr_details：
- 分数是派生值不落明细：dupr_details 只存事实快照（结算时四人分数/比分/时刻，
  一场一行按注册球员），dupr_ratings 缓存窗口重放结果——调参/纠偏重算即可，零迁移。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
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
    # 微信登记位全局唯一（一个微信一个账号；NULL 不参与唯一，未绑多行不冲突）——
    # 唯一索引不在模型里声明（删列重建的测试路径会与改名表上的同名索引撞车），
    # 由 main._ENSURE_INDEXES 启动补建（IF NOT EXISTS 幂等，新库老库一趟覆盖）

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
    # ---- 密码钥匙（1.6 第三把）----
    # password_hash 只存加工暗记不存原文（C1）；fail/locked 是"用密码"这一条路的
    # 连错计数与 15 分钟锁（login/redeem 共用）；grace 是短信验明正身后的设密宽限窗
    # （接管/找回时置位，窗内设密码免再发一条码）
    password_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    pwd_fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pwd_locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pwd_grace_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # ---- 微信钥匙登记位（1.7 第四把）----
    # 规则与 device_keys.verified 完全镜像：wechat_verified="绑定那一刻手机号是否
    # 验过"——验明正身时绑的=True（微信进门等同短信），纯建号顺手绑的=False
    # （等同未验证钥匙，验明正身时自动解开，D4 防冒填者的镜像）；接管/注销/换锁清位
    wechat_openid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    wechat_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    wechat_bound_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


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


class WechatPending(Base):
    """微信绑定凭条（1.7）：授权认人后的"生面孔"凭条——建号/验明正身时刻凭它
    顺手绑上。只存指纹不存原文（同钥匙/验证码规矩）；10 分钟一次性，过期行在
    下次核销时顺手清扫。"""

    __tablename__ = "wechat_pendings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    openid: Mapped[str] = mapped_column(String(64), nullable=False)
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


class Bill(Base):
    """一场局一份账（1.3 技术设计 §1）：出账即定格，账永久留档（无删除/改写入口）。

    per_head = 向下抹零的整份（fee_total // heads）；账单日期不在此冗余存——
    按散场那天（games.ended_at）归属，billed_at 只记出账时刻（补填的局=补填那刻）。
    """

    __tablename__ = "bills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id"), unique=True, nullable=False
    )
    fee_total: Mapped[int] = mapped_column(Integer, nullable=False)
    heads: Mapped[int] = mapped_column(Integer, nullable=False)
    per_head: Mapped[int] = mapped_column(Integer, nullable=False)
    billed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # 摊费口径版本记号（6.1 §4.4，值=bills.py SPLIT_VERSION）：存量行 NULL=不回填
    # ——旧账按当时的规矩摊的，不追认新记号
    rule_version: Mapped[str | None] = mapped_column(String(8), nullable=True)


class BillRow(Base):
    """摊钱名单每人一行（1.3 技术设计 §1）：正式/空降/早退/缺席的账号行一人一行
    （候补从不进 live_players 故天然不进账）；访客不单独成行——份额归担保人
    （guest_count=名下访客行数，share_count=1+guest_count）。amount 出账定格，
    组织者行=总价−Σ非组织者（差额兜底，合计恒等于总价）。"""

    __tablename__ = "bill_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bill_id: Mapped[int] = mapped_column(
        ForeignKey("bills.id"), nullable=False, index=True
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id"), nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    guest_count: Mapped[int] = mapped_column(Integer, nullable=False)
    share_count: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class LiveState(Base):
    """现场总账头（2.3 技术设计 §2）：每局一行，开了账才有现场。

    total_seq 是全场总号（任何现场写 +1），与各片的 LiveCourt.court_seq 构成两级号
    并发防线（2.3 附录 B1）；round 为全场第几场的轮次计数。分制真值复用 game 列
    （2.3 裁决 Q1），片上另有开赛快照 LiveCourt.scoring——改分制在打片照旧、
    新开片用新制（2.6 机制A）。
    """

    __tablename__ = "live_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id"), unique=True, nullable=False
    )
    total_seq: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # rules 四件套快照（分制真值在 game 列、片快照在 LiveCourt.scoring）：
    # 双打 / 谁下 / 怎么配 / 连庄上限
    doubles: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    down: Mapped[str] = mapped_column(String(8), default="all", nullable=False)
    pairing: Mapped[str] = mapped_column(String(8), default="queue", nullable=False)
    streak_max: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    round: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # 开账人账号 id（2.5 B1「谁开的账」新记；组织者或窗内正式成员，旧账 None）
    started_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 管理员名单（2.2 §4.6 封撤的真值，存 Account.id；组织者独占封撤、散场即止不回写局簿）
    admins: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # 战报事件句留痕（2.2 §4.6/§4.9 撤管理员与换人）：结构化事件行，句式拼装归前端
    # （契约§2 后端不产中文文案）
    feed: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # 场地片数（2.2 场地设置的后端真值）：开账按订场登记起笔、缺省按人数回退
    # （镜像 rotate.ts courtCount 单一源）；缩片先撤空闲片、不得少于在用片数
    courts_count: Mapped[int] = mapped_column(Integer, default=2, nullable=False)


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
    """片行（2.3 技术设计 §2；2026-10-09 记分本地化修订）：game+court_no 唯一，
    一片一行可复用——空闲(idle)↔在打(playing) 状态机在行上循环。进行中比分不落
    服务端（活在各手机本地），上传结算直接进战报行。

    seq = 该片今天第几场（开新场 +1）；court_seq = 片号（该片写动作 +1），
    与 LiveState.total_seq 构成两级号。
    """

    __tablename__ = "live_courts"
    __table_args__ = (UniqueConstraint("game_id", "court_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id"), nullable=False, index=True
    )
    court_no: Mapped[int] = mapped_column(Integer, nullable=False)
    # idle|playing
    status: Mapped[str] = mapped_column(String(8), default="idle", nullable=False)
    seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    court_seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 片分制快照（2.6 机制A）：开赛定格当时 game.scoring——改分制只影响此后
    # 新开的片，在打片卡头按它亮分制（本地判到分在前端）；default 11 只是行不裸奔
    scoring: Mapped[int] = mapped_column(Integer, default=11, nullable=False)


class LiveMatch(Base):
    """战报行（2.3 §4.6）：确认落账即冻结；唯一例外=改分重落（settle_overwrite，
    2026-10-09 裁决③）——仅限该片仍是最新一场、下一场未落账的窗口内 UPDATE 本行。

    winners/losers 为名册行快照 JSON（[{id,name,guest}...]，id 是 LivePlayer.id）；
    elo_rows 结算快照（[{account_id,name,guest,rating_before,rating_after,delta}...]，
    访客行有 delta 展示值但无落账，2.3 裁决访客不进账；改分重落按它反算）。
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


# Elo 娱乐轨初始分（1.4 裁决 8：初始 1200、地板 800，访客代入同值）：
# 建行默认值与 services（live 积分账 / 战力榜展示兜底）共用此一处——
# 前端 utils/elo.ts 的 ELO_INIT 同值仅作展示镜像，不担公式
ELO_RATING_INIT = 1200


class EloRating(Base):
    """Elo 娱乐轨积分账（2.3 落地基，1.4 §3 调参为娱乐轨）：一人一行。

    rating 默认 ELO_RATING_INIT；访客代入同值参与期望计算但访客不入行——
    只有正式球友有行。仅 2.3 确认时写；读/榜归战力域册（4.1）。
    """

    __tablename__ = "elo_ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id"), unique=True, nullable=False
    )
    rating: Mapped[int] = mapped_column(
        Integer, default=ELO_RATING_INIT, nullable=False
    )
    play: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    win: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class DuprRating(Base):
    """DUPR 派生分缓存（1.4 技术设计 §2）：一人一行，重算后整行覆写。

    分数 = 起步分（GUEST_DUPR 2.5，1.4 §10 修订）+ 窗口内明细逐场重放的派生值
    （口径常量在 services/dupr.py 单一源）；games 缓存明细总行数（定级门槛 ≥5），
    两者都由 StatsLedger 每次结算后对涉事者同步重写。
    """

    __tablename__ = "dupr_ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id"), unique=True, nullable=False
    )
    rating: Mapped[float] = mapped_column(Float, default=2.5, nullable=False)
    games: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class DuprDetail(Base):
    """DUPR 明细（1.4 技术设计 §2）：一场确认制结束对局，每名注册球员一行
    （访客不落，按 GUEST_DUPR 2.5 代入对面的快照）。

    每行带自己视角的完整输入快照（结算时四人当前派生分 + 比分 + 胜负），
    落账即冻结无 UPDATE（沿 live_matches 先例）——重放不依赖回溯历史评分状态，
    与在线落分天然一致。索引 (account_id, id)：窗口 = 按 id 倒序取近 30
    （id=结算序，避开多片同时确认的 ended_at 抖动）。
    """

    __tablename__ = "dupr_details"
    __table_args__ = (Index("ix_dupr_details_account_id_id", "account_id", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    match_id: Mapped[int] = mapped_column(ForeignKey("live_matches.id"), nullable=False)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    partner_rating: Mapped[float] = mapped_column(Float, nullable=False)
    opp_a: Mapped[float] = mapped_column(Float, nullable=False)
    opp_b: Mapped[float] = mapped_column(Float, nullable=False)
    score_w: Mapped[int] = mapped_column(Integer, nullable=False)  # 胜方分
    score_l: Mapped[int] = mapped_column(Integer, nullable=False)
    won: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # 算分口径版本记号（6.1 §4.4，值=dupr.py RULES_VERSION）：存量行 NULL=不回填
    # ——旧明细按当时的口径算的，不追认新记号
    rule_version: Mapped[str | None] = mapped_column(String(8), nullable=True)
