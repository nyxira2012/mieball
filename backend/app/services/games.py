"""GameBook —— 球局域（docs/1.2）的局簿深模块：发局、找局列表、我的局、详情、报名/退局/改局。

策略全部内聚在这里，路由只做参数搬运：
- 懒判定（规格 4.8）：生死不靠定时器，任何入口先跑 _evaluate()——把过了截止还 open
  的局当场判完落库（GET 里落定写库是规格明定的设计，不是副作用违规）；
  pending 拖过开打的僵尸出口是读时派生（_derive），不落库。
- 派生态：库存 5 态、视图 7 态；locked 按 now 对 start/end 派生 locked/live/done；
  pending（待处置）只对组织者可见，其他人一律按 terminated 出。
- 可见性：public 人人；played=组织者∨同打过∨已涉及；invite_only=已涉及。
  链接即门票——detail 不做档位拦截（4.2），档位只管列表翻不翻得到。
- 打过（played_with）：两人同在一个 state='locked' 局的正式名单；候补/终止/撤局不算。
- 写串行：SQLite 无行锁，模块级锁罩住全部写动作（publish/join/quit/edit 与懒判定落库），
  check-then-act 全锁内——两人同秒抢最后坑不超线的地基（规格 B1）。
- 整行进出（不变承诺 5）：报名行=1+bring 原子占坑；装不下整行落候补、退出/放宽按
  seq 试转正、收紧按 joined_at 倒序降候补——全走 _promote_waitlist/_demote_to_cap。
"""

from __future__ import annotations

import json
import threading
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from ..core import clock, errors
from ..db.models import Account, Entry, Game, Invite
from .accounts import ANON_NAME, DEFAULT_CHIBI

CN_TZ = timezone(timedelta(hours=8))  # 接口进出的统一时区（契约§2：ISO 8601 +08:00）
VISIBILITIES = ("played", "public", "invite_only")
JOINABLE_STATUSES = ("open", "locked", "live")  # 截止后照常可加到局结束（4.14）

# 局簿写动作全串行：SQLite 无行锁，靠它保住"正式人头 ≤ max"的不变承诺（技术设计 §3）
_write_lock = threading.Lock()


