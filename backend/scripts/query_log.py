"""query_log —— 排障快捷指令（6.1 批4）：不启服务，直接翻日志文件。

用法（在 backend/ 目录下）：
    .venv/bin/python scripts/query_log.py --game 7            # 这个局都发生了什么
    .venv/bin/python scripts/query_log.py --err ERR-a1b2c3    # 按错误号捞案发现场
    .venv/bin/python scripts/query_log.py --game 7 --days 7 --dir /path/to/logs

扫描逻辑复用 app/api/routes/logs.py 的纯函数（HTTP 读取口同一份文件格式知识），
默认翻 LOG_DIR 环境变量的目录、近 KEEP_DAYS 天——与在跑服务读到的口径一致。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ 入 import 路径

from app.api.routes.logs import ERR_NOT_FOUND_NOTE, read_audit_events, read_error_lines
from app.core.config import get_settings


def _print_events(game_id: int, days: int, log_dir: str) -> None:
    events = read_audit_events(log_dir, days, game_id)
    if not events:
        print(f"局 #{game_id} 近 {days} 天没有审计记录。")
        return
    print(f"局 #{game_id} 近 {days} 天的审计事件（{len(events)} 笔，时间升序）：")
    for e in events:
        who = e.get("account_id")
        who_s = f"#{who}" if who is not None else "?"
        detail = f" · {e['detail']}" if e.get("detail") else ""
        print(f"  {e['at']} {who_s} {e['action']}{detail}")


def main() -> None:
    settings = get_settings()
    ap = argparse.ArgumentParser(
        description="翻日志：按球局拉审计事件 / 按错误号捞案发现场（只读）"
    )
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--game", type=int, metavar="N", help="按球局号拉审计事件")
    g.add_argument("--err", metavar="ERR-XXXXXX", help="按错误号捞运行日志")
    ap.add_argument(
        "--days",
        type=int,
        default=settings.keep_days,
        help="翻近几天（默认取 KEEP_DAYS 配置）",
    )
    ap.add_argument(
        "--dir", default=settings.log_dir, help="日志目录（默认取 LOG_DIR 配置）"
    )
    args = ap.parse_args()

    if args.game is not None:
        _print_events(args.game, args.days, args.dir)
        return

    lines = read_error_lines(args.dir, args.days, args.err)
    if lines is None:
        print(ERR_NOT_FOUND_NOTE)
        return
    print(f"编号 {args.err} 的案发现场（命中行向前 2 行，向后整段到下一条记录首行）：")
    for ln in lines:
        print(f"  {ln}")
    # spec 4.2「顺带把前后几分钟同一个局的相关事件也列在一起」：命中行头的 g=
    # 有局号（不是 "-"）就把这个局的审计也列上。只加在 CLI——4.9 的 HTTP
    # 读取口只承诺两条查询。
    hit = next((ln for ln in lines if args.err in ln), "")
    m = re.search(r"g=(\d+)", hit)
    if m:
        _print_events(int(m.group(1)), args.days, args.dir)


if __name__ == "__main__":
    main()
