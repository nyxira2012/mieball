"""现场记分链（2.3 批2）—— docs/2.3 §4.1-4.8：deal 开打、到分自动待确认（净胜 2）、
片冻结与出口、窗内撤分两路（auto 重判/manual 不关窗）、清零、确认一本账
（战报行 + EloRating 结算 + 访客不落账 + 回流四件套 + no_redeal 定格）、取消回流队首、
两级号 409 携最新视图、确认幂等、权限分级（记分到场即可，结束对局类收权）、撤不成负。

考勤与入队的写端点批3 才有（check），到场/候场队真值直落数据库（沿批1 seed 先例）；
时刻基准 FakeClock 10-04 12:00（conftest）。
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import EloRating, Game, LivePlayer, LiveState

from .conftest import signup
from .test_games_actions import join_ok
from .test_games_read import publish

NOW_ISO = "2026-10-04T12:00:00+08:00"  # FakeClock 基点（conftest）


def auth(token: str | None) -> dict:
    return {"Authorization": f"Bearer {token}"} if token else {}


def live_get(client: TestClient, game_id: int, token: str | None = None) -> dict:
    r = client.get(f"/api/games/{game_id}/live", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def live_call(client: TestClient, token: str, game_id: int, action: str, body: dict):
    return client.post(
        f"/api/games/{game_id}/live/{action}", headers=auth(token), json=body
    )


def court(view: dict, court_no: int) -> dict:
    return next(c for c in view["courts"] if c["court_no"] == court_no)


def side_ids(view: dict, court_no: int, side: str) -> set[int]:
    return {
        r["id"]
        for r in view["players"]
        if r["court_no"] == court_no and r["court_side"] == side
    }


def _ph(seed: int, i: int) -> str:
    return f"1380003{seed * 10 + i:04d}"


def open_live(
    client: TestClient,
    *,
    seed: int,
    players: int = 6,
    bring: int = 0,
    scoring: int = 11,
    rules: dict | None = None,
) -> dict:
    """org + players-1 位球友（首位带 bring 个访客）→ 发局报名 → 开账 →
    全员到场、按行序进候场队（报到端点批3，真值直落）。返回现场环境。"""
    org = signup(client, _ph(seed, 1), "o")
    mates = [signup(client, _ph(seed, i + 2), f"p{i}") for i in range(players - 1)]
    g = publish(
        client,
        org["token"],
        visibility="public",
        scoring=scoring,
        max_players=players + bring,  # 访客行也占坑（1.2 报名口径）
    )
    join_ok(client, mates[0]["token"], g["id"], bring=bring)
    for u in mates[1:]:
        join_ok(client, u["token"], g["id"])
    r = live_call(client, org["token"], g["id"], "start", {})
    assert r.status_code == 200, r.text
    db = client.app.state.session_factory()
    try:
        rows = (
            db.execute(
                select(LivePlayer)
                .where(LivePlayer.game_id == g["id"])
                .order_by(LivePlayer.id)
            )
            .scalars()
            .all()
        )
        for i, row in enumerate(rows):
            row.check = "ok"
            row.queue_pos = i
        if rules:
            st = db.execute(
                select(LiveState).where(LiveState.game_id == g["id"])
            ).scalar_one()
            for k, v in rules.items():
                setattr(st, k, v)
        db.commit()
    finally:
        db.close()
    return {
        "game_id": g["id"],
        "org": org,
        "mate": mates[0],
        "view": live_get(client, g["id"], org["token"]),
    }


def deal_court(
    client: TestClient, token: str, game_id: int, view: dict, courts: list[dict]
) -> dict:
    r = live_call(
        client,
        token,
        game_id,
        "deal",
        {"courts": courts, "base_total_seq": view["total_seq"]},
    )
    assert r.status_code == 200, r.text
    return r.json()


def deal_one(client: TestClient, env: dict) -> dict:
    """默认开 1 号片：候场队头 4 人上场（a=前 2、b=次 2）——现取最新视图，
    前面动过账（取消后再发牌）也不拿旧号。"""
    v = live_get(client, env["game_id"], env["org"]["token"])
    q = v["queue"]
    return deal_court(
        client,
        env["org"]["token"],
        env["game_id"],
        v,
        [{"court_no": 1, "a": q[:2], "b": q[2:4]}],
    )


def pt(
    client: TestClient,
    token: str,
    game_id: int,
    view: dict,
    court_no: int,
    side: str,
    n: int = 1,
) -> dict:
    """连记 n 分——每笔都带最新两级号（响应即最新视图，直接续用）。"""
    for _ in range(n):
        c = court(view, court_no)
        r = live_call(
            client,
            token,
            game_id,
            "point",
            {
                "court_no": court_no,
                "side": side,
                "base_total_seq": view["total_seq"],
                "base_court_seq": c["court_seq"],
            },
        )
        assert r.status_code == 200, r.text
        view = r.json()
    return view


def to_11_9(client: TestClient, token: str, game_id: int, view: dict) -> dict:
    """11 分制安全路径到 11:9（途中 11:10 类分线状态不出现）。"""
    view = pt(client, token, game_id, view, 1, "a", 10)
    view = pt(client, token, game_id, view, 1, "b", 9)
    return pt(client, token, game_id, view, 1, "a", 1)


def settled_11_9(client: TestClient, env: dict) -> dict:
    """开片并记到 11:9（a 胜方在左），返回待确认视图。"""
    return to_11_9(client, env["org"]["token"], env["game_id"], deal_one(client, env))


def write_body(view: dict, court_no: int, **over) -> dict:
    return {
        "court_no": court_no,
        "base_total_seq": view["total_seq"],
        "base_court_seq": court(view, court_no)["court_seq"],
    } | over


def confirm(client: TestClient, token: str, game_id: int, view: dict, **over) -> object:
    body = (
        write_body(
            view,
            1,
            winner_side="a",
            score_a=court(view, 1)["score_a"],
            score_b=court(view, 1)["score_b"],
        )
        | over
    )
    return live_call(client, token, game_id, "settle-confirm", body)


def ratings(client: TestClient, *account_ids: int) -> dict[int, EloRating]:
    """拉指定人的积分账行（detached 只读列，关会话后仍可取属性）。"""
    db = client.app.state.session_factory()
    try:
        rows = (
            db.execute(select(EloRating).where(EloRating.account_id.in_(account_ids)))
            .scalars()
            .all()
        )
        return {r.account_id: r for r in rows}
    finally:
        db.close()


# ---- deal 开打与到分自动待确认（§4.1/§4.3） ----


def test_deal_opens_match_then_auto_pending_at_11_9(client: TestClient):
    env = open_live(client, seed=1)
    v = deal_one(client, env)
    c = court(v, 1)
    assert c["status"] == "playing" and c["seq"] == 1
    assert (c["score_a"], c["score_b"]) == (0, 0)
    ids = [r["id"] for r in env["view"]["players"]]
    assert side_ids(v, 1, "a") == set(ids[:2])
    assert side_ids(v, 1, "b") == set(ids[2:4])
    assert v["queue"] == ids[4:]  # 其余人候场、序不变
    assert all(r["queue_pos"] is None for r in v["players"][:4])

    v = to_11_9(client, env["org"]["token"], env["game_id"], v)
    c = court(v, 1)
    assert c["status"] == "pending" and c["pending_origin"] == "auto"
    assert (c["score_a"], c["score_b"]) == (11, 9)
    assert c["preselect"] == "a"  # 胜方预选=领先方（A4 定值给出）
    assert c["last_winner_side"] == "a"


def test_pending_court_frozen_point_and_player_undo(client: TestClient):
    env = open_live(client, seed=2)
    v = settled_11_9(client, env)
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "point",
        write_body(v, 1, side="a"),
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "court_frozen"
    # 窗内撤一分是全权动作：球友碰不了（§4.5）
    r = live_call(
        client, env["mate"]["token"], env["game_id"], "undo", write_body(v, 1)
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "live_forbidden"


def test_deuce_not_triggered_until_lead_two(client: TestClient):
    env = open_live(client, seed=3)
    v = deal_one(client, env)
    v = pt(client, env["org"]["token"], env["game_id"], v, 1, "a", 10)
    v = pt(client, env["org"]["token"], env["game_id"], v, 1, "b", 10)
    v = pt(client, env["org"]["token"], env["game_id"], v, 1, "a", 1)
    assert court(v, 1)["status"] == "playing"  # 11:10 净胜不够：不弹窗
    v = pt(client, env["org"]["token"], env["game_id"], v, 1, "a", 1)
    assert court(v, 1)["status"] == "pending"  # 12:10 弹窗


def test_clear_from_pending_back_to_playing_people_stay(client: TestClient):
    env = open_live(client, seed=4)
    v = settled_11_9(client, env)
    before = (side_ids(v, 1, "a"), side_ids(v, 1, "b"))
    r = live_call(
        client, env["org"]["token"], env["game_id"], "clear", write_body(v, 1)
    )
    assert r.status_code == 200, r.text
    v = r.json()
    c = court(v, 1)
    assert c["status"] == "playing" and c["pending_origin"] is None
    assert (c["score_a"], c["score_b"]) == (0, 0)
    assert (side_ids(v, 1, "a"), side_ids(v, 1, "b")) == before  # 人不下场


# ---- 窗内撤分两路（§4.5）与预选（§4.4） ----


def test_manual_window_undo_keeps_window(client: TestClient):
    env = open_live(client, seed=5)
    v = deal_one(client, env)
    v = pt(client, env["org"]["token"], env["game_id"], v, 1, "a", 5)
    v = pt(client, env["org"]["token"], env["game_id"], v, 1, "b", 3)
    r = live_call(
        client, env["org"]["token"], env["game_id"], "settle-open", write_body(v, 1)
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert court(v, 1)["status"] == "pending"
    assert court(v, 1)["pending_origin"] == "manual"
    assert court(v, 1)["preselect"] == "a"  # 领先方预选
    r = live_call(client, env["org"]["token"], env["game_id"], "undo", write_body(v, 1))
    assert r.status_code == 200, r.text
    v = r.json()
    c = court(v, 1)
    # 人工开的窗不被误触撤掉：只撤最后一次得分方（b）那 1 分，比分 5:3→5:2 不关窗
    assert c["status"] == "pending" and c["pending_origin"] == "manual"
    assert (c["score_a"], c["score_b"]) == (5, 2)
    # 平分开窗不预选（先清零再记平）
    v = live_call(
        client, env["org"]["token"], env["game_id"], "clear", write_body(v, 1)
    ).json()
    v = pt(client, env["org"]["token"], env["game_id"], v, 1, "a", 2)
    v = pt(client, env["org"]["token"], env["game_id"], v, 1, "b", 2)
    v = live_call(
        client, env["org"]["token"], env["game_id"], "settle-open", write_body(v, 1)
    ).json()
    assert court(v, 1)["preselect"] is None


def test_auto_window_undo_below_line_closes(client: TestClient):
    env = open_live(client, seed=6)
    v = settled_11_9(client, env)
    r = live_call(client, env["org"]["token"], env["game_id"], "undo", write_body(v, 1))
    assert r.status_code == 200, r.text
    c = court(r.json(), 1)
    assert c["status"] == "playing" and c["pending_origin"] is None
    assert (c["score_a"], c["score_b"]) == (10, 9)  # 接着打


# ---- 确认结束：一本账（§4.6） ----


def test_settle_confirm_match_row_elo_and_requeue(client: TestClient):
    env = open_live(client, seed=7, players=6, bring=1)
    v = settled_11_9(client, env)
    # 名册序 org,b(带访客),guest,c,d,e,f —— deal 后 a=[org,b] b=[guest,c]，d/e/f 候场
    rows = env["view"]["players"]
    org_row, b_row, guest_row, c_row = rows[0], rows[1], rows[2], rows[3]
    d_row, e_row, f_row = rows[4], rows[5], rows[6]
    # 抬败方一人的分：期望算得动（1200 均势测不出公式）
    db = client.app.state.session_factory()
    try:
        db.execute(
            select(EloRating).where(EloRating.account_id == c_row["account_id"])
        ).scalar_one().rating = 1600
        db.commit()
    finally:
        db.close()

    # 胜方必须分高方：11:8 记 b 胜 → 拒
    r = confirm(client, env["org"]["token"], env["game_id"], v, winner_side="b")
    assert r.status_code == 422 and r.json()["error"]["code"] == "live_invalid"

    # 窗内调过比分：按改过的 11:8 落账
    r = confirm(client, env["org"]["token"], env["game_id"], v, score_a=11, score_b=8)
    assert r.status_code == 200, r.text
    v = r.json()

    m = v["matches"][-1]
    assert m["court_no"] == 1 and m["seq"] == 1  # 片号、该片第几场
    assert m["winners"] == [
        {"id": org_row["id"], "name": org_row["name"], "guest": False},
        {"id": b_row["id"], "name": b_row["name"], "guest": False},
    ]
    assert [w["id"] for w in m["losers"]] == [guest_row["id"], c_row["id"]]
    assert (m["score_a"], m["score_b"], m["winner_side"]) == (11, 8, "a")
    assert m["ended_at"] == NOW_ISO  # 结束时刻（clock.now 定值）

    # elo：胜队均值 1200 vs 败队 (1200+1600)/2 —— delta=18、败方六成=11（K=24 公式）
    assert [
        (r_["delta"], r_["rating_before"], r_["rating_after"]) for r_ in m["elo_rows"]
    ] == [(18, 1200, 1218), (18, 1200, 1218), (-11, 1200, 1189), (-11, 1600, 1589)]
    assert [r_["guest"] for r_ in m["elo_rows"]] == [False, False, True, False]
    # 正式球友落账、访客不落账不进榜（2.3 裁决：代入 1200 参与期望）
    rt = ratings(
        client,
        org_row["account_id"],
        b_row["account_id"],
        c_row["account_id"],
        d_row["account_id"],
    )
    assert [
        (rt[a].rating, rt[a].play, rt[a].win)
        for a in (org_row["account_id"], b_row["account_id"], c_row["account_id"])
    ] == [(1218, 1, 1), (1218, 1, 1), (1589, 1, 0)]
    assert rt[d_row["account_id"]].play == 0  # 没上场的人零动

    # 回流（默认 all + queue）：四人回队尾、候场首 4 人补全新一队（第 1、2 位一队）
    c1 = court(v, 1)
    assert c1["status"] == "playing" and c1["seq"] == 2
    assert (c1["score_a"], c1["score_b"]) == (0, 0)
    assert side_ids(v, 1, "a") == {d_row["id"], e_row["id"]}
    assert side_ids(v, 1, "b") == {f_row["id"], org_row["id"]}
    assert v["queue"] == [b_row["id"], guest_row["id"], c_row["id"]]  # 没补上的接队尾
    assert v["players"][b_row["id"] - 1]["queue_pos"] == 0


def test_confirm_loser_down_winners_stay(client: TestClient):
    env = open_live(client, seed=8, rules={"down": "loser"})
    v = settled_11_9(client, env)
    rows = env["view"]["players"]
    r = confirm(client, env["org"]["token"], env["game_id"], v)
    assert r.status_code == 200, r.text
    v = r.json()
    # 败方（b 边）回队尾、胜者留场；候场首两人补成新挑战队（不重配）
    assert side_ids(v, 1, "a") == {rows[0]["id"], rows[1]["id"]}
    assert side_ids(v, 1, "b") == {rows[4]["id"], rows[5]["id"]}
    assert v["queue"] == [rows[2]["id"], rows[3]["id"]]
    assert court(v, 1)["status"] == "playing"


def test_confirm_no_redeal_freezes_no_fill(client: TestClient):
    env = open_live(client, seed=9)
    v = settled_11_9(client, env)
    rows = env["view"]["players"]
    r = confirm(client, env["org"]["token"], env["game_id"], v, no_redeal=True)
    assert r.status_code == 200, r.text
    v = r.json()
    c = court(v, 1)
    assert c["status"] == "idle" and c["seq"] == 1  # 不排下一场：片腾空、场次不进
    oncourt = [r["id"] for r in rows[:4]]
    assert v["queue"] == [rows[4]["id"], rows[5]["id"], *oncourt]  # 人只回流定格
    assert all(
        r["court_no"] is None and r["court_side"] is None for r in v["players"][:4]
    )
    assert len(v["matches"]) == 1  # 战报照常落账
    assert ratings(client, rows[0]["account_id"])[rows[0]["account_id"]].play == 1


def test_settle_confirm_idempotent_replay(client: TestClient):
    env = open_live(client, seed=10)
    v = settled_11_9(client, env)
    body = write_body(v, 1, winner_side="a", score_a=11, score_b=9)
    first = live_call(
        client, env["org"]["token"], env["game_id"], "settle-confirm", body
    )
    assert first.status_code == 200, first.text
    after = first.json()
    # 断网重发同一笔（号已旧）：幂等回当前视图，不重落
    again = live_call(
        client, env["org"]["token"], env["game_id"], "settle-confirm", body
    )
    assert again.status_code == 200, again.text
    assert again.json() == after
    v = live_get(client, env["game_id"], env["org"]["token"])
    assert len(v["matches"]) == 1
    rows = env["view"]["players"]
    assert ratings(client, rows[0]["account_id"])[rows[0]["account_id"]].play == 1


# ---- 取消对局（§4.7） ----


def test_cancel_returns_players_to_queue_head(client: TestClient):
    env = open_live(client, seed=11)
    rows = env["view"]["players"]
    oncourt = [r["id"] for r in rows[:4]]

    v = deal_one(client, env)  # 在打取消
    r = live_call(
        client, env["org"]["token"], env["game_id"], "cancel", write_body(v, 1)
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["queue"] == [*oncourt, rows[4]["id"], rows[5]["id"]]  # 原样回流队首
    c = court(v, 1)
    assert c["status"] == "idle" and (c["score_a"], c["score_b"]) == (0, 0)

    v = to_11_9(client, env["org"]["token"], env["game_id"], deal_one(client, env))
    r = live_call(
        client, env["org"]["token"], env["game_id"], "cancel", write_body(v, 1)
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert court(v, 1)["status"] == "idle" and court(v, 1)["pending_origin"] is None
    assert v["queue"] == [*oncourt, rows[4]["id"], rows[5]["id"]]
    assert v["matches"] == []  # 作废不留战报
    # 全员积分零动：无战报即无结算
    assert ratings(client, rows[0]["account_id"])[rows[0]["account_id"]].play == 0


# ---- 两级号防线（§4.8/附录 B1） ----


def test_stale_total_and_court_409_carries_latest_view(client: TestClient):
    env = open_live(client, seed=12)
    v0 = deal_one(client, env)  # total 1→2
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "point",
        write_body(v0, 1, side="a", base_total_seq=1),  # 旧总号：断网重发/连击
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "live_stale_total"
    assert r.json()["view"]["total_seq"] == v0["total_seq"]  # 最新画面随 409 送来
    assert r.json()["view"]["game_id"] == env["game_id"]

    v1 = pt(client, env["org"]["token"], env["game_id"], v0, 1, "a")  # 片号 +1
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "point",
        # 总号新（对得上）、片号旧（同片并发：只拦这片）
        write_body(v1, 1, side="a", base_court_seq=court(v0, 1)["court_seq"]),
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "live_stale_court"
    assert r.json()["view"]["total_seq"] == v1["total_seq"]
    assert court(r.json()["view"], 1)["court_seq"] == court(v1, 1)["court_seq"]
    # 别片不受牵连：旧片号只拦该片（多片互不等待见 test_multi_court_parallel_independent）


def test_multi_court_parallel_independent(client: TestClient):
    env = open_live(client, seed=13, players=9)
    ids = [r["id"] for r in env["view"]["players"]]
    v = deal_court(
        client,
        env["org"]["token"],
        env["game_id"],
        env["view"],
        [
            {"court_no": 1, "a": ids[:2], "b": ids[2:4]},
            {"court_no": 2, "a": ids[4:6], "b": ids[6:8]},
        ],
    )
    v = to_11_9(client, env["org"]["token"], env["game_id"], v)  # 1 号片进待确认
    assert court(v, 1)["status"] == "pending"
    v = pt(client, env["org"]["token"], env["game_id"], v, 2, "b", 2)  # 2 号片照打
    assert (court(v, 2)["score_a"], court(v, 2)["score_b"]) == (0, 2)
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "point",
        write_body(v, 1, side="a"),
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "court_frozen"


# ---- 权限分级（附录 B1）与散场拒收 ----


def test_score_open_to_arrived_full_power_actions_gated(client: TestClient):
    env = open_live(client, seed=14)
    v = deal_one(client, env)
    token, gid = env["mate"]["token"], env["game_id"]
    v = pt(client, token, gid, v, 1, "a", 1)  # 球友可记分
    r = live_call(client, token, gid, "undo", write_body(v, 1))  # 在打可撤分
    assert r.status_code == 200, r.text
    v = r.json()
    for action in ("clear", "settle-open", "settle-confirm", "cancel"):
        body = write_body(v, 1)
        if action == "settle-confirm":
            body |= {"winner_side": "a", "score_a": 1, "score_b": 0}
        r = live_call(client, token, gid, action, body)
        assert r.status_code == 403 and r.json()["error"]["code"] == "live_forbidden", (
            action,
            r.text,
        )
    stranger = signup(client, "13800039999", "s")
    r = live_call(client, stranger["token"], gid, "point", write_body(v, 1, side="a"))
    assert r.status_code == 403 and r.json()["error"]["code"] == "live_forbidden"


def test_write_after_game_ended_rejected(client: TestClient):
    env = open_live(client, seed=15)
    v = deal_one(client, env)
    db = client.app.state.session_factory()
    try:
        game = db.get(Game, env["game_id"])
        game.ended_at = game.end_at  # 散场时刻锚（批3 的 end 端点未到，直落）
        db.commit()
    finally:
        db.close()
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "point",
        write_body(v, 1, side="a"),
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "live_ended"


# ---- 撤一分守卫（§4.1：撤不成负） ----


def test_undo_never_negative_noop_at_zero(client: TestClient):
    env = open_live(client, seed=16)
    v = deal_one(client, env)
    r = live_call(client, env["org"]["token"], env["game_id"], "undo", write_body(v, 1))
    assert r.status_code == 200, r.text  # 0:0 无可撤：原样回，不动账不进号
    v0 = r.json()
    assert (court(v0, 1)["score_a"], court(v0, 1)["score_b"]) == (0, 0)
    assert v0["total_seq"] == v["total_seq"]
    v1 = pt(client, env["org"]["token"], env["game_id"], v0, 1, "a", 1)
    r = live_call(
        client, env["org"]["token"], env["game_id"], "undo", write_body(v1, 1)
    )
    v2 = r.json()
    assert (court(v2, 1)["score_a"], court(v2, 1)["score_b"]) == (0, 0)
    r = live_call(
        client, env["org"]["token"], env["game_id"], "undo", write_body(v2, 1)
    )
    v3 = r.json()
    assert court(v3, 1)["score_a"] == 0  # 连撤两下停在 0:0，不出现 -1
    assert v3["total_seq"] == v2["total_seq"]  # 第二下是无可撤：不进号


# ---- 读链与开账路由冒烟（start 幂等/分权在批1 测过 LiveBook，这里锁路由面） ----


def test_start_route_permission_and_idempotent(client: TestClient):
    env = open_live(client, seed=17, players=3)
    r = live_call(client, env["mate"]["token"], env["game_id"], "start", {})
    assert r.status_code == 403 and r.json()["error"]["code"] == "organizer_only"
    again = live_call(client, env["org"]["token"], env["game_id"], "start", {})
    assert again.status_code == 200, again.text
    assert again.json()["players"] == env["view"]["players"]  # 再点开账当没事


def test_anonymous_can_read_view(client: TestClient):
    env = open_live(client, seed=18, players=3)
    v = live_get(client, env["game_id"])  # 不带钥匙：游客可读
    assert v["game_id"] == env["game_id"] and v["ended"] is False
    assert len(v["players"]) == 3 and v["courts"] == [] and v["matches"] == []


# ---- deal 把关（总账只认事实：名册内 + 候场队头顺位） ----


def test_deal_validates_roster_and_queue_head(client: TestClient):
    env = open_live(client, seed=19)
    v = env["view"]
    ids = [r["id"] for r in v["players"]]
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "deal",
        {
            "courts": [{"court_no": 1, "a": [999], "b": [ids[1]]}],
            "base_total_seq": v["total_seq"],
        },
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "live_invalid"
    r = live_call(  # 跳位：队头 4 人不取、直取队尾
        client,
        env["org"]["token"],
        env["game_id"],
        "deal",
        {
            "courts": [{"court_no": 1, "a": ids[4:5], "b": ids[5:6]}],
            "base_total_seq": v["total_seq"],
        },
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "live_invalid"
    v = deal_one(client, env)
    r = live_call(  # 在打的片不能重复发牌
        client,
        env["org"]["token"],
        env["game_id"],
        "deal",
        {
            "courts": [{"court_no": 1, "a": ids[4:5], "b": ids[5:6]}],
            "base_total_seq": v["total_seq"],
        },
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "live_invalid"
