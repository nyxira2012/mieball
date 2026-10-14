"""配置 —— 环境变量一次性读入，全项目只经 get_settings() 取用。

开发期零配置可跑：默认 SQLite 落在 backend/mieball.db、固定开发 pepper、
短信走控制台假发送器（验证码打印到后端日志，对应发送器抽象）。
上线前必须设置 MIEBALL_PEPPER 与 MIEBALL_SMS_PROVIDER。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv

    _root_env = Path(__file__).resolve().parents[3] / ".env"
    if _root_env.is_file():
        load_dotenv(_root_env)
    else:
        load_dotenv()
except ImportError:
    pass

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
    # 微信钥匙（1.7 第四把）：fake=假通道（开发，凭证即身份号），real=真网页授权；
    # real 必须配 AppID/Secret，缺了通道按"还没开通"关死（绝不能拿假通道上生产——
    # 假通道等于免认证放行）
    wechat_provider: str = "fake"
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    # 6.1 日志地基：目录 / 慢回应警告阈值 ms / 文件保留天数 / 读取口钥匙
    # （环境变量不带 MIEBALL_ 前缀：LOG_DIR / SLOW_MS / KEEP_DAYS / OPS_KEY；
    # 行为机制见 core/logs.py；ops_key 空=读取口关闭，见 api/routes/logs.py）
    log_dir: str = "./logs"
    slow_ms: int = 1000
    keep_days: int = 14
    ops_key: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    pepper = os.environ.get("MIEBALL_PEPPER", _DEV_PEPPER)
    if pepper == _DEV_PEPPER:
        # 不拦启动（开发零配置），但上线换 pepper 前旧指纹全部失配=全员重新拿钥匙，属预期
        print("[config] 使用开发默认 pepper，仅限开发环境")
    wechat_provider = os.environ.get("MIEBALL_WECHAT_PROVIDER", "fake")
    if wechat_provider == "fake":
        print(
            "[config] 微信通道走假通道（开发用）——上线必须设 MIEBALL_WECHAT_PROVIDER=real 与 AppID/Secret"
        )
    return Settings(
        db_url=os.environ.get("MIEBALL_DB", "sqlite:///./mieball.db"),
        pepper=pepper,
        sms_provider=os.environ.get("MIEBALL_SMS_PROVIDER", "console"),
        sms_daily_budget=int(os.environ.get("MIEBALL_SMS_DAILY_BUDGET", "200")),
        wechat_provider=wechat_provider,
        wechat_app_id=os.environ.get("MIEBALL_WECHAT_APP_ID", ""),
        wechat_app_secret=os.environ.get("MIEBALL_WECHAT_APP_SECRET", ""),
        log_dir=os.environ.get("LOG_DIR", "./logs"),
        slow_ms=int(os.environ.get("SLOW_MS", "1000")),
        keep_days=int(os.environ.get("KEEP_DAYS", "14")),
        ops_key=os.environ.get("OPS_KEY", ""),
    )
