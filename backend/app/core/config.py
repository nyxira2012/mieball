"""配置 —— 环境变量一次性读入，全项目只经 get_settings() 取用。

开发期零配置可跑：默认 SQLite 落在 backend/mieball.db、固定开发 pepper、
短信走控制台假发送器（验证码打印到后端日志，对应评审 R1 的发送器抽象）。
上线前必须设置 MIEBALL_PEPPER 与 MIEBALL_SMS_PROVIDER（见 docs/1.1 §B）。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

_DEV_PEPPER = "mieball-dev-pepper-do-not-use-in-prod"


@dataclass(frozen=True)
class Settings:
    db_url: str
    # 钥匙/验证码指纹的 HMAC 密钥；库里只存指纹不存原文，泄露库不泄露钥匙
    pepper: str
    # console=假发送器（开发），real=真服务商（上线换入，SmsGate 内部选择）
    sms_provider: str
    # 全站每日短信总预算（防换号刷量把短信费刷光），超了明确报"暂时发不出"
    sms_daily_budget: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    pepper = os.environ.get("MIEBALL_PEPPER", _DEV_PEPPER)
    if pepper == _DEV_PEPPER:
        # 不拦启动（开发零配置），但上线换 pepper 前旧指纹全部失配=全员重新拿钥匙，属预期
        print("[config] 使用开发默认 pepper，仅限开发环境")
    return Settings(
        db_url=os.environ.get("MIEBALL_DB", "sqlite:///./mieball.db"),
        pepper=pepper,
        sms_provider=os.environ.get("MIEBALL_SMS_PROVIDER", "console"),
        sms_daily_budget=int(os.environ.get("MIEBALL_SMS_DAILY_BUDGET", "200")),
    )
