"""钥匙/验证码的生成与指纹、密码暗记 —— 只在这里碰 secrets 与 HMAC。

库表只存指纹（HMAC-SHA256(pepper, 原文)）：数据库泄露也拿不到可用的钥匙/验证码。
密码存加工暗记（C1）：PBKDF2-HMAC-SHA256 慢哈希 + 每密码随机盐，pepper 作最外层
（盐随库泄露也拿不到原文，pepper 不在库里才挡得住离线爆破）。
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from .config import get_settings

# PBKDF2 迭代次数：OWASP 2023 起点值（600k 太慢会拖登录响应，自用产品取 120k 量级）
PBKDF2_ITERATIONS = 120_000


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


def new_bind_token() -> str:
    """微信绑定凭条原文（1.7）：与设备钥匙同规格，只发一次，库里只落指纹。"""
    return secrets.token_urlsafe(32)


def new_nonce() -> str:
    """JS-SDK 签名用随机串：不可猜即可，不落库不进指纹，无需钥匙级长度。"""
    return secrets.token_hex(8)


def bind_fingerprint(token: str) -> str:
    return _hmac(f"wxb:{token}")


def hash_password(plain: str) -> str:
    """密码暗记："盐$pepper(pbkdf2(原文, 盐))"。盐每密码随机，同文不同记。"""
    salt = secrets.token_hex(16)
    return f"{salt}${_pwd_digest(plain, salt)}"


def verify_password(plain: str, stored: str) -> bool:
    salt, sep, want = stored.partition("$")
    if not sep:
        return False
    return hmac.compare_digest(_pwd_digest(plain, salt), want)


def _hmac(msg: str) -> str:
    return hmac.new(
        get_settings().pepper.encode(), msg.encode(), hashlib.sha256
    ).hexdigest()


def _pwd_digest(plain: str, salt: str) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), PBKDF2_ITERATIONS)
    return _hmac(f"pwd:{dk.hex()}")
