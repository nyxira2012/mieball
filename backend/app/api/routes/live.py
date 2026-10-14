"""live 路由 —— 现场总账的 HTTP 面（读 + 记分链写 + 2.2 域写 + 散场链）：
纯参数搬运，规则全在 LiveBook。

响应约定同 games：成功体直接是总账视图（写后回最新画面）；防线退回的 409 在
{"error": {code, message}} 之外再带 "view"（最新总账，前端对表用）。
写请求一律带 base_total_seq（片级另带 base_court_seq）——出发时看到的两级号；
check/swap/tempo/rules/封撤管理员/散场链动全场，只走总号（2.3 §4.8-4）。
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...core.logs import audit
from ...db.models import Account
from ...services.live import LiveBook
from ..deps import current_account, get_live_book, require_account

router = APIRouter(prefix="/games/{game_id}/live", tags=["live"])


class DealIn(BaseModel):
    """一键排阵（2.8 §4.5）：空载荷只带出发号——按下=让后端补满所有空片，
    全权闸在 services 层。旧 courts 牌面字段已随前端薄壳批整体删除。"""

    base_total_seq: int


class SettleConfirmIn(BaseModel):
    """上传结算（2026-10-09 记分本地化）：记分在各手机本地，这片打完把本地账
    传上来——胜方/比分全由上传者给定，谁先传先落。"""

    court_no: int
    winner_side: Literal["a", "b"]
    score_a: int = Field(ge=0)
    score_b: int = Field(ge=0)
    no_redeal: bool = False
    base_total_seq: int
    base_court_seq: int


class SettleOverwriteIn(BaseModel):
    """改分重落（全权）：目标=该片最新一场落账；窗口=下一场落账前（片号闸把关）。"""

    court_no: int
    winner_side: Literal["a", "b"]
    score_a: int = Field(ge=0)
    score_b: int = Field(ge=0)
    base_total_seq: int
    base_court_seq: int


class CancelIn(BaseModel):
    court_no: int
    base_total_seq: int
    base_court_seq: int
    # 清扫态逐调用声明（前端编排态，后端无全局旗）：真=取消后不补片，好散场
    no_redeal: bool = False


class CheckIn(BaseModel):
    """报到四态（2.2 §4.2/4.3/4.5）：player_id 是名册行 id，代办他人需全权。"""

    player_id: int
    check: Literal["ok", "late", "join", "left"]
    base_total_seq: int


class SwapIn(BaseModel):
    """换人（2.2 §4.9）：out_id 场上名册行、in_id 候场名册行。"""

    out_id: int
    in_id: int
    base_total_seq: int


class TempoIn(BaseModel):
    """歇连（2.2 §4.10）：skip 按一次叠一轮、fire 连战、unskip 取消休息。"""

    player_id: int
    action: Literal["skip", "fire", "unskip"]
    base_total_seq: int


class RulesIn(BaseModel):
    """规则四件套+场地片数+分制（2.2 §4.7 收权 / 2.6 机制A）：全可选，只动显式给的字段。"""

    doubles: bool | None = None
    down: Literal["all", "loser", "n1", "n2", "n3"] | None = None
    pairing: Literal["queue", "balance"] | None = None
    streak_max: int | None = Field(default=None, ge=1)
    courts_count: int | None = Field(default=None, ge=1)
    # 分制写 game 列（组局口径）；改后在打片照旧打完旧制、新开片用新制
    scoring: int | None = Field(default=None, ge=1)
    base_total_seq: int


class PlayerWriteIn(BaseModel):
    """按名册行定靶的全场写（封撤管理员）公共身位。"""

    player_id: int
    base_total_seq: int


class GuestsIn(BaseModel):
    """带访客（1.3 附录 B1，全权）：count 位访客挂 guarantor 名册行（账号行）名下。"""

    count: int = Field(ge=1)
    name: str | None = None
    guarantor_id: int
    base_total_seq: int


class TotalWriteIn(BaseModel):
    """全场写的公共身位（只走总号）。"""

    base_total_seq: int


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
    out = book.start(game_id=game_id, organizer_id=account.id)
    audit(
        "live_start",
        game_id=game_id,
        account_id=account.id,
        detail=f"开账 {len(out['players'])} 人在册",
    )
    return out


@router.post("/deal")
def live_deal(
    game_id: int,
    body: DealIn,
    account: Account = Depends(require_account),
    book: LiveBook = Depends(get_live_book),
):
    out = book.deal(
        game_id=game_id,
        actor_id=account.id,
        base_total_seq=body.base_total_seq,
    )
    audit(
        "live_deal",
        game_id=game_id,
        account_id=account.id,
        detail="一键排阵",
    )
    return out


@router.post("/settle-confirm")
def live_settle_confirm(
    game_id: int,
    body: SettleConfirmIn,
    account: Account = Depends(require_account),
    book: LiveBook = Depends(get_live_book),
):
    out = book.settle_confirm(
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
    audit(
        "live_settle_confirm",
        game_id=game_id,
        account_id=account.id,
        detail=f"片 {body.court_no} 定格 {body.score_a}:{body.score_b}",
    )
    return out


@router.post("/settle-overwrite")
def live_settle_overwrite(
    game_id: int,
    body: SettleOverwriteIn,
    account: Account = Depends(require_account),
    book: LiveBook = Depends(get_live_book),
):
    out = book.settle_overwrite(
        game_id=game_id,
        actor_id=account.id,
        court_no=body.court_no,
        winner_side=body.winner_side,
        score_a=body.score_a,
        score_b=body.score_b,
        base_total_seq=body.base_total_seq,
        base_court_seq=body.base_court_seq,
    )
    audit(
        "live_settle_overwrite",
        game_id=game_id,
        account_id=account.id,
        detail=f"片 {body.court_no} 改判 {body.score_a}:{body.score_b}",
    )
    return out


@router.post("/cancel")
def live_cancel(
    game_id: int,
    body: CancelIn,
    account: Account = Depends(require_account),
    book: LiveBook = Depends(get_live_book),
):
    out = book.cancel(
        game_id=game_id,
        actor_id=account.id,
        court_no=body.court_no,
        base_total_seq=body.base_total_seq,
        base_court_seq=body.base_court_seq,
        no_redeal=body.no_redeal,
    )
    audit(
        "live_cancel",
        game_id=game_id,
        account_id=account.id,
        detail=f"取消 片 {body.court_no}",
    )
    return out


@router.post("/check")
def live_check(
    game_id: int,
    body: CheckIn,
    account: Account = Depends(require_account),
    book: LiveBook = Depends(get_live_book),
):
    out = book.check(
        game_id=game_id,
        actor_id=account.id,
        player_id=body.player_id,
        check=body.check,
        base_total_seq=body.base_total_seq,
    )
    audit(
        "live_check",
        game_id=game_id,
        account_id=account.id,
        detail=f"{body.check} 名册行 {body.player_id}",
    )
    return out


@router.post("/swap")
def live_swap(
    game_id: int,
    body: SwapIn,
    account: Account = Depends(require_account),
    book: LiveBook = Depends(get_live_book),
):
    return book.swap(
        game_id=game_id,
        actor_id=account.id,
        out_id=body.out_id,
        in_id=body.in_id,
        base_total_seq=body.base_total_seq,
    )


@router.post("/tempo")
def live_tempo(
    game_id: int,
    body: TempoIn,
    account: Account = Depends(require_account),
    book: LiveBook = Depends(get_live_book),
):
    return book.tempo(
        game_id=game_id,
        actor_id=account.id,
        player_id=body.player_id,
        action=body.action,
        base_total_seq=body.base_total_seq,
    )


@router.post("/rules")
def live_rules(
    game_id: int,
    body: RulesIn,
    account: Account = Depends(require_account),
    book: LiveBook = Depends(get_live_book),
):
    return book.rules(
        game_id=game_id,
        actor_id=account.id,
        base_total_seq=body.base_total_seq,
        **body.model_dump(exclude={"base_total_seq"}),
    )


@router.post("/set-admin")
def live_set_admin(
    game_id: int,
    body: PlayerWriteIn,
    account: Account = Depends(require_account),
    book: LiveBook = Depends(get_live_book),
):
    out = book.set_admin(
        game_id=game_id,
        actor_id=account.id,
        player_id=body.player_id,
        base_total_seq=body.base_total_seq,
    )
    audit(
        "live_set_admin",
        game_id=game_id,
        account_id=account.id,
        detail=f"封管理员 名册行 {body.player_id}",
    )
    return out


@router.post("/unset-admin")
def live_unset_admin(
    game_id: int,
    body: PlayerWriteIn,
    account: Account = Depends(require_account),
    book: LiveBook = Depends(get_live_book),
):
    out = book.unset_admin(
        game_id=game_id,
        actor_id=account.id,
        player_id=body.player_id,
        base_total_seq=body.base_total_seq,
    )
    audit(
        "live_unset_admin",
        game_id=game_id,
        account_id=account.id,
        detail=f"撤管理员 名册行 {body.player_id}",
    )
    return out


@router.post("/dropin")
def live_dropin(
    game_id: int,
    body: TotalWriteIn,  # 空降报到（1.3 附录 B1，本人写本人）：只走总号的公共身位
    account: Account = Depends(require_account),
    book: LiveBook = Depends(get_live_book),
):
    out = book.dropin(
        game_id=game_id,
        actor_id=account.id,
        base_total_seq=body.base_total_seq,
    )
    audit("live_dropin", game_id=game_id, account_id=account.id, detail="空降报到")
    return out


@router.post("/guests")
def live_guests(
    game_id: int,
    body: GuestsIn,
    account: Account = Depends(require_account),
    book: LiveBook = Depends(get_live_book),
):
    out = book.guests(
        game_id=game_id,
        actor_id=account.id,
        guarantor_id=body.guarantor_id,
        count=body.count,
        name=body.name,
        base_total_seq=body.base_total_seq,
    )
    audit(
        "live_guests",
        game_id=game_id,
        account_id=account.id,
        detail=f"带 {body.count} 访客 挂名册行 {body.guarantor_id}",
    )
    return out


@router.post("/sweep-cancel-all")
def live_sweep_cancel_all(
    game_id: int,
    body: TotalWriteIn,
    account: Account = Depends(require_account),
    book: LiveBook = Depends(get_live_book),
):
    out = book.sweep_cancel_all(
        game_id=game_id,
        actor_id=account.id,
        base_total_seq=body.base_total_seq,
    )
    audit(
        "live_sweep_cancel_all",
        game_id=game_id,
        account_id=account.id,
        detail="未完对局一键全取消",
    )
    return out


@router.post("/end")
def live_end(
    game_id: int,
    body: TotalWriteIn,
    account: Account = Depends(require_account),
    book: LiveBook = Depends(get_live_book),
):
    out = book.end(
        game_id=game_id,
        actor_id=account.id,
        base_total_seq=body.base_total_seq,
    )
    audit(
        "live_end",
        game_id=game_id,
        account_id=account.id,
        detail=f"散场 {out['ended_at']}",
    )
    return out
