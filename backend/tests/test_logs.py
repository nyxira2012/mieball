"""6.1 批1【日志地基】锁：心跳静默 / 失败行 / 慢警告 / access 流水 / 14 天清理 /
缺口标记 / 脱敏 / 启动补清理（docs/6.1 §4.5、§4.7、§4.8、§4.10、§5）。

夹具自足（不动 conftest）：仿 conftest 的独立 Settings 建 app，log_dir 指到 tmp_path。
"""

from __future__ import annotations

import json
import time
from contextvars import ContextVar
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.core import clock, logs
from app.core.config import Settings
from app.core.logs import Journal, mask
from app.main import create_app

from .conftest import signup
from .test_games_read import publish


def make_client(tmp_path: Path, **over) -> TestClient:
    kw = {
        "db_url": f"sqlite:///{tmp_path}/test.db",
        "pepper": "test-pepper",
        "sms_provider": "console",
        "sms_daily_budget": 200,
        "log_dir": str(tmp_path / "logs"),
    } | over
    return TestClient(create_app(Settings(**kw)))


def app_log(logs_dir: Path) -> str:
    files = list(logs_dir.glob("app-*.log"))  # 文件名日期字典序=时间序
    assert files, "运行日志文件没建出来"
    return max(files).read_text(encoding="utf-8")


def audit_rows(logs_dir: Path) -> list[dict]:
    files = list(logs_dir.glob("audit-*.log"))
    assert files, "审计文件没建出来"
    return [
        json.loads(ln) for ln in max(files).read_text(encoding="utf-8").splitlines()
    ]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def heartbeat_game(client: TestClient) -> int:
    """发一个当天可开账的局并开账（锁必打即刻成局，不等截止），返回局号。"""
    token = signup(client, "13800000001", "d1")["token"]
    now = clock.now()
    game = publish(
        client,
        token,
        start_at=clock.iso(now + timedelta(hours=2)),
        end_at=clock.iso(now + timedelta(hours=4)),
        deadline_at=clock.iso(now + timedelta(hours=1)),
    )
    gid = game["id"]
    r = client.post(f"/api/games/{gid}/lock", headers=auth(token))
    assert r.status_code == 200, r.text
    r = client.post(f"/api/games/{gid}/live/start", headers=auth(token))
    assert r.status_code == 200, r.text
    return gid


# ---- 中间件行为（spec §4.5 心跳静默 / 慢警告 / 流水 / 失败行）----


def test_heartbeat_200_silent(tmp_path):
    logs_dir = tmp_path / "logs"
    client = make_client(tmp_path)
    gid = heartbeat_game(client)
    before = len(app_log(logs_dir).splitlines())
    for _ in range(3):
        r = client.get(f"/api/games/{gid}/live")
        assert r.status_code == 200, r.text
    # 现场页正常刷新一个字不写（spec 4.5）
    assert len(app_log(logs_dir).splitlines()) == before


def test_heartbeat_failure_recorded(tmp_path):
    logs_dir = tmp_path / "logs"
    client = make_client(tmp_path)
    r = client.get("/api/games/999999/live")
    assert r.status_code == 404
    text = app_log(logs_dir)
    # 心跳回应不正常 → 失败行：时间+球局+谁（u=- 游客）+耗时
    assert "[warn]" in text and "access GET /api/games/999999/live 404" in text


def test_normal_request_access_line(tmp_path):
    logs_dir = tmp_path / "logs"
    client = make_client(tmp_path)
    assert client.get("/api/health").status_code == 200
    text = app_log(logs_dir)
    assert "[info]" in text and "access GET /api/health 200" in text and "c=web" in text


def test_access_line_carries_account(tmp_path):
    logs_dir = tmp_path / "logs"
    client = make_client(tmp_path)
    token = signup(client, "13800000002", "d2")["token"]
    assert client.get("/api/auth/me", headers=auth(token)).status_code == 200
    # 谁做的操作：deps 解析成功 → u=<账号号>（spec B1 记操作人编号，不记手机号）
    assert "(u=1 g=- c=web)" in app_log(logs_dir)


def test_client_label_mp(tmp_path):
    logs_dir = tmp_path / "logs"
    client = make_client(tmp_path)
    client.get("/api/health", headers={"User-Agent": "MicroMessenger miniProgram/1.0"})
    assert "c=mp" in app_log(logs_dir)


def test_slow_warning(tmp_path):
    logs_dir = tmp_path / "logs"
    client = make_client(tmp_path, slow_ms=50)

    @client.app.get("/api/slowpoke")
    def slowpoke():
        time.sleep(0.2)
        return {"ok": True}

    assert client.get("/api/slowpoke").status_code == 200
    text = app_log(logs_dir)
    # 慢的那拍即使 200 也记警告、写明等了多久（spec 4.5），不重复流水行
    assert "[warn]" in text and "slow GET /api/slowpoke 200" in text
    assert "access GET /api/slowpoke" not in text


