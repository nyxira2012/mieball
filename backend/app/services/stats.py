"""StatsLedger —— 战力双轨账房（1.4）：DUPR 核心轨的明细落账、窗口重放与派生读。

与 LiveBook 的关系：settle 只在 settle_confirm 的一本账事务内被调（Elo 之后、
同一 commit——双写两本账）；pairing_rating / card 是读侧（配平代位与名片）。
口径常量全在 dupr.py（单一源），本模块只管持久化与重放编排。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import clock
from ..db.models import Account, DuprDetail, DuprRating
from . import dupr


class StatsLedger:
    def __init__(self, db: Session):
        self.db = db

    def settle(
        self,
        *,
        game_id: int,
        match_id: int,
        ended_at: datetime,
        winner_side: list[tuple[int | None, float]],
        loser_side: list[tuple[int | None, float]],
        score_w: int,
        score_l: int,
    ) -> None:
        """一场确认制结束对局的 DUPR 落账：每名注册球员一行明细（自己视角的
        完整输入快照）→ 各自窗口重放 → 派生分缓存整行覆写。

        边按 (account_id, 结算时 DUPR 分) 给全队——访客 account_id=None、分数
        已按 3.0 代入（参与对面的快照，自身不落行不进账，1.4 §4）。
        """
        opp_w = [r for _, r in winner_side]
        opp_l = [r for _, r in loser_side]

        def snap(
            acct: int,
            own: float,
            side: list[tuple[int | None, float]],
            opps: list[float],
            won: bool,
        ) -> DuprDetail:
            mates = [r for a, r in side if a != acct]
            return DuprDetail(
                account_id=acct,
                match_id=match_id,
                game_id=game_id,
                ended_at=ended_at,
                # 双打一名搭档；单人边记自身分（队伍均值口径不变形）
                partner_rating=mates[0] if mates else own,
                opp_a=opps[0],
                opp_b=opps[1] if len(opps) > 1 else opps[0],
                score_w=score_w,
                score_l=score_l,
                won=won,
            )

        for acct, own in winner_side:
            if acct is not None:
                self.db.add(snap(acct, own, winner_side, opp_l, won=True))
        for acct, own in loser_side:
            if acct is not None:
                self.db.add(snap(acct, own, loser_side, opp_w, won=False))
        # 明细先落（会话 autoflush 关闭，不 flush 重算查不到；id 即窗口序）
        self.db.flush()
        for acct in (a for a, _ in [*winner_side, *loser_side] if a is not None):
            self._recompute(acct)

    def pairing_rating(self, account_id: int | None) -> float:
        """配平代位分（1.4 §6 + 技术设计 §0）：访客 3.0；注册球员吃当前派生分
        ——0 场时与自评档字面一致（起步分即自评档，第 5 场定级无切换跳变）。"""
        if account_id is None:
            return dupr.GUEST_DUPR
        row = self.db.execute(
            select(DuprRating).where(DuprRating.account_id == account_id)
        ).scalar_one_or_none()
        if row is not None:
            return row.rating
        account = self.db.get(Account, account_id)
        return dupr.start_of(account.self_rating if account else None)

    def card(self, account_id: int) -> dict:
        """名片三件套：{rating, provisional(=未定级，明细不足 5 场), games}。"""
        row = self.db.execute(
            select(DuprRating).where(DuprRating.account_id == account_id)
        ).scalar_one_or_none()
        games = row.games if row else 0
        rating = row.rating if row else self.pairing_rating(account_id)
        return {
            "rating": rating,
            "provisional": games < dupr.RATED_GAMES,
            "games": games,
        }

    def _recompute(self, account_id: int) -> None:
        """涉事者重算：起步分 + 窗口内明细重放 → 派生分缓存覆写（幂等）。
        games 记明细总行数（定级门槛看总量，不看窗口）。"""
        account = self.db.get(Account, account_id)
        details = (
            self.db.execute(
                select(DuprDetail)
                .where(DuprDetail.account_id == account_id)
                .order_by(DuprDetail.id)
            )
            .scalars()
            .all()
        )
        rating = dupr.replay(
            dupr.start_of(account.self_rating if account else None),
            [
                {
                    "partner_rating": r.partner_rating,
                    "opp_a": r.opp_a,
                    "opp_b": r.opp_b,
                    "score_w": r.score_w,
                    "score_l": r.score_l,
                    "won": r.won,
                }
                for r in details[-dupr.WINDOW :]
            ],
        )
        row = self.db.execute(
            select(DuprRating).where(DuprRating.account_id == account_id)
        ).scalar_one_or_none()
        if row is None:
            row = DuprRating(account_id=account_id, rating=3.0, games=0)
            self.db.add(row)
        row.rating = rating
        row.games = len(details)
        row.updated_at = clock.now()
