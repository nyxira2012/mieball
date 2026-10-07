"""2.5 自动管理员 —— 账开张后第一个到场签到的人暂管现场（2.5 §4.2/§8 裁决）：
组织者首签不授、已是管理员不重授、第二人不顶替、组织者走现有 unset-admin 收回。
开账直调 LiveBook（沿 test_live_base 先例），签到/撤管理员走路由端点（带总号）。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import signup
from .test_games_actions import join_ok
from .test_games_read import publish, seed_entry
from .test_live_base import lock_past_deadline, start_live, view_live


def auth(token: str | None) -> dict:
    return {"Authorization": f"Bearer {token}"} if token else {}


def check_in(client: TestClient, token: str, game_id: int, player_id: int) -> dict:
    v = view_live(client, game_id, None)  # 取当前总号（写入口带出发号）
    r = client.post(
        f"/api/games/{game_id}/live/check",
        headers=auth(token),
        json={"player_id": player_id, "check": "ok", "base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200, r.text
    return r.json()


def row_id(view: dict, account_id: int) -> int:
    return next(r for r in view["players"] if r["account_id"] == account_id)["id"]


def seed_member_scene(client: TestClient, fake, *, opener: str):
    """org + 两成员、成局、由 opener（"org"/"b"）开账的公共前戏；返回环境。"""
    org = signup(client, "13800020201", "o")
    b = signup(client, "13800020202", "b", nickname="小乙", nickname_set=True)
    c = signup(client, "13800020203", "c")
    g = publish(client, org["token"], visibility="public")
    join_ok(client, b["token"], g["id"])
    join_ok(client, c["token"], g["id"])
    lock_past_deadline(client, fake, g["id"])  # → 开打前 1h，成局
    starter = org if opener == "org" else b
    start_live(client, g["id"], starter["account"]["id"])
    v = view_live(client, g["id"], None)
    return {
        "org": org,
        "b": b,
        "c": c,
        "game_id": g["id"],
        "ids": {u["account"]["id"]: row_id(v, u["account"]["id"]) for u in (org, b, c)},
    }


def test_first_checkin_member_becomes_admin(client, fake):
    env = seed_member_scene(client, fake, opener="b")  # 成员开账
    b_id, c_id = env["b"]["account"]["id"], env["c"]["account"]["id"]

    v = check_in(client, env["b"]["token"], env["game_id"], env["ids"][b_id])

    assert v["admins"] == [b_id]
    assert [e["kind"] for e in v["feed"]] == ["auto_admin"]
    assert v["feed"][0]["target"] == "小乙" and v["feed"][0]["actor"] == "小乙"

    # 已是管理员再报一次：幂等不重授、不追加事件
    v = check_in(client, env["b"]["token"], env["game_id"], env["ids"][b_id])
    assert v["admins"] == [b_id] and len(v["feed"]) == 1

    # 第二人签到：管理员不变
    v = check_in(client, env["c"]["token"], env["game_id"], env["ids"][c_id])
    assert v["admins"] == [b_id] and len(v["feed"]) == 1


def test_organizer_first_checkin_not_granted(client, fake):
    """组织者首签不授（到场自然说了算）；随后成员签的也不再是"第一个"。"""
    env = seed_member_scene(client, fake, opener="org")
    b_id = env["b"]["account"]["id"]

    v = check_in(
        client,
        env["org"]["token"],
        env["game_id"],
        env["ids"][env["org"]["account"]["id"]],
    )
    assert v["admins"] == [] and v["feed"] == []

    v = check_in(client, env["b"]["token"], env["game_id"], env["ids"][b_id])
    assert v["admins"] == [] and v["feed"] == []


def test_guest_arrival_first_member_checkin_still_granted(client, fake):
    """访客行不参与首签判定（0号：第一个签到的"球友"）：组织者先带访客落
    check=ok，随后首个球友签到照授管理员；访客本身不授（admins 不含）。"""
    env = seed_member_scene(client, fake, opener="org")
    org_id, b_id = env["org"]["account"]["id"], env["b"]["account"]["id"]

    v = view_live(client, env["game_id"], None)
    r = client.post(
        f"/api/games/{env['game_id']}/live/guests",
        headers=auth(env["org"]["token"]),
        json={
            "guarantor_id": env["ids"][org_id],
            "count": 1,
            "name": None,
            "base_total_seq": v["total_seq"],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["admins"] == []  # 访客到场不授访客

    v = check_in(client, env["b"]["token"], env["game_id"], env["ids"][b_id])

    assert v["admins"] == [b_id]
    assert [e["kind"] for e in v["feed"]] == ["auto_admin"]


def test_dropin_waitlist_first_scan_gets_admin(client, fake):
    """空降扫码即签到（0号"第一个签到的球友"两路同权）：候补先扫码空降 →
    授他管理员；随后正式成员签到不重复授、不顶替。"""
    org = signup(client, "13800020211", "o")
    b = signup(client, "13800020212", "b")
    c = signup(client, "13800020213", "c", nickname="小丙", nickname_set=True)
    g = publish(client, org["token"], visibility="public")
    join_ok(client, b["token"], g["id"])
    seed_entry(client, g["id"], c["account"]["id"], standing="waitlist", wait_seq=1)
    lock_past_deadline(client, fake, g["id"])  # org+b 成局，候补不进名册
    start_live(client, g["id"], org["account"]["id"])

    v = view_live(client, g["id"], None)
    r = client.post(
        f"/api/games/{g['id']}/live/dropin",
        headers=auth(c["token"]),
        json={"base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["admins"] == [c["account"]["id"]]
    assert [e["kind"] for e in v["feed"]] == ["auto_admin"]
    assert v["feed"][0]["target"] == "小丙"

    v = check_in(client, b["token"], g["id"], row_id(v, b["account"]["id"]))
    assert v["admins"] == [c["account"]["id"]] and len(v["feed"]) == 1


def test_organizer_revokes_auto_admin(client, fake):
    """临时管家收得回（2.5 场景 4.6）：走现有 unset-admin，feed 留痕。"""
    env = seed_member_scene(client, fake, opener="b")
    b_id = env["b"]["account"]["id"]

    v = check_in(client, env["b"]["token"], env["game_id"], env["ids"][b_id])
    assert v["admins"] == [b_id]

    v = view_live(client, env["game_id"], None)
    r = client.post(
        f"/api/games/{env['game_id']}/live/unset-admin",
        headers=auth(env["org"]["token"]),
        json={"player_id": env["ids"][b_id], "base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["admins"] == []
    assert [e["kind"] for e in v["feed"]] == ["auto_admin", "unset_admin"]
    assert v["feed"][-1]["target"] == "小乙"
