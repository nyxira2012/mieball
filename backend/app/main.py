"""mieball 后端入口 —— create_app 工厂（测试用独立 Settings 各建各的 app）。

账号域（docs/1.1）路由挂在 /api 下；球局等后续业务按规格另行加路由文件，
不要往本文件堆业务。
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.routes import auth, users
from .core.config import Settings, get_settings
from .core.errors import ApiError
from .db.engine import Base, make_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    factory = make_session_factory(settings.db_url)
    # 第一版不引 Alembic：启动时建表；后续结构变了再上迁移（docs/1.1 §B 量级下够用）
    Base.metadata.create_all(factory.kw["bind"])

    app = FastAPI(title="mieball API", version="0.2.0")
    app.state.settings = settings
    app.state.session_factory = factory

    # 开发期全放开：前端 12543 与手机真机（微信内 H5 走局域网 IP）都要能直连；上线收紧
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ApiError)
    async def on_api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": str(exc.detail)}},
        )

    app.include_router(auth.router, prefix="/api")
    app.include_router(users.router, prefix="/api")

    @app.get("/")
    def root():
        return {
            "service": "mieball-backend",
            "version": "0.2.0",
            "docs": "/docs",
            "health": "/api/health",
        }

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
