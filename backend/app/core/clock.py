"""可注入时钟 —— 业务一律取 clock.now()，测试里 monkeypatch 本模块即可用假时钟测限频/过期，
不用真等（docs/1.1 §B 的 60 秒/5 分钟/一天窗口全走这里）。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def now() -> datetime:
    return datetime.now()


def today_key(t: datetime | None = None) -> str:
    """按本地日切一天的计数窗口（限频的"一天"用日期字符串分组，不精确到 24h 滚动，够用）。"""
    t = t or now()
    return t.strftime("%Y-%m-%d")


# 接口进出的统一时区（契约§2：ISO 8601 +08:00）；库内一律 naive 北京墙钟
CN_TZ = timezone(timedelta(hours=8))


def wall(dt: datetime) -> datetime:
    """aware 入参按东八区取墙钟存 naive；naive 直接当北京墙钟（技术设计 §3 时区口径）。"""
    return dt.astimezone(CN_TZ).replace(tzinfo=None) if dt.tzinfo is not None else dt


def iso(dt: datetime) -> str:
    """naive 北京墙钟 → 出参 ISO 8601 +08:00。"""
    return dt.replace(tzinfo=CN_TZ).isoformat()
