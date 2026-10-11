"""StatsLedger —— 战力双轨账房（1.4）：DUPR 核心轨的明细落账、窗口重放与派生读。

与 LiveBook 的关系：settle 只在 settle_confirm 的一本账事务内被调（Elo 之后、
同一 commit——双写两本账）；pairing_rating / card 是读侧（配平代位与名片）。
口径常量全在 dupr.py（单一源），本模块只管持久化与重放编排。
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core import clock
from ..db.models import Account, DuprDetail, DuprRating, EloRating
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
                # 口径记号（6.1 §4.4）：改分重落删行重插走同一 snap，自动带上
                rule_version=dupr.RULES_VERSION,
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
        """配平代位分（1.4 §6 + 技术设计 §0，修订后口径）：访客/无派分行统一
        GUEST_DUPR 起步——0 场即 2.5，第 5 场定级无切换跳变。"""
        if account_id is None:
            return dupr.GUEST_DUPR
        row = self.db.execute(
            select(DuprRating).where(DuprRating.account_id == account_id)
        ).scalar_one_or_none()
        if row is not None:
            return row.rating
        return dupr.GUEST_DUPR

    def pairing_ratings(self, account_ids: list[int | None]) -> dict[int | None, float]:
        """pairing_rating 的批量版（view / 确认回流逐人代位分一次查齐，免 N+1）：
        语义逐条同单发版——访客与查无派行者（含注销清户）统一回 GUEST_DUPR 起步。"""
        out: dict[int | None, float] = {}
        if any(a is None for a in account_ids):
            out[None] = dupr.GUEST_DUPR
        ids = sorted({a for a in account_ids if a is not None})
        if not ids:
            return out
        for row in self.db.execute(
            select(DuprRating).where(DuprRating.account_id.in_(ids))
        ).scalars():
            out[row.account_id] = row.rating
        for a in ids:  # 无派分行（新号）/账号行已不在（注销清户）：统一起步分
            out.setdefault(a, dupr.GUEST_DUPR)
        return out

    def leaderboard(self) -> list[dict]:
        """战力榜全量（1.4 §8 留的榜单端点欠账）：全部在册账号一行一份名片
        （card 同一口径——名字/小人来自账号行，战绩四件套来自 card），
        DUPR 降序、同分 id 升序（契约总则 §5 稳定排序）。注销账号不列
        （历史不留痕，1.1 注销口径）。行另带 elo_rating（Elo 娱乐轨只读——
        4.1 战力页 DUPR/Elo 切换的娱乐视图用；榜单排序口径仍只吃 DUPR）。
        演示库规模逐人 card() 直查，批量化等真有量级需求再做。"""
        accounts = (
            self.db.execute(
                select(Account)
                .where(Account.status == "active")
                .order_by(Account.id.asc())
            )
            .scalars()
            .all()
        )
        # Elo 一人一行全表一趟取齐（免逐人 N+1；无行=没打过落账局，回初始 1200，
        # 与 EloRating.rating 默认值同源——常量真身在 live.py RATING_INIT，
        # 这里不 import 它防 stats←live 循环）
        elo_map = {
            r.account_id: r.rating for r in self.db.execute(select(EloRating)).scalars()
        }
        out = []
        for a in accounts:
            c = self.card(a.id)
            out.append(
                {
                    "id": a.id,
                    "name": a.nickname,
                    "chibi": json.loads(a.chibi),
                    "card_bg": a.card_bg,
                    "dupr_rating": c["rating"],
                    "dupr_provisional": c["provisional"],
                    "dupr_games": c["games"],
                    "dupr_wins": c["wins"],
                    "dupr_last5": c["last5"],
                    "dupr_month_net": c["month_net"],
                    "elo_rating": elo_map.get(a.id, 1200),
                }
            )
        out.sort(key=lambda r: (-r["dupr_rating"], r["id"]))
        return out

    def card(self, account_id: int) -> dict:
        """名片数据：{rating, provisional(=未定级，明细不足 5 场), games, wins, last5, month_net}。"""
        row = self.db.execute(
            select(DuprRating).where(DuprRating.account_id == account_id)
        ).scalar_one_or_none()
        games = row.games if row else 0
        rating = row.rating if row else self.pairing_rating(account_id)
        if games == 0:
            return {
                "rating": rating,
                "provisional": True,
                "games": 0,
                "wins": 0,
                "last5": [],
                "month_net": 0,
            }

        wins = self.db.execute(
            select(func.count())
            .select_from(DuprDetail)
            .where(DuprDetail.account_id == account_id, DuprDetail.won.is_(True))
        ).scalar_one()

        last5_wons = list(
            self.db.execute(
                select(DuprDetail.won)
                .where(DuprDetail.account_id == account_id)
                .order_by(DuprDetail.id.desc())
                .limit(5)
            ).scalars()
        )[::-1]
        last5 = ["W" if w else "L" for w in last5_wons]

        n = clock.now()
        month_start = n.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_wons = list(
            self.db.execute(
                select(DuprDetail.won).where(
                    DuprDetail.account_id == account_id,
                    DuprDetail.ended_at >= month_start,
                )
            ).scalars()
        )
        month_net = sum(1 if w else -1 for w in month_wons)

        return {
            "rating": rating,
            "provisional": games < dupr.RATED_GAMES,
            "games": games,
            "wins": wins,
            "last5": last5,
            "month_net": month_net,
        }

    def _recompute(self, account_id: int) -> None:
        """涉事者重算：起步分 + 窗口内明细重放 → 派生分缓存覆写（幂等）。
        games 记明细总行数（定级门槛看总量，不看窗口）——窗口只搬尾部 WINDOW 行，
        总量单查 count，老账号几百场后不再整表搬运。"""
        window = list(
            self.db.execute(
                select(DuprDetail)
                .where(DuprDetail.account_id == account_id)
                .order_by(DuprDetail.id.desc())
                .limit(dupr.WINDOW)
            ).scalars()
        )[::-1]  # 倒取窗口后翻回 id 升序（重放按时间正序吃）
        total = (
            self.db.execute(
                select(func.count())
                .select_from(DuprDetail)
                .where(DuprDetail.account_id == account_id)
            )
        ).scalar_one()
        rating = dupr.replay(
            dupr.GUEST_DUPR,
            [
                {
                    "partner_rating": r.partner_rating,
                    "opp_a": r.opp_a,
                    "opp_b": r.opp_b,
                    "score_w": r.score_w,
                    "score_l": r.score_l,
                    "won": r.won,
                }
                for r in window
            ],
        )
        row = self.db.execute(
            select(DuprRating).where(DuprRating.account_id == account_id)
        ).scalar_one_or_none()
        if row is None:
            row = DuprRating(account_id=account_id, rating=dupr.GUEST_DUPR, games=0)
            self.db.add(row)
        row.rating = rating
        row.games = total
        row.updated_at = clock.now()
