"""auth 路由 —— 纯参数搬运：HTTP ↔ AccountBook/SmsGate，不写业务规则。

响应约定：成功体 {"token"?, "account"?, "ok"}；失败体 {"error": {"code", "message"}}，
前端按 error.code 分支（phone_taken / no_account / sms_* / ...）。
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ...core import errors
from ...db.models import Account
from ...services.accounts import AccountBook
from ..deps import (
    bearer_token,
    client_ip,
    current_account,
    get_account_book,
    require_account,
)

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
    # 1.7 微信绑定凭条：授权认人后的"生面孔"建号时带着，顺手绑（可空）
    bind_token: str | None = None


class SmsIn(BaseModel):
    phone: str
    purpose: Literal[
        "recovery",
        "takeover",
        "deactivate",
        "set_password",
        "reset_password",
        "bind_phone",  # 1.8：快进号补绑（判定反转：无账号才发码）
    ]


class PhoneBindIn(BaseModel):
    """补绑确认（1.8 §4.4）：输码绑上，必须收码验证。"""

    phone: str
    code: str


class RedeemIn(BaseModel):
    phone: str
    code: str
    purpose: Literal["recovery", "takeover"]
    device_marker: str
    card: CardIn | None = None
    bind_token: str | None = None  # 1.7：验明正身时刻凭它正式绑微信


class DeactivateIn(BaseModel):
    phone: str
    code: str


class ProfileIn(BaseModel):
    nickname: str | None = None
    chibi: dict[str, Any] | None = None
    card_bg: str | None = None


class PasswordSetIn(BaseModel):
    code: str
    password: str


class PasswordLoginIn(BaseModel):
    phone: str
    password: str
    device_marker: str
    bind_token: str | None = None  # 1.7：验明正身时刻凭它正式绑微信


class PasswordResetIn(BaseModel):
    phone: str
    code: str
    password: str
    device_marker: str
    bind_token: str | None = None


class PasswordChangeIn(BaseModel):
    old: str
    new: str


class PasswordRedeemIn(BaseModel):
    phone: str
    password: str
    device_marker: str
    card: CardIn | None = None
    bind_token: str | None = None


class WechatUrlIn(BaseModel):
    """跳微信授权页的完整地址（1.7 A4）：地址由这边拼好，画面只管跳。"""

    redirect_uri: str
    state: str


class WechatLoginIn(BaseModel):
    code: str
    device_marker: str
    # 1.8 快进建号：动作弹的卡（微信内）传 fast=True（+卡上手填昵称，可空）；
    # 登录页不传——unbound 仍走 1.7 原路发凭条落卡（4.7 防误快进护栏）
    fast: bool = False
    nickname: str | None = None


class WechatRedeemIn(BaseModel):
    """占卡「微信验证进入」（1.7 §4.4/4.5）：phone=占卡时填的那个号。"""

    code: str
    phone: str
    device_marker: str
    card: CardIn | None = None


def _session_out(view: dict, token: str, wechat_bound: bool) -> dict:
    """五路发钥匙端点共用收口；绑定真成了才带 wechat_bound（画面据此说「已绑上」，
    没绑上绝不说——1.7 §5 验收锁）。"""
    out = {"token": token, "account": view}
    if wechat_bound:
        out["wechat_bound"] = True
    return out


@router.post("/signup")
def signup(
    body: SignupIn,
    book: AccountBook = Depends(get_account_book),
):
    view, token, wechat_bound = book.signup(
        phone=body.card.phone,
        device_marker=body.device_marker,
        nickname=body.card.nickname,
        nickname_set=body.card.nickname_set,
        chibi=body.card.chibi,
        chibi_set=body.card.chibi_set,
        bind_token=body.bind_token,
    )
    return _session_out(view, token, wechat_bound)


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
    return {
        "account": book.update_profile(
            account.id, nickname=body.nickname, chibi=body.chibi, card_bg=body.card_bg
        )
    }


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
    account: Account | None = Depends(current_account),
    book: AccountBook = Depends(get_account_book),
):
    # 五用途查无账号不发码；bind_phone（1.8）判定反转且必须登录态发（快进号补绑）
    if body.purpose == "bind_phone" and account is None:
        raise errors.no_identity()
    book.send_code(
        body.phone,
        body.purpose,
        client_ip(request),
        account_id=account.id if account else None,
    )
    return {"ok": True}


@router.post("/phone/bind")
def phone_bind(
    body: PhoneBindIn,
    account: Account = Depends(require_account),
    book: AccountBook = Depends(get_account_book),
):
    return {
        "account": book.bind_phone(
            account_id=account.id, phone=body.phone, code=body.code
        )
    }


@router.post("/redeem")
def redeem(
    body: RedeemIn,
    current: Account | None = Depends(current_account),
    book: AccountBook = Depends(get_account_book),
):
    # adopt_from（1.8 验证收编）：本机若登着绑微信的快进号，验证成功即迁绑回老账号
    view, token, wechat_bound = book.redeem(
        phone=body.phone,
        code=body.code,
        purpose=body.purpose,
        device_marker=body.device_marker,
        card=body.card.model_dump(exclude_none=False) if body.card else None,
        bind_token=body.bind_token,
        adopt_from=current,
    )
    return _session_out(view, token, wechat_bound)


@router.post("/deactivate")
def deactivate(
    body: DeactivateIn,
    account: Account = Depends(require_account),
    book: AccountBook = Depends(get_account_book),
):
    book.deactivate(account_id=account.id, phone=body.phone, code=body.code)
    return {"ok": True}


# ---- 密码钥匙（docs/1.6 §4.8~§4.11）：纯搬运，规则全在 PasswordMixin ----


@router.post("/password/set")
def password_set(
    body: PasswordSetIn,
    account: Account = Depends(require_account),
    book: AccountBook = Depends(get_account_book),
):
    book.set_password(account.id, code=body.code, password=body.password)
    return {"ok": True}


@router.post("/password/login")
def password_login(
    body: PasswordLoginIn,
    book: AccountBook = Depends(get_account_book),
):
    view, token, wechat_bound = book.login_password(
        phone=body.phone,
        password=body.password,
        device_marker=body.device_marker,
        bind_token=body.bind_token,
    )
    return _session_out(view, token, wechat_bound)


@router.post("/password/reset")
def password_reset(
    body: PasswordResetIn,
    current: Account | None = Depends(current_account),
    book: AccountBook = Depends(get_account_book),
):
    # adopt_from（1.8 验证收编）：reset 也是「短信证明老账号主人」的路
    view, token, wechat_bound = book.reset_password(
        phone=body.phone,
        code=body.code,
        password=body.password,
        device_marker=body.device_marker,
        bind_token=body.bind_token,
        adopt_from=current,
    )
    return _session_out(view, token, wechat_bound)


@router.post("/password/change")
def password_change(
    body: PasswordChangeIn,
    account: Account = Depends(require_account),
    book: AccountBook = Depends(get_account_book),
):
    book.change_password(account.id, old=body.old, new=body.new)
    return {"ok": True}


@router.post("/password/redeem")
def password_redeem(
    body: PasswordRedeemIn,
    book: AccountBook = Depends(get_account_book),
):
    view, token, wechat_bound = book.redeem_password(
        phone=body.phone,
        password=body.password,
        device_marker=body.device_marker,
        card=body.card.model_dump(exclude_none=False) if body.card else None,
        bind_token=body.bind_token,
    )
    return _session_out(view, token, wechat_bound)


# ---- 微信钥匙（docs/1.7）：纯搬运，规则全在 WechatMixin/WeChatGate ----


@router.post("/wechat/url")
def wechat_url(
    body: WechatUrlIn,
    book: AccountBook = Depends(get_account_book),
):
    return {"url": book.wechat.build_url(body.redirect_uri, body.state)}


@router.post("/wechat/login")
def wechat_login(
    body: WechatLoginIn,
    book: AccountBook = Depends(get_account_book),
):
    status, first, second, bind_token, nickname_random = book.wechat_login(
        code=body.code,
        device_marker=body.device_marker,
        fast=body.fast,
        nickname=body.nickname,
    )
    if status == "unbound":
        return {"status": "unbound", "bind_token": first}
    if status == "created":
        # 快进建号一次完成绑定：不发凭条；随机名旗=前端 toast 报名字的判据（4.1）
        return {
            "status": "created",
            "token": first,
            "account": second,
            "nickname_random": nickname_random,
        }
    return {
        "status": "ok",
        "token": first,
        "account": second,
        "bind_token": bind_token,
    }


@router.post("/wechat/redeem")
def wechat_redeem(
    body: WechatRedeemIn,
    book: AccountBook = Depends(get_account_book),
):
    view, token = book.wechat_redeem(
        code=body.code,
        phone=body.phone,
        device_marker=body.device_marker,
        card=body.card.model_dump(exclude_none=False) if body.card else None,
    )
    return {"token": token, "account": view}
