"""GameBook —— 球局域（docs/1.2）的局簿深模块：发局、找局列表、我的局、详情、报名/退局/
改局、组织者工具箱（锁必打/订场/撤局/恢复/邀请）。

策略全部内聚在这里，路由只做参数搬运：
- 懒判定（规格 4.8）：生死不靠定时器，任何入口先跑 _evaluate()——把过了截止还 open
  的局当场判完落库（GET 里落定写库是规格明定的设计，不是副作用违规）；必打（手动锁
  或已订场）人数不足也成局。pending 拖过开打的僵尸出口同在此落 terminated（批3 收口）。
- 派生态：库存 5 态、视图 7 态，派生与 game_view 组装在 game_views（批3 拆出，
  写路径的窗口判断也用它）。
- 可见性：public 人人；played=组织者∨同打过∨已涉及；invite_only=已涉及。
  链接即门票——detail 不做档位拦截（4.2），档位只管列表翻不翻得到。
- 打过（played_with）：两人同在一个 state='locked' 局的正式名单；候补/终止/撤局不算。
- 写串行：SQLite 无行锁，模块级锁罩住全部写动作（含懒判定落库），check-then-act
  全锁内——两人同秒抢最后坑不超线的地基（规格 B1）。
- 整行进出（不变承诺 5）：报名行=1+bring 原子占坑；装不下整行落候补、退出/放宽按
  seq 试转正、收紧按 joined_at 倒序降候补——全走 _promote_waitlist/_demote_to_cap。
- 两簿唯一来往（技术设计 §3）：invite 写 invites 行 + 给有意向者置已邀标记；
  意向簿不反向碰局。
"""

from __future__ import annotations

import threading
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from ..core import clock, errors
from ..db.models import Account, Bill, BillRow, Entry, Game, Intent, Invite
from .game_views import (
    JOINABLE_STATUSES,
    TOOLBOX_STATUSES,
    booking_window_error,
    death_day,
    derive,
    game_view,
    lock_window_error,
    masked,
)
from .live import LiveBook
from .playlog import matches_count, played_game_ids

