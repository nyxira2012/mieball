"""live 路由 —— 现场总账的 HTTP 面（读 + 记分链写 + 现场管理 + 散场链）：
纯参数搬运，规则全在 LiveBook。

响应约定同 games：成功体直接是总账视图（写后回最新画面）；防线退回的 409 在
{"error": {code, message}} 之外再带 "view"（最新总账，前端对表用）。
写请求一律带 base_total_seq（片级另带 base_court_seq）——出发时看到的两级号；
动全场写操作只校验总号 base_total_seq。
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from ...core.logs import audit
from ...db.models import Account
from ...services.live import LiveBook
from ..deps import current_account, get_live_book, require_account

router = APIRouter(prefix="/games/{game_id}/live", tags=["live"])


class DealIn(BaseModel):
    """一键排阵：空载荷只带出发版本号，补满当前所有空片，全权权限闸在服务层校验。"""

    base_total_seq: int


class RedealIn(BaseModel):
    """重排这片（全权）：取消对局并立刻重新发牌。"""

    court_no: int
    base_total_seq: int
    base_court_seq: int


class SettleConfirmIn(BaseModel):
    """上传结算：由到场者将本地比分上传落账，胜方与比分由上传者指定，先传先落。"""

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
    """考勤打卡：修改名册行签到状态（ok/late/join/left），代办他人需全权。"""

    player_id: int
    check: Literal["ok", "late", "join", "left"]
    base_total_seq: int


class SwapIn(BaseModel):
    """换人：out_id 场上名册行、in_id 候场名册行。"""

    out_id: int
    in_id: int
    base_total_seq: int


class TempoIn(BaseModel):
    """歇连节奏：skip 休息一轮、fire 连战、unskip 取消休息。"""

    player_id: int
    action: Literal["skip", "fire", "unskip"]
    base_total_seq: int


class RulesIn(BaseModel):
    """规则四件套与场地参数修改：全可选字段，只更新显式给出的字段。
    pairing 四档（按候场队序/均衡配对/轮换优先/胜负均衡）；streak_max 0=不限。"""

    doubles: bool | None = None
    down: Literal["all", "loser", "n1", "n2", "n3"] | None = None
    pairing: Literal["queue", "balance", "partner", "even"] | None = None
    streak_max: int | None = Field(default=None, ge=0)
    courts_count: int | None = Field(default=None, ge=1)
    # 分制写 game 列（组局口径）；改后在打片照旧打完旧制、新开片用新制
    scoring: int | None = Field(default=None, ge=1)
    base_total_seq: int


class PlayerWriteIn(BaseModel):
    """按名册行定靶的全场写（封撤管理员）公共身位。"""

    player_id: int
    base_total_seq: int


class GuestsIn(BaseModel):
    """带访客（全权）：指定数量访客挂在 guarantor 名册行（账号行）名下。"""

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
    since_total_seq: int | None = None,
    since_fee_total: int | None = None,
    account: Account | None = Depends(current_account),
    book: LiveBook = Depends(get_live_book),
):
    """总账读取：游客可读（散场后为只读回看态）；考勤时刻按查看者分权。
    若携带 since_total_seq 与 since_fee_total 且数据未变，返回 204 无内容；
    任一变化或未带参数时返回全量视图。"""
    if (
        since_total_seq is not None
        and since_fee_total is not None
        and book.unchanged_since(
            game_id=game_id,
            since_total_seq=since_total_seq,
            since_fee_total=since_fee_total,
        )
    ):
        return Response(status_code=204)
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


@router.post("/redeal")
def live_redeal(
    game_id: int,
    body: RedealIn,
    account: Account = Depends(require_account),
    book: LiveBook = Depends(get_live_book),
):
    out = book.redeal(
        game_id=game_id,
        actor_id=account.id,
        court_no=body.court_no,
        base_total_seq=body.base_total_seq,
        base_court_seq=body.base_court_seq,
    )
    audit(
        "live_redeal",
        game_id=game_id,
        account_id=account.id,
        detail=f"court={body.court_no}",
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
        # 直接开场局无对局落账时散场即撤（无痕分支）：响应换形，审计记撤不记封存
        detail=(
            f"散场撤局无痕 {out['cancelled_at']}"
            if out.get("vacated")
            else f"散场 {out['ended_at']}"
        ),
    )
    return out
