"""可注入时钟 —— 业务一律取 clock.now()，测试中 monkeypatch 本模块即可用假时钟测试限频与过期逻辑。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def now() -> datetime:
    return datetime.now()


def today_key(t: datetime | None = None) -> str:
    """按本地日切一天的计数窗口（限频的"一天"用日期字符串分组，不精确到 24h 滚动，够用）。"""
    t = t or now()
    return t.strftime("%Y-%m-%d")


# 接口进出统一时区为 ISO 8601 +08:00；数据库内一律使用 naive 北京时间
CN_TZ = timezone(timedelta(hours=8))


def wall(dt: datetime) -> datetime:
    """带时区的时间戳转为东八区北京时间存为 naive；naive 时间直接当作北京时间。"""
    return dt.astimezone(CN_TZ).replace(tzinfo=None) if dt.tzinfo is not None else dt


def iso(dt: datetime) -> str:
    """naive 北京墙钟 → 出参 ISO 8601 +08:00。"""
    return dt.replace(tzinfo=CN_TZ).isoformat()
