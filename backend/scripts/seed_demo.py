"""seed_demo —— 一键重灌演示数据（开发库专用）。

用法（在 backend/ 目录下）：
    .venv/bin/python scripts/seed_demo.py          # 清库重灌（走查遗留一并清掉）
    MIEBALL_DB=sqlite:///./other.db .venv/bin/python scripts/seed_demo.py

行为：
- 清空全部业务表，主体经服务层重建（AccountBook.signup / GameBook.publish·join·book·
  lock·invite / IntentBook.save / LiveBook.start·check·deal·settle_confirm·end /
  BillBook.settle）——唯一键、人头账、两级号、两簿来往这些不变量由服务层自己保。
- 时间旅行只做一件事：monkeypatch clock.now()（服务层测试同款手法，各服务都按
  `from ..core import clock` 模块引用，补丁全局生效）把钟拨过去，让每个状态转换
  都发生在它该发生的时刻——
  · 账号建在两周前（报名晚于建号才是正序）；
  · 局 4（成局已订场档）截止显式钉在「现在 +10 分钟」，随后把钟拨过截止刷一次
    列表，懒判定真跑一遍把 open 落成 locked（lock() 只翻 pending 态，open 局的
    锁定出口就是截止懒判定——直写 state 会造出「未到截止却锁定」的库态）；
  · 局 6（上周复盘局）全程走真过程：上周发局→报名→订场→锁定→开账→签到→发牌
    打五场→散场（自动出账）→次日一位参加者点结算。战报/考勤/账单/打球记录全是
    过程长出来的（散场必先开账——end 走 _open_write；2026-10-11 修复前直写
    ended_at 造出「从未开账却已散场」的壳局：参加者记录查无、却互相解锁
    「跟我打过」）。
- 绕服务层的直写只剩积分底数两表（EloRating/DuprRating 插入或覆写）：正路在落账
  结算，演示没有可复用的服务层入口——DuprDetail 每行挂真实 match_id 外键，造不出
  「没有局的历史」。底数是展示用冷读数，数字口径对齐引擎：play==games（落账双写
  两轨必然相等）、Elo ≤ 1200+24×win（K=24、胜方单场至多 +24）。代价：近5场/月度
  涨跌无明细支撑（card 的 wins/last5 吃明细），且底数号第一次真落账时 DUPR 会按
  明细重放归位（重放锚 2.5、games 重算为明细行数）——走查别让这五位真上场打分。
- 时间全部以服务层同一个 clock.now() 为基准做相对偏移：本机不是东八区时，
  publish 的「截止须晚于现在」校验也照样通过；脚本重复跑结果稳定（时间随当下顺延）。
- 「开发库专用」是约定非防护：脚本按 MIEBALL_DB（默认开发库）清库，不拦线上误指。

灌完后打印账号表（含设备钥匙 token）、局清单与上周局战报/账单/记录速览；想扮演某个
演示账号：前端页面控制台执行
    uni.setStorageSync('mieball.token', '<token>')
刷新即可以该账号身份浏览。
"""

from __future__ import annotations

import sys
from datetime import datetime, time, timedelta
from pathlib import Path

from sqlalchemy import delete, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ 入 import 路径

