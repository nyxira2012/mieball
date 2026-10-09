"""依赖注入 —— 路由与服务之间的薄胶水：会话、服务装配、Bearer 钥匙、客户端 IP。"""

from __future__ import annotations

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from ..core import errors
from ..core.logs import ctx_account
from ..db.models import Account
from ..services.accounts import AccountBook
from ..services.bills import BillBook
from ..services.games import GameBook
from ..services.intents import IntentBook
from ..services.keys import KeyVault
from ..services.live import LiveBook
from ..services.sms import SmsGate


def get_db(request: Request):
    db: Session = request.app.state.session_factory()
    try:
        yield db
    finally:
        db.close()


def get_account_book(request: Request, db: Session = Depends(get_db)) -> AccountBook:
    settings = request.app.state.settings
    return AccountBook(db, SmsGate(db, settings), KeyVault(db))


def get_game_book(db: Session = Depends(get_db)) -> GameBook:
    return GameBook(db)


def get_intent_book(db: Session = Depends(get_db)) -> IntentBook:
    return IntentBook(db)


def get_live_book(db: Session = Depends(get_db)) -> LiveBook:
    return LiveBook(db)


def get_bill_book(db: Session = Depends(get_db)) -> BillBook:
    return BillBook(db)


def bearer_token(authorization: str | None = Header(default=None)) -> str | None:
    if authorization and authorization.startswith("Bearer "):
        return authorization[len("Bearer ") :]
    return None


def current_account(
    request: Request,
    token: str | None = Depends(bearer_token),
    book: AccountBook = Depends(get_account_book),
) -> Account | None:
    """钥匙无效/已作废/未带 → None（游客处理，不报错，docs/1.1 §B"认人"）。"""
    if not token:
        return None
    account = book.by_token(token)
    if account is not None:
        # 日志贴「谁」标签（6.1 §B1）：ctx 供同上下文读取；deps 在线程池里跑、
        # contextvars 拷贝回不到中间件，镜像一份到共享的 request.state
        ctx_account.set(account.id)
        request.state.log_account = account.id
    return account


def require_account(account: Account | None = Depends(current_account)) -> Account:
    """登录守卫：没钥匙/钥匙失效 → 401 no_identity（区别于 current_account 的游客静默）。"""
    if account is None:
        raise errors.no_identity()
    return account


def client_ip(request: Request) -> str:
    # 部署在反代后面时优先取 X-Forwarded-For 首段；直连时用 client.host
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else ""
