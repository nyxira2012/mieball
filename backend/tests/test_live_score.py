"""现场上传结算链（2.3 批2 · 2026-10-09 记分本地化修订）—— 记分在各手机本地，
服务端只收「上传结算」：deal 开打、playing 片直接传分落账（谁先传先落）、后到
不同分 409 settle_recorded、同分同位幂等 200、一本账（战报行 + EloRating 结算 +
访客不落账 + 回流四件套 + no_redeal 定格）、改分重落（全权、窗口=下一场落账前，
战报/Elo/DUPR 重写、物理轮转不动）、取消回流队首、两级号 409 携最新视图、
权限分级（上传=到场即可，改分/取消=全权）。

考勤与入队的写端点在 test_live_end 册（check），到场/候场队真值直落数据库；
时刻基准 FakeClock 10-04 12:00（conftest）。
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import (
    DuprDetail,
    DuprRating,
    EloRating,
    Game,
    LiveMatch,
    LivePlayer,
    LiveState,
)
from app.services import dupr

from .conftest import auth, signup
from .test_games_actions import join_ok
from .test_games_read import publish
from .test_logs import audit_rows, make_client


def audit_row_of(rows: list[dict], action: str) -> dict:
    # 局部副本（test_audit 同名件）：score 被 test_audit 间接依赖，反向 import 成环
    return next(r for r in rows if r["action"] == action)


NOW_ISO = "2026-10-04T12:00:00+08:00"  # FakeClock 基点（conftest）


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


def lock_game_direct(client: TestClient, game_id: int) -> None:
    """2.5 开账闸前置定格：成局才可开的真值直落数据库（沿本文件先例，免拨钟：
    过截止+懒判定的真实链路在 test_live_base 的守门组专测）。"""
    db = client.app.state.session_factory()
    try:
        db.get(Game, game_id).state = "locked"
        db.commit()
    finally:
        db.close()


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
    全员到场、按行序进候场队（报到端点在 test_live_end 册，真值直落）。返回现场环境。"""
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
    lock_game_direct(client, g["id"])
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


def write_body(view: dict, court_no: int, **over) -> dict:
    return {
        "court_no": court_no,
        "base_total_seq": view["total_seq"],
        "base_court_seq": court(view, court_no)["court_seq"],
    } | over


def confirm(client: TestClient, token: str, game_id: int, view: dict, **over):
    """上传结算一笔（playing 片直接传本地分）：默认 a 方 11:9，over 覆写载荷。"""
    body = (
        write_body(
            view,
            over.pop("court_no", 1),
            winner_side=over.pop("winner_side", "a"),
            score_a=over.pop("score_a", 11),
            score_b=over.pop("score_b", 9),
            no_redeal=over.pop("no_redeal", False),
        )
        | over
    )
    return live_call(client, token, game_id, "settle-confirm", body)


def overwrite(client: TestClient, token: str, game_id: int, view: dict, **over):
    """改分重落一笔：默认改成 a 方 11:9，over 覆写载荷。"""
    body = (
        write_body(
            view,
            over.pop("court_no", 1),
            winner_side=over.pop("winner_side", "a"),
            score_a=over.pop("score_a", 11),
            score_b=over.pop("score_b", 9),
        )
        | over
    )
    return live_call(client, token, game_id, "settle-overwrite", body)


def settled_11_9(client: TestClient, env: dict) -> dict:
    """开片并把本地账按 a 方 11:9 上传落账（确认即续场），返回落账后视图。"""
    r = confirm(client, env["org"]["token"], env["game_id"], deal_one(client, env))
    assert r.status_code == 200, r.text
    return r.json()


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


def dupr_ratings(client: TestClient, *account_ids: int) -> dict[int, DuprRating]:
    db = client.app.state.session_factory()
    try:
        rows = (
            db.execute(select(DuprRating).where(DuprRating.account_id.in_(account_ids)))
            .scalars()
            .all()
        )
        return {r.account_id: r for r in rows}
    finally:
        db.close()


# ---- deal 开打（§4.1）与视图契约收窄（2026-10-09：服务端不记进行中比分） ----


def test_deal_opens_match_and_view_contract(client: TestClient):
    env = open_live(client, seed=1)
    v = deal_one(client, env)
    c = court(v, 1)
    assert c["status"] == "playing" and c["seq"] == 1
    # 记分本地化契约：比分/最后得分方/待确认来源/预选全裁，只留片号与分制快照
    assert set(c) == {
        "court_no",
        "status",
        "seq",
        "court_seq",
        "scoring",
        "elo_preview",
    }
    ids = [r["id"] for r in env["view"]["players"]]
    assert side_ids(v, 1, "a") == set(ids[:2])
    assert side_ids(v, 1, "b") == set(ids[2:4])
    assert v["queue"] == ids[4:]  # 其余人候场、序不变
    assert all(r["queue_pos"] is None for r in v["players"][:4])


def test_scoring_switch_new_court_uses_new_scoring(client: TestClient):
    """改分制切真（2.6 机制A）：改 21 后再开的片自带 21 快照（本地判到分在前端，
    快照随视图给卡头亮数用）。"""
    env = open_live(client, seed=41)
    gid, token = env["game_id"], env["org"]["token"]
    v = live_get(client, gid, token)
    r = live_call(
        client, token, gid, "rules", {"scoring": 21, "base_total_seq": v["total_seq"]}
    )
    assert r.status_code == 200, r.text
    assert court(deal_one(client, env), 1)["scoring"] == 21


# ---- 上传结算：playing 片直接传分（谁先传先落） ----


def test_upload_settles_directly_match_elo_and_requeue(client: TestClient):
    """到场普通球友把本地账直接传上来：一本账——战报行（胜方/比分全吃入参）+
    Elo 结算（访客不落账）+ 回流补位，同一 commit。"""
    env = open_live(client, seed=7, players=6, bring=1)
    v = deal_one(client, env)
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
    r = confirm(client, env["mate"]["token"], env["game_id"], v, winner_side="b")
    assert r.status_code == 422 and r.json()["error"]["code"] == "live_invalid"

    # 到场球友按本地账传 11:8、a 胜 → 直接落账（全权不要求）
    r = confirm(client, env["mate"]["token"], env["game_id"], v, score_a=11, score_b=8)
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
    assert side_ids(v, 1, "a") == {d_row["id"], e_row["id"]}
    assert side_ids(v, 1, "b") == {f_row["id"], org_row["id"]}
    assert v["queue"] == [b_row["id"], guest_row["id"], c_row["id"]]  # 没补上的接队尾
    assert v["players"][b_row["id"] - 1]["queue_pos"] == 0


