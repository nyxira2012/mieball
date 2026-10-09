"""mieball 后端入口 —— create_app 工厂（测试用独立 Settings 各建各的 app）。

账号域（docs/1.1）路由挂在 /api 下；球局等后续业务按规格另行加路由文件，
不要往本文件堆业务。
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text

from .api.routes import auth, bills, games, intents, live, stats, users
from .core.config import Settings, get_settings
from .core.errors import ApiError
from .core.logs import AccessLogMiddleware, Journal, internal_error_handler
from .db.engine import Base, make_session_factory

API_VERSION = "0.2.0"

# 不引 Alembic 期间的列级补齐：create_all 只建缺表不补缺列，结构变更在此登记
# （SQLite 支持加列；新库由 create_all 直建、此表为空转）
_NEW_COLUMNS = {
    "games": {
        "terminated_at": "DATETIME",
        "cancelled_at": "DATETIME",
        "ended_at": "DATETIME",
    },
    # 2.3 批3：管理员名单/战报事件句/场地片数（JSON 列补齐要带字面默认值，存量行不吃 ORM default）
    "live_state": {
        "admins": "JSON DEFAULT '[]'",
        "feed": "JSON DEFAULT '[]'",
        "courts_count": "INTEGER NOT NULL DEFAULT 2",
        # 2.5 批1：开账人（可空——旧账没有这笔记录）
        "started_by": "INTEGER",
    },
    # 2.6 批1：片分制快照（在打片照旧旧制、新开片用新制——开赛定格 game.scoring）
    "live_courts": {
        "scoring": "INTEGER NOT NULL DEFAULT 11",
    },
    # 1.6 批1：密码钥匙四列（暗记/连错计数/锁/设密宽限窗，存量行不带密码）
    "accounts": {
        "password_hash": "VARCHAR(128)",
        "pwd_fail_count": "INTEGER NOT NULL DEFAULT 0",
        "pwd_locked_until": "DATETIME",
        "pwd_grace_until": "DATETIME",
    },
}


def _migrate_columns(bind) -> None:
    inspector = inspect(bind)
    todo = []
    for table, columns in _NEW_COLUMNS.items():
        if table not in inspector.get_table_names():
            continue
        present = {c["name"] for c in inspector.get_columns(table)}
        todo += [
            f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"
            for name, ddl in columns.items()
            if name not in present
        ]
    if todo:
        with bind.begin() as conn:
            for stmt in todo:
                conn.execute(text(stmt))


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    factory = make_session_factory(settings.db_url)
    # 第一版不引 Alembic：启动时建表 + 列级补齐；后续结构大了再上迁移（docs/1.1 §B 量级下够用）
    bind = factory.kw["bind"]
    Base.metadata.create_all(bind)
    _migrate_columns(bind)

    app = FastAPI(title="mieball API", version=API_VERSION)
    app.state.settings = settings
    app.state.session_factory = factory

    # 访问日志挂最内层（先 add=最里）：CORS 预检在外层短路，不产生流水（spec 4.5 不添堵）
    journal = Journal(settings.log_dir, keep_days=settings.keep_days)
    app.add_middleware(AccessLogMiddleware, journal=journal, slow_ms=settings.slow_ms)

    # 开发期全放开：前端 12543 与手机真机（微信内 H5 走局域网 IP）都要能直连；上线收紧
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 启动补做一次切换+清理检查，顺带留一行启动记号（spec 4.8 停机补做 / 4.10 启动几行）
    journal.startup(f"service start v{API_VERSION}")

    @app.exception_handler(ApiError)
    async def on_api_error(_: Request, exc: ApiError) -> JSONResponse:
        content = {"error": {"code": exc.code, "message": str(exc.detail)}}
        if exc.view is not None:  # 两级号 409 携最新总账视图（2.3 附录 B1）
            content["view"] = exc.view
        return JSONResponse(status_code=exc.status_code, content=content)

    # 意外错误兜底（6.1 spec 4.1）：500 错误体带 error_id，注册即对全部路由生效
    app.add_exception_handler(Exception, internal_error_handler)

    app.include_router(auth.router, prefix="/api")
    app.include_router(users.router, prefix="/api")
    app.include_router(games.router, prefix="/api")
    app.include_router(intents.router, prefix="/api")
    app.include_router(live.router, prefix="/api")
    app.include_router(bills.router, prefix="/api")
    app.include_router(stats.router, prefix="/api")

    @app.get("/")
    def root():
        return {
            "service": "mieball-backend",
            "version": API_VERSION,
            "docs": "/docs",
            "health": "/api/health",
        }

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
