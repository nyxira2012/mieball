"""game_views —— 局簿读视图：派生态与 game_view 组装（技术设计 §2.4，批3 自 games.py 拆出）。

GameBook 的读出口要把"局行 + 时刻 + 观看者"变成前端直接可用的定值形状（A4：画面不自算），
这里管两件事：
- 派生：存储 5 态 × 时刻 × 观看者 → 视图 7 态；pending 待处置只组织者可见（4.9），
  其他人按 terminated 出（masked）；灰字"当日"的锚（death_day）。
- 组装：game_view 全量字段——人头/剩坑/人均/forced 都在此算定值。
局簿写路径也用 derive 做窗口判断（游戏规则的"现在算什么态"只有这一份）。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import clock
from ..db.models import Account, Entry, Game, Invite
from .accounts import person_view

# 截止后照常可加到局结束（4.14）；done/terminated/cancelled/pending 不可加
JOINABLE_STATUSES = ("open", "locked", "live")


def derive(game: Game, now: datetime) -> str:
    """派生视图态：locked 随时刻翻 locked/live/done；
    pending 拖过开打 = 死局（待处置没有处置价值的时刻，僵尸出口由懒判定落库）。"""
    if game.state == "pending":
        return "pending" if now < game.start_at else "terminated"
    if game.state == "locked":
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


def game_view(
    db: Session,
    game: Game,
    *,
    viewer_id: int | None,
    heads: int,
    with_entries: bool = False,
) -> dict:
    """game_view 全量定值（技术设计 §2.1 字段表）；heads 由局簿唯一一把尺算好传入。"""
    now = clock.now()
    status = masked(game, viewer_id, now)
    view: dict[str, Any] = {
        "id": game.id,
        "name": game.name,
        "organizer": person_view(db.get(Account, game.organizer_id)),
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
        "courts": list(game.courts) if game.courts is not None else None,
        "fee_total": game.fee_total,
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
        "forced": game.manual_lock or bool(game.courts),
    }
    if with_entries:
        view["entries"] = entry_rows(db, game.id)
    if viewer_id is not None:
        view["my"] = my_block(db, game, viewer_id)
    return view


def entry_rows(db: Session, game_id: int) -> list[dict]:
    """正式名单按报名先后，候补按次序跟在后面（detail 全量）。"""
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
    return [
        {
            "account": person_view(db.get(Account, e.account_id)),
            "bring": e.bring,
            "standing": e.standing,
            "wait_seq": e.wait_seq,
        }
        for e in (*formal, *waiting)
    ]


def my_block(db: Session, game: Game, viewer_id: int) -> dict:
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
    return {
        "is_organizer": game.organizer_id == viewer_id,
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
    }
