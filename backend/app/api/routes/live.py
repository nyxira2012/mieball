"""live 路由 —— 现场总账的 HTTP 面（读 + 记分链写）：纯参数搬运，规则全在 LiveBook。

响应约定同 games：成功体直接是总账视图（写后回最新画面）；防线退回的 409 在
{"error": {code, message}} 之外再带 "view"（最新总账，前端对表用）。
写请求一律带 base_total_seq（片级另带 base_court_seq）——出发时看到的两级号。
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...db.models import Account
from ...services.live import LiveBook
from ..deps import current_account, get_live_book, require_account

router = APIRouter(prefix="/games/{game_id}/live", tags=["live"])


class DealCourtIn(BaseModel):
    """一片的排阵上报：a/b 是名册行标识（LivePlayer.id），发牌算法在前端。"""

    court_no: int = Field(ge=1)
    a: list[int] = Field(min_length=1)
    b: list[int] = Field(min_length=1)


class DealIn(BaseModel):
    courts: list[DealCourtIn] = Field(min_length=1)
    base_total_seq: int


class PointIn(BaseModel):
    court_no: int
    side: Literal["a", "b"]
    base_total_seq: int
    base_court_seq: int


class CourtWriteIn(BaseModel):
    """片级写动作的公共身位（undo/clear/settle-open）。"""

    court_no: int
    base_total_seq: int
    base_court_seq: int


class SettleConfirmIn(BaseModel):
    """确认结束：窗内可能调过比分——最终比分与胜方由确认窗定死送来。"""

    court_no: int
    winner_side: Literal["a", "b"]
    score_a: int = Field(ge=0)
    score_b: int = Field(ge=0)
    no_redeal: bool = False
    base_total_seq: int
    base_court_seq: int


class CancelIn(BaseModel):
    court_no: int
    no_redeal: bool = False
    base_total_seq: int
    base_court_seq: int


@router.get("")
def live_view(
    game_id: int,
    account: Account | None = Depends(current_account),
    book: LiveBook = Depends(get_live_book),
):
    """总账读：游客可读（散场后同一形状即只读回看）；考勤时刻按 viewer 分权。"""
    return book.view(game_id=game_id, viewer_id=account.id if account else None)


@router.post("/start")
def live_start(
    game_id: int,
    account: Account = Depends(require_account),
    book: LiveBook = Depends(get_live_book),
):
    return book.start(game_id=game_id, organizer_id=account.id)


@router.post("/deal")
def live_deal(
    game_id: int,
    body: DealIn,
    account: Account = Depends(require_account),
    book: LiveBook = Depends(get_live_book),
):
    return book.deal(
        game_id=game_id,
        actor_id=account.id,
        courts=[c.model_dump() for c in body.courts],
        base_total_seq=body.base_total_seq,
    )


@router.post("/point")
def live_point(
    game_id: int,
    body: PointIn,
    account: Account = Depends(require_account),
    book: LiveBook = Depends(get_live_book),
):
    return book.point(
        game_id=game_id,
        actor_id=account.id,
        court_no=body.court_no,
        side=body.side,
        base_total_seq=body.base_total_seq,
        base_court_seq=body.base_court_seq,
    )


@router.post("/undo")
def live_undo(
    game_id: int,
    body: CourtWriteIn,
    account: Account = Depends(require_account),
    book: LiveBook = Depends(get_live_book),
):
    return book.undo(
        game_id=game_id,
        actor_id=account.id,
        court_no=body.court_no,
        base_total_seq=body.base_total_seq,
        base_court_seq=body.base_court_seq,
    )


@router.post("/clear")
def live_clear(
    game_id: int,
    body: CourtWriteIn,
    account: Account = Depends(require_account),
    book: LiveBook = Depends(get_live_book),
):
    return book.clear(
        game_id=game_id,
        actor_id=account.id,
        court_no=body.court_no,
        base_total_seq=body.base_total_seq,
        base_court_seq=body.base_court_seq,
    )


@router.post("/settle-open")
def live_settle_open(
    game_id: int,
    body: CourtWriteIn,
    account: Account = Depends(require_account),
    book: LiveBook = Depends(get_live_book),
):
    return book.settle_open(
        game_id=game_id,
        actor_id=account.id,
        court_no=body.court_no,
        base_total_seq=body.base_total_seq,
        base_court_seq=body.base_court_seq,
    )


@router.post("/settle-confirm")
def live_settle_confirm(
    game_id: int,
    body: SettleConfirmIn,
    account: Account = Depends(require_account),
    book: LiveBook = Depends(get_live_book),
):
    return book.settle_confirm(
        game_id=game_id,
        actor_id=account.id,
        court_no=body.court_no,
        winner_side=body.winner_side,
        score_a=body.score_a,
        score_b=body.score_b,
        no_redeal=body.no_redeal,
        base_total_seq=body.base_total_seq,
        base_court_seq=body.base_court_seq,
    )


@router.post("/cancel")
def live_cancel(
    game_id: int,
    body: CancelIn,
    account: Account = Depends(require_account),
    book: LiveBook = Depends(get_live_book),
):
    return book.cancel(
        game_id=game_id,
        actor_id=account.id,
        court_no=body.court_no,
        no_redeal=body.no_redeal,
        base_total_seq=body.base_total_seq,
        base_court_seq=body.base_court_seq,
    )