from app.core import clock
from app.core.config import get_settings
from app.db import models
from app.db.engine import Base, make_session_factory
from app.services.accounts import AccountBook
from app.services.bills import BillBook
from app.services.games import GameBook
from app.services.intents import IntentBook
from app.services.live import LiveBook

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
    accounts = AccountBook.open(db, settings)
    games = GameBook(db)
    intents = IntentBook(db)
    live = LiveBook(db)
    bills = BillBook(db)

    # ---- 清库：演示库从零起（走查遗留全清） ----
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(delete(table))
    db.commit()

    real_now = clock.now  # 真钟；每次时间旅行后靠它复位
    base = real_now()

    def travel(t: datetime) -> None:
        clock.now = lambda: t

    # ---- 账号（9 名演示球友；形象=公共头像 6 款轮换）----
    roster = [
        ("海淀反手王", "13900000001"),
        ("二环吊球手", "13900000002"),
        ("朝阳扣杀王", "13900000003"),
        ("回龙观搭子", "13900000004"),
        ("老周", "13900000005"),
        ("小雨", "13900000006"),
        ("Kevin", "13900000007"),
        ("板鸭", "13900000008"),
        ("五道口教练", "13900000009"),
    ]
    # 两周前建号：局 6 的报名发生在上周，建号必须更早才是正序
    travel(
        (base - timedelta(days=14)).replace(hour=12, minute=0, second=0, microsecond=0)
    )
    tokens: dict[str, tuple[int, str]] = {}  # nickname -> (id, token)
    for i, (nickname, phone) in enumerate(roster):
        view, token, _bound = (
            accounts.signup(  # 三元组（1.8 快进：微信绑没绑上，seed 不消费）
                phone=phone,
                device_marker=f"seed-{phone}",
                nickname=nickname,
                nickname_set=True,
                avatar=f"a-p{i % 6 + 1}",
            )
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
        deadline: datetime | None = None,
    ) -> int:
        # 截止默认开打前 2h；保底「现在 +10 分钟」——publish 要求 now < deadline < start
        dl = deadline or (start - timedelta(hours=2))
        dl = max(clock.now() + timedelta(minutes=10), dl)
        view = games.publish(
            organizer_id=uid(organizer),
            name=name,
            start_at=start,
            end_at=start + timedelta(hours=hours),
            deadline_at=dl,
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

    clock.now = real_now  # 回真钟：局 1~5 与意向/邀请都是「现在」的事

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
    # 截止显式钉在「现在 +10 分钟」：随后拨过截止刷一次列表，懒判定把 open 落成
    # locked（lock() 只翻 pending 态；直写 state 是「未到截止却锁定」的假库态）
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
        deadline=base + timedelta(minutes=10),
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
    travel(base + timedelta(minutes=12))  # 截止刚过
    games.list_for(viewer_id=None)  # 懒判定落库：局 4 open→locked（8 人 ≥ 最少 6）
    clock.now = real_now

    # ---- 局 5：今晚 · 满员带候补（候补栏演示：6/6 正式 + 1 行候补——五道口教练） ----
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

    # ---- 局 6：上周 · 真过程散场局（战报/考勤/账单/打球记录全由此长出） ----
    anchor = (base - timedelta(days=8)).replace(
        hour=12, minute=0, second=0, microsecond=0
    )

    def wk(day_off: int, mins: int) -> datetime:
        return (anchor + timedelta(days=day_off)).replace(
            hour=mins // 60, minute=mins % 60, second=0, microsecond=0
        )

    travel(wk(0, 12 * 60))
    g6 = publish(
        organizer="老周",
        name="上周 · 清青球馆复盘局",
        start=wk(2, 19 * 60 + 30),
        hours=2.5,
        venue="五道口 · 清青球馆",
        lo=4,
        hi=8,
        visibility="public",
    )
    for who, day_off, mins in (
        ("小雨", 0, 12 * 60 + 40),
        ("板鸭", 0, 19 * 60),
        ("回龙观搭子", 1, 10 * 60),
        ("Kevin", 1, 12 * 60),
        ("二环吊球手", 1, 15 * 60),
    ):
        travel(wk(day_off, mins))
        games.join(game_id=g6, account_id=uid(who), bring=0)
    travel(wk(1, 16 * 60))
    games.book(game_id=g6, organizer_id=uid("老周"), courts=["1号场"], fee_total=400)
    travel(wk(1, 16 * 60 + 5))
    games.lock(game_id=g6, organizer_id=uid("老周"))

    # 开账（组织者随时）→ 签到四人 → 打五场 → 散场。Kevin/二环吊球手放了鸽子：
    # absent 落考勤、账单照摊（缺席照摊）、不上场——他们的积分底数才保得住。
    travel(wk(2, 19 * 60 + 20))
    v = live.start(game_id=g6, organizer_id=uid("老周"))
    row_of = {p["account_id"]: p["id"] for p in v["players"]}
    for who, mins in (
        ("老周", 19 * 60 + 25),
        ("小雨", 19 * 60 + 28),
        ("板鸭", 19 * 60 + 35),  # 过了开打时刻，签到自动落 late（迟到口径）
        ("回龙观搭子", 19 * 60 + 41),
    ):
        travel(wk(2, mins))
        v = live.check(
            game_id=g6,
            actor_id=uid(who),
            player_id=row_of[uid(who)],
            check="ok",
            base_total_seq=v["total_seq"],
        )
    # 五场对局——四人各满 5 场正好跨过定级门槛（1.4 §5）。赛制是「确认即开下一场」：
    # settle_confirm 落账后后端自动回流补位续场（场片保持 playing），首场发牌
    # 走 2.8 收编后的空载荷 deal（全权补所有空片，取队口径在后端单一真值）。
    # 胜方 a/b 交替防连庄一边倒；最后一场 no_redeal 定格（= 组织者散场时对残局
    # 「上传比分」的正路：落账计分但不排下一场），场片回 idle 散场才放行。
    travel(wk(2, 19 * 60 + 45))  # 首场开打
    v = live.view(game_id=g6, viewer_id=uid("老周"))
    v = live.deal(
        game_id=g6,
        actor_id=uid("老周"),
        base_total_seq=v["total_seq"],
    )
    for i, (hi, lo) in enumerate(((11, 9), (11, 7), (11, 6), (12, 10), (11, 8))):
        travel(wk(2, 19 * 60 + 45 + 23 + 25 * i))  # 落账时刻
        a_wins = i % 2 == 0
        v = live.settle_confirm(
            game_id=g6,
            actor_id=uid("小雨"),  # 上传权=到场者，谁传都行
            court_no=1,
            winner_side="a" if a_wins else "b",
            score_a=hi if a_wins else lo,
            score_b=lo if a_wins else hi,
            no_redeal=i == 4,
            base_total_seq=v["total_seq"],
            base_court_seq=next(c for c in v["courts"] if c["court_no"] == 1)[
                "court_seq"
            ],
        )
    travel(wk(2, 21 * 60 + 52))
    v = live.view(game_id=g6, viewer_id=uid("老周"))
    live.end(
        game_id=g6, actor_id=uid("老周"), base_total_seq=v["total_seq"]
    )  # 散场自动出账

    travel(wk(3, 10 * 60))  # 次日：小雨微信转完账点「结算」——组织者侧亮「已转·待收」
    bills.settle(game_id=g6, account_id=uid("小雨"))

    clock.now = real_now

    # ---- 积分底数（展示用冷读数，口径见文件头）：只给没走真过程的五位 ----
    # 上场四人（老周/小雨/板鸭/回龙观搭子）的五场对局已由落账自然长出双轨积分，不碰。
    # Kevin/二环吊球手在局 6 开账时被建了 1200 底行——这里覆写成底数（upsert）。
    for nickname, elo_r, n, wins, dupr_r in (
        ("海淀反手王", 1876, 42, 29, 4.21),
        ("二环吊球手", 1652, 30, 19, 3.55),
        ("朝阳扣杀王", 1932, 55, 38, 4.58),
        ("五道口教练", 1988, 78, 57, 4.35),
        ("Kevin", 1548, 20, 15, 3.20),
    ):
        # Elo 1200 起步、K=24：胜方单场至多 +24，分数在给定胜场内必须够得着
        assert elo_r <= 1200 + 24 * wins, (
            f"{nickname} 的 Elo 在 {wins} 胜内到不了 {elo_r}"
        )
        elo_row = db.execute(
            select(models.EloRating).where(models.EloRating.account_id == uid(nickname))
        ).scalar_one_or_none()
        if elo_row is None:
            elo_row = models.EloRating(account_id=uid(nickname))
            db.add(elo_row)
        elo_row.rating, elo_row.play, elo_row.win = elo_r, n, wins
        dupr_row = db.execute(
            select(models.DuprRating).where(
                models.DuprRating.account_id == uid(nickname)
            )
        ).scalar_one_or_none()
        if dupr_row is None:
            dupr_row = models.DuprRating(account_id=uid(nickname))
            db.add(dupr_row)
        dupr_row.rating, dupr_row.games, dupr_row.updated_at = dupr_r, n, base
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
    print()
    v6 = live.view(game_id=g6, viewer_id=uid("老周"))
    arrived = sum(1 for p in v6["players"] if p["check"] != "absent")
    print(
        f"上周复盘局 #{g6}（真过程）：开账 {v6['started_at']} · 散场 {v6['ended_at']}"
    )
    print(
        f"  考勤 {arrived}/{len(v6['players'])} 到场 · 战报 {len(v6['matches'])} 场："
    )
    for i, m in enumerate(v6["matches"], 1):
        names = "+".join(w["name"] for w in m["winners"])
        print(f"    第{i}场 {names} 胜 {m['score_a']}:{m['score_b']}")
    zhou = bills.view(account_id=uid("老周"))
    yu = bills.view(account_id=uid("小雨"))
    print(
        f"  账单（400 = 66×5 + 组织者兜零头 70）：老周待收 {zhou['summary']['receivable']} 元；"
        f"小雨已结算（组织者侧显「已转·待收」），剩余应付 {yu['summary']['due']} 元"
    )
    pl_yu = games.playlog(account_id=uid("小雨"))
    pl_kevin = games.playlog(account_id=uid("Kevin"))
    print(
        f"  打球记录：小雨 {len(pl_yu['games'])} 局 · 累计上场 {pl_yu['matches_count']} 场对局；"
        f"Kevin {len(pl_kevin['games'])} 局（缺席照摊在列）· 累计 {pl_kevin['matches_count']} 场"
    )
    db.close()


if __name__ == "__main__":
    main()
