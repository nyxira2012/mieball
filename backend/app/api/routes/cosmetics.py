# ruff: noqa: B008
"""cosmetics 路由 —— 装扮域的 HTTP 面，前缀 /api/cosmetics。

域职责：装扮页全视图（GET）与保存穿戴（POST /dress）。核算/把关/册子裁剪的
判定真值都收口在 services/cosmetics.py，本文件只做一行委托（bills 同风格）；
Depends 参数默认值是全项目路由的 FastAPI 惯例写法（bills/stats 等同款触发
B008），不单独迁移 Annotated 风格。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...db.models import Account
from ...services import cosmetics
from ..deps import get_db, require_account

router = APIRouter(prefix="/cosmetics", tags=["cosmetics"])


class DressIn(BaseModel):
    """保存穿戴载荷：None/未传的栏不改动（穿戴永远「最后保存的赢」）。"""

    avatar: str | None = None
    back: str | None = None


@router.get("")
def dressing(
    account: Account = Depends(require_account), db: Session = Depends(get_db)
):
    """装扮页全视图：顺手核算三类进度（失败不拦路）→ 册子条目+解锁状态+穿戴。"""
    return cosmetics.dressing_page(db, account)


@router.post("/dress")
def dress(
    body: DressIn,
    account: Account = Depends(require_account),
    db: Session = Depends(get_db),
):
    """保存穿戴：服务端把关（公共款/已解锁款/有记录的微信头像），全过写列。"""
    return cosmetics.dress(db, account, avatar=body.avatar, back=body.back)
