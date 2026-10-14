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
import traceback
import uuid
from contextvars import ContextVar
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import IO

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .clock import CN_TZ

ctx_account: ContextVar[int | None] = ContextVar("log_account", default=None)
ctx_game: ContextVar[int | None] = ContextVar("log_game", default=None)
ctx_client: ContextVar[str | None] = ContextVar("log_client", default=None)
# 当前请求的账本：中间件进门时 set，路由里的 audit() 凭它找到 Journal
ctx_journal: ContextVar[Journal | None] = ContextVar("log_journal", default=None)

_PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)")
_BLOB_RE = re.compile(r"[0-9A-Za-z]{24,}")

# 按天文件名前缀（写读两侧单一源：Journal 写侧与 ops 读取口/CLI 查询都从这取，
# 文件名知识不散落两处）——app=运行流水 / audit=审计账本
APP_PREFIX = "app"
AUDIT_PREFIX = "audit"


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
    """客户端标签：微信小程序 UA 包含 miniProgram 时标记为 mp，其余为 web。"""
    return "mp" if "miniprogram" in ua.lower() else "web"


def audit(
    action: str,
    *,
    game_id: int | None = None,
    detail: str | None = None,
    account_id: int | None = None,
) -> None:
    """记录一笔审计日志：不在请求中或无 Journal 实例时静默忽略。account_id 由调用方显式传入。"""
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
        """启动标记行：写入一条启动日志，并触发检查日志文件的按天轮转与历史清理。"""
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
        """访问流水：HTTP 状态码 ≥400 记为 warn 警告，正常响应记为 info。"""
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
        self._app = open(  # noqa: SIM115
            self._dir / f"{APP_PREFIX}-{day}.log", "a", encoding="utf-8"
        )
        self._audit = open(  # noqa: SIM115
            self._dir / f"{AUDIT_PREFIX}-{day}.log", "a", encoding="utf-8"
        )
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
        for prefix in (APP_PREFIX, AUDIT_PREFIX):
            for f in self._dir.glob(f"{prefix}-*.log"):
                d = f.stem.rsplit("-", 1)[-1]
                if len(d) == 8 and d.isdigit() and d <= cutoff:
                    try:
                        f.unlink()
                    except OSError:
                        pass


_HEARTBEAT_RE = re.compile(r"^/api/games/\d+/live$")
# 局号路径：/api/games/7（详情）与 /api/games/7/live/... 都认；
# /api/games（列表）与 /api/intents（局号在体里）不认——路径是唯一可靠来源
_GAME_PATH_RE = re.compile(r"^/api/games/(\d+)(?:/|$)")


def game_from_path(path: str) -> int | None:
    """从 HTTP 路径认局号：行头 g= 由此而来（路径没有就 None，不瞎认）。"""
    m = _GAME_PATH_RE.match(path)
    return int(m.group(1)) if m else None


class AccessLogMiddleware(BaseHTTPMiddleware):
    """计时中间件：心跳 200 静默；耗时超过阈值记慢请求警告；≥400 记失败警告；其余记访问流水。"""

    def __init__(self, app, journal: Journal, slow_ms: int = 1000) -> None:
        super().__init__(app)
        self.journal = journal
        self.slow_ms = slow_ms

    async def dispatch(self, request: Request, call_next):
        start = perf_counter()
        client = _client_label(request.headers.get("user-agent", ""))
        try:
            ctx_client.set(client)  # 向下可见：路由里的 audit()/日志行自带端标签
            gid = game_from_path(request.url.path)
            if gid is not None:
                # 本请求的失败行/慢行与兜底 error 行的 g=（同任务向下可见，
                # internal_error_handler 与 ctx_journal 同机制读得到）
                ctx_game.set(gid)
            ctx_journal.set(self.journal)
            response = await call_next(request)
        except Exception:
            # call_next 单独 try：这里冒出来的都是路由侧异常——经 _record 补一行失败
            # 流水（自带操作人/慢判断）后原样交回框架，不吞业务异常（spec 4.7）
            self._record(request, 500, round((perf_counter() - start) * 1000), client)
            raise
        self._record(
            request,
            response.status_code,
            round((perf_counter() - start) * 1000),
            client,
        )
        return response

    def _record(self, request: Request, status: int, ms: int, client: str) -> None:
        """记一行流水，内部包死不外抛——日志侧任何故障不击穿中间件（spec 4.7）。"""
        try:
            method, path = request.method, request.url.path
            # deps 镜像到共享 request.state 的操作人（contextvars 拷贝回不到中间件，见模块头）
            who = getattr(request.state, "log_account", None)
            if ms > self.slow_ms:
                self.journal.slow(
                    method, path, status, ms, account_id=who, client=client
                )
            elif method == "GET" and _HEARTBEAT_RE.match(path) and status < 400:
                return  # 心跳静默：现场页正常刷新一个字不写（spec 4.5）
            else:
                self.journal.access(
                    method, path, status, ms, account_id=who, client=client
                )
        except Exception:  # noqa: S110, BLE001 —— 这里除了吞掉没有可做的事情
            pass


def new_error_id() -> str:
    """错误号（spec 术语表）：「ERR-」+ uuid4 前 6 位 hex ≈ 24bit，生日界约四千次不撞，自用量级安全。"""
    return "ERR-" + uuid.uuid4().hex[:6]


async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """意外错误兜底（spec 4.1）：按号记完整 traceback——批4 的按号查错直达这一行；
    回 500 错误体带号。main.py 注册为 app 级 Exception handler，ApiError 走自己的
    handler 不进这里（业务错误不带号）。ctx_journal/ctx_game 由中间件进门 set、
    ServerErrorMiddleware 的兜底调用与其同任务，读得到（见模块头 contextvars 机制）。"""
    error_id = new_error_id()
    j = ctx_journal.get()
    if j is not None:  # 没账本就不记，兜底响应本身绝不依赖日志成败（spec 4.7）
        gid = game_from_path(
            request.url.path
        )  # g= 从路径认（中间件已 set，此处兜同样值）
        if gid is not None:
            ctx_game.set(gid)
        j.line(
            "error",
            f"{error_id} {request.method} {request.url.path}\n"
            + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            account_id=getattr(request.state, "log_account", None),
        )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "出错了，请稍后再试",
                "error_id": error_id,
            }
        },
    )
