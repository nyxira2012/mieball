"""manage_users 跨端绑定记号三动作（1.10 4.13/C2 运维口）——本地直连模式走真
SQLite 临时库：--cross-flags 两号各一行全列出、--clear-flags 双向清、
--move-mp-key 钥匙三列搬家（to 被覆盖、from 清空）连带清两号记号、来源无
小程序钥匙报错退出非零。

跑法：cd backend && python -m pytest scripts/tests/test_manage_users_flags.py -q
"""

from __future__ import annotations

import importlib.util
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[2]
# 本目录无 conftest 挂 backend 到 sys.path（tests/ 包那套不覆盖这里）
sys.path.insert(0, str(BACKEND_DIR))

from app.core.clock import CN_TZ, wall
from app.db.models import Account, Base, WechatCrossFlag

PHONE_A = "13800001234"
PHONE_B = "13900005678"
# 库内时间契约是 naive 北京墙钟——用 wall() 把带时区的定值落成 naive 再入库
FOUND_AT = wall(datetime(2026, 10, 25, 21, 0, 0, tzinfo=CN_TZ))


def _load_tool():
    spec = importlib.util.spec_from_file_location(
        "manage_users_under_test", BACKEND_DIR / "scripts" / "manage_users.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def db(tmp_path, monkeypatch):
    """真表库：甲号持小程序钥匙三件、甲乙互指两行记号（4.13 的人工处理现场）。
    建号走 ORM（列真值跟模型走），库址经 MIEBALL_MANAGE_DB 改指 tmp 库。"""
    path = tmp_path / "ops.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Account(
                id=1,
                phone=PHONE_A,
                nickname="阿甲",
                device_marker="ops-tool",
                created_at=datetime(2026, 10, 1, 10, 0, 0, tzinfo=timezone.utc),
                wechat_mp_openid="mp-openid-a",
                wechat_mp_bound_at=wall(datetime(2026, 10, 20, 12, 0, 0, tzinfo=CN_TZ)),
                wechat_unionid="union-x",
            )
        )
        session.add(
            Account(
                id=2,
                phone=PHONE_B,
                nickname="阿乙",
                device_marker="ops-tool",
                created_at=datetime(2026, 10, 2, 10, 0, 0, tzinfo=timezone.utc),
            )
        )
        session.add(
            WechatCrossFlag(account_id=1, other_account_id=2, found_at=FOUND_AT)
        )
        session.add(
            WechatCrossFlag(account_id=2, other_account_id=1, found_at=FOUND_AT)
        )
        session.commit()
    engine.dispose()
    monkeypatch.setenv("MIEBALL_MANAGE_DB", str(path))
    return path


def flags_of(path) -> list[tuple]:
    con = sqlite3.connect(path)
    rows = con.execute(
        "SELECT account_id, other_account_id FROM wechat_cross_flags ORDER BY id"
    ).fetchall()
    con.close()
    return rows


def mp_cols(path, uid: int) -> tuple:
    con = sqlite3.connect(path)
    row = con.execute(
        "SELECT wechat_mp_openid, wechat_mp_bound_at, wechat_unionid"
        " FROM accounts WHERE id = ?",
        (uid,),
    ).fetchone()
    con.close()
    return row


def run_cli(db, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(BACKEND_DIR / "scripts" / "manage_users.py"),
            "--local",
            *args,
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "MIEBALL_MANAGE_DB": str(db)},
        check=False,
    )


def test_cross_flags_lists_both_rows_and_cli_echo(db):
    tool = _load_tool()
    res = tool.run_local("cross_flags")
    assert res["success"] is True
    by_acc = {f["account_id"]: f for f in res["flags"]}
    assert set(by_acc) == {1, 2}  # 一对冲突两号各一行
    assert by_acc[1]["nickname"] == "阿甲"
    assert by_acc[1]["other_account_id"] == 2 and by_acc[1]["other_nickname"] == "阿乙"
    assert by_acc[2]["other_account_id"] == 1 and by_acc[2]["other_nickname"] == "阿甲"
    assert by_acc[1]["found_at"]
    # CLI 壳端到端：人类可读表照出
    r = run_cli(db, "--cross-flags")
    assert r.returncode == 0, r.stderr
    assert "共 2 条" in r.stdout and "阿甲" in r.stdout and "阿乙" in r.stdout


def test_clear_flags_clears_both_directions(db):
    tool = _load_tool()
    res = tool.run_local("clear_flags", "1")
    assert res["success"] is True and res["cleared"] == 2
    assert flags_of(db) == []  # 只报一侧账号、两侧两行全清
    assert tool.run_local("cross_flags")["flags"] == []


def test_move_mp_key_moves_columns_and_clears_flags(db):
    tool = _load_tool()
    res = tool.run_local("move_mp_key", "1", "2")
    assert res["success"] is True
    assert res["openid"] == "mp-openid-a" and res["unionid"] == "union-x"
    assert mp_cols(db, 1) == (None, None, None)  # from 三列清空
    oid, bound_at, unionid = mp_cols(db, 2)  # to 被来源值覆盖
    assert oid == "mp-openid-a" and unionid == "union-x"
    assert bound_at is not None and bound_at.startswith("2026-10-20 12:00:00")
    assert flags_of(db) == []  # 两号记号连带清


def test_move_mp_key_requires_source_key_exits_nonzero(db):
    tool = _load_tool()
    res = tool.run_local("move_mp_key", "2", "1")  # 乙号从没绑过小程序
    assert "没有小程序钥匙" in res["error"]
    assert mp_cols(db, 1)[0] == "mp-openid-a"  # 拒搬不动库
    r = run_cli(db, "--move-mp-key", "2", "1")
    assert r.returncode != 0 and "搬钥匙失败" in r.stdout
