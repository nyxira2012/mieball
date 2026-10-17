"""可注入时钟 —— 业务一律取 clock.now()，测试中 monkeypatch 本模块即可用假时钟测试限频与过期逻辑。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# 接口进出统一时区为 ISO 8601 +08:00；数据库内一律使用 naive 北京时间
CN_TZ = timezone(timedelta(hours=8))


def now() -> datetime:
    """北京墙钟（naive），不随部署机器时区走——datetime.now() 取机器本地钟，在非 +8
    时区的机器（开发机/异国 ECS/Docker 默认 UTC）入库即整体漂移，而 iso() 出参恒标
    +08:00，漂多少产品就错多少（2026-10-17 走查：+1100 开发机上「2 小时的局剩
    5 小时」、底账到点时刻整体偏 3 小时）。前端 time.ts 修复批 F2 已同款收口。"""
    return datetime.now(CN_TZ).replace(tzinfo=None)


def today_key(t: datetime | None = None) -> str:
    """按北京日切一天的计数窗口（限频的"一天"用日期字符串分组，不精确到 24h 滚动，够用）。"""
    t = t or now()
    return t.strftime("%Y-%m-%d")


def wall(dt: datetime) -> datetime:
    """带时区的时间戳转为东八区北京时间存为 naive；naive 时间直接当作北京时间。"""
    return dt.astimezone(CN_TZ).replace(tzinfo=None) if dt.tzinfo is not None else dt


def iso(dt: datetime) -> str:
    """naive 北京墙钟 → 出参 ISO 8601 +08:00。"""
    return dt.replace(tzinfo=CN_TZ).isoformat()
