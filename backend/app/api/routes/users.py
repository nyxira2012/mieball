"""users 路由 —— 隐私出口的 HTTP 面。

"给别人看什么"的规则本体在 AccountBook.view()；观看者身份在这里裁决（1.2 服务端化）：
本人 = self（全号）；与目标同在一个成局的正式名单（GameBook.played_with，服务端核名单）
= same_game（放行尾号 4 位）；游客/陌生人 = other。1.1 留的 same_game 自报查询参数
废弃：保留解析仅为老客户端不炸，服务端一律不信。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...db.models import Account
from ...services.accounts import AccountBook, Viewer
from ...services.games import GameBook
from ..deps import current_account, get_account_book, get_game_book

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{account_id}")
def public_view(
    account_id: int,
    same_game: bool = False,  # 废弃参数（1.2 收口）：自报不作数，见模块 docstring
    account: Account | None = Depends(current_account),
    book: AccountBook = Depends(get_account_book),
    games: GameBook = Depends(get_game_book),
):
    viewer: Viewer
    if account is None:
        viewer = "other"  # 匿名永不见尾号
    elif account.id == account_id:
        viewer = "self"
    elif games.played_with(account_a=account.id, account_b=account_id):
        viewer = "same_game"  # 同局打过（成局正式名单）才放行尾号（1.1 隐私口径）
    else:
        viewer = "other"
    return {"account": book.view(account_id, viewer=viewer)}
