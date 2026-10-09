"""stats 路由 —— 战力域的公开读出口。

榜单是全圈公开数据（游客可看，无 Bearer 依赖）；口径全在 StatsLedger
（card 单一源），这里只做 HTTP 面。1.4 §8 记的「榜单端点」欠账在此落账。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...services.stats import StatsLedger
from ..deps import get_db

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/leaderboard")
def leaderboard(db: Session = Depends(get_db)):
    """战力榜全量（可匿名，裸数组——与找局打列表同形）：DUPR 降序、同分 id
    升序；满 5 场定级与否由 dupr_provisional 表达，前端据此分区（入榜 /
    参考未定级）。"""
    return StatsLedger(db).leaderboard()
