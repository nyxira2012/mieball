"""开账后报名补册（2026-10-10 修复批 F6/F9）—— join 只写 Entry，名册行归现场：
start 只展开开账那一刻的 formal 行，开账后才 join 的人此前线上有名、名册没行
（签到没靶、自签到被迫走空降道背「空降」标）。修复后 join 落 formal 即调
LiveBook.absorb_join 补进名册（本人行 + bring 访客行，absent 不排队、首见建
Elo 行）；候补行不补（没到场不进现场）、先空降后补报名不建双行、没开账不补
（start 会展开）。

时刻基准 FakeClock 10-04 12:00（conftest）。
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import EloRating, LivePlayer

from .conftest import signup
from .test_games_actions import join_ok
from .test_games_read import publish
from .test_live_score import _ph, live_call, live_get, lock_game_direct, open_live


def _slack_live(client: TestClient, *, seed: int, heads: int) -> dict:
    """留坑现场：heads 个 formal（max 8 有余位）→ 锁 → 开账，返回 org 环境。"""
    org = signup(client, _ph(seed, 1), "o")
    mates = [signup(client, _ph(seed, i + 2), f"p{i}") for i in range(heads - 1)]
    g = publish(client, org["token"], visibility="public", max_players=8)
    for u in mates:
        join_ok(client, u["token"], g["id"])
    lock_game_direct(client, g["id"])
    r = live_call(client, org["token"], g["id"], "start", {})
    assert r.status_code == 200, r.text
    return {"game_id": g["id"], "org": org, "view": r.json()}


def test_join_after_start_absorbs_row_with_guests(client: TestClient):
    env = _slack_live(client, seed=71, heads=3)
    gid = env["game_id"]
    base = live_get(client, gid, env["org"]["token"])
    late = signup(client, _ph(71, 9), "z")
    r = client.post(
        f"/api/games/{gid}/join",
        headers={"Authorization": f"Bearer {late['token']}"},
        json={"bring": 1},
    )
    assert r.status_code == 200, r.text
    v = live_get(client, gid, env["org"]["token"])
    # 名册 +2 行：本人 formal 行 + 访客行，全 absent、不进候场队（报到驱动）
    new = [p for p in v["players"] if p["id"] not in {q["id"] for q in base["players"]}]
    assert len(new) == 2
    mine = next(p for p in new if p["account_id"] == late["account"]["id"])
    guest = next(p for p in new if p["guest"])
    assert mine["dropin"] is False and mine["check"] == "absent"
    assert guest["guarantor_account_id"] == late["account"]["id"]
    assert guest["check"] == "absent"
    assert mine["id"] not in v["queue"] and guest["id"] not in v["queue"]
    assert v["total_seq"] == base["total_seq"] + 1  # 名册变更推进总号
    assert v["fee"]["heads"] == base["fee"]["heads"] + 2  # 摊钱人头照算
    # 首见建 Elo 行（start 同口径）
    db = client.app.state.session_factory()
    try:
        er = db.execute(
            select(EloRating).where(EloRating.account_id == late["account"]["id"])
        ).scalar_one_or_none()
        assert er is not None
    finally:
        db.close()


def test_join_waitlist_not_absorbed(client: TestClient):
    env = open_live(client, seed=72)  # 6/6 满
    gid = env["game_id"]
    base = live_get(client, gid, env["org"]["token"])
    stranger = signup(client, _ph(72, 9), "z")
    r = client.post(
        f"/api/games/{gid}/join",
        headers={"Authorization": f"Bearer {stranger['token']}"},
        json={"bring": 0},
    )
    assert r.status_code == 200, r.text
    v = live_get(client, gid, env["org"]["token"])
    # 候补不进现场：名册、总号、摊钱人头全不动
    assert len(v["players"]) == len(base["players"])
    assert v["total_seq"] == base["total_seq"]
    assert v["fee"]["heads"] == base["fee"]["heads"]


def test_dropin_then_formal_join_no_double_row(client: TestClient):
    env = _slack_live(client, seed=73, heads=2)
    gid = env["game_id"]
    base = live_get(client, gid, env["org"]["token"])
    stranger = signup(client, _ph(73, 9), "z")
    r = live_call(
        client, stranger["token"], gid, "dropin", {"base_total_seq": base["total_seq"]}
    )
    assert r.status_code == 200, r.text
    after_dropin = r.json()
    # 先空降后补报名：同账号不建双行，空降行原样保留
    r = client.post(
        f"/api/games/{gid}/join",
        headers={"Authorization": f"Bearer {stranger['token']}"},
        json={"bring": 0},
    )
    assert r.status_code == 200, r.text
    v = live_get(client, gid, env["org"]["token"])
    rows = [p for p in v["players"] if p["account_id"] == stranger["account"]["id"]]
    assert len(rows) == 1
    assert rows[0]["id"] == next(
        p["id"]
        for p in after_dropin["players"]
        if p["account_id"] == stranger["account"]["id"]
    )
    assert rows[0]["dropin"] is True
    assert v["total_seq"] == after_dropin["total_seq"]  # 补册没动账


def test_join_before_start_left_to_start_expand(client: TestClient):
    org = signup(client, _ph(74, 1), "o")
    mate = signup(client, _ph(74, 2), "p0")
    g = publish(client, org["token"], visibility="public", max_players=8)
    join_ok(client, mate["token"], g["id"])
    # 没开账：join 不补册（名册行归 start 展开，防止双份）
    db = client.app.state.session_factory()
    try:
        assert (
            db.execute(select(LivePlayer).where(LivePlayer.game_id == g["id"]))
            .scalars()
            .all()
            == []
        )
        lock_game_direct(client, g["id"])
    finally:
        db.close()
    r = live_call(client, org["token"], g["id"], "start", {})
    assert r.status_code == 200, r.text
    assert len(r.json()["players"]) == 2  # org 自占 + mate，各一行
