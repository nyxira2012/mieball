"""bills 路由 —— 账单域（docs/1.3）的 HTTP 面，前缀 /api/bills。

域职责：账单页全视图（GET /api/bills）与两向记账动作（settle・receive）。出账的
写入口不在这里——散场出账挂在 live 的 end() commit 内、补填总价走 games 路由的
fee 端点。

写动作响应直出账单页视图（与 GET 同形状）：「应收点一人少一笔、两处永远同一个
数」由同一视图单点保证；period 跟请求带上（默认 all），前端整树按当前档换新。

响应约定同 auth/games：成功体直接是业务字段；失败体 {"error": {code, message}}。
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...core.logs import audit
from ...db.models import Account
from ...services.bills import BillBook
from ..deps import get_bill_book, require_account

router = APIRouter(prefix="/bills", tags=["bills"])

Period = Literal["7d", "30d", "all"]


class ReceiveIn(BaseModel):
    """收款靶子（§4.4 按人明细里的一行）。"""

    account_id: int


@router.get("")
def list_bills(
    period: Period = "all",
    account: Account = Depends(require_account),
    bills: BillBook = Depends(get_bill_book),
):
    """账单页全视图（1.3 §4.6）：登录者的待付/已付 + 应收/已收 + 谁还欠你 +
    费用未定提醒——SQL 只取 viewer 的行/viewer 组织的局，分权在服务层裁死。"""
    return bills.view(account_id=account.id, period=period)


@router.post("/{game_id}/settle")
def settle_bill(
    game_id: int,
    period: Period = "all",
    account: Account = Depends(require_account),
    bills: BillBook = Depends(get_bill_book),
):
    """点「结算」（§4.3）：本人行 paid_at 置位，终态不可逆；重放幂等回视图。"""
    out = bills.settle(game_id=game_id, account_id=account.id, period=period)
    audit(
        "settle_bill",
        game_id=game_id,
        account_id=account.id,
        detail=f"period={period}",
    )
    return out


@router.post("/{game_id}/receive")
def receive_payer(
    game_id: int,
    body: ReceiveIn,
    period: Period = "all",
    account: Account = Depends(require_account),
    bills: BillBook = Depends(get_bill_book),
):
    """逐人点「已收」（§4.4）：组织者本人（管理员不碰钱，C2），幂等回视图。"""
    out = bills.receive(
        game_id=game_id,
        payer_account_id=body.account_id,
        organizer_id=account.id,
        period=period,
    )
    audit(
        "receive_payer",
        game_id=game_id,
        account_id=account.id,
        detail=f"付款人 {body.account_id}",
    )
    return out