VISIBILITIES = ("played", "public", "invite_only")
# 工具箱受理窗口 TOOLBOX_STATUSES 已随写窗谓词迁 game_views（闸旗同源，
# 2026-10-08 债清偿）——lock 走 lock_window_error，cancel 仍直用三态判据

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
        if min_players < 1 or max_players < 1:
            raise errors.range_invalid("最少和最多人数都要至少 1 人")
        if min_players > max_players:
            raise errors.range_invalid()
        start, end, deadline = (
            clock.wall(start_at),
            clock.wall(end_at),
            clock.wall(deadline_at),
        )
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
        mates = self.played_mates(
            viewer_id
        )  # played 档可见性一次判齐（免逐局联表 COUNT）
        batch = self._list_batch(games, viewer_id)
        out = []
        for game in games:
            if masked(game, viewer_id, now) not in ("open", "locked", "live", "done"):
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
                    game.visibility == "played" and game.organizer_id in mates
                )
            if visible:
                out.append(self._view(game, viewer_id=viewer_id, batch=batch))
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
        batch = self._list_batch(games, account_id)
        out = []
        for game in games:
            status = masked(game, account_id, now)
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
                    and death_day(game) == now.date()
                )
            else:
                # 被邀未加入：局还在进行中才挂"我的局"（4.12：放着不动直到截止/被撤/打完）
                keep = status in JOINABLE_STATUSES
            if keep:
                out.append(self._view(game, viewer_id=account_id, batch=batch))
        return out

    # ---- 打球记录（2.6 §4.4）：名单三笔规矩另立一把尺，与 mine() 的「我的局」语义无涉 ----

    def playlog(self, *, account_id: int) -> dict:
        """打球记录（附录 A4：名单后端算好给，页面不自判）：行同 mine() 同款
        （with_entries=False），按散场时刻倒序（同刻 id desc 兜稳定序）；
        matches_count=累计上场对局数，与列表行数解耦（缺席照摊进列表、场数不加）。"""
        self._evaluate()
        ids = played_game_ids(self.db, account_id)
        games = (
            self.db.execute(
                select(Game)
                .where(Game.id.in_(ids))
                .order_by(Game.ended_at.desc(), Game.id.desc())
            )
            .scalars()
            .all()
        )
        batch = self._list_batch(games, account_id)
        return {
            "games": [
                self._view(game, viewer_id=account_id, batch=batch) for game in games
            ],
            "matches_count": matches_count(self.db, account_id),
        }

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
            entry = self._entry_row(game_id, account_id)
            if entry is None:
                if derive(game, clock.now()) not in JOINABLE_STATUSES:
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
                    # 兜底的极端竞态（技术设计 §3）——回滚重查，按幂等（B1）当没事
                    self.db.rollback()
                    game = self.db.get(Game, game_id)
                    entry = self._entry_row(game_id, account_id)
                else:
                    if self._heads(game_id) > game.max_players:
                        # 整行进出：formal 装不下这一整行 → 候补，wait_seq 追加递增（4.3）
                        row.standing = "waitlist"
                        row.wait_seq = self._next_wait_seq(game_id)
                    self.db.commit()
                    entry = row
            # 开账后 formal 落定即补进名册：幂等重放/竞态重查/新写三个来路同走这
            # 一口（新出口漏不了桥）；没开账/已有本人行 absorb_join 自判不动
            if entry is not None and entry.standing == "formal":
                self._absorb_live(game_id, account_id, entry.bring)
            return self._view(game, viewer_id=account_id, with_entries=True)

    def _absorb_live(self, game_id: int, account_id: int, bring: int) -> None:
        """join → 现场总账的桥（2026-10-10 修复批）：语义、锁序与自判不动条款见
        LiveBook.absorb_join；formal 与否由调用方把关。"""
        LiveBook(self.db).absorb_join(
            game_id=game_id, account_id=account_id, bring=bring
        )

    # ---- 退局（4.4：截止锁的是"防鸽退出"；改约解锁窗例外；带的人整行跟着退） ----

    def _entry_row(self, game_id: int, account_id: int) -> Entry | None:
        """本账号在本局的报名行（join 幂等/竞态重查与 quit 共用的取数口）"""
        return self.db.execute(
            select(Entry).where(
                Entry.game_id == game_id, Entry.account_id == account_id
            )
        ).scalar_one_or_none()

    def quit(self, *, game_id: int, account_id: int) -> dict:
        self._evaluate()
        with _write_lock:
            game = self.db.get(Game, game_id)
            if game is None:
                raise errors.game_not_found()
            entry = self._entry_row(game_id, account_id)
            if entry is None:
                return {"ok": True}  # 幂等（B1）：没报名/已退出，当没事
            if game.organizer_id == account_id:
                raise errors.not_organizer("组织者不能退出，只能撤局")
            status = derive(game, clock.now())
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
            game = self._owned(game_id, organizer_id)
            now = clock.now()
            status = derive(game, now)
            if status not in ("open", "locked"):
                raise errors.game_not_open()  # live/done/pending/terminated/cancelled
            # None 参沿用原值；合并出"这次编辑后的完整新值"再统一判（判不许看旧值）
            new = {
                "name": name if name is not None else game.name,
                "start_at": clock.wall(start_at)
                if start_at is not None
                else game.start_at,
                "end_at": clock.wall(end_at) if end_at is not None else game.end_at,
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
            if new["min_players"] < 1 or new["max_players"] < 1:
                raise errors.range_invalid("最少和最多人数都要至少 1 人")
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

    # ---- 组织者工具箱（4.7 锁必打 / 4.10 撤局 / 4.9 恢复，窗口开打前；
    #      4.7 订场/清空窗口到散场确认前——1.3 §4.5 修订①） ----

    def lock(self, *, game_id: int, organizer_id: int) -> dict:
        """空锁必打（4.7）：不订场也锁"人数不足照开"；一锁不撤（清订场不松、无解锁）。
        已锁再锁当没事（幂等）；pending 锁了即处置完、回正常局。窗口真值收在
        game_views.lock_window_error（闸旗同源，my 块 can_lock 同一份）。"""
        self._evaluate()
        with _write_lock:
            game = self._owned(game_id, organizer_id)
            err = lock_window_error(game, clock.now())
            if err is not None:
                raise err
            game.manual_lock = True
            if game.state == "pending":
                game.state = "locked"  # 待处置的锁必打出口（4.9）
            self.db.commit()
            return self._view(game, viewer_id=organizer_id, with_entries=True)

    def book(
        self, *, game_id: int, organizer_id: int, courts: list[str], fee_total: int
    ) -> dict:
        """订场登记（4.7 / 1.3 §4.5 修订①）：订场发生在 app 外，这里只登记结果——
        最后写赢、可反复改；填了场地号即必打、费用落定（人均按当前人数摊，最少保底
        作废）。名单锁只锁人，截止后（locked）仍可改——临到场场馆换号很常见；开打后
        一样改（加一片场、中场买球买水的钱都往总价里加），窗口到散场确认为止。"""
        if not courts:
            raise errors.booking_invalid("至少填一个场地号")
        if fee_total < 0:
            raise errors.booking_invalid("总价不能是负数，免费的填 0")
        self._evaluate()
        with _write_lock:
            game = self._owned(game_id, organizer_id)
            self._check_booking_window(game)
            game.courts = list(courts)
            game.fee_total = fee_total
            if game.state == "pending":
                game.state = "locked"  # 订场登记同为待处置出口（技术设计 §2.4）
            self.db.commit()
            return self._view(game, viewer_id=organizer_id, with_entries=True)

    def clear_booking(self, *, game_id: int, organizer_id: int) -> dict:
        """清空订场登记（4.7）：费用回未定、截止照常判人数；手动锁一上不撤。幂等；
        窗口同 book——散场确认前随时可清（清空即回未定）。"""
        self._evaluate()
        with _write_lock:
            game = self._owned(game_id, organizer_id)
            self._check_booking_window(game)
            game.courts = None
            game.fee_total = None
            self.db.commit()
            return self._view(game, viewer_id=organizer_id, with_entries=True)

    def cancel(self, *, game_id: int, organizer_id: int) -> dict:
        """撤局（4.10）：开打前、想清楚了的明确动作——组织者"我的局"不留痕；
        底账留档不删（不变承诺 8），撤局时刻记 cancelled_at（灰字"当日"的锚）。"""
        self._evaluate()
        with _write_lock:
            game = self._owned(game_id, organizer_id)
            if derive(game, clock.now()) not in TOOLBOX_STATUSES:
                raise errors.game_not_open()  # 开打后是现场的事；terminated 走恢复
            game.state = "cancelled"
            game.cancelled_at = clock.now()
            self.db.commit()
        return {"ok": True}

    def restore(self, *, game_id: int, organizer_id: int) -> dict:
        """救回未成局（4.9）：开打前的 terminated → pending 待处置——只组织者可见、
        不再触发截止判定（球友打开也不会把它判死），锁必打/订场/撤局后才回正常列表。"""
        self._evaluate()
        with _write_lock:
            game = self._owned(game_id, organizer_id)
            now = clock.now()
            if derive(game, now) == "pending":
                return self._view(game, viewer_id=organizer_id, with_entries=True)
            if game.state != "terminated" or now >= game.start_at:
                raise errors.game_not_open()  # 恢复窗口 = 开打时刻前（裁决）
            game.state = "pending"
            self.db.commit()
            return self._view(game, viewer_id=organizer_id, with_entries=True)

    def invite(self, *, game_id: int, organizer_id: int, invitee_id: int) -> dict:
        """邀请（4.11/4.12）：局直接出现在对方"我的局"，被邀不占坑；重复邀当没事
        （不刷新、不重复记）。两簿唯一来往：invites 行永远记；已邀标记只给
        有意向的 invitee 置位（技术设计 §3）。"""
        self._evaluate()
        with _write_lock:
            game = self._owned(game_id, organizer_id)
            if derive(game, clock.now()) not in JOINABLE_STATUSES:
                raise errors.game_not_open()  # 终态/待处置的局不发邀约
            seen = self.db.execute(
                select(Invite.id).where(
                    Invite.game_id == game_id, Invite.invitee_id == invitee_id
                )
            ).first()
            if seen is None:
                self.db.add(
                    Invite(
                        game_id=game_id,
                        invitee_id=invitee_id,
                        created_at=clock.now(),
                    )
                )
            intent = self.db.execute(
                select(Intent).where(Intent.account_id == invitee_id)
            ).scalar_one_or_none()
            if intent is not None and intent.invited_at is None:
                intent.invited_at = clock.now()  # 已邀不刷新（幂等）
            self.db.commit()
        return {"ok": True}

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

    def played_mates(self, viewer_id: int | None) -> set[int]:
        """viewer 的共打账号集（played_with 的批量版）：与 viewer 同在一个已成局
        （state='locked'，含之后的进行中/已结束）正式名单的其他人——列表/意向页
        逐条判打过会叠成 N+1，一次拉齐逐条对表。"""
        if viewer_id is None:
            return set()
        mine = (
            select(Entry.game_id).where(
                Entry.account_id == viewer_id, Entry.standing == "formal"
            )
        ).scalar_subquery()
        rows = self.db.execute(
            select(Entry.account_id)
            .join(Game, Game.id == Entry.game_id)
            .where(
                Entry.game_id.in_(mine),
                Entry.standing == "formal",
                Game.state == "locked",
            )
        ).scalars()
        return {a for a in rows if a != viewer_id}

    # ---- 内部 ----

    def _owned(self, game_id: int, organizer_id: int) -> Game:
        """组织者守卫：查无 → 404，非本人局 → 403（改局与工具箱动作共用）。"""
        game = self.db.get(Game, game_id)
        if game is None:
            raise errors.game_not_found()
        if game.organizer_id != organizer_id:
            raise errors.not_organizer()
        return game

    def _check_booking_window(self, game: Game) -> None:
        """订场/清空的改价窗口（1.3 §4.5 修订①）——真值收在 game_views.
        booking_window_error（闸旗同源）：本闸与 my 块 can_book 同一份代码，
        窗口规则改动只改那一处，前后端自动同步（2026-10-08 债清偿，开发日志）。"""
        err = booking_window_error(game)
        if err is not None:
            raise err

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
        必打（手动锁或已订场）人数不足也成局。pending 拖过开打 = 僵尸出口，落 terminated。"""
        with _write_lock:
            now = clock.now()
            expired = (
                self.db.execute(
                    select(Game).where(Game.state == "open", Game.deadline_at <= now)
                )
                .scalars()
                .all()
            )
            for game in expired:
                forced = game.manual_lock or bool(game.courts)
                if forced or self._heads(game.id) >= game.min_players:
                    game.state = "locked"
                else:
                    game.state = "terminated"
                    # 死于截止那一刻：判定只是迟到，不改死期（灰字"当日"锚，技术设计 §3）
                    game.terminated_at = game.deadline_at
            zombies = (
                self.db.execute(
                    select(Game).where(Game.state == "pending", Game.start_at <= now)
                )
                .scalars()
                .all()
            )
            for game in zombies:
                game.state = "terminated"
                game.terminated_at = game.start_at  # 死于开打时刻
            if expired or zombies:
                self.db.commit()

    def _list_batch(self, games: list[Game], viewer_id: int | None) -> dict:
        """列表读的批量预取（找局打/我的局一页几十局 × 逐局五六查会叠成 N+1）：
        人头（GROUP BY 一把尺同口径）/账本/我的账行/报名与邀请/组织者账号一次查齐，
        game_view 逐字段消费；单局路径不传 batch 照旧现查。"""
        ids = [g.id for g in games]
        batch: dict = {
            "heads": {},
            "bills": {},
            "my_bill_rows": {},
            "my_entries": {},
            "invited": set(),
            "accounts": {},
        }
        if not ids:
            return batch
        batch["heads"] = dict(
            self.db.execute(
                select(Entry.game_id, func.coalesce(func.sum(1 + Entry.bring), 0))
                .where(Entry.game_id.in_(ids), Entry.standing == "formal")
                .group_by(Entry.game_id)
            ).all()
        )
        bills = (
            self.db.execute(select(Bill).where(Bill.game_id.in_(ids))).scalars().all()
        )
        bill_game = {b.id: b.game_id for b in bills}
        for bill in bills:
            batch["bills"][bill.game_id] = bill
        if viewer_id is not None:
            for r in self.db.execute(
                select(BillRow).where(
                    BillRow.account_id == viewer_id,
                    BillRow.bill_id.in_(bill_game),
                )
            ).scalars():
                batch["my_bill_rows"][bill_game[r.bill_id]] = r
            for e in self.db.execute(
                select(Entry).where(
                    Entry.account_id == viewer_id, Entry.game_id.in_(ids)
                )
            ).scalars():
                batch["my_entries"][e.game_id] = e
            batch["invited"] = set(
                self.db.execute(
                    select(Invite.game_id).where(
                        Invite.invitee_id == viewer_id, Invite.game_id.in_(ids)
                    )
                ).scalars()
            )
        batch["accounts"] = {
            a.id: a
            for a in self.db.execute(
                select(Account).where(Account.id.in_({g.organizer_id for g in games}))
            ).scalars()
        }
        return batch

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
        self,
        game: Game,
        *,
        viewer_id: int | None,
        with_entries: bool = False,
        batch: dict | None = None,
    ) -> dict:
        """读视图组装在 game_views（批3 拆出）；局簿只补自己的一把尺（人头）——
        列表路径由 _list_batch 预取递入，单局路径现查。"""
        heads = batch["heads"].get(game.id) if batch is not None else None
        if heads is None:
            heads = self._heads(game.id)
        return game_view(
            self.db,
            game,
            viewer_id=viewer_id,
            heads=int(heads),
            with_entries=with_entries,
            batch=batch,
        )
