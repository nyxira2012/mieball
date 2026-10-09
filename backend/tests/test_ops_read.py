"""6.1 批4【读取口+快捷指令】锁（docs/6.1 §4.2/§4.3/§4.9/§4.10 / 技术设计 §1.4、§6）：
钥匙三态（没配=口子关着 / 不对 / 对）、按球局拉审计（升序、空 note、缺参 422）、
按错误号捞现场（带上下文整段、查无客气话）、CLI 冒烟（不启服务直接翻文件）。

夹具自足（不动 conftest）：复用 test_logs 的 make_client/auth，ops_key 经
make_client(**over) 注入。
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.core import clock, logs

from .conftest import signup
from .test_games_actions import join_ok
from .test_games_read import publish
from .test_logs import app_log, make_client

OPS = {"X-Ops-Key": "k1"}


# ---- 钥匙三态（技术设计 §1.4：OPS_KEY 空=读取口关闭）----


def test_gate_off_when_unconfigured(tmp_path):
    client = make_client(tmp_path)  # ops_key 默认空 → 口子整个关着
    r = client.get("/api/ops/audit?game_id=1")
    assert r.status_code == 403 and r.json()["error"]["code"] == "ops_key_off"
    r = client.get("/api/ops/errors?error_id=ERR-aaaaaa")
    assert r.status_code == 403 and r.json()["error"]["code"] == "ops_key_off"


def test_gate_wrong_key(tmp_path):
    client = make_client(tmp_path, ops_key="k1")
    r = client.get("/api/ops/audit?game_id=1", headers={"X-Ops-Key": "wrong"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "ops_key_wrong"
    r = client.get("/api/ops/errors?error_id=ERR-aaaaaa")  # 没带也一样拒
    assert r.status_code == 403 and r.json()["error"]["code"] == "ops_key_wrong"


# ---- 按球局拉审计 ----


def test_audit_by_game_ascending(tmp_path):
    client = make_client(tmp_path, ops_key="k1")
    org = signup(client, "13800000001", "o")
    mate = signup(client, "13800000002", "m")
    now = clock.now()
    g = publish(
        client,
        org["token"],
        visibility="public",
        start_at=clock.iso(now + timedelta(hours=2)),
        end_at=clock.iso(now + timedelta(hours=4)),
        deadline_at=clock.iso(now + timedelta(hours=1)),
    )
    join_ok(client, mate["token"], g["id"])

    r = client.get(f"/api/ops/audit?game_id={g['id']}", headers=OPS)
    assert r.status_code == 200, r.text
    events = r.json()["events"]
    actions = [e["action"] for e in events]
    assert "publish_game" in actions and "join_game" in actions
    ats = [e["at"] for e in events]
    assert ats == sorted(ats)  # 时间升序（spec 4.11 组织者回看顺序）
    assert all(e["game_id"] == g["id"] for e in events)  # 只含这个局


def test_audit_empty_and_missing_param(tmp_path):
    client = make_client(tmp_path, ops_key="k1")
    r = client.get("/api/ops/audit?game_id=999999", headers=OPS)
    assert r.json() == {"events": [], "note": "没有记录"}
    assert client.get("/api/ops/audit", headers=OPS).status_code == 422  # 缺参自动


# ---- 按错误号捞现场 ----


def test_error_by_id_with_context(tmp_path):
    client = make_client(tmp_path, ops_key="k1")

    @client.app.get("/api/boom")  # 临时测试路由（沿 test_logs 惯例）
    def boom():
        raise RuntimeError("炸了")

    crash = TestClient(client.app, raise_server_exceptions=False)
    r = crash.get("/api/boom")
    error_id = r.json()["error"]["error_id"]

    r = client.get(f"/api/ops/errors?error_id={error_id}", headers=OPS)
    body = r.json()
    assert body["found"] is True
    text = "\n".join(body["lines"])
    # 命中行向前 2 行 + 向后整段到下一条记录首行：traceback 是不带行头的多行
    # 续体——整段案发现场直接带出（异常末行也在），不被 ±2 截断
    assert error_id in text and "Traceback (most recent call last):" in text
    assert "炸了" in text  # 异常末行（RuntimeError: 炸了）也带出来了
    assert len(body["lines"]) > 3  # 不止命中一行：真带上下文


def test_error_not_found_note(tmp_path):
    client = make_client(tmp_path, ops_key="k1")
    r = client.get("/api/ops/errors?error_id=ERR-zzzzzz", headers=OPS)
    assert r.json() == {
        "found": False,
        "note": "没有这个编号：可能抄错了、已过 14 天销毁、或当时没写成",
    }


def test_error_line_carries_game_from_path(tmp_path):
    """g= 从路径认局号（B4）：错误行/失败行的行头不再恒 "-"。"""
    client = make_client(tmp_path, ops_key="k1")

    @client.app.get("/api/games/{game_id}/boom")  # 临时测试路由（沿 test_logs 惯例）
    def boom(game_id: int):
        raise RuntimeError("又炸了")

    crash = TestClient(client.app, raise_server_exceptions=False)
    r = crash.get("/api/games/9/boom")
    error_id = r.json()["error"]["error_id"]
    client.get("/api/games/9/nope")  # 404 → 中间件失败行（同路径也该带 g=9）

    r = client.get(f"/api/ops/errors?error_id={error_id}", headers=OPS)
    text = "\n".join(r.json()["lines"])
    assert "g=9" in text  # 兜底 error 行的行头
    assert "g=9" in app_log(tmp_path / "logs")  # 中间件失败行（access 404）的行头


# ---- keep_days 窗口边界（读取窗口与 §4.8 清理线对齐）----


def test_keep_days_window_edges(tmp_path):
    """13 天前的文件还在窗口内可读，15 天前的不再读（keep_days=14：含今天往前数）。"""
    client = make_client(tmp_path, ops_key="k1")
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(exist_ok=True)  # create_app 挂 Journal 时已顺手建过

    def day(n: int) -> str:  # n 天前的文件名日期
        return (
            datetime.strptime(logs.today(), "%Y%m%d")  # noqa: DTZ007 —— 纯文件名日期算术
            - timedelta(days=n)
        ).strftime("%Y%m%d")

    (logs_dir / f"audit-{day(13)}.log").write_text(
        '{"at":"2026-10-01T10:00:00+08:00","action":"publish_game",'
        '"account_id":1,"game_id":101,"detail":null}\n',
        encoding="utf-8",
    )
    (logs_dir / f"audit-{day(15)}.log").write_text(
        '{"at":"2026-09-29T10:00:00+08:00","action":"publish_game",'
        '"account_id":1,"game_id":102,"detail":null}\n',
        encoding="utf-8",
    )
    (logs_dir / f"app-{day(13)}.log").write_text(
        "2026-10-01T10:00:00.000+08:00 [error] (u=- g=101 c=web) ERR-old13 boom\n",
        encoding="utf-8",
    )
    (logs_dir / f"app-{day(15)}.log").write_text(
        "2026-09-29T10:00:00.000+08:00 [error] (u=- g=102 c=web) ERR-old15 boom\n",
        encoding="utf-8",
    )

    assert client.get("/api/ops/audit?game_id=101", headers=OPS).json()["events"]
    assert client.get("/api/ops/audit?game_id=102", headers=OPS).json() == {
        "events": [],
        "note": "没有记录",
    }
    assert (
        client.get("/api/ops/errors?error_id=ERR-old13", headers=OPS).json()["found"]
        is True
    )
    assert (
        client.get("/api/ops/errors?error_id=ERR-old15", headers=OPS).json()["found"]
        is False
    )


# ---- CLI 冒烟（不启服务；慢就删——快审优先）----


def test_cli_smoke(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    today = logs.today()
    # 案发现场：错误号行 + traceback 后续行 + 前后噪音，行头用真实格式
    # （时间戳+08:00 是记录界碑——向后带出整段 traceback，噪音下一行不带出）
    (logs_dir / f"app-{today}.log").write_text(
        "噪音上一行\n"
        "2026-10-10T12:00:00.000+08:00 [error] (u=- g=- c=web) ERR-abc123 GET /api/boom\n"
        "Traceback (most recent call last):\n"
        "RuntimeError: 炸了\n"
        "2026-10-10T12:00:01.000+08:00 [info] (u=- g=- c=web) access GET /api/x 200 5ms\n"
        "噪音下一行\n",
        encoding="utf-8",
    )
    hit = subprocess.run(
        [
            sys.executable,
            str(backend / "scripts/query_log.py"),
            "--err",
            "ERR-abc123",
            "--dir",
            str(logs_dir),
        ],
        capture_output=True,
        text=True,
        cwd=backend,
        check=False,
    )
    assert hit.returncode == 0, hit.stderr
    assert "ERR-abc123" in hit.stdout and "RuntimeError" in hit.stdout
    assert "噪音下一行" not in hit.stdout  # 下一条记录首行之后的不再带出
    assert "局 #" not in hit.stdout  # g=- 时不去翻审计（spec 4.2 顺带只在有局号时）

    miss = subprocess.run(
        [
            sys.executable,
            str(backend / "scripts/query_log.py"),
            "--game",
            "7",
            "--dir",
            str(logs_dir),
        ],
        capture_output=True,
        text=True,
        cwd=backend,
        check=False,
    )
    assert miss.returncode == 0, miss.stderr
    assert "没有审计记录" in miss.stdout


def test_cli_err_lists_same_game_events(tmp_path):
    """spec 4.2「顺带把同一个局的相关事件也列在一起」：命中行头 g= 有局号，
    CLI 把该局审计事件一并打印（HTTP 读取口不加——4.9 只承诺两条查询）。"""
    backend = Path(__file__).resolve().parents[1]
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / f"app-{logs.today()}.log").write_text(
        "2026-10-10T12:00:00.000+08:00 [error] (u=3 g=7 c=mp) ERR-xyz789 POST /api/games/7/live/score\n"
        "Traceback (most recent call last):\n"
        "RuntimeError: 现场炸了\n",
        encoding="utf-8",
    )
    (logs_dir / f"audit-{logs.today()}.log").write_text(
        '{"at":"2026-10-10T11:58:00+08:00","action":"live_score",'
        '"account_id":3,"game_id":7,"detail":"21:15"}\n',
        encoding="utf-8",
    )
    r = subprocess.run(
        [
            sys.executable,
            str(backend / "scripts/query_log.py"),
            "--err",
            "ERR-xyz789",
            "--dir",
            str(logs_dir),
        ],
        capture_output=True,
        text=True,
        cwd=backend,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    assert "RuntimeError: 现场炸了" in r.stdout
    assert "局 #7" in r.stdout and "live_score" in r.stdout  # 同局审计顺带列出
