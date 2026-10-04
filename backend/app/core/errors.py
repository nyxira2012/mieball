"""业务错误 —— 服务层只抛 ApiError(code, message)，路由层统一映射成
HTTP {\"error\": {code, message}}；前端按 code 分支，不解析中文文案。"""
from __future__ import annotations

from fastapi import HTTPException


class ApiError(HTTPException):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(status_code=status, detail=message)
        self.code = code


def phone_taken() -> ApiError:
    return ApiError(409, "phone_taken", "这个手机号已经有人用了")


def no_account() -> ApiError:
    return ApiError(404, "no_account", "这个手机号还没有账号，请核对后重输")


def no_identity() -> ApiError:
    return ApiError(401, "no_identity", "请先登录")


def phone_invalid() -> ApiError:
    return ApiError(422, "phone_invalid", "手机号位数不对，请输入 11 位大陆手机号")


def nickname_invalid(msg: str = "昵称需 1-16 个字符") -> ApiError:
    return ApiError(422, "nickname_invalid", msg)


def chibi_invalid() -> ApiError:
    return ApiError(422, "chibi_invalid", "形象配置不合法")


def sms_cooldown(retry_after: int) -> ApiError:
    return ApiError(429, "sms_cooldown", f"发送太频繁，{retry_after} 秒后再试")


def sms_phone_daily() -> ApiError:
    return ApiError(429, "sms_phone_daily", "这个手机号今天收码次数到上限了，明天再试；收不到码且发码不是你本人操作的，联系平台客服")


def sms_ip_daily() -> ApiError:
    return ApiError(429, "sms_ip_daily", "今天收码次数到上限了，明天再试")


def sms_unavailable() -> ApiError:
    return ApiError(503, "sms_unavailable", "短信暂时发不出，请稍后再试")


def sms_bad_code(remaining: int) -> ApiError:
    return ApiError(400, "sms_bad_code", f"验证码不对，还可试 {remaining} 次")


def sms_code_invalid() -> ApiError:
    return ApiError(400, "sms_code_invalid", "验证码已失效，请重新获取")


def sms_code_expired() -> ApiError:
    return ApiError(400, "sms_code_expired", "验证码已过期，请重新获取")
