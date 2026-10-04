"""auth 路由 —— 纯参数搬运：HTTP ↔ AccountBook/SmsGate，不写业务规则。

响应约定：成功体 {"token"?, "account"?, "ok"}；失败体 {"error": {"code", "message"}}，
前端按 error.code 分支（phone_taken / no_account / sms_* / ...）。
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ...db.models import Account
from ...services.accounts import AccountBook
from ..deps import bearer_token, client_ip, current_account, get_account_book, require_account

router = APIRouter(prefix="/auth", tags=["auth"])


class CardIn(BaseModel):
    """名片三行（4.2）。*_set 是"用户确实填了这一项"的显式标志（D5：不做值推断）。"""

    phone: str
    nickname: str | None = None
    nickname_set: bool = False
    chibi: dict[str, Any] | None = None
    chibi_set: bool = False


class SignupIn(BaseModel):
    device_marker: str
    card: CardIn


class SmsIn(BaseModel):
    phone: str
    purpose: Literal["recovery", "takeover", "deactivate"]


class RedeemIn(BaseModel):
    phone: str
    code: str
    purpose: Literal["recovery", "takeover"]
    device_marker: str
    card: CardIn | None = None


class DeactivateIn(BaseModel):
    phone: str
    code: str


class ProfileIn(BaseModel):
    nickname: str | None = None
    chibi: dict[str, Any] | None = None
    card_bg: str | None = None


@router.post("/signup")
def signup(
    body: SignupIn,
    book: AccountBook = Depends(get_account_book),
):
    view, token = book.signup(
        phone=body.card.phone,
        device_marker=body.device_marker,
        nickname=body.card.nickname,
        nickname_set=body.card.nickname_set,
        chibi=body.card.chibi,
        chibi_set=body.card.chibi_set,
    )
    return {"token": token, "account": view}


@router.get("/me")
def me(
    account: Account | None = Depends(current_account),
    book: AccountBook = Depends(get_account_book),
):
    """认人不报错：没带钥匙/钥匙失效 → {"account": null}，前端静默降级为游客。"""
    if account is None:
        return {"account": None}
    return {"account": book.view(account.id, viewer="self")}


@router.post("/profile")
def update_profile(
    body: ProfileIn,
    account: Account = Depends(require_account),
    book: AccountBook = Depends(get_account_book),
):
    return {"account": book.update_profile(
        account.id, nickname=body.nickname, chibi=body.chibi, card_bg=body.card_bg
    )}


@router.post("/logout")
def logout(
    token: str | None = Depends(bearer_token),
    book: AccountBook = Depends(get_account_book),
):
    """退出：只作废这一台的钥匙；幂等（没带钥匙也回 ok）。"""
    if token:
        book.logout(token)
    return {"ok": True}


@router.post("/sms")
def send_sms(
    body: SmsIn,
    request: Request,
    book: AccountBook = Depends(get_account_book),
):
    # 查无账号不发码、所有限频都在 book.send_code 这一条路径上
    book.send_code(body.phone, body.purpose, client_ip(request))
    return {"ok": True}


@router.post("/redeem")
def redeem(
    body: RedeemIn,
    book: AccountBook = Depends(get_account_book),
):
    view, token = book.redeem(
        phone=body.phone,
        code=body.code,
        purpose=body.purpose,
        device_marker=body.device_marker,
        card=body.card.model_dump(exclude_none=False) if body.card else None,
    )
    return {"token": token, "account": view}


@router.post("/deactivate")
def deactivate(
    body: DeactivateIn,
    account: Account = Depends(require_account),
    book: AccountBook = Depends(get_account_book),
):
    book.deactivate(account_id=account.id, phone=body.phone, code=body.code)
    return {"ok": True}
