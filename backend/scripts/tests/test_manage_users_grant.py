"""manage_users 发卡/收卡（1.9 §4.10 运维口）——本地直连模式走真 SQLite 临时库：
发放入库可见（直查 unlocks）、重复发幂等、不存在编号拒、荣誉款拒、--wear 顺手
穿上（头像/卡背按册子 kind 各写各列）、穿着时收回退各档默认（头像退头像的、
卡背退卡背的）、收没穿的不动穿戴、收荣誉款拒。

编号校验与默认款断言都吃后端册子单一源（app/services/cosmetics），不抄清单。

跑法：cd backend && python -m pytest scripts/tests/test_manage_users_grant.py -q
"""

from __future__ import annotations

import importlib.util
import json
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
# 本目录无 conftest 挂 backend 到 sys.path（tests/ 包那套不覆盖这里），册子常量自取
sys.path.insert(0, str(BACKEND_DIR))

from app.db.models import Account, Base
from app.services.cosmetics import DEFAULT_AVATAR, DEFAULT_BACK

PHONE = "13800001234"


def _load_tool():
    spec = importlib.util.spec_from_file_location(
        "manage_users_under_test", BACKEND_DIR / "scripts" / "manage_users.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def db(tmp_path, monkeypatch):
    """真表库——accounts 由 Base.metadata 建模建表（列真值跟模型走，不手抄
    第二份清单），建号走 ORM 让列默认兜住 NOT NULL；库址经 MIEBALL_MANAGE_DB
    改指 tmp 库（run_local 的测试钩子），绝不碰开发机真库。"""
    path = tmp_path / "ops.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Account(
                id=1,
                phone=PHONE,
                nickname="阿甲",
                device_marker="ops-tool",
                created_at=datetime(2026, 10, 1, 10, 0, 0, tzinfo=timezone.utc),
            )
        )
        session.commit()
    engine.dispose()
    monkeypatch.setenv("MIEBALL_MANAGE_DB", str(path))
    return path


def account_of(path) -> tuple[list[str], str | None, str | None]:
    """直查库：解锁清单（含 new 标原样）、头像穿戴、卡背穿戴。"""
    con = sqlite3.connect(path)
    row = con.execute(
        "SELECT unlocks, dress_avatar, dress_back FROM accounts WHERE id = 1"
    ).fetchone()
    con.close()
    rows = json.loads(row[0]) if row[0] else []
    return rows, row[1], row[2]


def test_grant_writes_unlocks_and_regrant_is_idempotent(db):
    tool = _load_tool()
    res = tool.run_local("grant", PHONE, "a-x1")
    assert res["success"] is True and res["already"] is False
    rows, _, _ = account_of(db)
    assert rows == [{"id": "a-x1", "new": True}]  # 入库可见，含「新」标
    # 幂等：重复发提示不发，清单不长第二行（首发行原样保留）
    res2 = tool.run_local("grant", "1", "a-x1")
    assert res2["success"] is True and res2["already"] is True
    assert account_of(db)[0] == rows


def test_grant_rejects_unknown_user_and_cid_and_non_custom_tiers(db):
    tool = _load_tool()
    assert "未找到目标用户" in tool.run_local("grant", "13900000000", "a-x1")["error"]
    assert "编号不存在" in tool.run_local("grant", PHONE, "a-nope")["error"]
    # 荣誉款进出只走达标核算；公共款人人可用无需发——一律只放定制款
    assert "荣誉款" in tool.run_local("grant", PHONE, "a-m5")["error"]
    assert "公共款" in tool.run_local("grant", PHONE, "b-c1")["error"]


def test_grant_wear_dresses_by_kind(db):
    tool = _load_tool()
    res = tool.run_local("grant", PHONE, "a-x1", "wear")
    assert res["worn"] is True
    _, avatar, back = account_of(db)
    assert avatar == "a-x1" and back is None  # 头像编号写头像列，不碰卡背
    tool.run_local("grant", PHONE, "b-x1", "wear")
    _, avatar, back = account_of(db)
    assert avatar == "a-x1" and back == "b-x1"


