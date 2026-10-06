"""LiveBook —— 现场总账深模块（docs/2.3）：开账、总账读视图、两级号并发防线。

批1 只落骨架（start/view + 两级号机制），记分/确认/散场等动作批2/3 逐批入住。
策略内聚在这里，路由只做参数搬运：
- 现场是"另一本账"：locked 局之上由 start 展开（正式球友一人一行 + 随行访客一行），
  散场后 games.ended_at 落库即封存，view 同一形状 = 只读回看（2.3 §4.10）。
- 考勤分权：arrive/left 时刻只有组织者与本人可见，其他人一律 null（2.3 裁决 Q2）。
- 两级号（附录 B1）：全场一个总号（任何现场写 +1）、每片自己的片号（该片记分类写 +1）；
  写入口带"出发时看到的号"，号旧即退回——同片并发才互斥，别片照常。
- 写串行：SQLite 无行锁，模块级锁罩住全部写动作（沿 GameBook 先例），check-then-act
  全锁内。
"""

from __future__ import annotations

import threading

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import clock, errors
from ..db.models import (
    Account,
    EloRating,
    Entry,
    Game,
    LiveCourt,
    LiveMatch,
    LivePlayer,
    LiveState,
)
from .accounts import person_view

# 开账起笔的 rules 快照默认值（镜像前端 startLive 起笔，2.2 批2 §4.1）：
# 双打 / 谁下挂 all 占位（推荐重算在前端）/ 按候场队序 / 连庄上限 3
_DEFAULT_RULES = {"doubles": True, "down": "all", "pairing": "queue", "streak_max": 3}
# 新人初始等级单一源（2.4 §8 定值；对齐前端 ui「Elo 默认 1500 起」）
RATING_INIT = 1500

# 现场写动作全串行：SQLite 无行锁，靠它保住"账只有一本"（2.3 附录 B1）
_write_lock = threading.Lock()