class GameBook:
    def __init__(self, db: Session):
        self.db = db

    # ---- 发局（4.1：组织者自动占第一坑；截止发布即定死） ----

    def publish(
        self,
        *,
        organizer_id: int,
        name: str | None,
        start_at: datetime,
        end_at: datetime,
        deadline_at: datetime,
        venue_name: str,
        venue_address: str | None,
        min_players: int,
        max_players: int,
        visibility: str,
        scoring: int,
        rotation: str,
        score_rule: str,
    ) -> dict:
        if visibility not in VISIBILITIES:
            raise errors.visibility_invalid()
        if min_players > max_players:
            raise errors.range_invalid()
        start, end, deadline = _wall(start_at), _wall(end_at), _wall(deadline_at)
        now = clock.now()
        if not now < deadline < start:
            raise errors.deadline_inverted(
                "开打时间必须晚于截止时间"
                if deadline >= start
                else "截止时间必须晚于现在"
            )
        if start >= end:
            raise errors.deadline_inverted("结束时间必须晚于开打时间")
        with _write_lock:
            game = Game(
                organizer_id=organizer_id,
                name=name,
                start_at=start,
                end_at=end,
                deadline_at=deadline,
                venue_name=venue_name,
                venue_address=venue_address,
                min_players=min_players,
                max_players=max_players,
                visibility=visibility,
                scoring=scoring,
                rotation=rotation,
                score_rule=score_rule,
                state="open",
                created_at=now,
            )
            self.db.add(game)
            self.db.flush()  # autoflush=False：显式 flush 拿 game.id 给报名行用
            self.db.add(
                Entry(
                    game_id=game.id,
                    account_id=organizer_id,
                    bring=0,
                    standing="formal",
                    joined_at=now,
                )
            )
            self.db.commit()
        return self.detail(game_id=game.id, viewer_id=organizer_id)

    # ---- 找局打列表（4.2：三档可见 + 懒判定；排除 terminated/cancelled/pending） ----

    def list_for(self, *, viewer_id: int | None) -> list[dict]:
        self._evaluate()
        now = clock.now()
        games = self.db.execute(select(Game).order_by(Game.id.desc())).scalars().all()
        entry_ids, invite_ids = self._viewer_game_ids(viewer_id)
        out = []
        for game in games:
            if _masked(game, viewer_id, now) not in ("open", "locked", "live", "done"):
                continue
            if game.visibility == "public":
                visible = True
            elif viewer_id is None:
                visible = False  # 匿名只能翻到 public；played/invite_only 靠登录身份认
            else:
                involved = (
                    game.organizer_id == viewer_id
                    or game.id in entry_ids
                    or game.id in invite_ids
                )
                visible = involved or (
                    game.visibility == "played"
                    and self.played_with(
                        account_a=game.organizer_id, account_b=viewer_id
                    )
                )
            if visible:
                out.append(self._view(game, viewer_id=viewer_id))
        return out

    # ---- 我的局（组织者含未成局区/恢复窗口；参加者含当日灰字；被邀未加入也挂） ----

    def mine(self, *, account_id: int) -> list[dict]:
        self._evaluate()
        now = clock.now()
        entry_ids, invite_ids = self._viewer_game_ids(account_id)
        games = (
            self.db.execute(
                select(Game)
                .where(
                    or_(
                        Game.organizer_id == account_id,
                        Game.id.in_(entry_ids | invite_ids),
                    )
                )
                .order_by(Game.id.desc())
            )
            .scalars()
            .all()
        )
        out = []
        for game in games:
            status = _masked(game, account_id, now)
            if game.organizer_id == account_id:
                # 组织者：在办局全看 + pending 未成局区；terminated 只在恢复窗口（开打前）内；
                # cancelled 永不回来（撤局不留痕，4.10）
                keep = status != "cancelled" and not (
                    status == "terminated" and now >= game.start_at
                )
            elif game.id in entry_ids:
                # 参加者：在办局 + 终止/撤局当日灰字（pending 按 terminated 对待，次日收走，4.8）
                keep = status in ("open", "locked", "live", "done") or (
                    status in ("terminated", "cancelled")
                    and _death_day(game) == now.date()
                )
            else:
                # 被邀未加入：局还在进行中才挂"我的局"（4.12：放着不动直到截止/被撤/打完）
                keep = status in JOINABLE_STATUSES
            if keep:
                out.append(self._view(game, viewer_id=account_id))
        return out

    # ---- 详情（链接即门票：匿名可看、档位不拦；终态照常 200 带状态） ----

    def detail(self, *, game_id: int, viewer_id: int | None) -> dict:
        self._evaluate()
        game = self.db.get(Game, game_id)
        if game is None:
            raise errors.game_not_found()
        return self._view(game, viewer_id=viewer_id, with_entries=True)

    # ---- 报名（4.3/4.14：整行进出、满员落候补、截止后照常可加、重复提交幂等） ----

    def join(self, *, game_id: int, account_id: int, bring: int) -> dict:
        self._evaluate()  # 截止过期的局先落定：终止 → join_closed，锁定 → 照常可加
        with _write_lock:
            game = self.db.get(Game, game_id)
            if game is None:
                raise errors.game_not_found()
            existing = self.db.execute(
                select(Entry).where(
                    Entry.game_id == game_id, Entry.account_id == account_id
                )
            ).scalar_one_or_none()
            if existing is not None:
                # 幂等（B1）：已有本账号行——忽略新 bring、不重复占坑，组织者再 join 同此
                return self._view(game, viewer_id=account_id, with_entries=True)
            if _derive(game, clock.now()) not in JOINABLE_STATUSES:
                raise errors.join_closed()  # done/terminated/cancelled/pending 不可加
            if not 0 <= bring <= 3:
                raise errors.bring_limit()
            row = Entry(
                game_id=game_id,
                account_id=account_id,
                bring=bring,
                standing="formal",
                joined_at=clock.now(),
            )
            self.db.add(row)
            try:
                self.db.flush()  # autoflush=False：显式 flush 让 heads 计入本行
            except IntegrityError:
                # 写锁已串行化本进程写动作，撞 Unique(game_id,account_id) 只剩数据库
                # 兜底的极端竞态（技术设计 §3）——回滚重查，按幂等当没事
                self.db.rollback()
                game = self.db.get(Game, game_id)
                return self._view(game, viewer_id=account_id, with_entries=True)
            if self._heads(game_id) > game.max_players:
                # 整行进出：formal 装不下这一整行 → 候补，wait_seq 追加递增（4.3）
                row.standing = "waitlist"
                row.wait_seq = self._next_wait_seq(game_id)
            self.db.commit()
            return self._view(game, viewer_id=account_id, with_entries=True)

    # ---- 退局（4.4：截止锁的是"防鸽退出"；改约解锁窗例外；带的人整行跟着退） ----

    def quit(self, *, game_id: int, account_id: int) -> dict:
        self._evaluate()
        with _write_lock:
            game = self.db.get(Game, game_id)
            if game is None:
                raise errors.game_not_found()
            entry = self.db.execute(
                select(Entry).where(
                    Entry.game_id == game_id, Entry.account_id == account_id
                )
            ).scalar_one_or_none()
            if entry is None:
                return {"ok": True}  # 幂等（B1）：没报名/已退出，当没事
            if game.organizer_id == account_id:
                raise errors.not_organizer("组织者不能退出，只能撤局")
            status = _derive(game, clock.now())
            # 窗口：报名中随便退；锁定局只在改约解锁窗内可退（4.6）；
            # locked 未解锁/live/done/terminated/cancelled/pending 一律拦
            unlockable = status == "locked" and game.unlocked_at is not None
            if status != "open" and not unlockable:
                raise errors.game_locked()
            self.db.delete(entry)
            self.db.flush()  # 让 promote 的人头计算看到删掉的行
            self._promote_waitlist(game)  # 候补按 seq 递补（4.4：名额立刻释放）
            self.db.commit()
        return {"ok": True}

    # ---- 改局（4.6：开打前、只有组织者；截止不在参数表=不可改，不变承诺 3） ----

    def edit(
        self,
        *,
        game_id: int,
        organizer_id: int,
        name: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        venue_name: str | None = None,
        venue_address: str | None = None,
        min_players: int | None = None,
        max_players: int | None = None,
        visibility: str | None = None,
        scoring: int | None = None,
        rotation: str | None = None,
        score_rule: str | None = None,
    ) -> dict:
        self._evaluate()
        with _write_lock:
            game = self.db.get(Game, game_id)
            if game is None:
                raise errors.game_not_found()
            if game.organizer_id != organizer_id:
                raise errors.not_organizer()
            now = clock.now()
            status = _derive(game, now)
            if status not in ("open", "locked"):
                raise errors.game_not_open()  # live/done/pending/terminated/cancelled
            # None 参沿用原值；合并出"这次编辑后的完整新值"再统一判（判不许看旧值）
            new = {
                "name": name if name is not None else game.name,
                "start_at": _wall(start_at) if start_at is not None else game.start_at,
                "end_at": _wall(end_at) if end_at is not None else game.end_at,
                "venue_name": (
                    venue_name if venue_name is not None else game.venue_name
                ),
                "venue_address": (
                    venue_address if venue_address is not None else game.venue_address
                ),
                "min_players": (
                    min_players if min_players is not None else game.min_players
                ),
                "max_players": (
                    max_players if max_players is not None else game.max_players
                ),
                "visibility": (
                    visibility if visibility is not None else game.visibility
                ),
                "scoring": scoring if scoring is not None else game.scoring,
                "rotation": rotation if rotation is not None else game.rotation,
                "score_rule": (
                    score_rule if score_rule is not None else game.score_rule
                ),
            }
            if new["start_at"] >= new["end_at"]:
                raise errors.deadline_inverted("结束时间必须晚于开打时间")
            if game.deadline_at >= new["start_at"]:  # deadline 永远取原值
                raise errors.deadline_inverted("开打时间必须晚于截止时间")
            if new["min_players"] > new["max_players"]:
                raise errors.range_invalid()
            if new["visibility"] not in VISIBILITIES:
                raise errors.visibility_invalid()
            # 改约解锁（4.6）：截止后的锁定局动了时间/地点 → 置解锁标记（参加者可退、
            # 候补照常递补、到开打重新锁死）；报名中改这些不置位
            schedule_changed = any(
                new[key] != getattr(game, key)
                for key in ("start_at", "end_at", "venue_name", "venue_address")
            )
            old_max = game.max_players
            for key, value in new.items():
                setattr(game, key, value)
            if status == "locked" and schedule_changed:
                game.unlocked_at = now
            self.db.flush()
            # 上限调整（不变承诺 1：正式人头 ≤ max 全路径）；改 visibility 不赶人
            if new["max_players"] < old_max:
                self._demote_to_cap(game)
            elif new["max_players"] > old_max:
                self._promote_waitlist(game)
            self.db.commit()
            return self._view(game, viewer_id=organizer_id, with_entries=True)

    # ---- 打过（4.2 唯一算法；users 接缝 same_game 同源） ----

    def played_with(self, *, account_a: int, account_b: int) -> bool:
        """两人同在一个已成局（state='locked'，含之后的进行中/已结束）的正式名单。"""
        ea, eb = aliased(Entry), aliased(Entry)
        hits = self.db.execute(
            select(func.count())
            .select_from(ea)
            .join(eb, and_(eb.game_id == ea.game_id))
            .join(Game, Game.id == ea.game_id)
            .where(
                ea.account_id == account_a,
                eb.account_id == account_b,
                ea.standing == "formal",
                eb.standing == "formal",
                Game.state == "locked",
            )
        ).scalar_one()
        return hits > 0

    # ---- 内部 ----

    def _viewer_game_ids(self, viewer_id: int | None) -> tuple[set[int], set[int]]:
        """该账号 (报过名的局 id 集, 被邀的局 id 集)；匿名两集皆空。"""
        if viewer_id is None:
            return set(), set()
        entries = self.db.execute(
            select(Entry.game_id).where(Entry.account_id == viewer_id)
        ).scalars()
        invites = self.db.execute(
            select(Invite.game_id).where(Invite.invitee_id == viewer_id)
        ).scalars()
        return set(entries), set(invites)

    def _evaluate(self) -> None:
        """懒判定（4.8）：入口先跑。过期 open 局当场判生死落库，谁先打开谁触发；
        必打（手动锁或已订场）人数不足也成局。"""
        with _write_lock:
            expired = (
                self.db.execute(
                    select(Game).where(
                        Game.state == "open", Game.deadline_at <= clock.now()
                    )
                )
                .scalars()
                .all()
            )
            if not expired:
                return
            for game in expired:
                forced = game.manual_lock or bool(game.courts)
                game.state = (
                    "locked"
                    if forced or self._heads(game.id) >= game.min_players
                    else "terminated"
                )
            self.db.commit()

    def _heads(self, game_id: int) -> int:
        """正式名单人头 = Σ(1+bring)——全篇数人数的唯一一把尺（规格 §4 开头）。"""
        return int(
            self.db.execute(
                select(func.coalesce(func.sum(1 + Entry.bring), 0)).where(
                    Entry.game_id == game_id, Entry.standing == "formal"
                )
            ).scalar_one()
        )

    def _next_wait_seq(self, game_id: int) -> int:
        """候补队尾的下一个号（wait_seq 全局追加递增）。"""
        return (
            int(
                self.db.execute(
                    select(func.coalesce(func.max(Entry.wait_seq), 0)).where(
                        Entry.game_id == game_id
                    )
                ).scalar_one()
            )
            + 1
        )

    def _promote_waitlist(self, game: Game) -> None:
        """候补按 seq 逐行试转正（4.3/4.6 退出与放宽上限共用）：整行算（1+bring），
        装得下才转、装不下的顺延下一位（spec 4.3「谁装得下谁先转」）、不拆行。"""
        heads = self._heads(game.id)
        waiting = (
            self.db.execute(
                select(Entry)
                .where(Entry.game_id == game.id, Entry.standing == "waitlist")
                .order_by(Entry.wait_seq)
            )
            .scalars()
            .all()
        )
        for row in waiting:
            size = 1 + row.bring
            if heads + size <= game.max_players:
                row.standing = "formal"
                row.wait_seq = None
                heads += size

    def _demote_to_cap(self, game: Game) -> None:
        """上限改小（4.6）：formal 按 joined_at 倒序逐行降候补到达标——最后报的先降、
        组织者行永不被转（不变承诺 2）；被降行按 joined_at 升序接到候补尾（保持报名
        先后公平）。"""
        rows = (
            self.db.execute(
                select(Entry)
                .where(Entry.game_id == game.id, Entry.standing == "formal")
                .order_by(Entry.joined_at.desc(), Entry.id.desc())
            )
            .scalars()
            .all()
        )
        demoted: list[Entry] = []
        heads = self._heads(game.id)
        for row in rows:
            if heads <= game.max_players:
                break
            if row.account_id == game.organizer_id:
                continue
            row.standing = "waitlist"
            demoted.append(row)
            heads -= 1 + row.bring
        seq = self._next_wait_seq(game.id)
        for row in reversed(demoted):  # 收集时新→旧，反转成报名先后（旧→新）接队尾
            row.wait_seq = seq
            seq += 1

    def _view(
        self, game: Game, *, viewer_id: int | None, with_entries: bool = False
    ) -> dict:
        now = clock.now()
        status = _masked(game, viewer_id, now)
        heads = self._heads(game.id)
        view: dict[str, Any] = {
            "id": game.id,
            "name": game.name,
            "organizer": _person(self._account(game.organizer_id)),
            "start_at": _iso(game.start_at),
            "end_at": _iso(game.end_at),
            "deadline_at": _iso(game.deadline_at),
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
            view["entries"] = self._entry_rows(game.id)
        if viewer_id is not None:
            view["my"] = self._my_block(game, viewer_id)
        return view

    def _entry_rows(self, game_id: int) -> list[dict]:
        """正式名单按报名先后，候补按次序跟在后面（detail 全量）。"""
        formal = (
            self.db.execute(
                select(Entry)
                .where(Entry.game_id == game_id, Entry.standing == "formal")
                .order_by(Entry.joined_at, Entry.id)
            )
            .scalars()
            .all()
        )
        waiting = (
            self.db.execute(
                select(Entry)
                .where(Entry.game_id == game_id, Entry.standing == "waitlist")
                .order_by(Entry.wait_seq)
            )
            .scalars()
            .all()
        )
        return [
            {
                "account": _person(self._account(e.account_id)),
                "bring": e.bring,
                "standing": e.standing,
                "wait_seq": e.wait_seq,
            }
            for e in (*formal, *waiting)
        ]

    def _my_block(self, game: Game, viewer_id: int) -> dict:
        entry = self.db.execute(
            select(Entry).where(Entry.game_id == game.id, Entry.account_id == viewer_id)
        ).scalar_one_or_none()
        invited = (
            self.db.execute(
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

    def _account(self, account_id: int) -> Account | None:
        return self.db.get(Account, account_id)


def _wall(dt: datetime) -> datetime:
    """aware 入参按东八区取墙钟存 naive；naive 直接当北京墙钟（技术设计 §3 时区口径）。"""
    return dt.astimezone(CN_TZ).replace(tzinfo=None) if dt.tzinfo is not None else dt


def _iso(dt: datetime) -> str:
    return dt.replace(tzinfo=CN_TZ).isoformat()


def _derive(game: Game, now: datetime) -> str:
    """派生视图态（技术设计 §2.4）：locked 随时刻翻 locked/live/done；
    pending 拖过开打 = 死局（待处置没有处置价值的时刻）。"""
    if game.state == "pending":
        return "pending" if now < game.start_at else "terminated"
    if game.state == "locked":
        if now < game.start_at:
            return "locked"
        return "live" if now < game.end_at else "done"
    return game.state  # open（进 _evaluate 后必未过期）/ terminated / cancelled 原样


def _masked(game: Game, viewer_id: int | None, now: datetime) -> str:
    status = _derive(game, now)
    # 待处置只组织者可见（4.9），其他人按已终止出
    return (
        "terminated"
        if status == "pending" and viewer_id != game.organizer_id
        else status
    )


def _death_day(game: Game) -> date:
    """灰字"当日"的锚：terminated/pending 死于截止（懒判定由截止驱动）；
    cancelled 的精确撤局时刻无处记——批3 cancel 实现时补判。"""
    return game.deadline_at.date()


def _person(account: Account | None) -> dict:
    """名单里的一人：昵称+小人（1.1 隐私口径）；已注销 → 占位形象（C3）。"""
    if account is None or account.status != "active":
        return {
            "id": account.id if account else 0,
            "nickname": ANON_NAME,
            "chibi": dict(DEFAULT_CHIBI),
        }
    return {
        "id": account.id,
        "nickname": account.nickname,
        "chibi": json.loads(account.chibi),
    }
