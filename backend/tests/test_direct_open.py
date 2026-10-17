"""现场页直接开场（2026-10-17 用户裁决）：免填建局+空锁必开+开账一步（POST
/games/direct），与散场无痕分支——direct 局一场对局都没落账时散场走撤局语义
（cancelled 无痕 + 现场行整删）；落过账的照常封存。开场前基本信息（场馆+时长）
由前端表单收口，这里只把关非空与时长范围。

时刻基准 FakeClock 10-04 12:00（conftest）——直接开场局 start=建局时刻。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import auth, signup
from .test_live_score import live_call, live_get, write_body


def open_direct(client: TestClient, seed: int, **over) -> tuple[dict, dict]:
    """组织者直接开场两小时局：返回 (org 账号, game_view)。"""
    org = signup(client, f"1380005{seed:04d}", "o")
    body = {"venue_name": "朝阳匹克球馆", "hours": 2, "courts": ["1号"]} | over
    r = client.post("/api/games/direct", headers=auth(org["token"]), json=body)
    assert r.status_code == 200, r.text
    return org, r.json()


def test_direct_open_defaults_and_opened_live(client: TestClient):
    org, g = open_direct(client, 41)
    gid = g["id"]
    # 建局默认：必开（空锁）、仅邀请、direct 来源；开账一步到位
    assert g["source"] == "direct" and g["forced"] is True
    assert g["visibility"] == "invite_only" and g["live_opened"] is True
    assert g["status"] == "live" and g["heads"] == 1
    # 规则默认（2026-10-17 裁决）：15 分、2人下、轮换优先——局与现场同源
    assert g["scoring"] == 15 and g["rotation"] == "partner"
    v = live_get(client, gid, org["token"])
    assert v["rules"]["scoring"] == 15
    assert v["rules"]["down"] == "n2" and v["rules"]["pairing"] == "partner"
    assert v["total_seq"] == 1
    # 名册只有组织者一行（absent——报到才进队），片全 idle
    assert len(v["players"]) == 1 and v["players"][0]["check"] == "absent"
    assert v["queue"] == [] and all(c["status"] == "idle" for c in v["courts"])
    # 场地号收拢（走查裁决）：片数唯一真值=场地号个数
    assert g["courts"] == ["1号"] and v["courts_count"] == 1
    # 仅邀请：找局列表藏起来；组织者自己的「我的局」在场
    other = signup(client, "13800059999", "x")
    rows = client.get("/api/games", headers=auth(other["token"])).json()
    assert all(row["id"] != gid for row in rows)
    rows = client.get("/api/games/mine", headers=auth(org["token"])).json()
    assert gid in [row["id"] for row in rows]


def test_direct_open_courts_set_court_count(client: TestClient):
    """场地号收拢：填几个号开几片（订场同源 game.courts），空串/重复清洗、上限防呆。
    片行（LiveCourt）开赛才落库，空闲片由前端按 courtsCount 合成——此处只断真值。"""
    org, g = open_direct(client, 44, courts=[" 3号 ", "", "5号", "3号"])
    assert g["courts"] == ["3号", "5号"]
    v = live_get(client, g["id"], org["token"])
    assert v["courts_count"] == 2 and v["courts"] == []
    r = client.post(
        "/api/games/direct",
        headers=auth(org["token"]),
        json={
            "venue_name": "馆",
            "hours": 2,
            "courts": [f"{i}号" for i in range(9)],
        },
    )
    assert r.status_code == 422


def test_direct_open_validates_venue_and_hours(client: TestClient):
    org = signup(client, "13800054100", "o")
    bodies = [
        {"venue_name": "  ", "hours": 2, "courts": ["1号"]},  # 场馆空白
        {"venue_name": "馆", "hours": 2, "courts": []},  # 场地号必填
        {"venue_name": "馆", "hours": 2, "courts": ["  "]},  # 场地号全空白
        {"venue_name": "馆", "hours": 0, "courts": ["1号"]},  # 时长下界
        {"venue_name": "馆", "hours": 9, "courts": ["1号"]},  # 时长上界
    ]
    for body in bodies:
        r = client.post("/api/games/direct", headers=auth(org["token"]), json=body)
        assert r.status_code == 422, body
    # 未登录不放行（先看后报：游客走建号卡，属前端编排）
    r = client.post(
        "/api/games/direct", json={"venue_name": "馆", "hours": 2, "courts": ["1号"]}
    )
    assert r.status_code == 401


def test_direct_sweep_without_matches_leaves_no_trace(client: TestClient):
    org, g = open_direct(client, 42)
    gid = g["id"]
    v = live_get(client, gid, org["token"])
    r = live_call(client, org["token"], gid, "end", {"base_total_seq": v["total_seq"]})
    assert r.status_code == 200, r.text
    assert r.json()["vacated"] is True and r.json()["ok"] is True
    # 现场行整删：深链 404——不留「已撤还能写」的僵尸局
    r = client.get(f"/api/games/{gid}/live", headers=auth(org["token"]))
    assert r.status_code == 404
    # 撤局语义：组织者列表永不回见、打球记录查无（ended_at 锚天然排除 cancelled）
    rows = client.get("/api/games/mine", headers=auth(org["token"])).json()
    assert all(row["id"] != gid for row in rows)
    pl = client.get("/api/games/playlog", headers=auth(org["token"])).json()
    assert all(row["id"] != gid for row in pl["games"])
    assert pl["matches_count"] == 0


def test_direct_sweep_after_settled_match_ends_normally(client: TestClient):
    org, g = open_direct(client, 43)
    gid = g["id"]
    # 三位球友经深链直接报名（仅邀请：链接即门票，join 不拦档）→ 开账后补册
    mates = [signup(client, f"1380007{i:04d}", f"m{i}") for i in range(3)]
    for m in mates:
        r = client.post(f"/api/games/{gid}/join", headers=auth(m["token"]), json={})
        assert r.status_code == 200, r.text
    v = live_get(client, gid, org["token"])
    assert len(v["players"]) == 4
    # 组织者代办全员到场；第 4 人报到路自动补片开赛（现18），无需手动发牌
    for row in v["players"]:
        r = live_call(
            client,
            org["token"],
            gid,
            "check",
            {"player_id": row["id"], "check": "ok", "base_total_seq": v["total_seq"]},
        )
        assert r.status_code == 200, r.text
        v = r.json()
    assert v["courts"][0]["status"] == "playing" and v["queue"] == []
    # 落一场对局（清扫态不排下一场）→ 散场走正常封存，不走无痕分支
    r = live_call(
        client,
        org["token"],
        gid,
        "settle-confirm",
        write_body(v, 1, winner_side="a", score_a=11, score_b=9, no_redeal=True),
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert len(v["matches"]) == 1
    r = live_call(client, org["token"], gid, "end", {"base_total_seq": v["total_seq"]})
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["ended"] is True and v["round"] == 1
    # 打球记录在册（组织者上过场、已散场锚过）
    pl = client.get("/api/games/playlog", headers=auth(org["token"])).json()
    assert gid in [row["id"] for row in pl["games"]]
    assert pl["matches_count"] == 1
