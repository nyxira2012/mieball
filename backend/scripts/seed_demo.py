"""seed_demo —— 一键重灌演示数据（开发库专用）。

用法（在 backend/ 目录下）：
    .venv/bin/python scripts/seed_demo.py          # 清库重灌（走查遗留一并清掉）
    MIEBALL_DB=sqlite:///./other.db .venv/bin/python scripts/seed_demo.py

行为：
- 清空全部业务表，主体经服务层重建（AccountBook.signup / GameBook.publish·join·book·lock·
  invite / IntentBook.save）——唯一键、人头账、两簿来往这些不变量由服务层自己保。
- 三处绕服务层的直写（都带注释）：①局4 提前落定 locked、②局6 整体回拨上周并落 ended_at
  （都是懒判定本就会做的同一动作，只是不等那一刻）、③积分底数 EloRating 直插（ 正路在
  LiveBook 确认结算，演示底数没有可复用的服务层入口）。
- 时间全部以服务层同一个 clock.now() 为基准做相对偏移：本机不是东八区时，
  publish 的「截止须晚于现在」校验也照样通过；脚本重复跑结果稳定（时间随当下顺延）。
- 「开发库专用」是约定非防护：脚本按 MIEBALL_DB（默认开发库）清库，不拦线上误指。

灌完后打印账号表（含设备钥匙 token）与局清单；想扮演某个演示账号：前端页面控制台执行
    uni.setStorageSync('mieball.token', '<token>')
刷新即可以该账号身份浏览。
"""

from __future__ import annotations

import sys
from datetime import datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ 入 import 路径

from sqlalchemy import delete

from app.core import clock
from app.core.config import get_settings
from app.db import models  # 注册全部表
from app.db.engine import Base, make_session_factory
from app.services.accounts import AccountBook
from app.services.games import GameBook
from app.services.intents import IntentBook
from app.services.keys import KeyVault
from app.services.sms import SmsGate

WD = "一二三四五六日"


def at_wall(
    base: datetime, day_offset: int, hh: int, mm: int, *, min_gap_min: int = 45
) -> datetime:
    """base 偏 day_offset 天的指定墙钟；离 base 太近（默认 45 分钟内）就顺延一天。"""
    t = (base + timedelta(days=day_offset)).replace(
        hour=hh, minute=mm, second=0, microsecond=0
    )
    while t <= base + timedelta(minutes=min_gap_min):
        t += timedelta(days=1)
    return t


def next_weekday(
    base: datetime, weekday: int, hh: int, mm: int, *, min_gap_h: int = 2
) -> datetime:
    """下一个指定周几的墙钟时刻（至少留 min_gap_h 小时余量，不够顺延一周）。"""
    d = base.date() + timedelta(days=1)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    t = datetime.combine(d, time(hh, mm))
    while t <= base + timedelta(hours=min_gap_h):
        t += timedelta(days=7)
    return t


def day_label(d: datetime, base: datetime) -> str:
    off = (d.date() - base.date()).days
    if off == 0:
        return "今天"
    if off == 1:
        return "明天"
    return f"周{WD[d.weekday()]}"


