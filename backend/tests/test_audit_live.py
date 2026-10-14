"""6.1 批3b【审计·现场】锁（docs/6.1 §C1 / 技术设计 §1.3）：12 现场端点 + 首签
自动管理员服务层埋点的代表行——开账（带在册人数）/发牌（片数）/上传结算（片号与
最终比分进 detail）/改分重落（新比分）/取消片/签到四态（detail 带态）/封撤管理员/
空降/带访客（人数）/一键全取消/散场（时刻）；自动授予行 detail=auto_first_checkin
且操作人=被授首签者；错误路径（服务抛 ApiError）不落审计。

夹具自足（不动 conftest）：复用 test_logs 的 make_client/auth/audit_rows（log_dir
指 tmp_path）+ test_live_score 的现场造数惯例（open_live/deal_one/settled_11_9）；
fake 时钟让 publish 默认开球时刻（10-06）落在未来——开账闸与现场册同基。
"""

from __future__ import annotations

from pathlib import Path

from .conftest import signup
from .test_audit import audit_row_of
from .test_games_actions import join_ok
from .test_games_read import publish
from .test_live_score import (
    deal_one,
    live_call,
    live_get,
    lock_game_direct,
    open_live,
    overwrite,
    settled_11_9,
    write_body,
)
from .test_logs import audit_rows, make_client


def test_live_chain_audited(tmp_path: Path, fake):
    """开账→发牌→上传结算链：动作行带 game_id 与操作人，detail 带片数与比分。"""
    logs_dir = tmp_path / "logs"
    client = make_client(tmp_path)
    env = open_live(client, seed=51)  # 发局→报名→开账→全员到场（真值直落）
    gid, org = env["game_id"], env["org"]

    start = audit_row_of(audit_rows(logs_dir), "live_start")
    assert start["game_id"] == gid and start["account_id"] == org["account"]["id"]
    assert "6" in start["detail"]  # detail 带在册人数

    settled_11_9(client, env)  # 内部开片并按 11:9 上传落账
    rows = audit_rows(logs_dir)
    deal = audit_row_of(rows, "live_deal")
    assert deal["game_id"] == gid and deal["account_id"] == org["account"]["id"]
    assert "一键排阵" in deal["detail"]  # 2.8 载荷退役：detail 记动作不记上报片数

    confirm = audit_row_of(rows, "live_settle_confirm")
    assert confirm["game_id"] == gid
    assert "片 1" in confirm["detail"] and "11:9" in confirm["detail"]


def test_overwrite_and_cancel_audited(tmp_path: Path, fake):
    logs_dir = tmp_path / "logs"
    client = make_client(tmp_path)
    env = open_live(client, seed=52)
    gid, org, mate = env["game_id"], env["org"], env["mate"]
    v = settled_11_9(client, env)

    # 错误路径不落审计：球友无改分权（403 ApiError）→ 那行 audit 不执行
    r = overwrite(client, mate["token"], gid, v, score_a=11, score_b=8)
    assert r.status_code == 403
    assert not [
        x for x in audit_rows(logs_dir) if x["action"] == "live_settle_overwrite"
    ]

    r = overwrite(client, org["token"], gid, v, score_a=11, score_b=8)
    assert r.status_code == 200, r.text
    row = audit_row_of(audit_rows(logs_dir), "live_settle_overwrite")
    assert row["account_id"] == org["account"]["id"]
    assert "片 1" in row["detail"] and "11:8" in row["detail"]  # 片号与新比分

    # 改判后片仍在打第二场：取消回流，审计带片号
    r = live_call(client, org["token"], gid, "cancel", write_body(r.json(), 1))
    assert r.status_code == 200, r.text
    cancel = audit_row_of(audit_rows(logs_dir), "live_cancel")
    assert cancel["game_id"] == gid and "1" in cancel["detail"]