def test_revoke_while_wearing_restores_each_default(db):
    tool = _load_tool()
    tool.run_local("grant", PHONE, "a-x1", "wear")
    tool.run_local("grant", PHONE, "b-x1", "wear")
    # 收卡背：只退卡背默认，头像穿着不动（各退各的，互不影响）
    res = tool.run_local("revoke", PHONE, "b-x1")
    assert res["success"] is True and res["undressed"] is True
    rows, avatar, back = account_of(db)
    assert back == DEFAULT_BACK and avatar == "a-x1"
    assert [r["id"] for r in rows] == ["a-x1"]
    # 再收头像：头像退头像的默认
    tool.run_local("revoke", PHONE, "a-x1")
    rows, avatar, back = account_of(db)
    assert avatar == DEFAULT_AVATAR and back == DEFAULT_BACK
    assert rows == []


def test_revoke_unworn_keeps_dressing(db):
    tool = _load_tool()
    tool.run_local("grant", PHONE, "a-x1")  # 发而不穿
    tool.run_local("grant", PHONE, "b-x1", "wear")
    res = tool.run_local("revoke", PHONE, "a-x1")
    assert res["success"] is True and res["undressed"] is False
    rows, avatar, back = account_of(db)
    assert avatar is None and back == "b-x1"  # 穿戴原样不动
    assert [r["id"] for r in rows] == ["b-x1"]


def test_revoke_rejects_honor_tier(db):
    tool = _load_tool()
    assert "荣誉款" in tool.run_local("revoke", PHONE, "a-m5")["error"]
    rows, _, _ = account_of(db)
    assert rows == []  # 拒收不动库


def test_revoke_on_never_granted_null_unlocks(db):
    """收卡遇上 unlocks=NULL（新号从未被发过）：不崩、回话「其清单里本就没有」、
    库无变化。（曾崩点：worker 末段回显 json.loads(None) 抛 TypeError 不是
    ValueError，except 接不住——收口 parse_unlocks 后 NULL 走空清单 had=False。）"""
    tool = _load_tool()
    res = tool.run_local("revoke", PHONE, "a-x1")
    assert res["success"] is True and res["had"] is False
    assert res["undressed"] is False
    # 库无变化：直查断言 unlocks 仍 NULL、穿戴原样（不走 account_of 的容错兜底）
    con = sqlite3.connect(db)
    row = con.execute(
        "SELECT unlocks, dress_avatar, dress_back FROM accounts WHERE id = 1"
    ).fetchone()
    con.close()
    assert row == (None, None, None)
    # CLI 壳同链路端到端：零退出码 + 回话原文
    r = subprocess.run(
        [
            sys.executable,
            str(BACKEND_DIR / "scripts" / "manage_users.py"),
            "--local",
            "--revoke",
            "1",
            "--cid",
            "a-x1",
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "MIEBALL_MANAGE_DB": str(db)},
        check=False,
    )
    assert r.returncode == 0, r.stderr
    assert "其清单里本就没有" in r.stdout


def test_cli_grant_then_revoke_roundtrip(db):
    """CLI 壳端到端：--local -g/--wear 与 --revoke 成功路径零退出码——顺带锁住
    fail() 出口对成功回话必须放行（曾无守卫致成功后 KeyError 崩壳）。"""
    r = subprocess.run(
        [
            sys.executable,
            str(BACKEND_DIR / "scripts" / "manage_users.py"),
            "--local",
            "-g",
            PHONE,
            "--cid",
            "b-x1",
            "--wear",
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "MIEBALL_MANAGE_DB": str(db)},
        check=False,
    )
    assert r.returncode == 0, r.stderr
    assert "发卡成功" in r.stdout and "已顺手穿上" in r.stdout
    r = subprocess.run(
        [
            sys.executable,
            str(BACKEND_DIR / "scripts" / "manage_users.py"),
            "--local",
            "--revoke",
            "1",
            "--cid",
            "b-x1",
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "MIEBALL_MANAGE_DB": str(db)},
        check=False,
    )
    assert r.returncode == 0, r.stderr
    assert "收卡成功" in r.stdout and "已自动退回默认公共款" in r.stdout
    _, _, back = account_of(db)
    assert back == DEFAULT_BACK
