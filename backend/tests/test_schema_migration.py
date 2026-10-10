"""启动清障：存量库退役列的删列迁移（2026-10-10 生产事故回归）。

事故：生产库 live_courts 建于 10-08（含 sa/sb NOT NULL 记分列），10-09 记分
本地化从模型删了四列（sa/sb/last_winner_side/pending_origin），create_all
不改旧表——发牌首次 INSERT 片行不带 sa → IntegrityError「NOT NULL constraint
failed: live_courts.sa」→ 该局所有 deal 500（前端看着「排阵成功又突然取消」）。
main._drop_legacy_columns 启动时借道重建清掉退役列；本册锁三件事：旧列已清、
历史行无损搬入新表、事故路径（建局→签到→发牌）全链复活。
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from app.core.config import Settings
from app.db.engine import Base
from app.main import create_app
from tests.conftest import FakeClock, signup
from tests.test_games_actions import join_ok
from tests.test_games_read import publish
from tests.test_live_score import live_call, lock_game_direct

# 生产库实测的旧表形状（10-08 版：有 2.6 的 scoring、也有记分本地化前的四列）
_LEGACY_DDL = """
CREATE TABLE live_courts (
    id INTEGER NOT NULL PRIMARY KEY,
    game_id INTEGER NOT NULL,
    court_no INTEGER NOT NULL,
    status VARCHAR(8) NOT NULL,
    seq INTEGER NOT NULL,
    court_seq INTEGER NOT NULL,
    scoring INTEGER NOT NULL DEFAULT 11,
    sa INTEGER NOT NULL,
    sb INTEGER NOT NULL,
    last_winner_side VARCHAR(1),
    pending_origin VARCHAR(6)
)
"""


def _legacy_db(tmp_path) -> str:
    """预置一张带退役列的存量 live_courts + 一行历史片行。"""
    db = tmp_path / "legacy.db"
    eng = create_engine(f"sqlite:///{db}")
    with eng.begin() as c:
        c.execute(text(_LEGACY_DDL))
        # 历史局残留行：idle 片、打过 2 场（搬迁后 seq/court_seq/scoring 必须原样）
        c.execute(
            text(
                "INSERT INTO live_courts "
                "(id, game_id, court_no, status, seq, court_seq, scoring, sa, sb) "
                "VALUES (1, 99, 1, 'idle', 2, 2, 15, 11, 9)"
            )
        )
    eng.dispose()
    return f"sqlite:///{db}"


def test_drop_legacy_columns_and_keep_history(tmp_path, fake: FakeClock, monkeypatch):
    db_url = _legacy_db(tmp_path)
    create_app(
        Settings(db_url=db_url, pepper="p", sms_provider="console", sms_daily_budget=50)
    )

    eng = create_engine(db_url)
    try:
        cols = {c["name"] for c in inspect(eng).get_columns("live_courts")}
        model_cols = set(Base.metadata.tables["live_courts"].columns.keys())
        assert cols == model_cols  # 退役四列已清、模型列齐
        assert not {"sa", "sb", "last_winner_side", "pending_origin"} & cols
        with eng.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT game_id, court_no, status, seq, court_seq, scoring "
                    "FROM live_courts WHERE id = 1"
                )
            ).fetchone()
        assert tuple(row) == (99, 1, "idle", 2, 2, 15)  # 历史行无损搬入
        assert inspect(eng).get_table_names().count("live_courts") == 1
        assert "live_courts_legacy_drop" not in inspect(eng).get_table_names()
    finally:
        eng.dispose()


def test_deal_on_legacy_schema_revives(tmp_path, fake: FakeClock, monkeypatch):
    """事故路径回归：存量旧表上开账→签到→发牌全链 200（修复前 deal 必 500）。"""
    db_url = _legacy_db(tmp_path)
    app = create_app(
        Settings(db_url=db_url, pepper="p", sms_provider="console", sms_daily_budget=50)
    )
    c = TestClient(app)

    org = signup(c, "13800046001", "o")
    mates = [signup(c, f"1380004600{i}", f"p{i}") for i in range(2, 6)]
    g = publish(c, org["token"], visibility="public", max_players=6)
    for u in mates:
        join_ok(c, u["token"], g["id"])
    lock_game_direct(c, g["id"])
    r = live_call(c, org["token"], g["id"], "start", {})
    assert r.status_code == 200, r.text
    v = r.json()
    for p in v["players"]:
        r = live_call(
            c,
            org["token"],
            g["id"],
            "check",
            {"player_id": p["id"], "check": "ok", "base_total_seq": v["total_seq"]},
        )
        assert r.status_code == 200, r.text
        v = r.json()
    q = v["queue"]
    r = live_call(
        c,
        org["token"],
        g["id"],
        "deal",
        {
            "courts": [{"court_no": 1, "a": q[:2], "b": q[2:4]}],
            "base_total_seq": v["total_seq"],
        },
    )
    assert r.status_code == 200, r.text  # 事故现场：这条曾是 500 八连
    assert (
        next(x for x in r.json()["courts"] if x["court_no"] == 1)["status"] == "playing"
    )


def test_drop_self_rating_keeps_accounts(tmp_path, fake: FakeClock, monkeypatch):
    """二段启动版：先按现行模型建库、立真账号，再手工加回自评列模拟旧库演进
    （生产实测 2026-10-10：accounts 只多 self_rating 一列）——二次启动清障后
    列清、账号与登录钥匙无损；三次启动幂等空转。"""
    db = tmp_path / "acct.db"
    url = f"sqlite:///{db}"
    app = create_app(
        Settings(db_url=url, pepper="p", sms_provider="console", sms_daily_budget=50)
    )
    signup(TestClient(app), "13800047001", "o")

    eng = create_engine(url)
    try:
        with eng.begin() as c:
            c.execute(text("ALTER TABLE accounts ADD COLUMN self_rating FLOAT"))
        assert "self_rating" in {
            x["name"] for x in inspect(eng).get_columns("accounts")
        }
    finally:
        eng.dispose()

    create_app(
        Settings(db_url=url, pepper="p", sms_provider="console", sms_daily_budget=50)
    )
    eng = create_engine(url)
    try:
        cols = {x["name"] for x in inspect(eng).get_columns("accounts")}
        assert "self_rating" not in cols
        assert "phone" in cols  # 模型列与 UNIQUE 约束随重建按模型落齐
        row = (
            eng.connect().execute(text("SELECT phone FROM accounts LIMIT 1")).fetchone()
        )
        assert row is not None  # 账号数据无损
    finally:
        eng.dispose()

    create_app(
        Settings(db_url=url, pepper="p", sms_provider="console", sms_daily_budget=50)
    )  # 幂等空转
