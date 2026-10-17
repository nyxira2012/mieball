"""game_views —— 局簿读视图：派生态、game_view 组装与写窗谓词（技术设计 §2.4，批3 自 games.py 拆出）。

GameBook 的读出口要把"局行 + 时刻 + 观看者"变成前端直接可用的定值形状（A4：画面不自算），
这里管三件事：
- 派生：存储 5 态 × 时刻 × 观看者 → 视图 7 态；pending 待处置只组织者可见（4.9），
  其他人按 terminated 出（masked）；灰字"当日"的锚（death_day）。
- 组装：game_view 全量字段——人头/剩坑/人均/forced/ended 都在此算定值，
  my 块带能力旗（can_book/can_fill_fee/can_lock，闸旗同源）。
- 写窗谓词：booking/fill_fee/lock 三个窗口的拦路错只此一份——写端点拿它把关、
  my 块拿它亮旗，窗口规则改动不出本模块（2026-10-08 债清偿，沿 is_forced 先例）。
局簿写路径也用 derive 做窗口判断（游戏规则的"现在算什么态"只有这一份）。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core import clock, errors
from ..db.models import (
    Account,
    Bill,
    BillRow,
    Entry,
    Game,
    Invite,
    LivePlayer,
    LiveState,
)
from .accounts import person_view

# 截止后照常可加到局结束（4.14）；done/terminated/cancelled/pending 不可加
JOINABLE_STATUSES = ("open", "locked", "live")

# 工具箱（锁必打/撤局）的受理窗口：开打前；pending 是恢复后的待处置，
# 锁/撤局是它的处置出口（4.9）。订场/清空不在此列——改价窗口已放宽到散场确认前
# （1.3 §4.5 修订①），走 booking_window_error
TOOLBOX_STATUSES = ("open", "locked", "pending")


def is_forced(game: Game) -> bool:
    """必开 = 已订场登记或手动锁必打——开账闸（2.5 §4.4）与卡片 forced 标志同一源。"""
    return bool(game.courts) or game.manual_lock


def owned_game(db: Session, game_id: int, organizer_id: int) -> Game:
    """组织者守卫单一源（GameBook._owned / BillBook._owned_game 同委托）：
    查无 → 404，非本人局 → 403。账是钱的事只认组织者本人（C2），不走 live 分级权
    ——两簿此前靠 docstring 互认口径，收此地后权限语义改动只改这一处。"""
    game = db.get(Game, game_id)
    if game is None:
        raise errors.game_not_found()
    if game.organizer_id != organizer_id:
        raise errors.not_organizer()
    return game


def derive(game: Game, now: datetime) -> str:
    """派生视图态：locked 随时刻翻 locked/live/done；
    pending 拖过开打 = 死局（待处置没有处置价值的时刻，僵尸出口由懒判定落库）。"""
    if game.state == "pending":
        return "pending" if now < game.start_at else "terminated"
    if game.state == "locked":
        if game.ended_at is not None:
            return "done"  # 散场时刻是局簿终态锚（2.3 §4.9）：散过的局不回头
        if now < game.start_at:
            return "locked"
        return "live" if now < game.end_at else "done"
    return game.state  # open（进懒判定后必未过期）/ terminated / cancelled 原样


def masked(game: Game, viewer_id: int | None, now: datetime) -> str:
    """带观看者的派生态：待处置只组织者可见（4.9），其他人一律按已终止出。"""
    status = derive(game, now)
    return (
        "terminated"
        if status == "pending" and viewer_id != game.organizer_id
        else status
    )


def death_day(game: Game) -> date:
    """灰字"当日"的锚（次日收走，4.8/4.10）：terminated/cancelled 各死于自己的终局
    时刻列（技术设计 §3）；`or deadline_at` 只兜两列皆空的旧账。"""
    if game.state == "cancelled":
        return game.cancelled_at.date()
    return (game.terminated_at or game.deadline_at).date()


# ---- 写窗谓词（闸旗同源，2026-10-08 债清偿）：写端点拿它把关（有拦路错就抛），
#      my 块拿它亮能力旗（无拦路错才 true）——窗口规则只剩这一份，改一处两端同步。
#      沿 is_forced 先例（开账闸与卡片 forced 同源）落在读视图模块。 ----


def booking_window_error(game: Game) -> errors.ApiError | None:
    """订场/清空改价窗口的拦路错（1.3 §4.5 修订①）：散场确认前随时可改——只锚
    ended_at 与存储终态，不看派生态（开打中 live、到点未散场的 done 都在窗内）；
    散场确认后总价定死（game_ended），终态局仍 game_not_open。"""
    if game.ended_at is not None:
        return errors.game_ended()
    if game.state in ("terminated", "cancelled"):
        return errors.game_not_open()
    return None


def fill_fee_error(game: Game) -> errors.ApiError | None:
    """补填窗口的拦路错（1.3 §4.5）：只有散场过且从未填过价（fee_total 空）的局
    留这一个口子——未散场 game_not_ended、填过（含 0）fee_already_set。"""
    if game.ended_at is None:
        return errors.game_not_ended()
    if game.fee_total is not None:
        return errors.fee_already_set()
    return None


def lock_window_error(game: Game, now: datetime) -> errors.ApiError | None:
    """空锁必打窗口的拦路错（4.7/4.9）：开打前的工具箱三态——pending 锁必打是
    恢复局的处置出口，开打后 game_not_open（空锁语义只存在开打前）。"""
    if derive(game, now) not in TOOLBOX_STATUSES:
        return errors.game_not_open()
    return None


def game_view(
    db: Session,
    game: Game,
    *,
    viewer_id: int | None,
    heads: int,
    with_entries: bool = False,
    batch: dict | None = None,
) -> dict:
    """game_view 全量定值（技术设计 §2.1 字段表）；heads 由局簿唯一一把尺算好传入。
    batch 是列表读的批量预取（heads/账本/我的账行/报名邀请/组织者账号，GameBook.
    _list_batch 产）——单局路径（detail/写响应）不传，逐局现查照旧。"""
    now = clock.now()
    status = masked(game, viewer_id, now)
    organizer = (
        batch["accounts"].get(game.organizer_id)
        if batch is not None
        else db.get(Account, game.organizer_id)
    )
    view: dict[str, Any] = {
        "id": game.id,
        "name": game.name,
        "organizer": person_view(organizer),
        "start_at": clock.iso(game.start_at),
        "end_at": clock.iso(game.end_at),
        "deadline_at": clock.iso(game.deadline_at),
        "venue_name": game.venue_name,
        "venue_address": game.venue_address,
        "min_players": game.min_players,
        "max_players": game.max_players,
        "visibility": game.visibility,
        "scoring": game.scoring,
        "rotation": game.rotation,
        "score_rule": game.score_rule,
        "manual_lock": game.manual_lock,
        # 开场来源（plan|direct）：前端只在散场确认文案等少数位消费
        "source": game.source,
        "courts": list(game.courts) if game.courts is not None else None,
        "fee_total": game.fee_total,
        "bill": bill_block(db, game, viewer_id, batch=batch),
        "status": status,
        "unlocked": game.unlocked_at is not None and now < game.start_at,
        "joinable": status in JOINABLE_STATUSES,
        "heads": heads,
        "slots_left": max(0, game.max_players - heads),
        # half-up 对齐 JS Math.round（技术设计 §3），不用 Python banker's round
        "per_head": (
            int(game.fee_total / heads + 0.5)
            if game.fee_total is not None and heads
            else None
        ),
        # 必开标志（is_forced 单一源：后端开账闸与 A4 卡片同源）
        "forced": is_forced(game),
        # 账开标志（2.5 B1「账开没开」新记）：现场账头行存在即开过——列表路走 batch
        # 预取一把查齐（N+1 债清偿）；单局路径逐局一查，SQLite 十人规模可接受
        "live_opened": (
            game.id in batch["live_opened"]
            if batch is not None
            else db.execute(
                select(LiveState.id).where(LiveState.game_id == game.id)
            ).first()
            is not None
        ),
        # 散场确认锚（与 live 视图 ended 同名同义）：流程态 done 与派生显示态 done
        # 不是一回事——到点未散场的局派生出 done 但 ended 仍 false，现场回口/补填
        # 都要锚它（2.3 §4.9）
        "ended": game.ended_at is not None,
        # 实际散场时刻（与 live 视图 ended_at 同名同义）；end_at 是排场时的计划收尾
        "ended_at": clock.iso(game.ended_at) if game.ended_at else None,
    }
    if with_entries:
        view["entries"] = entry_rows(db, game.id)
        view["dropins"] = dropin_rows(db, game.id)
        # 实到口径（现场账头时刻 + 名册行数）：heads/start_at 是排场时的计划数，
        # 开过账的局人数以名册为准（空降/现场带人都在册）
        state = db.execute(
            select(LiveState).where(LiveState.game_id == game.id)
        ).scalar_one_or_none()
        view["live_started_at"] = clock.iso(state.started_at) if state else None
        view["live_heads"] = (
            db.execute(
                select(func.count())
                .select_from(LivePlayer)
                .where(LivePlayer.game_id == game.id)
            ).scalar_one()
            if state
            else None
        )
    if viewer_id is not None:
        view["my"] = my_block(db, game, viewer_id, batch=batch, now=now)
    return view


def bill_block(
    db: Session, game: Game, viewer_id: int | None, batch: dict | None = None
) -> dict | None:
    """已出账局的实摊定值块（1.3 §3）：fee_total/per_head/heads 是引擎定格数，
    my_share 按 viewer 在账行的 amount（不在摊钱名单/游客 → null）；未出账 → None
    ——前端以块有无区分「约（预估）」与实摊（A4）。只给自己的行：别人摊多少、
    结没结一字节不漏（§4.6 看账边界）。"""
    if batch is not None:
        bill = batch["bills"].get(game.id)
        mine = batch["my_bill_rows"].get(game.id) if viewer_id is not None else None
    else:
        bill = db.execute(
            select(Bill).where(Bill.game_id == game.id)
        ).scalar_one_or_none()
        mine = None
        if bill is not None and viewer_id is not None:
            mine = db.execute(
                select(BillRow).where(
                    BillRow.bill_id == bill.id, BillRow.account_id == viewer_id
                )
            ).scalar_one_or_none()
    if bill is None:
        return None
    return {
        "fee_total": bill.fee_total,
        "per_head": bill.per_head,
        "heads": bill.heads,
        "my_share": mine.amount if mine else None,
        "my_guest_count": mine.guest_count if mine else None,
    }


def entry_rows(db: Session, game_id: int) -> list[dict]:
    """正式名单按报名先后，候补按次序跟在后面（detail 全量）。账号一次 in 查齐
    （intents 同款防 N+1 手法；.get 对缺行回 None，与 db.get 同语义）。"""
    formal = (
        db.execute(
            select(Entry)
            .where(Entry.game_id == game_id, Entry.standing == "formal")
            .order_by(Entry.joined_at, Entry.id)
        )
        .scalars()
        .all()
    )
    waiting = (
        db.execute(
            select(Entry)
            .where(Entry.game_id == game_id, Entry.standing == "waitlist")
            .order_by(Entry.wait_seq)
        )
        .scalars()
        .all()
    )
    rows = (*formal, *waiting)
    accounts = {
        a.id: a
        for a in db.execute(
            select(Account).where(Account.id.in_({e.account_id for e in rows}))
        ).scalars()
    }
    return [
        {
            "account": person_view(accounts.get(e.account_id)),
            "bring": e.bring,
            "standing": e.standing,
            "wait_seq": e.wait_seq,
        }
        for e in rows
    ]


def dropin_rows(db: Session, game_id: int) -> list[dict]:
    """空降进场者（名册 dropin 标记的账号行），按进场先后。空降不报名不占
    formal 名额、也不进 entries——局页名单若只列报名行会把实到的人漏掉，
    战报名单与摊钱名单都算他一份，这里同口径带出。未开账局查无行 → 空。"""
    rows = (
        db.execute(
            select(LivePlayer)
            .where(
                LivePlayer.game_id == game_id,
                LivePlayer.dropin.is_(True),
                LivePlayer.account_id.is_not(None),
            )
            .order_by(LivePlayer.id)
        )
        .scalars()
        .all()
    )
    accounts = {
        a.id: a
        for a in db.execute(
            select(Account).where(Account.id.in_({r.account_id for r in rows}))
        ).scalars()
    }
    return [{"account": person_view(accounts.get(r.account_id))} for r in rows]


def my_block(
    db: Session,
    game: Game,
    viewer_id: int,
    batch: dict | None = None,
    now: datetime | None = None,
) -> dict:
    if batch is not None:
        entry = batch["my_entries"].get(game.id)
        invited = game.id in batch["invited"]
    else:
        entry = db.execute(
            select(Entry).where(Entry.game_id == game.id, Entry.account_id == viewer_id)
        ).scalar_one_or_none()
        invited = (
            db.execute(
                select(Invite.id).where(
                    Invite.game_id == game.id, Invite.invitee_id == viewer_id
                )
            ).first()
            is not None
        )
    is_org = game.organizer_id == viewer_id
    return {
        "is_organizer": is_org,
        "my_entry": (
            {
                "bring": entry.bring,
                "standing": entry.standing,
                "wait_seq": entry.wait_seq,
            }
            if entry
            else None
        ),
        "invited": invited,
        # 能力旗（闸旗同源）：组织者身份 × 写窗真值一次算定——前端显隐直读，不再拿
        # 派生 status 拼窗口（到点未散场的派生 done 曾把订场钮收走、补填钮错亮，
        # 2026-10-08 债清偿）。旗是读取刻的快照，过期由写端点的闸兜底
        "can_book": is_org and booking_window_error(game) is None,
        "can_fill_fee": is_org and fill_fee_error(game) is None,
        "can_lock": is_org and lock_window_error(game, now or clock.now()) is None,
    }
