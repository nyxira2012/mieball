"""intents 路由 —— 意向簿的 HTTP 面：纯参数搬运，规则全在 IntentBook。

known（与 viewer 打过没打过）是两簿组合视图：在这里用 GameBook.played_with 覆写，
IntentBook 不反向依赖局簿（技术设计 §3 两簿边界）；游客 viewer 没有 known，恒 False。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...db.models import Account
from ...services.games import GameBook
from ...services.intents import IntentBook
from ..deps import (
    current_account,
    get_game_book,
    get_intent_book,
    require_account,
)

router = APIRouter(prefix="/intents", tags=["intents"])


class IntentIn(BaseModel):
    """留/改意向表单（4.13）：至少一个时段 + 频率（0/1/2）+ 备注可空。"""

    slots: list[str]
    frequency: int
    note: str | None = None


# /mine 先于其它路由声明：同前缀下带字面段的路径不靠参数匹配（games /mine 同款规矩）
@router.get("/mine")
def my_intent(
    account: Account = Depends(require_account),
    book: IntentBook = Depends(get_intent_book),
):
    return book.mine(account_id=account.id)


@router.get("")
def list_intents(
    account: Account | None = Depends(current_account),
    book: IntentBook = Depends(get_intent_book),
    games: GameBook = Depends(get_game_book),
):
    """意向列表：谁都能翻（含游客，4.13 评审裁决）；known 两簿组合。"""
    viewer_id = account.id if account else None
    out = book.list(viewer_id=viewer_id)
    if viewer_id is not None:
        for v in out:
            v["known"] = games.played_with(
                account_a=viewer_id, account_b=v["account"]["id"]
            )
    return out


@router.post("")
def save_intent(
    body: IntentIn,
    account: Account = Depends(require_account),
    book: IntentBook = Depends(get_intent_book),
):
    """留/改意向（4.13）：一人一份；改了想法清已邀标记、重排回前面。"""
    return book.save(
        account_id=account.id,
        slots=body.slots,
        frequency=body.frequency,
        note=body.note,
    )


@router.post("/delete")
def delete_intent(
    account: Account = Depends(require_account),
    book: IntentBook = Depends(get_intent_book),
):
    """删意向（4.13）：删掉即真没了；幂等。"""
    return book.delete(account_id=account.id)
