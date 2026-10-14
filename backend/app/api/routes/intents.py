"""intents 路由 —— 意向簿的 HTTP 面：纯参数搬运，规则全在 IntentBook。

known（与当前查看者是否共同打过球）是组合视图：在此处通过 GameBook.played_mates 对表覆写，
IntentBook 保持独立不反向依赖局簿；游客没有打球记录，known 恒为 False。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...core.logs import audit
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
    """留/改意向表单：至少一个时段 + 频率选项 + 可选备注。"""

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
    """意向列表：公开可翻看；known 字段由意向簿与对局记录组合计算。"""
    viewer_id = account.id if account else None
    out = book.list(viewer_id=viewer_id)
    if viewer_id is not None:
        mates = games.played_mates(
            viewer_id
        )  # 共打集一次拉齐，逐条对表（免逐行联表 COUNT）
        for v in out:
            v["known"] = v["account"]["id"] in mates
    return out


@router.post("")
def save_intent(
    body: IntentIn,
    account: Account = Depends(require_account),
    book: IntentBook = Depends(get_intent_book),
):
    """留/改意向：一人一份；更新后清除已邀请标记并重新置顶。"""
    out = book.save(
        account_id=account.id,
        slots=body.slots,
        frequency=body.frequency,
        note=body.note,
    )
    # 意向不挂靠具体球局：审计日志 game_id 为空，详情记录时段与频率
    audit(
        "save_intent",
        account_id=account.id,
        detail=f"{len(body.slots)} 个时段 频率 {body.frequency}",
    )
    return out


@router.post("/delete")
def delete_intent(
    account: Account = Depends(require_account),
    book: IntentBook = Depends(get_intent_book),
):
    """删意向（4.13）：删掉即真没了；幂等。"""
    out = book.delete(account_id=account.id)
    audit("delete_intent", account_id=account.id, detail="删掉意向")
    return out