def main() -> None:
    settings = get_settings()
    factory = make_session_factory(settings.db_url)
    bind = factory.kw["bind"]
    Base.metadata.create_all(bind)

    db = factory()
    accounts = AccountBook(db, SmsGate(db, settings), KeyVault(db))
    games = GameBook(db)
    intents = IntentBook(db)

    # ---- 清库：演示库从零起（走查遗留全清） ----
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(delete(table))
    db.commit()

    base = clock.now()

    # ---- 账号（9 名演示球友；chibi 值都在 CHIBI_RANGES 界内） ----
    roster = [
        (
            "海淀反手王",
            "13900000001",
            {"skin": 0, "hair": 2, "hc": 5, "shirt": 7, "face": 3, "acc": 1},
        ),
        (
            "二环吊球手",
            "13900000002",
            {"skin": 1, "hair": 5, "hc": 0, "shirt": 1, "face": 1, "acc": 2},
        ),
        (
            "朝阳扣杀王",
            "13900000003",
            {"skin": 0, "hair": 0, "hc": 0, "shirt": 5, "face": 0, "acc": 0},
        ),
        (
            "回龙观搭子",
            "13900000004",
            {"skin": 1, "hair": 1, "hc": 2, "shirt": 2, "face": 0, "acc": 0},
        ),
        (
            "老周",
            "13900000005",
            {"skin": 2, "hair": 0, "hc": 1, "shirt": 4, "face": 1, "acc": 1},
        ),
        (
            "小雨",
            "13900000006",
            {"skin": 0, "hair": 3, "hc": 4, "shirt": 0, "face": 3, "acc": 0},
        ),
        (
            "Kevin",
            "13900000007",
            {"skin": 1, "hair": 4, "hc": 3, "shirt": 6, "face": 2, "acc": 0},
        ),
        (
            "板鸭",
            "13900000008",
            {"skin": 0, "hair": 1, "hc": 5, "shirt": 3, "face": 0, "acc": 1},
        ),
        (
            "五道口教练",
            "13900000009",
            {"skin": 2, "hair": 2, "hc": 0, "shirt": 7, "face": 1, "acc": 0},
        ),
    ]
    tokens: dict[str, tuple[int, str]] = {}  # nickname -> (id, token)
    for nickname, phone, chibi in roster:
        view, token = accounts.signup(
            phone=phone,
            device_marker=f"seed-{phone}",
            nickname=nickname,
            nickname_set=True,
            chibi=chibi,
            chibi_set=True,
        )
        tokens[nickname] = (view["id"], token)

    def uid(nickname: str) -> int:
        return tokens[nickname][0]

    def publish(
        *,
        organizer: str,
        name: str,
        start: datetime,
        hours: float,
        venue: str,
        lo: int,
        hi: int,
        visibility: str,
    ) -> int:
        # 截止默认开打前 2h；局快开打时截到「现在 +10 分钟」——publish 要求 now < deadline < start
        deadline = start - timedelta(hours=2)
        floor = base + timedelta(minutes=10)
        deadline = max(floor, deadline)
        view = games.publish(
            organizer_id=uid(organizer),
            name=name,
            start_at=start,
            end_at=start + timedelta(hours=hours),
            deadline_at=deadline,
            venue_name=venue,
            venue_address=None,
            min_players=lo,
            max_players=hi,
            visibility=visibility,
            scoring=11,
            rotation="balance",
            score_rule="rally",
        )
        return view["id"]

    # ---- 局 1：今晚 · 报名中 · 公开（约球页主力可报名局） ----
    g1_start = at_wall(base, 0, 19, 30)
    g1 = publish(
        organizer="海淀反手王",
        name=f"{day_label(g1_start, base)} · 五棵松夜战双打",
        start=g1_start,
        hours=2.5,
        venue="五棵松 · 万事达匹克球馆",
        lo=4,
        hi=10,
        visibility="public",
    )
    for who, bring in (("二环吊球手", 1), ("Kevin", 0), ("板鸭", 0), ("小雨", 0)):
        games.join(game_id=g1, account_id=uid(who), bring=bring)

    # ---- 局 2：明晚 · 报名中（演示档全用 public：新注册的号一进来就翻得到；
    #      played 档位的可见性行为由后端测试锁定，不在演示数据里演） ----
    g2_start = at_wall(base, 1, 19, 0)
    g2 = publish(
        organizer="老周",
        name=f"{day_label(g2_start, base)} · 朝阳红砖混双局",
        start=g2_start,
        hours=2,
        venue="朝阳公园 · 红砖匹克球馆",
        lo=6,
        hi=12,
        visibility="public",
    )
    for who, bring in (("朝阳扣杀王", 0), ("Kevin", 2), ("小雨", 0), ("五道口教练", 0)):
        games.join(game_id=g2, account_id=uid(who), bring=bring)

    # ---- 局 3：周六白天 · 报名中 · 公开（周末档演示） ----
    g3_start = next_weekday(base, 5, 10, 0)  # 周六 10:00
    g3 = publish(
        organizer="五道口教练",
        name=f"{day_label(g3_start, base)}白天 · 奥森晨练局",
        start=g3_start,
        hours=3,
        venue="奥林匹克森林公园 · 北园球场",
        lo=4,
        hi=8,
        visibility="public",
    )
    for who, bring in (("回龙观搭子", 0), ("板鸭", 0)):
        games.join(game_id=g3, account_id=uid(who), bring=bring)

    # ---- 局 4：明晚 · 已成局已订场（locked 档演示：满员 8/8 + 两片场 + 费用） ----
    g4_start = at_wall(base, 1, 20, 0)
    g4 = publish(
        organizer="朝阳扣杀王",
        name=f"{day_label(g4_start, base)} · 回龙观双片成局",
        start=g4_start,
        hours=2.5,
        venue="回龙观 · 体育公园球馆",
        lo=6,
        hi=8,
        visibility="public",
    )
    for who in (
        "海淀反手王",
        "二环吊球手",
        "回龙观搭子",
        "Kevin",
        "小雨",
        "老周",
        "板鸭",
    ):
        games.join(game_id=g4, account_id=uid(who), bring=0)
    games.book(
        game_id=g4,
        organizer_id=uid("朝阳扣杀王"),
        courts=["3号场", "5号场"],
        fee_total=480,
    )
    games.lock(game_id=g4, organizer_id=uid("朝阳扣杀王"))
    # 绕服务层唯一处①：把 state 提前落成 locked——懒判定在截止时刻做的同一件事
    db.get(models.Game, g4).state = "locked"
    db.commit()

    # ---- 局 5：今晚 · 满员带候补（候补栏演示：6/6 正式 + 2 候补） ----
    g5_start = at_wall(base, 0, 21, 30)
    g5 = publish(
        organizer="小雨",
        name=f"{day_label(g5_start, base)} · 速拼四缺二",
        start=g5_start,
        hours=1.5,
        venue="望京 · SOHO 空中球场",
        lo=4,
        hi=6,
        visibility="public",
    )
    for who, bring in (
        ("海淀反手王", 0),
        ("老周", 1),
        ("Kevin", 0),
        ("板鸭", 0),
        ("二环吊球手", 0),
        ("五道口教练", 0),
    ):
        games.join(game_id=g5, account_id=uid(who), bring=bring)

    # ---- 局 6：上周已散场（done 档演示：出现在参加者的「我的局」历史里） ----
    g6 = publish(
        organizer="五道口教练",
        name="上周 · 五道口复盘局",
        start=base + timedelta(days=1, hours=3),  # 占位时间，随后整体回拨
        hours=2.5,
        venue="五道口 · 清青球馆",
        lo=4,
        hi=8,
        visibility="public",
    )
    for who in ("海淀反手王", "二环吊球手", "小雨", "老周", "Kevin"):
        games.join(game_id=g6, account_id=uid(who), bring=0)
    # 绕服务层唯一处②：整局回拨到上周并落 ended_at——懒判定对 locked+ended_at 恒出 done
    row = db.get(models.Game, g6)
    row.start_at = base - timedelta(days=6)
    row.start_at = row.start_at.replace(hour=19, minute=30, second=0, microsecond=0)
    row.end_at = row.start_at + timedelta(hours=2.5)
    row.deadline_at = row.start_at - timedelta(hours=2)
    row.created_at = row.deadline_at - timedelta(hours=2)
    row.state = "locked"
    row.manual_lock = True
    row.ended_at = row.end_at
    db.commit()

    # ---- 意向簿（时段 key 与前端词表一致：wd 工作日晚 / ln 午休 / we-d 周末白天 / we-n 周末晚）。
    #      先落意向再发邀请：invite 只给「已有意向的人」置已邀标记，顺序反了标记就落不上 ----
    for who, slots, freq, note in (
        ("老周", ["we-d", "we-n"], 1, "免费场优先"),
        ("Kevin", ["wd", "ln"], 2, None),
        ("二环吊球手", ["we-n"], 1, "只想约晚场"),
        ("板鸭", ["wd", "we-n"], 0, None),
        ("五道口教练", ["wd", "we-d"], 2, "可以带练"),
    ):
        intents.save(account_id=uid(who), slots=slots, frequency=freq, note=note)

    # ---- 邀请（两簿来往演示）：局 1 邀有意向的老周（跑马灯+已邀标记）；局 4 邀五道口教练 ----
    games.invite(game_id=g1, organizer_id=uid("海淀反手王"), invitee_id=uid("老周"))
    games.invite(
        game_id=g4, organizer_id=uid("朝阳扣杀王"), invitee_id=uid("五道口教练")
    )

    # ---- 积分账（战力地基：仅确认结算会写，这里直插演示底数） ----
    db.add_all(
        [
            models.EloRating(
                account_id=uid("海淀反手王"), rating=1876, play=42, win=26
            ),
            models.EloRating(
                account_id=uid("二环吊球手"), rating=1652, play=30, win=15
            ),
            models.EloRating(
                account_id=uid("朝阳扣杀王"), rating=1932, play=55, win=38
            ),
            models.EloRating(account_id=uid("回龙观搭子"), rating=1420, play=12, win=4),
            models.EloRating(account_id=uid("老周"), rating=1588, play=24, win=11),
            models.EloRating(account_id=uid("小雨"), rating=1502, play=8, win=3),
            models.EloRating(account_id=uid("Kevin"), rating=1710, play=20, win=10),
            models.EloRating(account_id=uid("板鸭"), rating=1355, play=6, win=1),
            models.EloRating(
                account_id=uid("五道口教练"), rating=1988, play=78, win=57
            ),
        ]
    )
    db.commit()

    # ---- 汇报 ----
    print(f"已重灌演示数据 → {bind.url}")
    print(
        f"基准时刻 clock.now() = {base:%Y-%m-%d %H:%M}（本机墙钟，库里按北京墙钟口径存 naive）\n"
    )
    print(
        "账号（想扮演谁，前端控制台执行 uni.setStorageSync('mieball.token', '<token>') 后刷新）："
    )
    for nickname, (aid, token) in tokens.items():
        print(f"  #{aid:<2} {nickname:<6} token={token}")
    print()
    print("局清单（游客视角 list_for）：")
    for v in games.list_for(viewer_id=None):
        print(
            f"  #{v['id']} [{v['status']:<5}] {v['name']} · {v['venue_name']} · "
            f"{v['start_at']} ~ {v['end_at']} · {v['heads']}/{v['max_players']} 人"
        )
    db.close()


if __name__ == "__main__":
    main()
