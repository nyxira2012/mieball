"""stats 路由 —— 战力域的公开读出口。

榜单是全圈公开数据（游客可看，无 Bearer 依赖）；计算口径收口在 StatsLedger，
本路由只做 HTTP 面。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...services.stats import StatsLedger
from ..deps import get_db

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/leaderboard")
def leaderboard(db: Session = Depends(get_db)):
    """战力榜全量列表（公开可匿名访问）：按 DUPR 降序、同分按 id 升序；
    定级状态由 dupr_provisional 字段表达。"""
    return StatsLedger(db).leaderboard()
