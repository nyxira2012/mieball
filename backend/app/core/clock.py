"""可注入时钟 —— 业务一律取 clock.now()，测试里 monkeypatch 本模块即可用假时钟测限频/过期，
不用真等（docs/1.1 §B 的 60 秒/5 分钟/一天窗口全走这里）。"""
from __future__ import annotations

from datetime import datetime


def now() -> datetime:
    return datetime.now()


def today_key(t: datetime | None = None) -> str:
    """按本地日切一天的计数窗口（限频的"一天"用日期字符串分组，不精确到 24h 滚动，够用）。"""
    t = t or now()
    return t.strftime("%Y-%m-%d")