def test_upload_permission_arrived_only(client: TestClient):
    """上传权=到场（§4.1 口径）：未到场（absent）拒，到场即放行——组织者不在场
    也拦不住球友记自家的账。"""
    env = open_live(client, seed=3)
    v = deal_one(client, env)
    db = client.app.state.session_factory()
    try:
        row = db.execute(
            select(LivePlayer).where(
                LivePlayer.game_id == env["game_id"],
                LivePlayer.account_id == env["mate"]["account"]["id"],
            )
        ).scalar_one()
        row.check = "absent"
        db.commit()
    finally:
        db.close()
    r = confirm(client, env["mate"]["token"], env["game_id"], v)
    assert r.status_code == 403 and r.json()["error"]["code"] == "live_forbidden"
    db = client.app.state.session_factory()
    try:
        row = db.get(LivePlayer, row.id)
        row.check = "ok"
        db.commit()
    finally:
        db.close()
    r = confirm(client, env["mate"]["token"], env["game_id"], v)
    assert r.status_code == 200, r.text


def test_upload_conflict_distinct_score_409_settle_recorded(client: TestClient):
    """双传冲突（裁决②）：A 传 11:9 先落，B 拿着旧画面传 9:11 → 409
    settle_recorded，message 说清已记比分、最新视图随 409 送来。"""
    env = open_live(client, seed=4)
    v0 = deal_one(client, env)  # B 出发时的画面
    r = confirm(client, env["org"]["token"], env["game_id"], v0, score_a=11, score_b=9)
    assert r.status_code == 200, r.text
    v1 = r.json()
    r = confirm(
        client,
        env["mate"]["token"],
        env["game_id"],
        v0,
        winner_side="b",
        score_a=9,
        score_b=11,
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "settle_recorded"
    assert "已按 11:9 记账" in r.json()["error"]["message"]
    assert r.json()["view"]["total_seq"] == v1["total_seq"]  # 最新画面随 409 送来
    assert len(live_get(client, env["game_id"], env["org"]["token"])["matches"]) == 1


def test_upload_same_score_replay_200_idempotent(client: TestClient):
    env = open_live(client, seed=10)
    v = deal_one(client, env)
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


def test_upload_rejected_when_court_not_playing(client: TestClient):
    """片校验只收 playing：没开的片、清扫后腾空的片都不收上传。"""
    env = open_live(client, seed=5)
    v = env["view"]
    r = live_call(  # 没开过的片（片行都不存在）：片号无从对起，直落 body
        client,
        env["org"]["token"],
        env["game_id"],
        "settle-confirm",
        {
            "court_no": 1,
            "winner_side": "a",
            "score_a": 11,
            "score_b": 9,
            "base_total_seq": v["total_seq"],
            "base_court_seq": 1,
        },
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "court_idle"
    v = settled_11_9(client, env)  # 落账一场后用 no_redeal 腾空（换比分避开重放）
    v = confirm(
        client, env["org"]["token"], env["game_id"], v, no_redeal=True, score_b=8
    ).json()
    assert court(v, 1)["status"] == "idle"
    r = confirm(
        client,
        env["org"]["token"],
        env["game_id"],
        v,
        score_a=9,
        score_b=11,
        winner_side="b",
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "court_idle"


# ---- 在打片 ±积分预演双分支（§4.11，2026-10-09 改挂 playing 片） ----


def test_playing_elo_preview_two_branches_equal_settlement(client: TestClient):
    """预演=落账：在打片 elo_preview 给 A/B 两套（胜队在前、访客同路），
    上传所选分支的 elo_rows 与预演逐行一致；非在打片不给。"""
    env = open_live(client, seed=2)
    v = deal_one(client, env)
    pre = court(v, 1)["elo_preview"]
    ids_a = side_ids(v, 1, "a")
    ids_b = side_ids(v, 1, "b")
    # 行序胜队在前（与 settle_confirm 同走名册序）：两分支都是先涨后扣，
    # 区别在前两行是谁——A 分支 A 队在前、B 分支 B 队在前
    assert [r["delta"] > 0 for r in pre["a"]] == [True, True, False, False]
    assert [r["delta"] > 0 for r in pre["b"]] == [True, True, False, False]
    assert {r["account_id"] for r in pre["a"][:2]} == {
        p["account_id"] for p in v["players"] if p["id"] in ids_a
    }
    assert {r["account_id"] for r in pre["b"][:2]} == {
        p["account_id"] for p in v["players"] if p["id"] in ids_b
    }
    # 上传 A 胜：落账 elo_rows 与预演 A 分支逐行相等（同一条公式路，前端零公式）
    r = confirm(client, env["org"]["token"], env["game_id"], v)
    assert r.status_code == 200, r.text
    assert r.json()["matches"][-1]["elo_rows"] == pre["a"]

    env2 = open_live(client, seed=20)  # 非在打片不随附预演
    v2 = settled_11_9(client, env2)
    v2 = confirm(
        client, env2["org"]["token"], env2["game_id"], v2, no_redeal=True, score_b=8
    ).json()
    assert court(v2, 1)["elo_preview"] is None


# ---- 改分重落（2026-10-09 裁决③：战报/Elo/DUPR 重写，物理轮转不动） ----


def test_overwrite_rewrites_match_elo_dupr_not_rotation(client, fake):
    env = open_live(client, seed=8, players=6, bring=1)
    v = deal_one(client, env)
    rows = env["view"]["players"]
    org_row, b_row, guest_row, c_row = rows[0], rows[1], rows[2], rows[3]
    d_row, e_row, f_row = rows[4], rows[5], rows[6]
    db = client.app.state.session_factory()
    try:
        db.execute(
            select(EloRating).where(EloRating.account_id == c_row["account_id"])
        ).scalar_one().rating = 1600
        db.commit()
    finally:
        db.close()

    r = confirm(client, env["org"]["token"], env["game_id"], v, score_a=11, score_b=9)
    assert r.status_code == 200, r.text
    after_upload = r.json()
    fake.advance(minutes=30)  # 落账与改分不同时刻：ended_at 不回头才验得出来

    # 组织者把 11:9(a) 改判成 9:11(b)：四人原班换边
    r = overwrite(
        client,
        env["org"]["token"],
        env["game_id"],
        after_upload,
        winner_side="b",
        score_a=9,
        score_b=11,
    )
    assert r.status_code == 200, r.text
    v = r.json()

    # 战报行原行改写：不新落一场，胜方名单=原败方四人换边、ended_at 保持原时刻
    assert len(v["matches"]) == 1
    m = v["matches"][-1]
    assert (m["court_no"], m["seq"]) == (1, 1)
    assert (m["score_a"], m["score_b"], m["winner_side"]) == (9, 11, "b")
    assert [w["id"] for w in m["winners"]] == [guest_row["id"], c_row["id"]]
    assert [w["id"] for w in m["losers"]] == [org_row["id"], b_row["id"]]
    assert m["ended_at"] == NOW_ISO

    # Elo 反算重加：旧 delta 全退（rating/play/win 回赛前）、按新划分重算
    # 新胜队均值 1400 vs 败队 1200 → 强队赢期望高：delta=6、败方六成=4；快照=新账面
    assert [
        (r_["delta"], r_["rating_before"], r_["rating_after"]) for r_ in m["elo_rows"]
    ] == [(6, 1200, 1206), (6, 1600, 1606), (-4, 1200, 1196), (-4, 1200, 1196)]
    rt = ratings(
        client,
        org_row["account_id"],
        b_row["account_id"],
        c_row["account_id"],
    )
    assert [
        (rt[a].rating, rt[a].play, rt[a].win)
        for a in (org_row["account_id"], b_row["account_id"], c_row["account_id"])
    ] == [(1196, 1, 0), (1196, 1, 0), (1606, 1, 1)]

    # DUPR 明细删行重插：仍每人一行、胜负比分翻面；派生分=窗口重放该明细的结果
    # （战报 id 不进视图，直查行）
    db = client.app.state.session_factory()
    try:
        m_row = db.execute(
            select(LiveMatch).where(LiveMatch.game_id == env["game_id"])
        ).scalar_one()
        details = (
            db.execute(select(DuprDetail).where(DuprDetail.match_id == m_row.id))
            .scalars()
            .all()
        )
    finally:
        db.close()
    assert {d.account_id for d in details} == {
        org_row["account_id"],
        b_row["account_id"],
        c_row["account_id"],
    }
    for d in details:
        assert d.won is (d.account_id == c_row["account_id"])
        assert (d.score_w, d.score_l) == (11, 9)
        expected = dupr.replay(
            dupr.GUEST_DUPR,
            [
                {
                    "partner_rating": d.partner_rating,
                    "opp_a": d.opp_a,
                    "opp_b": d.opp_b,
                    "score_w": d.score_w,
                    "score_l": d.score_l,
                    "won": d.won,
                }
            ],
        )
        assert dupr_ratings(client, d.account_id)[d.account_id].rating == expected

    # 物理轮转不动：回流格局、候场队、场次号照上传那一刻（只进片号/总号）
    assert court(v, 1)["status"] == "playing" and court(v, 1)["seq"] == 2
    assert side_ids(v, 1, "a") == {d_row["id"], e_row["id"]}
    assert side_ids(v, 1, "b") == {f_row["id"], org_row["id"]}
    assert v["queue"] == after_upload["queue"]
    assert court(v, 1)["court_seq"] == court(after_upload, 1)["court_seq"] + 1


def test_overwrite_rejected_once_next_match_settled(client: TestClient):
    """窗口=下一场落账前（裁决③④）：下一场已落账，旧画面里的改分拒收、
    最新一场不被误改。"""
    env = open_live(client, seed=9)
    v1 = settled_11_9(client, env)  # 第一场 11:9(a) 落账、第二场开打
    r = confirm(client, env["org"]["token"], env["game_id"], v1, score_b=8)
    assert r.status_code == 200, r.text
    v2 = r.json()
    # 拿第一场落账后的片号（下一场落账前的画面）改分：片号闸退回
    r = overwrite(
        client,
        env["org"]["token"],
        env["game_id"],
        v2,
        winner_side="b",
        score_a=9,
        score_b=11,
        base_court_seq=court(v1, 1)["court_seq"],
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "live_stale_court"
    cur = live_get(client, env["game_id"], env["org"]["token"])
    assert len(cur["matches"]) == 2
    assert (cur["matches"][-1]["score_a"], cur["matches"][-1]["score_b"]) == (11, 8)
    # 拿最新画面改的永远是自己看见的最新一场（窗口内）：放行
    r = overwrite(
        client,
        env["org"]["token"],
        env["game_id"],
        v2,
        winner_side="b",
        score_a=9,
        score_b=11,
    )
    assert r.status_code == 200, r.text
    cur = live_get(client, env["game_id"], env["org"]["token"])
    assert (cur["matches"][-1]["score_a"], cur["matches"][-1]["winner_side"]) == (
        9,
        "b",
    )


def test_overwrite_full_power_only_and_idempotent(client: TestClient):
    env = open_live(client, seed=30)
    v = settled_11_9(client, env)
    # 球友不能改分（全权闸）
    r = overwrite(
        client, env["mate"]["token"], env["game_id"], v, score_a=11, score_b=8
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "live_forbidden"
    # 组织者改分；同载荷重复覆盖幂等 200（不重复反算）
    r = overwrite(client, env["org"]["token"], env["game_id"], v, score_a=11, score_b=8)
    assert r.status_code == 200, r.text
    after = r.json()
    rt0 = ratings(client, after["players"][0]["account_id"])[
        after["players"][0]["account_id"]
    ]
    again = overwrite(
        client, env["org"]["token"], env["game_id"], v, score_a=11, score_b=8
    )
    assert again.status_code == 200, again.text
    assert again.json() == after
    rt1 = ratings(client, after["players"][0]["account_id"])[
        after["players"][0]["account_id"]
    ]
    assert (rt1.rating, rt1.play, rt1.win) == (rt0.rating, rt0.play, rt0.win)


# ---- 取消对局（§4.7）：非清扫取消回流即重发（2.8 验收 3），清扫态只清不补 ----


def test_cancel_refills_right_away_recognizing_skip(client: TestClient):
    """验收 3（422 消亡）：非清扫取消回流队首 → 出口自动重发认歇——含歇者在
    取人窗口不再被打回；作废不留战报、积分零动。"""
    env = open_live(client, seed=11)
    rows = env["view"]["players"]
    gid, tok = env["game_id"], env["org"]["token"]
    v = deal_one(client, env)
    v = tempo(client, tok, gid, v, rows[2]["id"], "skip")  # 场上设歇
    r = live_call(client, tok, gid, "cancel", write_body(v, 1))
    assert r.status_code == 200, r.text
    v = r.json()
    # 回流即重发：歇者 2 被跳过（消耗一次）、坑由 3/4 顶
    assert court(v, 1)["status"] == "playing"
    assert side_ids(v, 1, "a") == {rows[0]["id"], rows[1]["id"]}
    assert side_ids(v, 1, "b") == {rows[3]["id"], rows[4]["id"]}
    assert player(v, rows[2]["id"])["skip"] == 0
    assert v["queue"] == [rows[2]["id"], rows[5]["id"]]
    assert v["matches"] == []  # 作废不留战报
    assert ratings(client, rows[0]["account_id"])[rows[0]["account_id"]].play == 0


def test_cancel_sweep_variant_only_clears(client: TestClient):
    """清扫态取消（no_redeal 声明豁免）：只清不补——场上的人原样回流队首、
    片留空好散场。"""
    env = open_live(client, seed=16)
    rows = env["view"]["players"]
    gid, tok = env["game_id"], env["org"]["token"]
    v = deal_one(client, env)
    oncourt = [r["id"] for r in rows[:4]]
    r = live_call(client, tok, gid, "cancel", write_body(v, 1) | {"no_redeal": True})
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["queue"] == [*oncourt, rows[4]["id"], rows[5]["id"]]  # 原样回流队首
    c = court(v, 1)
    assert c["status"] == "idle" and c["elo_preview"] is None
    assert v["matches"] == []  # 作废不留战报
    # 全员积分零动：无战报即无结算
    assert ratings(client, rows[0]["account_id"])[rows[0]["account_id"]].play == 0


# ---- 两级号防线（§4.8/附录 B1）：409 携最新视图 ----


def test_stale_total_and_court_409_carries_latest_view(client: TestClient):
    env = open_live(client, seed=12)
    v0 = deal_one(client, env)  # total 1→2
    r = confirm(
        client,
        env["org"]["token"],
        env["game_id"],
        v0,
        base_total_seq=1,  # 旧总号：断网重发/连击
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "live_stale_total"
    assert r.json()["view"]["total_seq"] == v0["total_seq"]  # 最新画面随 409 送来
    assert r.json()["view"]["game_id"] == env["game_id"]

    # 片号旧而总号新：走 cancel 前进片号后、重新开打（回 playing）再拿新总号+
    # 旧片号传分（未被落账 → 纯防线）
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "cancel",
        write_body(v0, 1),
    )
    assert r.status_code == 200, r.text
    v1 = deal_one(client, env)
    r = confirm(
        client,
        env["org"]["token"],
        env["game_id"],
        v1,
        base_court_seq=court(v0, 1)["court_seq"],
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "live_stale_court"
    assert r.json()["view"]["total_seq"] == v1["total_seq"]
    assert court(r.json()["view"], 1)["court_seq"] == court(v1, 1)["court_seq"]


def test_multi_court_independent_court_seq(client: TestClient):
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
    seq2 = court(v, 2)["court_seq"]
    v = confirm(
        client, env["org"]["token"], env["game_id"], v
    ).json()  # 1 号片落账（总号进）
    assert len(v["matches"]) == 1
    # 2 号片照打：总号变了、该片片号没动——带最新总号+原片号上传照常落账
    r = confirm(client, env["org"]["token"], env["game_id"], v, court_no=2)
    assert r.status_code == 200, r.text
    assert len(r.json()["matches"]) == 2
    assert court(r.json(), 2)["court_seq"] == seq2 + 1


# ---- 权限分级（附录 B1）与散场拒收 ----


def test_full_power_actions_gated_upload_open_to_arrived(client: TestClient):
    env = open_live(client, seed=14)
    v = deal_one(client, env)
    token, gid = env["mate"]["token"], env["game_id"]
    for action in ("cancel", "settle-overwrite"):
        body = write_body(v, 1)
        if action == "settle-overwrite":
            body |= {"winner_side": "a", "score_a": 1, "score_b": 0}
        r = live_call(client, token, gid, action, body)
        assert r.status_code == 403 and r.json()["error"]["code"] == "live_forbidden", (
            action,
            r.text,
        )
    stranger = signup(client, "13800039999", "s")
    r = confirm(client, stranger["token"], env["game_id"], v)
    assert r.status_code == 403 and r.json()["error"]["code"] == "live_forbidden"


def test_write_after_game_ended_rejected(client: TestClient):
    env = open_live(client, seed=15)
    v = deal_one(client, env)
    db = client.app.state.session_factory()
    try:
        game = db.get(Game, env["game_id"])
        game.ended_at = game.end_at  # 散场时刻锚（end 端点链路在 test_live_end 册）
        db.commit()
    finally:
        db.close()
    r = confirm(client, env["org"]["token"], env["game_id"], v)
    assert r.status_code == 409 and r.json()["error"]["code"] == "live_ended"


# ---- 读链与开账路由冒烟（守门分支在批1/2.5 测过 LiveBook，这里锁路由面） ----


def test_start_route_opened_idempotent_and_open_game_blocked(client: TestClient):
    env = open_live(client, seed=17, players=3)
    # 已开账：成员再点也只回视图（2.5 后成员本就有开账权，幂等先行）
    r = live_call(client, env["mate"]["token"], env["game_id"], "start", {})
    assert r.status_code == 200, r.text
    again = live_call(client, env["org"]["token"], env["game_id"], "start", {})
    assert again.status_code == 200, again.text
    assert again.json()["players"] == env["view"]["players"]  # 再点开账当没事
    # 报名中的局谁都不能开（2.5 §4.4 收紧——组织者旧路就此关闭）
    org2 = signup(client, _ph(179, 1), "o")
    g2 = publish(client, org2["token"], visibility="public")
    r = live_call(client, org2["token"], g2["id"], "start", {})
    assert r.status_code == 403 and r.json()["error"]["code"] == "live_requires_forced"


def test_anonymous_can_read_view(client: TestClient):
    env = open_live(client, seed=18, players=3)
    v = live_get(client, env["game_id"])  # 不带钥匙：游客可读
    assert v["game_id"] == env["game_id"] and v["ended"] is False
    assert len(v["players"]) == 3 and v["courts"] == [] and v["matches"] == []


# ---- 排阵上报载荷退役（2.8）：收下即丢、闸随收编删除 ----


def test_deal_payload_retired_gate_gone(client: TestClient):
    """验收 3 后半：旧牌面（名册外/跳位/在打片重复发）一律收下即丢不再校验，
    「发牌的人不在候场队首」在发牌链无触发路径；实际动作=按后端真值补所有
    空片，空手幂等回最新视图不双开。"""
    env = open_live(client, seed=19)
    v = env["view"]
    ids = [r["id"] for r in v["players"]]
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "deal",
        {
            "courts": [{"court_no": 1, "a": [999], "b": []}],
            "base_total_seq": v["total_seq"],
        },
    )
    assert r.status_code == 200, r.text  # 旧「名册外的人」422 消亡
    v = r.json()
    assert court(v, 1)["status"] == "playing"  # 实际=后端按候场队首补片
    assert side_ids(v, 1, "a") == {ids[0], ids[1]}
    # 跳位牌面 + 在打片再来一手（旧 422 两连）：照单全收、空手不双开
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "deal",
        {
            "courts": [{"court_no": 1, "a": ids[4:5], "b": ids[5:6]}],
            "base_total_seq": v["total_seq"],
        },
    )
    assert r.status_code == 200, r.text
    after = r.json()
    assert after["total_seq"] == v["total_seq"] + 1  # 空手也是一写动作：恰一 bump
    assert court(after, 1)["seq"] == 1  # 片号没进：不双开
    assert after["queue"] == ids[4:]


def test_deal_full_power_only(client: TestClient):
    """验收 10：一键排阵收权（2.8 批3）——事件驱动补片已归写动作出口，手动 deal
    是全权本事：到场普通球友 403；被封管理员与组织者同权 200（空手幂等）。"""
    env = open_live(client, seed=42)
    gid = env["game_id"]
    v = live_get(client, gid, env["org"]["token"])
    # 到场普通球友（check=ok，非组织者非管理员）：403
    r = live_call(
        client,
        env["mate"]["token"],
        gid,
        "deal",
        {"base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "live_forbidden"
    # 组织者封 mate 为管理员 → 全权随授，一键排阵放行（此刻无空片：空手幂等回视图）
    mate_row_id = next(
        r_["id"]
        for r_ in v["players"]
        if r_["account_id"] == env["mate"]["account"]["id"]
    )
    r = live_call(
        client,
        env["org"]["token"],
        gid,
        "set-admin",
        {"player_id": mate_row_id, "base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200, r.text
    v2 = r.json()  # 封管也是一写动作：号已进，deal 吃新号
    r = live_call(
        client,
        env["mate"]["token"],
        gid,
        "deal",
        {"base_total_seq": v2["total_seq"]},
    )
    assert r.status_code == 200, r.text


# ---- 2.8 批2：写路径出口补片（验收 2/6/8/9） ----


def seed_row(client: TestClient, player_id: int, **kw) -> None:
    """直落一行名册真值（本册局部改态用；批量版在 test_live_end.seed_rows）。"""
    from app.db.models import LivePlayer as LP

    db = client.app.state.session_factory()
    try:
        row = db.get(LP, player_id)
        for k, val in kw.items():
            setattr(row, k, val)
        db.commit()
    finally:
        db.close()


def test_idle_fill_skips_queue_skipper_and_consumes(client: TestClient):
    """验收 2（歇·空片路）：歇者坐取人窗口 → 补片跳过他、坑由下位顶、skip 消耗
    一次、保位留队（报到路触发）。"""
    env = open_live(client, seed=91, players=5)
    gid, tok = env["game_id"], env["org"]["token"]
    ids = [r["id"] for r in env["view"]["players"]]
    seed_row(client, ids[3], check="absent", queue_pos=None)  # 拉薄候场防抢补
    v = live_get(client, gid, tok)
    v = tempo(client, tok, gid, v, ids[0], "skip")  # 队首设歇：可发 3 < 4，不补
    assert v["courts"] == [] and player(v, ids[0])["skip"] == 1
    # 报到凑齐第四个可发人：补片跳过歇者、坑由下位顶
    r = live_call(
        client,
        tok,
        gid,
        "check",
        {"player_id": ids[3], "check": "ok", "base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert court(v, 1)["status"] == "playing"
    assert side_ids(v, 1, "a") == {ids[1], ids[2]}
    assert side_ids(v, 1, "b") == {ids[4], ids[3]}
    assert player(v, ids[0])["skip"] == 0  # 轮到即消耗一次
    assert v["queue"] == [ids[0]]  # 保位：歇者仍坐队首


def test_write_exit_refills_idle_court_per_endpoint(client: TestClient):
    """验收 6 前半：报到/空降/换人/取消/改规则/tempo 成功后空片被顺手补满
    （逐端点）。前两段用「七人可发、差一个可发人」的世界——写动作自己凑齐
    第四人；后四段用「两片全开再清扫态腾空 2 号片」的世界——片空、候场够一片。"""

    def scene_thin(seed: int):
        # 9 人名册、2 人缺席：开 1 号片后候场可发 3 人，2 号片空着等第四人
        env = open_live(client, seed=seed, players=9)
        for i in (7, 8):
            seed_row(
                client,
                env["view"]["players"][i]["id"],
                check="absent",
                queue_pos=None,
            )
        return env, deal_one(client, env)

    def scene_vacant(seed: int):
        # 9 人全到：两片全开，再清扫态取消 2 号片（只清不补）腾出空片
        env = open_live(client, seed=seed, players=9)
        v = deal_one(client, env)
        v = live_call(
            client,
            env["org"]["token"],
            env["game_id"],
            "cancel",
            write_body(v, 2) | {"no_redeal": True},
        ).json()
        assert court(v, 2)["status"] == "idle"
        return env, v

    env, v = scene_thin(61)  # 报到：第四个可发人进队即点亮
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "check",
        {
            "player_id": env["view"]["players"][7]["id"],
            "check": "ok",
            "base_total_seq": v["total_seq"],
        },
    )
    assert r.status_code == 200 and court(r.json(), 2)["status"] == "playing"

    env, v = scene_thin(62)  # 空降
    stranger = signup(client, "13800036201", "d")
    r = live_call(
        client,
        stranger["token"],
        env["game_id"],
        "dropin",
        {"base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200 and court(r.json(), 2)["status"] == "playing"

    env, v = scene_vacant(63)  # 换人（不改变可发数，出口照补）
    rows = env["view"]["players"]
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "swap",
        {
            "out_id": rows[0]["id"],
            "in_id": rows[4]["id"],
            "base_total_seq": v["total_seq"],
        },
    )
    assert r.status_code == 200 and court(r.json(), 2)["status"] == "playing"

    env, v = scene_vacant(64)  # 取消（非清扫）：回流队首后原地重发
    r = live_call(
        client, env["org"]["token"], env["game_id"], "cancel", write_body(v, 1)
    )
    assert r.status_code == 200 and court(r.json(), 1)["status"] == "playing"

    env, v = scene_vacant(65)  # 改规则
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "rules",
        {"streak_max": 5, "base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200 and court(r.json(), 2)["status"] == "playing"

    env, v = scene_vacant(66)  # tempo：设歇是减员方向，出口照常补别的空片
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "tempo",
        {
            "player_id": env["view"]["players"][0]["id"],
            "action": "skip",
            "base_total_seq": v["total_seq"],
        },
    )
    assert r.status_code == 200 and court(r.json(), 2)["status"] == "playing"


def test_exempt_endpoints_never_refill(client: TestClient):
    """验收 6 后半：改分重落/清扫取消/一键清扫/散场四处不补（声明式豁免）。"""
    # 改分重落：账面动作，2 号片空着照旧空着（7 人局凑不齐第二片，片行都没开）
    env = open_live(client, seed=67, players=6, bring=1)
    v = settled_11_9(client, env)
    assert [c["court_no"] for c in v["courts"]] == [1]
    r = overwrite(client, env["org"]["token"], env["game_id"], v, score_a=11, score_b=8)
    assert r.status_code == 200
    assert [c["court_no"] for c in r.json()["courts"]] == [1]

    # 清扫态取消
    env = open_live(client, seed=68)
    v = deal_one(client, env)
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "cancel",
        write_body(v, 1) | {"no_redeal": True},
    )
    assert r.status_code == 200 and court(r.json(), 1)["status"] == "idle"

    # 一键清扫
    env = open_live(client, seed=69)
    v = deal_one(client, env)
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "sweep-cancel-all",
        {"base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200 and court(r.json(), 1)["status"] == "idle"

    # 散场：无残局直接收工，收工不把空片点亮
    env = open_live(client, seed=70)
    v = deal_one(client, env)
    v = confirm(client, env["org"]["token"], env["game_id"], v, no_redeal=True).json()
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "end",
        {"base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200, r.text
    assert all(c["status"] == "idle" for c in r.json()["courts"])


def test_fill_failure_degrades_without_killing_main_action(tmp_path, monkeypatch, fake):
    """验收 8（降级不连坐）：补片段构造性失败 → 主动作照常 200 落账、片留空态、
    live_auto_fill_error 审计落盘。"""
    from app.services import live_rotation

    def boom(players, courts, rules, queue):
        raise RuntimeError("构造性失败")

    monkeypatch.setattr(live_rotation, "autofill_idle", boom)
    logs_dir = tmp_path / "logs"
    client = make_client(tmp_path)
    env = open_live(client, seed=74)
    gid, tok = env["game_id"], env["org"]["token"]
    v = env["view"]
    r = live_call(
        client,
        tok,
        gid,
        "tempo",
        {
            "player_id": v["players"][4]["id"],
            "action": "skip",
            "base_total_seq": v["total_seq"],
        },
    )
    assert r.status_code == 200, r.text  # 主动作照常
    after = r.json()
    assert after["players"][4]["skip"] == 1  # 主动作落账
    assert after["courts"] == []  # 片留空态：失败只回滚补片段
    assert after["total_seq"] == v["total_seq"] + 1  # 一写动作恰一 bump
    row = audit_row_of(audit_rows(logs_dir), "live_auto_fill_error")
    assert row["game_id"] == gid and "RuntimeError" in row["detail"]


def test_auto_deal_audit_row(tmp_path, fake):
    """验收 9：自动开片落「自动排阵」审计行，操作人=触发写动作的人。"""
    logs_dir = tmp_path / "logs"
    client = make_client(tmp_path)
    env = open_live(client, seed=75)
    gid = env["game_id"]
    v = env["view"]
    r = live_call(
        client,
        env["org"]["token"],
        gid,
        "tempo",
        {
            "player_id": v["players"][0]["id"],
            "action": "fire",
            "base_total_seq": v["total_seq"],
        },
    )
    assert r.status_code == 200, r.text
    row = audit_row_of(audit_rows(logs_dir), "live_auto_deal")
    assert row["game_id"] == gid
    assert row["account_id"] == env["org"]["account"]["id"]
    assert "courts=1" in row["detail"]  # 6 人候场只够一片


# ---- 早退抽空片（2026-10-10 事故修复：单边空 playing 片不再炸 view） ----


def test_left_empties_side_keeps_view_alive(client: TestClient):
    """片上的人早退清位、片行保持 playing（「打短维持现状」）：一边被抽空后
    view 不得 500（elo_preview 单边空返 None），现场仍有自救入口（取消该片）。"""
    env = open_live(client, seed=71, players=6)
    gid, tok = env["game_id"], env["org"]["token"]
    v = deal_one(client, env)
    side_b_ids = [
        r["id"] for r in v["players"] if r["court_no"] == 1 and r["court_side"] == "b"
    ]
    assert len(side_b_ids) == 2

    # b 边两人先后早退（代办 left 清片位，片行仍 playing）
    for pid in side_b_ids:
        r = live_call(
            client,
            tok,
            gid,
            "check",
            {"player_id": pid, "check": "left", "base_total_seq": v["total_seq"]},
        )
        assert r.status_code == 200, r.text
        v = r.json()

    # 视图活着：该片区 elo_preview=None（没有对局可言），其余照常
    assert court(v, 1)["status"] == "playing"
    assert court(v, 1)["elo_preview"] is None
    oncourt = [r for r in v["players"] if r["court_no"] == 1]
    assert len(oncourt) == 2  # a 边照旧在打（打短维持现状）

    # 排阵另一片也不受牵连（候场够人时照常发牌）
    q = v["queue"]
    if len(q) >= 4:
        r = live_call(
            client,
            tok,
            gid,
            "deal",
            {
                "courts": [{"court_no": 2, "a": q[:2], "b": q[2:4]}],
                "base_total_seq": v["total_seq"],
            },
        )
        assert r.status_code == 200, r.text


def test_settle_single_sided_match_no_elo_no_dupr(client: TestClient):
    """单边空片结算落账：战报行照落（名单比分是事实），双轨积分都不动账。"""
    env = open_live(client, seed=72, players=6)
    gid, tok = env["game_id"], env["org"]["token"]
    v = deal_one(client, env)
    losers = [r for r in v["players"] if r["court_no"] == 1 and r["court_side"] == "b"]
    for p in losers:  # b 边全早退 → 单边空
        r = live_call(
            client,
            tok,
            gid,
            "check",
            {"player_id": p["id"], "check": "left", "base_total_seq": v["total_seq"]},
        )
        assert r.status_code == 200, r.text
        v = r.json()

    r = confirm(client, tok, gid, v)  # a 方 11:9 落账
    assert r.status_code == 200, r.text
    v = r.json()
    m = v["matches"][-1]
    assert m["elo_rows"] == []  # 无胜负两队可算，Elo 零行
    assert [w["id"] for w in m["losers"]] == []  # 名单快照如实记空边

    # Elo/DUPR 全库无这场痕迹（胜方也不吃分）
    db = client.app.state.session_factory()
    try:
        assert (
            db.execute(select(EloRating).where(EloRating.play > 0)).scalar_one_or_none()
            is None
        )
        assert db.execute(select(DuprDetail)).scalar_one_or_none() is None
    finally:
        db.close()

    # 确认即续场：剩余人下、候场补位重开——新一场两边有人，预演恢复
    c1 = court(v, 1)
    oncourt = [r for r in v["players"] if r["court_no"] == 1]
    if oncourt:
        assert c1["status"] == "playing" and c1["elo_preview"] is not None


def test_overwrite_single_sided_match_keeps_accounts_clean(client: TestClient):
    """单边空战报改分重落：Elo 空快照无账可退、DUPR 明细删后不重插，全链 200。"""
    env = open_live(client, seed=73, players=6)
    gid, tok = env["game_id"], env["org"]["token"]
    v = deal_one(client, env)
    for p in [r for r in v["players"] if r["court_no"] == 1 and r["court_side"] == "b"]:
        r = live_call(
            client,
            tok,
            gid,
            "check",
            {"player_id": p["id"], "check": "left", "base_total_seq": v["total_seq"]},
        )
        assert r.status_code == 200, r.text
        v = r.json()
    r = confirm(client, tok, gid, v)
    assert r.status_code == 200, r.text
    v = live_get(client, gid, tok)

    r = overwrite(client, tok, gid, v, winner_side="b", score_a=9, score_b=11)
    assert r.status_code == 200, r.text
    m = r.json()["matches"][-1]
    assert m["elo_rows"] == []
    db = client.app.state.session_factory()
    try:
        assert db.execute(select(DuprDetail)).scalar_one_or_none() is None
    finally:
        db.close()


# ---- 2.8 §4.1 取队单一真值：结算回流吃歇/连战/资历（验收 1/4/5）与上场章 ----


def player(view: dict, player_id: int) -> dict:
    return next(r for r in view["players"] if r["id"] == player_id)


def court_marks(client: TestClient, game_id: int) -> dict[int, int | None]:
    """上场章不进视图（内部资历键），直查名册行。"""
    db = client.app.state.session_factory()
    try:
        rows = (
            db.execute(select(LivePlayer).where(LivePlayer.game_id == game_id))
            .scalars()
            .all()
        )
        return {r.id: r.court_mark for r in rows}
    finally:
        db.close()


def set_court_marks(client: TestClient, marks: dict[int, int]) -> None:
    db = client.app.state.session_factory()
    try:
        for pid, mark in marks.items():
            db.get(LivePlayer, pid).court_mark = mark
        db.commit()
    finally:
        db.close()


def tempo(client: TestClient, token: str, game_id: int, view: dict, pid: int, action):
    r = live_call(
        client,
        token,
        game_id,
        "tempo",
        {"player_id": pid, "action": action, "base_total_seq": view["total_seq"]},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_settle_skips_on_court_skipper_and_next_game_first(client: TestClient):
    """验收 1（歇·结算路）：在打的人设歇 → 结算 → 补位轮到他跳过、坑由下位顶、
    skip 减一、保位回队首；下一场第一个轮到。"""
    env = open_live(client, seed=81, players=5)
    gid, tok = env["game_id"], env["org"]["token"]
    ids = [r["id"] for r in env["view"]["players"]]
    v = deal_one(client, env)  # 0-3 上场、4 候场
    v = tempo(client, tok, gid, v, ids[2], "skip")
    assert player(v, ids[2])["skip"] == 1

    r = confirm(client, tok, gid, v)  # 全上全下：四人回队尾成 [4,0,1,2,3]，取 4
    assert r.status_code == 200, r.text
    v = r.json()
    assert side_ids(v, 1, "a") == {ids[4], ids[0]}
    assert side_ids(v, 1, "b") == {ids[1], ids[3]}  # 轮到 2 跳过、3 顶坑
    assert v["queue"] == [ids[2]] and player(v, ids[2])["skip"] == 0

    r = confirm(client, tok, gid, v, score_b=8)  # 下一场：2 在队首且歇已清
    assert r.status_code == 200, r.text
    v = r.json()
    assert side_ids(v, 1, "a") == {ids[2], ids[0]}
    assert side_ids(v, 1, "b") == {ids[1], ids[3]}
    assert v["queue"] == [ids[4]]  # 全下按上场章：4 最新资历排队尾


def test_n_down_by_court_mark_not_roster_order(client: TestClient):
    """验收 4（资历）：N 人下按上场章先上先下——deal 落位盖章、结算补位盖章、
    留场/下场不动章；章序与名册序相反时按章下人。"""
    env = open_live(client, seed=82, players=6, rules={"down": "n2"})
    gid, tok = env["game_id"], env["org"]["token"]
    ids = [r["id"] for r in env["view"]["players"]]
    v = deal_one(client, env)
    marks = court_marks(client, gid)
    assert [marks[i] for i in ids] == [1, 1, 1, 1, None, None]  # 章=落位时刻总号
    set_court_marks(client, {ids[0]: 9, ids[1]: 9})  # 把 0、1 改成最晚上场

    r = confirm(client, tok, gid, v)
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["queue"] == [ids[2], ids[3]]  # 章小的先下（按名册序会下 0、1）
    assert side_ids(v, 1, "a") == {ids[0], ids[1]}
    assert side_ids(v, 1, "b") == {ids[4], ids[5]}  # 候场首原位顶坑
    marks = court_marks(client, gid)
    assert marks[ids[4]] == marks[ids[5]] == 2  # 补位落位盖章=结算时总号
    assert [marks[i] for i in ids[:4]] == [9, 9, 1, 1]  # 留场不改、下场不清


def test_settle_fire_on_court_taken_first_next_game(client: TestClient):
    """验收 5（连战）：场上设连战（队列不动）→ 打完结算补位他排最前被取。"""
    env = open_live(client, seed=83, players=6)
    gid, tok = env["game_id"], env["org"]["token"]
    ids = [r["id"] for r in env["view"]["players"]]
    v = deal_one(client, env)
    v = tempo(client, tok, gid, v, ids[3], "fire")
    assert v["queue"] == [ids[4], ids[5]]

    r = confirm(client, tok, gid, v)  # 全下后队 [4,5,0,1,2,3]：3 越过所有人先收
    assert r.status_code == 200, r.text
    v = r.json()
    assert side_ids(v, 1, "a") == {ids[3], ids[4]}
    assert side_ids(v, 1, "b") == {ids[5], ids[0]}
    assert v["queue"] == [ids[1], ids[2]]


def test_swap_in_stamps_court_mark_out_keeps(client: TestClient):
    env = open_live(client, seed=84, players=6)
    gid, tok = env["game_id"], env["org"]["token"]
    ids = [r["id"] for r in env["view"]["players"]]
    v = deal_one(client, env)
    r = live_call(
        client,
        tok,
        gid,
        "swap",
        {"out_id": ids[0], "in_id": ids[4], "base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200, r.text
    marks = court_marks(client, gid)
    assert marks[ids[4]] == v["total_seq"]  # 换上即落位盖章
    assert marks[ids[0]] == 1  # 被换下的章不清（只盖不清）


# ---- 2.8 批5：轮询条件拉取（验收 12 + 号跳纪律） ----


def fee_fingerprint(view: dict) -> int:
    """视图侧 fee.total 折线上指纹（null=未定 → -1；两向约定的服务端镜像）。"""
    total = view["fee"]["total"]
    return -1 if total is None else total


def live_pull(
    client: TestClient,
    game_id: int,
    *,
    total_seq: int,
    fee_total: int,
    token: str | None = None,
):
    """带指纹的条件拉取：不代 assert 状态码——204/200/404 都是要验的结果。"""
    return client.get(
        f"/api/games/{game_id}/live",
        params={"since_total_seq": total_seq, "since_fee_total": fee_total},
        headers=auth(token),
    )


def test_pull_steady_204_read_never_bumps_guest_readable(client: TestClient):
    """验收 12 稳态 + 号跳纪律（读不加号）：带当前两把指纹回 204 空体；连拍两拍
    都 204——读端点不 bump，稳态拍恒稳态；游客（无钥匙）带指纹同样可读。"""
    env = open_live(client, seed=91)
    args = {
        "total_seq": env["view"]["total_seq"],
        "fee_total": fee_fingerprint(env["view"]),
    }
    r = live_pull(client, env["game_id"], token=env["org"]["token"], **args)
    assert r.status_code == 204 and r.content == b""
    r = live_pull(client, env["game_id"], token=env["org"]["token"], **args)
    assert r.status_code == 204  # 上一拍读完号没跳：稳态不被读破坏
    r = live_pull(client, env["game_id"], **args)
    assert r.status_code == 204  # 游客读权限不回归


def test_pull_write_returns_full_with_new_seq(client: TestClient):
    """验收 12 有写：稳态 204 后 tempo 设歇跳号 → 旧指纹回 200 全量且新号；
    吃新号再拍回 204（快路在新号上继续稳态）。"""
    env = open_live(client, seed=92)
    tok, gid = env["org"]["token"], env["game_id"]
    v = env["view"]
    fee = fee_fingerprint(v)
    assert (
        live_pull(
            client, gid, token=tok, total_seq=v["total_seq"], fee_total=fee
        ).status_code
        == 204
    )
    target = next(
        r["id"] for r in v["players"] if r["account_id"] == env["mate"]["account"]["id"]
    )
    v = tempo(client, tok, gid, v, target, "skip")
    assert v["total_seq"] == env["view"]["total_seq"] + 1
    r = live_pull(
        client, gid, token=tok, total_seq=env["view"]["total_seq"], fee_total=fee
    )
    assert r.status_code == 200 and r.json()["total_seq"] == v["total_seq"]
    r = live_pull(client, gid, token=tok, total_seq=v["total_seq"], fee_total=fee)
    assert r.status_code == 204


def test_pull_fee_change_returns_full_without_seq_bump(client: TestClient):
    """验收 12 改价（指纹带改价的由来）：账单/局簿域直改 games.fee_total 不走
    live 写链不 bump 号——只比号 204 会把改价闷掉，fee 指纹不同必须回全量；
    未定价（null）只吃 -1，任意报价都算变了；吃新价再拍回 204。"""
    env = open_live(client, seed=93)
    tok, gid = env["org"]["token"], env["game_id"]
    v = env["view"]
    assert v["fee"]["total"] is None  # 开账局默认未定价：null 向的基准
    assert (
        live_pull(
            client, gid, token=tok, total_seq=v["total_seq"], fee_total=-1
        ).status_code
        == 204
    )
    r = live_pull(client, gid, token=tok, total_seq=v["total_seq"], fee_total=99)
    assert r.status_code == 200  # null ≠ 99：未定价不冒领报价指纹
    db = client.app.state.session_factory()
    try:
        db.get(Game, gid).fee_total = 120  # 模拟局簿域改价：不经 live 号闸
        db.commit()
    finally:
        db.close()
    r = live_pull(client, gid, token=tok, total_seq=v["total_seq"], fee_total=-1)
    assert r.status_code == 200
    body = r.json()
    assert body["fee"]["total"] == 120
    assert body["total_seq"] == v["total_seq"]  # 号真没动——fee 指纹兜的就是这个洞
    r = live_pull(client, gid, token=tok, total_seq=v["total_seq"], fee_total=120)
    assert r.status_code == 204


def test_pull_partial_fingerprint_always_full(client: TestClient):
    """指纹不全=全量（快路只在两参都带时走）：只带号、只带价、都不带三形照旧。"""
    env = open_live(client, seed=94)
    tok, gid = env["org"]["token"], env["game_id"]
    v = env["view"]
    base = f"/api/games/{gid}/live"
    r = client.get(base, params={"since_total_seq": v["total_seq"]}, headers=auth(tok))
    assert r.status_code == 200 and r.json()["total_seq"] == v["total_seq"]
    r = client.get(
        base, params={"since_fee_total": fee_fingerprint(v)}, headers=auth(tok)
    )
    assert r.status_code == 200
    assert client.get(base, headers=auth(tok)).status_code == 200


def test_pull_not_opened_404(client: TestClient):
    """未开账沿现状 404：快路也先过 state 存在性（读 state 行本身完成了）。"""
    org = signup(client, _ph(95, 1), "o")
    g = publish(client, org["token"], visibility="public")
    r = live_pull(client, g["id"], total_seq=0, fee_total=-1)
    assert r.status_code == 404 and r.json()["error"]["code"] == "live_not_found"
