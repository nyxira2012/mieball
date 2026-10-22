"""mieball 后端入口 —— create_app 工厂（测试用独立 Settings 各建各的 app）。

账号域（docs/1.1）路由挂在 /api 下；球局等后续业务按规格另行加路由文件，
不要往本文件堆业务。
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text

from .api.routes import auth, bills, games, intents, live, logs, stats, users, wechat
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
        # 直接开场来源旗（plan|direct）：散场无痕分支的判据
        "source": "VARCHAR(8) NOT NULL DEFAULT 'plan'",
    },
    # 2.3 批3：管理员名单/战报事件句/场地片数（JSON 列补齐要带字面默认值，存量行不吃 ORM default）
    "live_state": {
        "admins": "JSON DEFAULT '[]'",
        "feed": "JSON DEFAULT '[]'",
        "courts_count": "INTEGER NOT NULL DEFAULT 2",
        # 2.5 批1：开账人（可空——旧账没有这笔记录）
        "started_by": "INTEGER",
        # 2.9 批1：排位引擎两列（轮转批次盖 wait_batch 用 / 上限手动记号）
        "rotation_batch": "INTEGER NOT NULL DEFAULT 0",
        "streak_manual": "BOOLEAN NOT NULL DEFAULT 0",
    },
    # 2.6 批1：片分制快照（在打片照旧旧制、新开片用新制——开赛定格 game.scoring）
    "live_courts": {
        "scoring": "INTEGER NOT NULL DEFAULT 11",
    },
    # 2.8 批1：上场章（落位时刻的总号；存量行 NULL=没盖过章、资历序按最新并列）
    "live_players": {
        "court_mark": "INTEGER",
        # 2.9 批1：排位引擎两列（连打场数 / 进场下那一刻的批次章）
        "streak": "INTEGER NOT NULL DEFAULT 0",
        "wait_batch": "INTEGER NOT NULL DEFAULT 0",
    },
    # 1.6 批1：密码钥匙四列（暗记/连错计数/锁/设密宽限窗，存量行不带密码）
    "accounts": {
        "password_hash": "VARCHAR(128)",
        "pwd_fail_count": "INTEGER NOT NULL DEFAULT 0",
        "pwd_locked_until": "DATETIME",
        "pwd_grace_until": "DATETIME",
        # 1.7 批1：微信钥匙登记位三列（存量行未绑；唯一性走 _ENSURE_INDEXES——
        # SQLite 的 ALTER ADD COLUMN 加不了 UNIQUE 约束）
        "wechat_openid": "VARCHAR(64)",
        "wechat_verified": "BOOLEAN NOT NULL DEFAULT 0",
        "wechat_bound_at": "DATETIME",
        # 装扮账本四列：存量库自动补列（穿戴/解锁清单/微信头像；存量行 NULL=
        # 默认公共款兜底，零迁移——读侧见 services/cosmetics.py）
        "dress_avatar": "TEXT",
        "dress_back": "TEXT",
        "unlocks": "TEXT",
        "wechat_avatar": "TEXT",
    },
    # 6.1 批5：规则版本记号（明细/账单落账时的口径版本，值见 dupr.RULES_VERSION
    # 与 bills.SPLIT_VERSION；存量行 NULL=不回填——旧数据按当时的规矩算的不追认）
    "dupr_details": {"rule_version": "VARCHAR(8)"},
    "bills": {"rule_version": "VARCHAR(8)"},
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


# 存量表补建索引（create_all 对已存在的表不建其索引；ALTER ADD COLUMN 又带不了
# UNIQUE）——一律 IF NOT EXISTS，新库老库空转无害。1.7 批1：微信登记位唯一索引
_ENSURE_INDEXES = (
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_accounts_wechat_openid ON accounts (wechat_openid)",
)


# 已从模型退役、但存量库可能还挂着的旧列（与 _NEW_COLUMNS 对偶的删列登记）。
# create_all 不会删除已有表中的旧列；如果旧列带有 NOT NULL 约束且新代码不再写入，
# 会导致首次 INSERT 触发 IntegrityError。清理逻辑借道表重建
# （改名 → 按新模型建表 → 复制交集列 → 删旧表），兼容各版本 SQLite 内核。
_DROPPED_COLUMNS = {
    # 记分本地化：比分仅保留在各手机本地内存，数据库片行不再持久化进行中比分
    "live_courts": ("sa", "sb", "last_winner_side", "pending_origin"),
    # 账号起步分统一为 2.5，清理不再使用的自评列
    "accounts": ("self_rating",),
}


def _drop_legacy_columns(bind) -> None:
    inspector = inspect(bind)
    for table, dropped in _DROPPED_COLUMNS.items():
        if table not in inspector.get_table_names():
            continue
        present = {c["name"] for c in inspector.get_columns(table)}
        legacy = [c for c in dropped if c in present]
        if not legacy:
            continue  # 新库直建无旧列，空转
        model_cols = set(Base.metadata.tables[table].columns.keys())
        keep = sorted((present - set(legacy)) & model_cols)
        collist = ", ".join(keep)
        with bind.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} RENAME TO {table}_legacy_drop"))
        Base.metadata.tables[table].create(bind, checkfirst=False)
        with bind.begin() as conn:
            if keep:
                conn.execute(
                    text(
                        f"INSERT INTO {table} ({collist}) "
                        f"SELECT {collist} FROM {table}_legacy_drop"
                    )
                )
            conn.execute(text(f"DROP TABLE {table}_legacy_drop"))


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    factory = make_session_factory(settings.db_url)
    # 启动时建表并补齐/清理列，暂不引入外部迁移工具
    bind = factory.kw["bind"]
    Base.metadata.create_all(bind)
    _migrate_columns(bind)
    _drop_legacy_columns(bind)
    with bind.begin() as conn:
        for stmt in _ENSURE_INDEXES:
            conn.execute(text(stmt))

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
    app.include_router(logs.router, prefix="/api")  # ops 读取口（6.1 批4）
    app.include_router(wechat.router, prefix="/api")

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