def test_check_four_states_and_auto_first_admin_audited(tmp_path: Path, fake):
    """签到四态各记一行（detail 带态）；首签自动管理员的服务层埋点带
    auto_first_checkin、操作人=被授者。"""
    logs_dir = tmp_path / "logs"
    client = make_client(tmp_path)
    org = signup(client, "13800051001", "o")
    mate = signup(client, "13800051002", "m")
    g = publish(client, org["token"], visibility="public")
    join_ok(client, mate["token"], g["id"])
    lock_game_direct(client, g["id"])
    assert live_call(client, org["token"], g["id"], "start", {}).status_code == 200
    rows = live_get(client, g["id"], org["token"])["players"]  # [org, mate] 全 absent

    # mate 开账后首签：自动暂管现场 → 服务层补 live_set_admin
    r = live_call(
        client,
        mate["token"],
        g["id"],
        "check",
        {"player_id": rows[1]["id"], "check": "ok", "base_total_seq": 1},
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["admins"] == [mate["account"]["id"]]
    auto = audit_row_of(audit_rows(logs_dir), "live_set_admin")
    assert auto["detail"] == "auto_first_checkin"
    assert auto["game_id"] == g["id"] and auto["account_id"] == mate["account"]["id"]

    # 四态逐个自报（late/join/left 直传即字面态），每态一行、detail 以态开头
    seq = v["total_seq"]
    for st in ("late", "join", "left"):
        r = live_call(
            client,
            mate["token"],
            g["id"],
            "check",
            {"player_id": rows[1]["id"], "check": st, "base_total_seq": seq},
        )
        assert r.status_code == 200, r.text
        seq = r.json()["total_seq"]
    checks = [x for x in audit_rows(logs_dir) if x["action"] == "live_check"]
    assert len(checks) == 4
    for st in ("ok", "late", "join", "left"):
        row = next(x for x in checks if x["detail"].startswith(st))
        assert row["game_id"] == g["id"] and row["account_id"] == mate["account"]["id"]


def test_live_tools_audited(tmp_path: Path, fake):
    """封撤管理员（操作人=组织者、detail 带名册行）/空降（操作人=空降者）/
    带访客（detail 带人数）。"""
    logs_dir = tmp_path / "logs"
    client = make_client(tmp_path)
    env = open_live(client, seed=53)
    gid, org = env["game_id"], env["org"]
    rows = env["view"]["players"]

    v = live_get(client, gid, org["token"])
    r = live_call(
        client,
        org["token"],
        gid,
        "set-admin",
        {"player_id": rows[1]["id"], "base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200, r.text
    v = r.json()
    r = live_call(
        client,
        org["token"],
        gid,
        "unset-admin",
        {"player_id": rows[1]["id"], "base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200, r.text
    v = r.json()

    stranger = signup(client, "13800053009", "s")  # 名册外的人空降进账
    r = live_call(
        client, stranger["token"], gid, "dropin", {"base_total_seq": v["total_seq"]}
    )
    assert r.status_code == 200, r.text
    v = r.json()
    r = live_call(
        client,
        org["token"],
        gid,
        "guests",
        {"count": 2, "guarantor_id": rows[1]["id"], "base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200, r.text

    audit = audit_rows(logs_dir)
    set_r = audit_row_of(audit, "live_set_admin")
    assert set_r["account_id"] == org["account"]["id"]
    assert str(rows[1]["id"]) in set_r["detail"]
    unset_r = audit_row_of(audit, "live_unset_admin")
    assert unset_r["account_id"] == org["account"]["id"]
    drop = audit_row_of(audit, "live_dropin")
    assert drop["game_id"] == gid and drop["account_id"] == stranger["account"]["id"]
    guests = audit_row_of(audit, "live_guests")
    assert "2" in guests["detail"]  # detail 带访客人数


def test_sweep_and_end_audited(tmp_path: Path, fake):
    """一键全取消与散场（detail 带散场时刻）；残局 409 不落散场审计。"""
    logs_dir = tmp_path / "logs"
    client = make_client(tmp_path)
    env = open_live(client, seed=54)
    gid, org = env["game_id"], env["org"]
    v = deal_one(client, env)  # 在打片即残局

    r = live_call(client, org["token"], gid, "end", {"base_total_seq": v["total_seq"]})
    assert r.status_code == 409  # 残局拦：错误路径不落审计
    assert not [x for x in audit_rows(logs_dir) if x["action"] == "live_end"]

    r = live_call(
        client,
        org["token"],
        gid,
        "sweep-cancel-all",
        {"base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200, r.text
    v = r.json()
    sweep = audit_row_of(audit_rows(logs_dir), "live_sweep_cancel_all")
    assert sweep["game_id"] == gid and sweep["account_id"] == org["account"]["id"]

    r = live_call(client, org["token"], gid, "end", {"base_total_seq": v["total_seq"]})
    assert r.status_code == 200, r.text
    end = audit_row_of(audit_rows(logs_dir), "live_end")
    assert end["account_id"] == org["account"]["id"]
    assert r.json()["ended_at"] in end["detail"]  # 散场时刻进 detail
