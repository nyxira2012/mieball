"""games 路由 —— 局簿的 HTTP 面（读链 + 报名/退局/改局 + 组织者工具箱/邀请）：
纯参数搬运，规则全在 GameBook。

响应约定同 auth：成功体直接是 game_view（或其列表）；失败体 {"error": {code, message}}。
时间进出统一为 ISO 8601 +08:00，换算收口在服务层。
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...core.logs import audit
from ...db.models import Account
from ...services.bills import BillBook
from ...services.games import GameBook
from ..deps import current_account, get_bill_book, get_game_book, require_account

router = APIRouter(prefix="/games", tags=["games"])


class PublishIn(BaseModel):
    """发局表单：报名截止时间发布后即定死，不提供修改接口。"""

    name: str | None = None
    start_at: datetime
    end_at: datetime
    deadline_at: datetime
    venue_name: str
    venue_address: str | None = None
    min_players: int
    max_players: int
    visibility: str
    scoring: int
    rotation: str
    score_rule: str


class JoinIn(BaseModel):
    """报名表单：带几人 0-3，缺省 0（自己占 1 坑）。"""

    bring: int = 0


class EditIn(BaseModel):
    """改局表单：字段可选，None 沿用原值；报名截止时间不可改。"""

    name: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    venue_name: str | None = None
    venue_address: str | None = None
    min_players: int | None = None
    max_players: int | None = None
    visibility: str | None = None
    scoring: int | None = None
    rotation: str | None = None
    score_rule: str | None = None


class BookingIn(BaseModel):
    """订场登记表单：场地名称列表 + 小票总价（免费填 0）。"""

    courts: list[str]
    fee_total: int


class InviteIn(BaseModel):
    """邀请球友加入球局：被邀请人不占名额，加入与否由对方自决。"""

    account_id: int


class FeeIn(BaseModel):
    """补填总价表单：只对已散场且从未填过价的局开放；免费填 0。"""

    fee_total: int


@router.post("")
def publish_game(
    body: PublishIn,
    account: Account = Depends(require_account),
    book: GameBook = Depends(get_game_book),
):
    out = book.publish(
        organizer_id=account.id,
        name=body.name,
        start_at=body.start_at,
        end_at=body.end_at,
        deadline_at=body.deadline_at,
        venue_name=body.venue_name,
        venue_address=body.venue_address,
        min_players=body.min_players,
        max_players=body.max_players,
        visibility=body.visibility,
        scoring=body.scoring,
        rotation=body.rotation,
        score_rule=body.score_rule,
    )
    audit(
        "publish_game",
        game_id=out["id"],
        account_id=account.id,
        detail=f"{body.venue_name} {body.start_at:%m-%d %H:%M} 开打",
    )
    return out


@router.get("")
def list_games(
    account: Account | None = Depends(current_account),
    book: GameBook = Depends(get_game_book),
):
    """找局打列表：可匿名（匿名只翻得到 public）；懒判定与三档过滤在 book。"""
    return book.list_for(viewer_id=account.id if account else None)


# /mine、/playlog 必须先于 /{game_id} 声明：FastAPI 按声明序匹配，否则被当成 id
@router.get("/mine")
def my_games(
    account: Account = Depends(require_account),
    book: GameBook = Depends(get_game_book),
):
    return book.mine(account_id=account.id)


@router.get("/playlog")
def my_playlog(
    account: Account = Depends(require_account),
    book: GameBook = Depends(get_game_book),
):
    """打球记录：当前用户参与过的球局列表与累计上场对局数。"""
    return book.playlog(account_id=account.id)


@router.get("/{game_id}")
def game_detail(
    game_id: int,
    account: Account | None = Depends(current_account),
    book: GameBook = Depends(get_game_book),
):
    """局详情：公开可看，包含球友与对局信息。"""
    return book.detail(game_id=game_id, viewer_id=account.id if account else None)


@router.post("/{game_id}/join")
def join_game(
    game_id: int,
    body: JoinIn,
    account: Account = Depends(require_account),
    book: GameBook = Depends(get_game_book),
):
    """报名（4.3/4.14）：整行进出、满员落候补、截止后照常可加、重复提交幂等。"""
    out = book.join(game_id=game_id, account_id=account.id, bring=body.bring)
    audit(
        "join_game",
        game_id=game_id,
        account_id=account.id,
        detail=f"带 {body.bring} 人",
    )
    return out


@router.post("/{game_id}/quit")
def quit_game(
    game_id: int,
    account: Account = Depends(require_account),
    book: GameBook = Depends(get_game_book),
):
    """退局（4.4）：截止锁退出、改约解锁窗可退、幂等。"""
    out = book.quit(game_id=game_id, account_id=account.id)
    audit("quit_game", game_id=game_id, account_id=account.id, detail="退出报名")
    return out


@router.post("/{game_id}/edit")
def edit_game(
    game_id: int,
    body: EditIn,
    account: Account = Depends(require_account),
    book: GameBook = Depends(get_game_book),
):
    """改局（4.6）：只有组织者、开打前；上限调整与改约解锁在 book。"""
    return book.edit(game_id=game_id, organizer_id=account.id, **body.model_dump())


@router.post("/{game_id}/lock")
def lock_game(
    game_id: int,
    account: Account = Depends(require_account),
    book: GameBook = Depends(get_game_book),
):
    """空锁必打（4.7）：人数不够也照开；一锁不撤、不可解锁（只能撤局）。"""
    out = book.lock(game_id=game_id, organizer_id=account.id)
    audit("lock_game", game_id=game_id, account_id=account.id, detail="空锁必打")
    return out


@router.post("/{game_id}/booking")
def book_game(
    game_id: int,
    body: BookingIn,
    account: Account = Depends(require_account),
    book: GameBook = Depends(get_game_book),
):
    """订场登记（4.7）：最后写赢、可反复改；截止后名单已锁也只锁人。"""
    out = book.book(
        game_id=game_id,
        organizer_id=account.id,
        courts=body.courts,
        fee_total=body.fee_total,
    )
    audit(
        "book_game",
        game_id=game_id,
        account_id=account.id,
        detail=f"{len(body.courts)} 片 场费 {body.fee_total}",
    )
    return out


@router.post("/{game_id}/booking/clear")
def clear_game_booking(
    game_id: int,
    account: Account = Depends(require_account),
    book: GameBook = Depends(get_game_book),
):
    """清空订场登记（4.7）：费用回未定、截止照常判人数；手动锁保留。"""
    out = book.clear_booking(game_id=game_id, organizer_id=account.id)
    audit(
        "clear_game_booking",
        game_id=game_id,
        account_id=account.id,
        detail="清空订场登记",
    )
    return out


@router.get("/{game_id}/fee-preview")
def game_fee_preview(
    game_id: int,
    amount: int,
    account: Account = Depends(require_account),
    bills: BillBook = Depends(get_bill_book),
):
    """补填总价预览：按当前名册实时计算预计分摊金额，仅组织者本人可查。"""
    return bills.preview(game_id=game_id, organizer_id=account.id, amount=amount)


@router.post("/{game_id}/fee")
def set_game_fee(
    game_id: int,
    body: FeeIn,
    account: Account = Depends(require_account),
    book: GameBook = Depends(get_game_book),
    bills: BillBook = Depends(get_bill_book),
):
    """补填总价：>0 当场出账、=0 标记免费不出账；设置后金额定死不可修改。"""
    bills.set_fee(game_id=game_id, organizer_id=account.id, fee_total=body.fee_total)
    audit(
        "set_game_fee",
        game_id=game_id,
        account_id=account.id,
        detail=f"补填总价 {body.fee_total} 元",
    )
    return book.detail(game_id=game_id, viewer_id=account.id)


@router.post("/{game_id}/cancel")
def cancel_game(
    game_id: int,
    account: Account = Depends(require_account),
    book: GameBook = Depends(get_game_book),
):
    """撤局（4.10）：开打前；底账留档，报名者当日灰字、次日收走。"""
    out = book.cancel(game_id=game_id, organizer_id=account.id)
    audit("cancel_game", game_id=game_id, account_id=account.id, detail="开打前撤局")
    return out


@router.post("/{game_id}/restore")
def restore_game(
    game_id: int,
    account: Account = Depends(require_account),
    book: GameBook = Depends(get_game_book),
):
    """救回未成局（4.9）：terminated 且开打前 → pending 待处置。"""
    out = book.restore(game_id=game_id, organizer_id=account.id)
    audit("restore_game", game_id=game_id, account_id=account.id, detail="救回未成局")
    return out


@router.post("/{game_id}/invite")
def invite_user(
    game_id: int,
    body: InviteIn,
    account: Account = Depends(require_account),
    book: GameBook = Depends(get_game_book),
):
    """邀请（4.11/4.12）：局进对方"我的局"；重复邀当没事。"""
    out = book.invite(
        game_id=game_id, organizer_id=account.id, invitee_id=body.account_id
    )
    audit(
        "invite_user",
        game_id=game_id,
        account_id=account.id,
        detail=f"邀账号 {body.account_id}",
    )
    return out
