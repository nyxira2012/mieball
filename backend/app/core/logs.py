"""日志地基（docs/6.1）—— 运行/审计两路按天文件、写失败全兜底、脱敏、请求上下文贴标签。

机制约束（实现期实测 starlette 1.7）：
- 切割日期一律 datetime.now(CN_TZ) 显式东八区——clock.now() 是 naive 本地墙钟，
  部署机不在东八区会切错天；测试 monkeypatch 模块级 today() 即可模拟跨天。
- contextvars 在 deps（线程池）/BaseHTTPMiddleware（任务边界）里拷贝不回传：
  ctx_* 只保证「中间件 → 路由」向下可见（audit() 用）；中间件要的操作人由
  deps 镜像到共享的 request.state（deps.py 里设）。
"""

from __future__ import annotations

import json
import re
from contextvars import ContextVar
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import IO

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .clock import CN_TZ

ctx_account: ContextVar[int | None] = ContextVar("log_account", default=None)
ctx_game: ContextVar[int | None] = ContextVar("log_game", default=None)
ctx_client: ContextVar[str | None] = ContextVar("log_client", default=None)
# 当前请求的账本：中间件进门时 set，路由里的 audit() 凭它找到 Journal
ctx_journal: ContextVar[Journal | None] = ContextVar("log_journal", default=None)

_PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)")
_BLOB_RE = re.compile(r"[0-9A-Za-z]{24,}")


def mask(text: str | None) -> str | None:
    """脱敏（spec C3：手机号与登录钥匙明文根本不落盘）：11 位手机号→138****1234，
    ≥24 连续字母数字长串（token/key 类）→前 6+****。长串先处理——手机号嵌在
    长串里时整串已被打码，不会拆散后漏网。"""
    if text is None:
        return None
    text = _BLOB_RE.sub(lambda m: m.group(0)[:6] + "****", text)
    return _PHONE_RE.sub(r"\g<1>****\g<2>", text)


def today() -> str:
    """切割用天号（东八区显式，禁 naive now）。"""
    return datetime.now(CN_TZ).strftime("%Y%m%d")


def _now_iso() -> str:
    return datetime.now(CN_TZ).isoformat(timespec="milliseconds")


def _fmt(v: int | str | None) -> str:
    return "-" if v is None else str(v)


def _client_label(ua: str) -> str:
    """端标签（6.1 §B1「用什么端」）：微信小程序 UA 带 miniProgram 字样，其余 web。"""
    return "mp" if "miniprogram" in ua.lower() else "web"


def audit(
    action: str,
    *,
    game_id: int | None = None,
    detail: str | None = None,
    account_id: int | None = None,
) -> None:
    """审计落一笔（spec C1）：不在请求里/没挂账本 → 静默不记。account_id 显式传——
    deps 在线程池里 set 的 ctx_account 拷贝不进路由（见模块头），批3 埋点从路由
    手上的 account 传入。"""
    j = ctx_journal.get()
    if j is not None:
        j.audit(action, game_id=game_id, detail=detail, account_id=account_id)