class LiveBook:
    def __init__(self, db: Session):
        self.db = db

    # ---- 开账（名册展开 + 总账头落库；幂等） ----

    def start(self, *, game_id: int, organizer_id: int) -> dict:
        """开账（2.2 §4.1 开场亮点的总账版）：名册行从正式报名展开——正式球友一人
        一行（首见建 EloRating 行 1500），bring N 展开成 N 行随行访客（挂担保人）；
        全员先记 absent、候场队空（报到驱动，check 端点批3）；total_seq 从 1 起。
        幂等：已有 LiveState 直接返视图（散场后再点也只回看，不重开）。"""
        with _write_lock:
            game = self.db.get(Game, game_id)
            if game is None:
                raise errors.game_not_found()
            if game.organizer_id != organizer_id:
                raise errors.organizer_only("只有组织者能开现场账")
            if self._state_or_none(game_id) is not None:
                return self.view(game_id=game_id, viewer_id=organizer_id)
            now = clock.now()
            self.db.add(
                LiveState(
                    game_id=game_id,
                    total_seq=1,
                    started_at=now,
                    **_DEFAULT_RULES,
                )
            )
            # 正式行按报名先后展开（joined_at, id 序沿 entry_rows 口径）
            formals = (
                self.db.execute(
                    select(Entry)
                    .where(Entry.game_id == game_id, Entry.standing == "formal")
                    .order_by(Entry.joined_at, Entry.id)
                )
                .scalars()
                .all()
            )
            for entry in formals:
                # person_view 的对外名单一源：在册出昵称、注销者按占位名定格（1.1 隐私口径）
                name = person_view(self.db.get(Account, entry.account_id))["nickname"]
                self.db.add(
                    LivePlayer(
                        game_id=game_id,
                        account_id=entry.account_id,
                        display_name=name,
                        check="absent",
                    )
                )
                self._ensure_elo(entry.account_id)
                for i in range(entry.bring):
                    self.db.add(
                        LivePlayer(
                            game_id=game_id,
                            account_id=None,
                            # 访客命名沿前端 startLive：担保人昵称前两字 + 编号
                            display_name=f"{name[:2]}的球友·{i + 1}",
                            guest=True,
                            guarantor_account_id=entry.account_id,
                            check="absent",
                        )
                    )
            self.db.commit()
        return self.view(game_id=game_id, viewer_id=organizer_id)

    # ---- 总账读视图（进行中与散场后同一形状：散场后 = 只读回看） ----

    def view(self, *, game_id: int, viewer_id: int | None) -> dict:
        """总账读（2.3 附录 A4：画面一个字不自算，全给定值）。考勤时刻按 viewer
        分权——组织者或本人见 arrive/left，其他人 null；带队 total_seq 与各片
        court_seq（契约总则 §4 预留的轮次/版本字段落地）。未开账 → 404。"""
        state = self._state_or_none(game_id)
        if state is None:
            raise errors.live_not_found()
        game = self.db.get(Game, game_id)
        is_organizer = viewer_id is not None and game.organizer_id == viewer_id
        players = (
            self.db.execute(
                select(LivePlayer)
                .where(LivePlayer.game_id == game_id)
                .order_by(LivePlayer.id)
            )
            .scalars()
            .all()
        )
        rows = [
            self._player_row(p, is_organizer=is_organizer, viewer_id=viewer_id)
            for p in players
        ]
        courts = (
            self.db.execute(
                select(LiveCourt)
                .where(LiveCourt.game_id == game_id)
                .order_by(LiveCourt.court_no)
            )
            .scalars()
            .all()
        )
        matches = (
            self.db.execute(
                select(LiveMatch)
                .where(LiveMatch.game_id == game_id)
                .order_by(LiveMatch.ended_at, LiveMatch.id)
            )
            .scalars()
            .all()
        )
        # 队列序定值给出（队首在前，候场外的行不排）；queue_pos 的持久化回写是写动作的事
        waiting = sorted(
            (r for r in rows if r["queue_pos"] is not None),
            key=lambda r: r["queue_pos"],
        )
        return {
            "game_id": game_id,
            "started_at": clock.iso(state.started_at),
            "ended": game.ended_at is not None,
            "ended_at": clock.iso(game.ended_at) if game.ended_at else None,
            "total_seq": state.total_seq,
            "round": state.round,
            "rules": {
                "scoring": game.scoring,  # 全场统一分制复用局列（2.3 裁决 Q1）
                "doubles": state.doubles,
                "down": state.down,
                "pairing": state.pairing,
                "streak_max": state.streak_max,
            },
            "players": rows,
            "queue": [r["id"] for r in waiting],
            "courts": [
                {
                    "court_no": c.court_no,
                    "status": c.status,
                    "seq": c.seq,
                    "score_a": c.sa,
                    "score_b": c.sb,
                    "last_winner_side": c.last_winner_side,
                    "court_seq": c.court_seq,
                    "pending_origin": c.pending_origin,
                }
                for c in courts
            ],
            "matches": [
                {
                    "court_no": m.court_no,
                    "seq": m.seq,
                    "winners": m.winners,
                    "losers": m.losers,
                    "score_a": m.sa,
                    "score_b": m.sb,
                    "winner_side": m.winner_side,
                    "ended_at": clock.iso(m.ended_at),
                    "elo_rows": m.elo_rows,
                }
                for m in matches
            ],
        }

    # ---- 内部：两级号机制（写动作批2/3 消费；全部在 _write_lock 内调用） ----

    def _state_or_none(self, game_id: int) -> LiveState | None:
        return self.db.execute(
            select(LiveState).where(LiveState.game_id == game_id)
        ).scalar_one_or_none()

    def _check_total(self, state: LiveState, base_total_seq: int) -> None:
        """写入口校验·总号（附录 B1）：带的号落后于总账，说明别人先改过全场——
        这笔退回（409 携最新视图），调用方在锁内先过这道再动账。"""
        if base_total_seq != state.total_seq:
            raise errors.live_stale_total()

    def _check_court(self, court: LiveCourt, base_court_seq: int) -> None:
        """写入口校验·片号：只拦该片（总号对、片号旧 = 同片并发），别片不受牵连。"""
        if base_court_seq != court.court_seq:
            raise errors.live_stale_court()

    def _bump_total(self, state: LiveState) -> None:
        state.total_seq += 1  # 任何现场写都往前进一

    def _bump_court(self, court: LiveCourt) -> None:
        court.court_seq += 1  # 该片记分类改动往前进一

    def _ensure_elo(self, account_id: int) -> None:
        """首见建行：积分账一人一行，起笔 1500（访客不建行，2.3 裁决访客不进账）。"""
        seen = self.db.execute(
            select(EloRating.id).where(EloRating.account_id == account_id)
        ).first()
        if seen is None:
            self.db.add(
                EloRating(
                    account_id=account_id,
                    rating=RATING_INIT,
                    play=0,
                    win=0,
                )
            )

    def _player_row(
        self, p: LivePlayer, *, is_organizer: bool, viewer_id: int | None
    ) -> dict:
        # 考勤分权（2.3 裁决 Q2）：早退迟到不展示给随便扫到的人
        visible = is_organizer or (viewer_id is not None and p.account_id == viewer_id)
        return {
            "id": p.id,
            "account_id": p.account_id,
            "name": p.display_name,
            "guest": p.guest,
            "guarantor_account_id": p.guarantor_account_id,
            "dropin": p.dropin,
            "check": p.check,
            "arrive_at": clock.iso(p.arrive_at) if visible and p.arrive_at else None,
            "left_at": clock.iso(p.left_at) if visible and p.left_at else None,
            "court_no": p.court_no,
            "court_side": p.court_side,
            "skip": p.skip,
            "fire": p.fire,
            "queue_pos": p.queue_pos,
        }
