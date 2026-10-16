"""ops 读取口（6.1 批4）—— 排障专用两条 GET：按球局拉审计、按错误号捞运行日志。

只读：直接扫 log_dir 里的既有文件，不碰 Journal 写侧（日志地基的行为一件不动）。
守卫在 deps.require_ops_key（OPS_KEY 没配=口子整个关着）。
扫描本体是纯函数 read_audit_events / read_error_lines——scripts/query_log.py
不启服务直接复用，文件格式知识只此一份。
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request

from ...core.clock import CN_TZ
from ...core.logs import APP_PREFIX, AUDIT_PREFIX, keep_floor
from ..deps import require_ops_key

router = APIRouter(prefix="/ops", tags=["ops"])

ERR_NOT_FOUND_NOTE = "没有这个编号：可能抄错了、已过 14 天销毁、或当时没写成"


def _recent_files(log_dir: Path, prefix: str, keep_days: int) -> list[Path]:
    """近 keep_days 天的按天文件，按文件名日期升序（文件名日期字典序=时间序）；
    保留窗下界单一源 keep_floor（Journal._cleanup 的删除线同吃）。"""
    floor = keep_floor(datetime.now(CN_TZ).strftime("%Y%m%d"), keep_days)
    return sorted(
        (
            f
            for f in log_dir.glob(f"{prefix}-*.log")
            if f.stem.rsplit("-", 1)[-1] >= floor
        ),
        key=lambda f: f.name,
    )


def read_audit_events(log_dir: str, keep_days: int, game_id: int) -> list[dict]:
    """近 keep_days 天 audit-*.log 里 game_id 命中的 JSON 行；按文件序+行序=写入序，
    天然升序。写坏的非 JSON 行跳过不炸（写侧兜底的缺口标记不落审计，防的是手改）。"""
    events = []
    for f in _recent_files(Path(log_dir), AUDIT_PREFIX, keep_days):
        for ln in f.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(ln)
            except ValueError:
                continue
            if row.get("game_id") == game_id:
                events.append(row)
    return events


# 记录首行的界碑：行头带时间戳+08:00 与 [lvl]；traceback 等续体不带——
# 向下截到它为止（gap 缺口标记也是带行头的完整记录，天然是界碑）
_RECORD_HEAD_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T[\d:.]+\+08:00 \[")


def read_error_lines(log_dir: str, keep_days: int, error_id: str) -> list[str] | None:
    """按错误号扫 app-*.log：命中 → 向前 2 行上下文 + 向后到下一条记录首行为止
    （internal_error handler 记的 traceback 是不带行头的多行续体，向下扩到界碑
    才停——案发现场整段带出，不再被 ±2 截断）；无命中 → None。"""
    for f in _recent_files(Path(log_dir), APP_PREFIX, keep_days):
        lines = f.read_text(encoding="utf-8").splitlines()
        hits = [i for i, ln in enumerate(lines) if error_id in ln]
        if hits:
            lo = max(0, min(hits) - 2)
            hi = max(hits) + 1
            while hi < len(lines) and not _RECORD_HEAD_RE.match(lines[hi]):
                hi += 1
            return lines[lo:hi]
    return None


@router.get("/audit", dependencies=[Depends(require_ops_key)])
def audit_by_game(request: Request, game_id: int) -> dict:
    settings = request.app.state.settings
    events = read_audit_events(settings.log_dir, settings.keep_days, game_id)
    if not events:
        return {"events": [], "note": "没有记录"}
    return {"events": events}


@router.get("/errors", dependencies=[Depends(require_ops_key)])
def error_by_id(request: Request, error_id: str) -> dict:
    settings = request.app.state.settings
    lines = read_error_lines(settings.log_dir, settings.keep_days, error_id)
    if lines is None:
        return {"found": False, "note": ERR_NOT_FOUND_NOTE}
    return {"found": True, "lines": lines}
