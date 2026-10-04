"""钥匙与验证码的生成/指纹 —— 只在这里碰 secrets 与 HMAC。

库表只存指纹（HMAC-SHA256(pepper, 原文)）：数据库泄露也拿不到可用的钥匙/验证码。
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from .config import get_settings


def new_device_token() -> str:
    """设备钥匙原文：256bit 随机，只发给客户端一次，库里只落指纹。"""
    return secrets.token_urlsafe(32)


def token_fingerprint(token: str) -> str:
    return _hmac(f"key:{token}")


def new_code() -> str:
    """6 位数字验证码（前导零补齐）。"""
    return f"{secrets.randbelow(1_000_000):06d}"


def code_fingerprint(phone: str, purpose: str, code: str) -> str:
    return _hmac(f"code:{phone}:{purpose}:{code}")


def _hmac(msg: str) -> str:
    return hmac.new(get_settings().pepper.encode(), msg.encode(), hashlib.sha256).hexdigest()
