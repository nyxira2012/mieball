"""引擎与会话 —— create_app 时按 Settings 建引擎并挂到 app.state，依赖注入取用；
测试用内存库各自建 app，互不串库。"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def make_session_factory(db_url: str) -> sessionmaker[Session]:
    engine = create_engine(
        db_url,
        # FastAPI 同步端点跑线程池，SQLite 需放开同线程限制（单进程小并发，够用）
        connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {},
    )
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
