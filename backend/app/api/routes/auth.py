# ruff: noqa: B008
"""auth 路由 —— 纯参数搬运：HTTP ↔ AccountBook/SmsGate，不写业务规则。

响应约定：成功体 {"token"?, "account"?, "ok"}；失败体 {"error": {"code", "message"}}，
前端按 error.code 分支（phone_taken / no_account / sms_* / ...）。
Depends 参数默认值是全项目路由的 FastAPI 惯例写法（cosmetics/bills 等同款
触发 B008），不单独迁移 Annotated 风格。
"""

from __future__ import annotations

from typing import Literal

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
    """名片卡（4.2）。昵称沿用 *_set 显式标志（D5：不做值推断）；头像 None=没挑，
    读侧兜默认第一款公共款——校验（只许公共款头像编号）收口在服务层。"""

    phone: str
    nickname: str | None = None
    nickname_set: bool = False
    avatar: str | None = None


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
        "bind_phone",  # 快进号补绑（无账号才发码）
    ]


class PhoneBindIn(BaseModel):
    """补绑手机号：校验验证码后绑定到当前账号。"""

    phone: str
    code: str


class RedeemIn(BaseModel):
    phone: str
    code: str
    purpose: Literal["recovery", "takeover"]
    device_marker: str
    card: CardIn | None = None
    bind_token: str | None = None  # 验明正身时刻凭此凭条绑定微信


class DeactivateIn(BaseModel):
    phone: str
    code: str


class ProfileIn(BaseModel):
    nickname: str | None = None


class PasswordSetIn(BaseModel):
    code: str
    password: str


class PasswordLoginIn(BaseModel):
    phone: str
    password: str
    device_marker: str
    bind_token: str | None = None  # 验明正身时刻凭此凭条绑定微信


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
    """跳转微信授权页的完整地址：服务端拼装完成，前端直接跳转。"""

    redirect_uri: str
    state: str


class WechatLoginIn(BaseModel):
    code: str
    device_marker: str
    # 端别：h5=网页版公众号钥匙（默认，老请求体零变化）；mp=小程序钥匙（两端
    # 各查各的钥匙登记位，认人顺序见服务层）
    source: Literal["h5", "mp"] = "h5"
    # 微信快进建号：动作弹卡且在微信内传 fast=True；登录页不传（未绑定时下发绑定凭条落卡）。
    # 携带名片手填字段：手填昵称优先、所选头像落档、手机号未占用则建带号账号。
    fast: bool = False
    nickname: str | None = None
    phone: str | None = None
    avatar: str | None = None


class WechatRedeemIn(BaseModel):
    """占卡后微信验证进入：phone 为占卡时填写的手机号。source 同 WechatLoginIn。"""

    code: str
    phone: str
    device_marker: str
    card: CardIn | None = None
    source: Literal["h5", "mp"] = "h5"


def _session_out(view: dict, token: str, wechat_bound: bool) -> dict:
    """各发钥匙端点共用响应组装；实际完成绑定才返回 wechat_bound=True。"""
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
        avatar=body.card.avatar,
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
    return {"account": book.update_profile(account.id, nickname=body.nickname)}


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


# ---- 密码钥匙路由：参数校验与结果组装，规则收口在 PasswordMixin ----


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
    out = book.wechat_login(
        code=body.code,
        device_marker=body.device_marker,
        fast=body.fast,
        nickname=body.nickname,
        phone=body.phone,
        avatar=body.avatar,
        source=body.source,
    )
    if out.status == "unbound":
        return {"status": "unbound", "bind_token": out.bind_token}
    if out.status == "created":
        # 快进建号一次完成绑定：不发凭条；随机名旗=前端 toast 报名字的判据（4.1）
        return {
            "status": "created",
            "token": out.token,
            "account": out.view,
            "nickname_random": out.nickname_random,
        }
    return {
        "status": "ok",
        "token": out.token,
        "account": out.view,
        "bind_token": out.bind_token,
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
        source=body.source,
    )
    return {"token": token, "account": view}