# ---- 写失败兜底（spec §4.7 丢日志不丢功能 / 缺口标记）----


def test_gap_marker_after_recovery(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("不是目录", encoding="utf-8")
    logs_dir = tmp_path / "logs"
    j = Journal(str(blocker))  # 目录打不开：持续写失败（每笔重开也打不开）
    j.line("info", "drop1")
    j.line("info", "drop2")
    j.audit("live_check")  # 审计失败也计入同一个缺口
    assert j._dropped == 3 and j._dropped_since is not None
    assert not logs_dir.exists()
    j._dir = logs_dir  # 恢复可写：下一笔自动重开真文件
    j.line("info", "after")
    text = app_log(logs_dir)
    # 恢复可写的第一笔前补缺口标记，丢的行本体不出现
    assert "gap: 自" in text and "起丢 3 条" in text
    assert "after" in text and "drop1" not in text


def test_unwritable_dir_never_breaks_business(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("不是目录", encoding="utf-8")
    client = make_client(tmp_path, log_dir=str(blocker))
    assert client.get("/api/health").status_code == 200  # 丢日志不丢功能（spec 4.7）


# ---- 14 天清理（spec §4.8 切换顺跑 + 启动补做）----


def test_startup_cleanup_and_note(tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    now = datetime.now(clock.CN_TZ)
    old = (now - timedelta(days=15)).strftime("%Y%m%d")
    recent = (now - timedelta(days=1)).strftime("%Y%m%d")
    for name in (f"app-{old}.log", f"audit-{old}.log"):
        (logs_dir / name).write_text("stale", encoding="utf-8")
    (logs_dir / f"app-{recent}.log").write_text("keep", encoding="utf-8")
    make_client(tmp_path)  # create_app 启动补做一次切换+清理（停机错过半夜那趟）
    assert not (logs_dir / f"app-{old}.log").exists()
    assert not (logs_dir / f"audit-{old}.log").exists()
    assert (logs_dir / f"app-{recent}.log").exists()
    assert "service start" in app_log(logs_dir)  # spec 4.10 启动几行


def test_day_rollover_cleans_old(tmp_path, monkeypatch):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    now = datetime.now(clock.CN_TZ)
    stale = (now - timedelta(days=20)).strftime("%Y%m%d")
    (logs_dir / f"app-{stale}.log").write_text("stale", encoding="utf-8")
    j = Journal(str(logs_dir))
    day1 = (now - timedelta(days=1)).strftime("%Y%m%d")
    monkeypatch.setattr(logs, "today", lambda: day1)
    j.line("info", "day1 写一笔")
    assert (logs_dir / f"app-{day1}.log").exists()
    assert not (logs_dir / f"app-{stale}.log").exists()  # 切换顺跑清理
    day2 = now.strftime("%Y%m%d")
    monkeypatch.setattr(logs, "today", lambda: day2)
    j.line("info", "day2 再写一笔")
    assert (logs_dir / f"app-{day2}.log").exists()  # 按天各归各的文件
    assert (logs_dir / f"app-{day1}.log").exists()  # 昨天的原样在位


# ---- 脱敏与审计行（spec §4.3 禁止 / C1）----


def test_mask_phone_and_long_token():
    assert mask("手机号 13812341234") == "手机号 138****1234"
    assert mask("key=Ab3dEf9kLm2qRs7uVw1yZx4C") == "key=Ab3dEf****"
    # 手机号嵌在长串里：整串按长串打码，不拆散漏网
    assert "13812341234" not in mask("token138123412345678901234")


def test_audit_json_line_masked(tmp_path):
    logs_dir = tmp_path / "logs"
    j = Journal(str(logs_dir))
    j.audit("join_game", game_id=7, detail="带 1 访客 13812341234")
    audit_file = max(logs_dir.glob("audit-*.log"))
    row = audit_rows(logs_dir)[-1]
    assert row["action"] == "join_game" and row["game_id"] == 7
    assert row["detail"] == "带 1 访客 138****1234"
    assert row["account_id"] is None and row["at"]
    assert "13812341234" not in audit_file.read_text(encoding="utf-8")


def test_module_audit_uses_context(tmp_path, monkeypatch):
    """模块级 audit()：中间件 set 的账本 + ctx 里的操作人自动带上（批3 埋点入口）；
    球局号按设计由调用点显式传。"""
    logs_dir = tmp_path / "logs"
    j = Journal(str(logs_dir))
    # 换成带固定默认值的新 ContextVar（monkeypatch 测后还原模块原件），免 token 手工复位
    monkeypatch.setattr(logs, "ctx_journal", ContextVar("t_journal", default=j))
    monkeypatch.setattr(logs, "ctx_account", ContextVar("t_account", default=5))
    logs.audit("live_start", game_id=3)
    row = audit_rows(logs_dir)[-1]
    assert row["action"] == "live_start"
    assert row["account_id"] == 5 and row["game_id"] == 3
