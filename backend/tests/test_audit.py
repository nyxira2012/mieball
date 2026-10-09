"""6.1 批3a【审计·局簿账单意向】锁（docs/6.1 §C1 / 技术设计 §1.3）：14 端点
埋点的代表行——发局（含 game_id 与操作人）/报名/锁定必打/订场与清空/邀请/退局/
撤局/救回/补填总价（detail 含金额）/结算/收款/留删意向（game_id=None 长相）；
错误路径（服务抛 ApiError）不落审计。断言从 audit-*.log 的 JSON 行读回。

夹具自足（不动 conftest）：复用 test_logs 的 make_client/auth/audit_rows，
log_dir 指到 tmp_path。
"""

from __future__ import annotations

from datetime import timedelta

from app.core import clock

from .conftest import signup
from .test_bills_read import receive, settle, stage
from .test_games_actions import join_ok
from .test_games_read import detail, publish
from .test_logs import audit_rows, auth, make_client


def audit_row_of(rows: list[dict], action: str) -> dict:
    return next(r for r in rows if r["action"] == action)


def test_publish_join_lock_audited(tmp_path):
    logs_dir = tmp_path / "logs"
    client = make_client(tmp_path)
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
    join_ok(client, mate["token"], g["id"], bring=1)
    r = client.post(f"/api/games/{g['id']}/lock", headers=auth(org["token"]))
    assert r.status_code == 200, r.text

    rows = audit_rows(logs_dir)
    pub = audit_row_of(rows, "publish_game")
    assert pub["game_id"] == g["id"] and pub["account_id"] == org["account"]["id"]
    assert pub["at"] and "海淀体育馆" in pub["detail"]  # detail 一句摘要（场馆）
    join = audit_row_of(rows, "join_game")
    assert join["game_id"] == g["id"] and join["account_id"] == mate["account"]["id"]
    assert "1" in join["detail"]  # 带 1 人
    lock = audit_row_of(rows, "lock_game")
    assert lock["game_id"] == g["id"] and lock["account_id"] == org["account"]["id"]


def test_organizer_tools_audited(tmp_path, fake):
    logs_dir = tmp_path / "logs"
    client = make_client(tmp_path)
    org = signup(client, "13800000004", "o")
    mate = signup(client, "13800000005", "m")
    g = publish(client, org["token"], visibility="public")
    join_ok(client, mate["token"], g["id"])
    r = client.post(
        f"/api/games/{g['id']}/booking",
        headers=auth(org["token"]),
        json={"courts": ["3号"], "fee_total": 480},
    )
    assert r.status_code == 200, r.text
    assert (
        client.post(f"/api/games/{g['id']}/booking/clear", headers=auth(org["token"]))
    ).status_code == 200
    r = client.post(
        f"/api/games/{g['id']}/invite",
        headers=auth(org["token"]),
        json={"account_id": mate["account"]["id"]},
    )
    assert r.status_code == 200, r.text
    assert (
        client.post(f"/api/games/{g['id']}/quit", headers=auth(mate["token"]))
    ).status_code == 200
    assert (
        client.post(f"/api/games/{g['id']}/cancel", headers=auth(org["token"]))
    ).status_code == 200

    # 救回：另一局过截止人数不足黄掉 → terminated → restore（沿 test_games_tools 流）
    org2 = signup(client, "13800000006", "o2")
    g2 = publish(client, org2["token"], visibility="public", min_players=3)
    join_ok(client, signup(client, "13800000007", "m2")["token"], g2["id"])
    fake.advance(days=2, hours=6)  # → 10-06 18:00 过截止
    assert detail(client, g2["id"], org2["token"])["status"] == "terminated"
    r = client.post(f"/api/games/{g2['id']}/restore", headers=auth(org2["token"]))
    assert r.status_code == 200, r.text

    rows = audit_rows(logs_dir)
    expect = {
        "book_game": (g["id"], org["account"]["id"]),
        "clear_game_booking": (g["id"], org["account"]["id"]),
        "invite_user": (g["id"], org["account"]["id"]),
        "quit_game": (g["id"], mate["account"]["id"]),
        "cancel_game": (g["id"], org["account"]["id"]),
        "restore_game": (g2["id"], org2["account"]["id"]),
    }
    for action, (gid, aid) in expect.items():
        row = audit_row_of(rows, action)
        assert row["game_id"] == gid and row["account_id"] == aid and row["at"], action
    assert "480" in audit_row_of(rows, "book_game")["detail"]  # detail 带场费
    assert (
        str(mate["account"]["id"]) in audit_row_of(rows, "invite_user")["detail"]
    )  # 邀请带被邀人


def test_bill_actions_audited(tmp_path):
    logs_dir = tmp_path / "logs"
    client = make_client(tmp_path)
    env = stage(client, seed=95, fee=None)  # 散场不订价 → 挂 unfixed 等补填
    org, payer = env["org"], env["mates"][0]

    # 错误路径不落审计：球友不碰钱（403 ApiError）→ 那行 audit 不执行
    r = client.post(
        f"/api/games/{env['game_id']}/fee",
        headers=auth(payer["token"]),
        json={"fee_total": 700},
    )
    assert r.status_code == 403
    assert not [x for x in audit_rows(logs_dir) if x["action"] == "set_game_fee"]

    r = client.post(
        f"/api/games/{env['game_id']}/fee",
        headers=auth(org["token"]),
        json={"fee_total": 700},
    )
    assert r.status_code == 200, r.text
    assert settle(client, payer["token"], env["game_id"]).status_code == 200
    assert (
        receive(
            client, org["token"], env["game_id"], payer["account"]["id"]
        ).status_code
        == 200
    )

    rows = audit_rows(logs_dir)
    fee = audit_row_of(rows, "set_game_fee")
    assert (
        fee["game_id"] == env["game_id"] and fee["account_id"] == org["account"]["id"]
    )
    assert "700" in fee["detail"]  # detail 带金额
    st = audit_row_of(rows, "settle_bill")
    assert (
        st["game_id"] == env["game_id"] and st["account_id"] == payer["account"]["id"]
    )  # 结算人=付款方本人
    rc = audit_row_of(rows, "receive_payer")
    assert rc["account_id"] == org["account"]["id"]  # 收款人=组织者
    assert str(payer["account"]["id"]) in rc["detail"]  # detail 带付款人


def test_intents_audited_without_game(tmp_path):
    """意向不挂局：审计行 game_id=None，语境靠 detail（技术设计 §1.3）。"""
    logs_dir = tmp_path / "logs"
    client = make_client(tmp_path)
    u = signup(client, "13800000003", "d")
    r = client.post(
        "/api/intents",
        headers=auth(u["token"]),
        json={"slots": ["weekend_night", "weekday_day"], "frequency": 2},
    )
    assert r.status_code == 200, r.text
    assert (
        client.post("/api/intents/delete", headers=auth(u["token"])).status_code == 200
    )

    rows = audit_rows(logs_dir)
    save = audit_row_of(rows, "save_intent")
    assert save["game_id"] is None and save["account_id"] == u["account"]["id"]
    assert "2" in save["detail"] and save["at"]  # 2 个时段 频率 2
    dele = audit_row_of(rows, "delete_intent")
    assert dele["game_id"] is None and dele["account_id"] == u["account"]["id"]
