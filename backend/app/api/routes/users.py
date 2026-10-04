"""users 路由 —— 隐私出口的 HTTP 面。

"给别人看什么"的规则本体在 AccountBook.view()；这里只算观看者身份：
带钥匙看自己 = self（全号）；same_game=1 是留给球局后端的钩子（同局名单里点人），
球局接上后由名单链路带上下文调用，游客/陌生人一律 other。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ...db.models import Account
from ...services.accounts import AccountBook, Viewer
from ..deps import current_account, get_account_book

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{account_id}")
def public_view(
    account_id: int,
    same_game: bool = False,
    account: Account | None = Depends(current_account),
    book: AccountBook = Depends(get_account_book),
):
    viewer: Viewer
    if account is not None and account.id == account_id:
        viewer = "self"
    elif same_game:
        viewer = "same_game"
    else:
        viewer = "other"
    return {"account": book.view(account_id, viewer=viewer)}
