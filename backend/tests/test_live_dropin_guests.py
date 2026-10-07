"""空降与带访客两条记账通道（1.3 批2）—— 1.3 附录 B1 末条 + 2.2 §4.4/§5 摊钱名单：
dropin（本人空降报到）：名册没我建行（dropin 标、考勤归一 ok/late、队尾、摊钱人头
+1），重放/重复点幂等 200 不动账（先于号检查，沿 settle_confirm 重放先例）、正式
球友误走 409 live_duplicate 携视图、散场后 live_ended 拒；guests（全权带访客）：
访客行挂担保人账号名下（出账归账键「1+名下访客人头」）、到场即带排队尾、命名沿
前端 addGuests 规则（空名=担保名前两字 / 多人具名=name·i）、球友 403、挂访客行/
名册外人 422 live_invalid、旧号 409 携视图、散场后拒；视图带出 dropin/guest/
guarantor——前端 applyLiveView 与出账引擎消费同一真值。

时刻基准 FakeClock 10-04 12:00（conftest）；开球时刻 10-06 19:00（test_games_read）
——开球前空降归一 ok，advance 三天后归一 late。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import signup
from .test_live_score import NOW_ISO, live_call, live_get, open_live


def dropin_call(client: TestClient, token: str, gid: int, base: int):
    return live_call(client, token, gid, "dropin", {"base_total_seq": base})


def guests_body(view_or_seq, guarantor_row_id: int, **over) -> dict:
    base = view_or_seq if isinstance(view_or_seq, int) else view_or_seq["total_seq"]
    return {
        "count": 1,
        "guarantor_id": guarantor_row_id,
        "base_total_seq": base,
    } | over


def row_of(view: dict, account_id: int) -> dict:
    return next(p for p in view["players"] if p["account_id"] == account_id)


def rows_of(view: dict, base: dict) -> list[dict]:
    """开账那拨之外的新行（按行 id 差集）。"""
    base_ids = {p["id"] for p in base["players"]}
    return [p for p in view["players"] if p["id"] not in base_ids]


# ---- dropin：空降报到（§5「没报名扫码直接打的」照摊） ----


def test_dropin_new_row_arrives_queue_tail_and_counts_head(client: TestClient):
    env = open_live(client, seed=41)
    gid = env["game_id"]
    stranger = signup(client, "13800039701", "d")
    v = live_get(client, gid, stranger["token"])
    assert v["fee"]["heads"] == 6
    r = dropin_call(client, stranger["token"], gid, v["total_seq"])
    assert r.status_code == 200, r.text
    v2 = r.json()
    assert v2["total_seq"] == v["total_seq"] + 1
    row = row_of(v2, stranger["account"]["id"])
    assert row["dropin"] is True and row["guest"] is False
    assert row["guarantor_account_id"] is None
    assert row["check"] == "ok" and row["arrive_at"] == NOW_ISO  # 开球前归一 ok
    assert v2["queue"][-1] == row["id"] and row["queue_pos"] == 6  # 进队尾
    assert v2["fee"]["heads"] == 7  # 空降进总账即进摊钱人头（附录 B1）


def test_dropin_idempotent_replay_then_late_after_start(client, fake):
    env = open_live(client, seed=42)
    gid = env["game_id"]
    stranger = signup(client, "13800039702", "d")
    v0 = live_get(client, gid, stranger["token"])
    r1 = dropin_call(client, stranger["token"], gid, v0["total_seq"])
    assert r1.status_code == 200, r1.text
    v1 = r1.json()
    # 断网重放（旧号）：幂等回 200——不新建行、不进号（先于号检查）
    r2 = dropin_call(client, stranger["token"], gid, v0["total_seq"])
    assert r2.status_code == 200, r2.text
    v2 = r2.json()
    assert v2["total_seq"] == v1["total_seq"]
    assert len([p for p in v2["players"] if p["dropin"]]) == 1
    # 过开球时刻后另一位空降：归一 late、排队尾
    fake.advance(days=3)
    late = signup(client, "13800039703", "d2")
    r3 = dropin_call(client, late["token"], gid, v1["total_seq"])
    assert r3.status_code == 200, r3.text
    v3 = r3.json()
    row = row_of(v3, late["account"]["id"])
    assert row["check"] == "late"
    assert v3["queue"][-1] == row["id"]


def test_dropin_duplicate_defense_then_after_end_rejected(client: TestClient):
    env = open_live(client, seed=43)
    gid = env["game_id"]
    v = live_get(client, gid, env["mate"]["token"])
    # 正式球友（有行非空降）误走空降通道：409 live_duplicate 携最新视图、不动账
    r = dropin_call(client, env["mate"]["token"], gid, v["total_seq"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "live_duplicate"
    assert r.json()["view"]["total_seq"] == v["total_seq"]
    assert live_get(client, gid, env["org"]["token"])["total_seq"] == v["total_seq"]
    # 散场后（无残局直接收工）空降拒 live_ended
    cur = live_get(client, gid, env["org"]["token"])
    r = live_call(
        client, env["org"]["token"], gid, "end", {"base_total_seq": cur["total_seq"]}
    )
    assert r.status_code == 200, r.text
    stranger = signup(client, "13800039704", "d3")
    r = dropin_call(client, stranger["token"], gid, cur["total_seq"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "live_ended"


# ---- guests：现场带访客（§8 裁决二：算在带来的人头上 1+带来数份） ----


def test_guests_full_power_only_naming_and_queue_tail(client: TestClient):
    env = open_live(client, seed=44)
    rows = env["view"]["players"]
    gid = env["game_id"]
    v = live_get(client, gid, env["org"]["token"])
    # 球友不能带（前端 needFull 前置、后端真闸）
    r = live_call(
        client, env["mate"]["token"], gid, "guests", guests_body(v, rows[1]["id"])
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "live_forbidden"
    # 组织者带 2 位具名：挂担保人账号名下、命名 name·i、到场即带、排队尾
    r = live_call(
        client,
        env["org"]["token"],
        gid,
        "guests",
        guests_body(v, rows[1]["id"], count=2, name="小王"),
    )
    assert r.status_code == 200, r.text
    v2 = r.json()
    gs = rows_of(v2, v)
    assert [g["name"] for g in gs] == ["小王·1", "小王·2"]
    assert all(
        g["guest"] and g["guarantor_account_id"] == rows[1]["account_id"] for g in gs
    )
    assert all(g["check"] == "ok" and g["arrive_at"] == NOW_ISO for g in gs)
    assert v2["queue"][-2:] == [g["id"] for g in gs]
    assert v2["fee"]["heads"] == 8  # 6 人头 + 2 访客（访客不单算、归担保人份额）
    # 空名：担保名前两字+的球友（沿前端 addGuests 命名规则后端重做）
    cur = live_get(client, gid, env["org"]["token"])
    r = live_call(
        client, env["org"]["token"], gid, "guests", guests_body(cur, rows[2]["id"])
    )
    assert r.status_code == 200, r.text
    g = rows_of(r.json(), cur)
    assert g[0]["name"] == f"{rows[2]['name'][:2]}的球友"
    # 单人具名：不带序号，名字照给（count=1 走 else 分支）
    cur = live_get(client, gid, env["org"]["token"])
    r = live_call(
        client,
        env["org"]["token"],
        gid,
        "guests",
        guests_body(cur, rows[2]["id"], count=1, name="阿花"),
    )
    assert r.status_code == 200, r.text
    g = rows_of(r.json(), cur)
    assert [x["name"] for x in g] == ["阿花"]


def test_guests_target_validation_gates_and_after_end(client: TestClient):
    env = open_live(client, seed=45, bring=1)
    rows = env["view"]["players"]
    gid = env["game_id"]
    v = live_get(client, gid, env["org"]["token"])
    guest_row = next(p for p in rows if p["guest"])
    # 访客挂不到访客名下 / 名册外人挂不了：均 live_invalid、被拒不进号
    r = live_call(
        client, env["org"]["token"], gid, "guests", guests_body(v, guest_row["id"])
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "live_invalid"
    r = live_call(client, env["org"]["token"], gid, "guests", guests_body(v, 999999))
    assert r.status_code == 422 and r.json()["error"]["code"] == "live_invalid"
    assert live_get(client, gid, env["org"]["token"])["total_seq"] == v["total_seq"]
    # 旧号（连击/断网重发）：退回携最新视图
    r = live_call(
        client,
        env["org"]["token"],
        gid,
        "guests",
        guests_body(v["total_seq"] - 1, rows[0]["id"]),
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "live_stale_total"
    assert r.json()["view"]["total_seq"] == v["total_seq"]
    # 散场后拒
    cur = live_get(client, gid, env["org"]["token"])
    r = live_call(
        client, env["org"]["token"], gid, "end", {"base_total_seq": cur["total_seq"]}
    )
    assert r.status_code == 200, r.text
    r = live_call(
        client, env["org"]["token"], gid, "guests", guests_body(cur, rows[0]["id"])
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "live_ended"