class Journal:
    """两路按天文件（app=运行流水 / audit=审计账本）：惰性切换、切换顺跑清理、写失败兜底。"""

    def __init__(self, log_dir: str, *, keep_days: int = 14) -> None:
        self._dir = Path(log_dir)
        self._keep_days = keep_days
        self._day: str | None = None
        self._app: IO[str] | None = None
        self._audit: IO[str] | None = None
        self._dropped = 0
        self._dropped_since: str | None = None

    # ---- 对外写口 ----

    def startup(self, note: str) -> None:
        """启动记号一行——落盘顺带触发一次切换+清理检查（停机错过半夜那趟，spec 4.8）。"""
        self.line("info", note)

    def line(self, level: str, msg: str, *, account_id: int | None = None) -> None:
        """运行日志一行（msg 过脱敏），行格式 `<iso+08:00> [lvl] (u= g= c=) msg`。"""
        who = account_id if account_id is not None else ctx_account.get()
        head = self._head(level, who, _fmt(ctx_client.get()))
        self._emit("app", head + mask(msg))

    def access(
        self,
        method: str,
        path: str,
        status: int,
        ms: int,
        *,
        account_id: int | None = None,
        client: str = "web",
    ) -> None:
        """访问流水（spec §6 先全记）：≥400 落 warn 失败行，其余 info 流水行。"""
        lvl = "warn" if status >= 400 else "info"
        head = self._head(lvl, account_id, client)
        self._emit("app", f"{head}access {method} {path} {status} {ms}ms")

    def slow(
        self,
        method: str,
        path: str,
        status: int,
        ms: int,
        *,
        account_id: int | None = None,
        client: str = "web",
    ) -> None:
        """慢回应警告，写明等了多久（spec 4.5：慢的那拍即使 200 也记）。"""
        head = self._head("warn", account_id, client)
        self._emit("app", f"{head}slow {method} {path} {status} {ms}ms")

    def audit(
        self,
        action: str,
        *,
        game_id: int | None = None,
        detail: str | None = None,
        account_id: int | None = None,
    ) -> None:
        """审计账本一笔（spec C1 清单动作）：JSON 行，detail 过脱敏。"""
        who = account_id if account_id is not None else ctx_account.get()
        row = {
            "at": _now_iso(),
            "action": action,
            "account_id": who,
            "game_id": game_id,
            "detail": mask(detail),
        }
        self._emit("audit", json.dumps(row, ensure_ascii=False))

    # ---- 落盘机制 ----

    def _head(self, level: str, account_id: int | None, client: str) -> str:
        return (
            f"{_now_iso()} [{level}] (u={_fmt(account_id)} "
            f"g={_fmt(ctx_game.get())} c={client}) "
        )

    def _emit(self, lane: str, text: str) -> None:
        """单条落盘总闸：开文件/写/冲全程兜底，失败只计数不外抛（spec 4.7）。"""
        try:
            self._ensure_open()
            if self._dropped:
                # 恢复可写的第一笔前补缺口标记（spec 4.7）；只进运行日志，
                # 审计文件保持纯 JSON 行（批4 读取口按行 json.loads）
                gap = (
                    self._head("warn", None, "-")
                    + f"gap: 自 {self._dropped_since} 起丢 {self._dropped} 条"
                )
                if self._put(self._app, gap):
                    self._dropped = 0
                    self._dropped_since = None
                else:
                    self._note_drop()
            ok = self._put(self._app if lane == "app" else self._audit, text)
        except Exception:  # noqa: BLE001 —— 日志侧任何故障不连累业务（spec 4.7 全兜底）
            ok = False
        if not ok:
            self._note_drop()

    @staticmethod
    def _put(f: IO[str] | None, text: str) -> bool:
        if f is None:
            return False
        f.write(text + "\n")
        f.flush()  # 按行落盘：进程崩了已写的行也在
        return True

    def _note_drop(self) -> None:
        if self._dropped == 0:
            self._dropped_since = _now_iso()
        self._dropped += 1
        self._close()  # 坏句柄关掉，下一笔重开再试（磁盘满/文件被挪走都可能自愈）

    def _ensure_open(self) -> None:
        day = today()
        if self._app is not None and self._audit is not None and self._day == day:
            return
        self._close()  # 跨天切换先关旧文件（首开时是空操作）
        self._dir.mkdir(parents=True, exist_ok=True)
        # 长持有追加句柄（跨请求复用）、手动 _close 管理——非一次性文件不用 with
        self._app = open(self._dir / f"app-{day}.log", "a", encoding="utf-8")  # noqa: SIM115
        self._audit = open(self._dir / f"audit-{day}.log", "a", encoding="utf-8")  # noqa: SIM115
        self._day = day
        self._cleanup(day)

    def _close(self) -> None:
        for f in (self._app, self._audit):
            if f is not None:
                try:
                    f.close()
                except Exception:  # noqa: S110, BLE001 —— 收尾路径同样不外抛（spec 4.7）
                    pass
        self._app = None
        self._audit = None
        self._day = None

    def _cleanup(self, day: str) -> None:
        """删文件名日期 ≤ 今天-keep_days 的同前缀文件（spec 4.8 磁盘封顶）；失败不碍事，下回再试。"""
        # 纯文件名日期字符串的先后比较，无时区语义
        cutoff = (
            datetime.strptime(day, "%Y%m%d")  # noqa: DTZ007
            - timedelta(days=self._keep_days)
        ).strftime("%Y%m%d")
        for prefix in ("app", "audit"):
            for f in self._dir.glob(f"{prefix}-*.log"):
                d = f.stem.rsplit("-", 1)[-1]
                if len(d) == 8 and d.isdigit() and d <= cutoff:
                    try:
                        f.unlink()
                    except OSError:
                        pass


_HEARTBEAT_RE = re.compile(r"^/api/games/\d+/live$")


class AccessLogMiddleware(BaseHTTPMiddleware):
    """计时中间件（main.py 挂最内层）：心跳 200 静默 / 慢警告（慢拍即使 200 也记）/
    ≥400 失败行 / 其余 access 流水（spec 4.5、§6「流水先全记」）。"""

    def __init__(self, app, journal: Journal, slow_ms: int = 1000) -> None:
        super().__init__(app)
        self.journal = journal
        self.slow_ms = slow_ms

    async def dispatch(self, request: Request, call_next):
        start = perf_counter()
        client = _client_label(request.headers.get("user-agent", ""))
        try:
            ctx_client.set(client)  # 向下可见：路由里的 audit()/日志行自带端标签
            ctx_journal.set(self.journal)
            response = await call_next(request)
            ms = round((perf_counter() - start) * 1000)
            self._record(request, response.status_code, ms, client)
            return response
        except Exception:  # 包死：日志侧故障不连累业务，异常原样交回框架（spec 4.7）
            try:
                ms = round((perf_counter() - start) * 1000)
                self.journal.access(
                    request.method, request.url.path, 500, ms, client=client
                )
            except Exception:  # noqa: S110, BLE001 —— 这里除了吞掉没有可做的事
                pass
            raise

    def _record(self, request: Request, status: int, ms: int, client: str) -> None:
        method, path = request.method, request.url.path
        # deps 镜像到共享 request.state 的操作人（contextvars 拷贝回不到中间件，见模块头）
        who = getattr(request.state, "log_account", None)
        if ms > self.slow_ms:
            self.journal.slow(method, path, status, ms, account_id=who, client=client)
        elif method == "GET" and _HEARTBEAT_RE.match(path) and status < 400:
            return  # 心跳静默：现场页正常刷新一个字不写（spec 4.5）
        else:
            self.journal.access(method, path, status, ms, account_id=who, client=client)
