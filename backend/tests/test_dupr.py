"""DUPR 核心轨（1.4 批1）—— 引擎单测（纯函数）+ 结算 seam 集成。

引擎：期望（队伍均值/SPREAD）、分差权重、K 双速切换点、每步 round 3 + clamp。
集成：确认结算双写两本账（明细+派生缓存）、访客不落账（2.5 代入快照）、
5 场定级门槛、30 场窗口挤出、view 回 dupr、均衡配对换源吃 DUPR、
Elo 娱乐轨新参数（初始 1200/地板 800）。helpers 复用 test_live_score。
自评废除后（1.4 §10 修订）：起步锚统一 GUEST_DUPR 2.5，分差场景靠直插
DuprRating 缓存行（代位分唯一来源，重放仍从 2.5 起）。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core import clock
from app.db.models import DuprDetail, DuprRating, EloRating, LiveMatch
from app.services import dupr
from app.services.stats import StatsLedger

from .test_live_score import (
    confirm,
    deal_one,
    live_call,
    live_get,
    open_live,
    pt,
    ratings,
    settled_11_9,
    side_ids,
    write_body,
)


def _detail(**over) -> dict:
    """3.0 均势 11:9 胜局的明细行（引擎单测用纯 dict）。"""
    return {
        "partner_rating": 3.0,
        "opp_a": 3.0,
        "opp_b": 3.0,
        "score_w": 11,
        "score_l": 9,
        "won": True,
    } | over


def dupr_rows(client: TestClient, *account_ids: int) -> dict[int, DuprRating]:
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


def seed_dupr_row(client: TestClient, account_id: int, rating: float) -> None:
    """直插派生缓存行造分差（自评废除后的代位分唯一来源）：
    pairing 读它、重放不读它（锚恒 GUEST_DUPR），games=0 不冒充定级。"""
    db = client.app.state.session_factory()
    try:
        db.add(
            DuprRating(
                account_id=account_id, rating=rating, games=0, updated_at=clock.now()
            )
        )
        db.commit()
    finally:
        db.close()


# ---- 引擎：期望 / 权重 / K 双速 / 重放（纯函数不带 app 夹具） ----


def test_expectation_team_average_and_spread():
    assert dupr.expectation(3.0, 3.0) == 0.5
    # SPREAD=2.0：差 1.0 档 ≈ 76:24、差 2.0 档 ≈ 91:9（Elo 400 差体感）
    assert dupr.expectation(3.0, 4.0) == pytest.approx(1 / (1 + 10**0.5))
    assert dupr.expectation(3.0, 5.0) == pytest.approx(1 / (1 + 10**1.0))
    assert dupr.expectation(3.0, 4.0) + dupr.expectation(4.0, 3.0) == pytest.approx(1.0)


def test_margin_weight_score_gap():
    assert dupr.margin_weight(11, 9) == pytest.approx(0.809, abs=1e-3)
    assert dupr.margin_weight(11, 2) == pytest.approx(1.191, abs=1e-3)
    assert dupr.margin_weight(5, 0) == pytest.approx(
        1.3
    )  # margin/score_w 恒 ≤1，上界天然
    assert dupr.margin_weight(11, 11) == 0.7  # 平分也能确认（胜方任选）
    assert dupr.margin_weight(0, 0) == 0.7  # 0:0 平分：分母兜 1，落最轻权重


def test_delta_two_speeds_and_signs():
    assert dupr.delta(0.5, 1.0, won=True, provisional=True) == pytest.approx(0.125)
    assert dupr.delta(0.5, 1.0, won=False, provisional=True) == pytest.approx(-0.125)
    assert dupr.delta(0.5, 1.0, won=True, provisional=False) == pytest.approx(0.05)
    assert dupr.delta(0.5, 1.0, won=False, provisional=False) == pytest.approx(-0.05)


def test_replay_single_step_rounds_three_decimals():
    # 均势 11:9：±0.25×0.80909…×0.5 = ±0.101136… → 三位小数落账
    assert dupr.replay(3.0, [_detail()]) == 3.101
    assert dupr.replay(3.0, [_detail(won=False)]) == 2.899


def test_replay_k_switches_at_fifth_game():
    # 每步把搭档分补成 6−当前分 ⇒ 队伍恒 3.0 均势、步长只由 K 决定：
    # 前 4 场 +0.101136…、第 5 场起 +0.040454…（RATED_GAMES=5 的切换点）
    befores = [3.0, 3.101, 3.202, 3.303, 3.404, 3.444]
    details = [_detail(partner_rating=6.0 - r) for r in befores]
    assert dupr.replay(3.0, details) == 3.484
    assert dupr.replay(3.0, details) != 3.606  # 若 K 不切换会一路 0.101136…


def test_replay_clamps_to_scale():
    blow = _detail(partner_rating=2.0, opp_a=8.0, opp_b=8.0, score_w=5, score_l=0)
    assert dupr.replay(7.99, [blow]) == 8.0  # 爆冷大胜也压不出天花板外
    assert dupr.replay(2.01, [_detail(won=False)]) == 2.0  # 地板兜底


# ---- 集成：结算 seam 双写（同一 commit 落两本账） ----


def test_settle_confirm_double_writes_dupr(client: TestClient):
    env = open_live(client, seed=101, players=6, bring=1)
    rows = env["view"]["players"]
    org_row, b_row, _guest_row, c_row = rows[0], rows[1], rows[2], rows[3]
    seed_dupr_row(client, b_row["account_id"], 4.0)

    v = settled_11_9(client, env)
    body = write_body(v, 1, winner_side="a", score_a=11, score_b=9)
    r = confirm(client, env["org"]["token"], env["game_id"], v)
    assert r.status_code == 200, r.text

    # 同一笔确认两本账都落：Elo 均势 1200 → 胜 +12 / 败 −7
    rt = ratings(
        client, org_row["account_id"], b_row["account_id"], c_row["account_id"]
    )
    assert rt[org_row["account_id"]].rating == 1212
    assert rt[c_row["account_id"]].rating == 1193

    # 明细：注册球员每人一行（访客不落），快照带自己视角的结算时四人分数
    db = client.app.state.session_factory()
    try:
        m = db.execute(
            select(LiveMatch).where(LiveMatch.game_id == env["game_id"])
        ).scalar_one()
        details = {
            d.account_id: d
            for d in db.execute(
                select(DuprDetail).where(DuprDetail.match_id == m.id)
            ).scalars()
        }
    finally:
        db.close()
    assert set(details) == {
        org_row["account_id"],
        b_row["account_id"],
        c_row["account_id"],
    }
    d_org = details[org_row["account_id"]]
    d_b = details[b_row["account_id"]]
    d_c = details[c_row["account_id"]]
    assert (d_org.partner_rating, d_org.opp_a, d_org.opp_b, d_org.won) == (
        4.0,
        2.5,
        2.5,
        True,
    )
    assert (d_b.partner_rating, d_b.opp_a, d_b.opp_b, d_b.won) == (2.5, 2.5, 2.5, True)
    # c 的搭档是访客（2.5 代入）、对面快照是 org(2.5)+b(4.0)
    assert (d_c.partner_rating, d_c.opp_a, d_c.opp_b, d_c.won) == (
        2.5,
        2.5,
        4.0,
        False,
    )
    assert (d_c.score_w, d_c.score_l) == (11, 9)
    assert d_c.game_id == env["game_id"] and d_c.ended_at == m.ended_at

    # 派生缓存：重放锚统一 2.5（b 的 4.0 只是结算时代位快照，重放不读它）——
    # b 均势胜 +0.101；org/c 强弱两翼对称 ±0.060
    dr = dupr_rows(
        client, org_row["account_id"], b_row["account_id"], c_row["account_id"]
    )
    assert [
        (dr[a].rating, dr[a].games)
        for a in (org_row["account_id"], b_row["account_id"], c_row["account_id"])
    ] == [(2.560, 1), (2.601, 1), (2.440, 1)]

    # 断网重发同一笔确认：幂等回 200，明细不翻倍
    again = live_call(
        client, env["org"]["token"], env["game_id"], "settle-confirm", body
    )
    assert again.status_code == 200, again.text
    db = client.app.state.session_factory()
    try:
        n = (
            db.execute(select(DuprDetail).where(DuprDetail.game_id == env["game_id"]))
            .scalars()
            .all()
        )
        assert len(n) == 3
    finally:
        db.close()


def test_view_players_carry_dupr(client: TestClient):
    env = open_live(client, seed=102, players=6, bring=1)
    rows = env["view"]["players"]
    org_row, b_row, guest_row = rows[0], rows[1], rows[2]

    v = live_get(client, env["game_id"], env["org"]["token"])
    by_id = {r["id"]: r for r in v["players"]}
    # 未结算：新号无派分行按起步 2.5（1.4 §5 修订统一口径）；访客恒 2.5
    assert [by_id[r["id"]]["dupr"] for r in (org_row, b_row, guest_row)] == [
        2.5,
        2.5,
        2.5,
    ]

    r = confirm(client, env["org"]["token"], env["game_id"], settled_11_9(client, env))
    assert r.status_code == 200, r.text
    v = r.json()
    by_id = {r_["id"]: r_ for r_ in v["players"]}
    # 结算后：参与者吃派生分（胜方涨/败方跌）；访客与没上场的人零动
    assert by_id[org_row["id"]]["dupr"] > 2.5
    assert by_id[b_row["id"]]["dupr"] > 2.5
    assert by_id[rows[3]["id"]]["dupr"] < 2.5
    assert by_id[guest_row["id"]]["dupr"] == 2.5
    assert by_id[rows[4]["id"]]["dupr"] == 2.5


def test_rated_after_five_confirmed_games(client: TestClient):
    env = open_live(client, seed=103, players=6, bring=1, scoring=5)
    org_id = env["view"]["players"][0]["account_id"]

    def card() -> dict:
        db = client.app.state.session_factory()
        try:
            return StatsLedger(db).card(org_id)
        finally:
            db.close()

    assert card() == {
        "rating": 2.5,
        "provisional": True,
        "games": 0,
        "wins": 0,
        "last5": [],
        "month_net": 0,
    }

    v = deal_one(client, env)
    seen = {0: True}
    c = card()
    for _ in range(20):
        v = pt(client, env["org"]["token"], env["game_id"], v, 1, "a", 5)
        r = confirm(client, env["org"]["token"], env["game_id"], v)
        assert r.status_code == 200, r.text
        v = r.json()
        c = card()
        seen[c["games"]] = c["provisional"]
        if c["games"] >= dupr.RATED_GAMES:
            break
    # 满 5 场定级（两态，1.4 裁决 5）；第 4 场时仍属未定级
    assert c["games"] == 5 and c["provisional"] is False
    assert seen[4] is True
    assert c["wins"] == 1
    assert len(c["last5"]) == 5
    assert c["month_net"] == c["wins"] - (c["games"] - c["wins"])


def test_window_keeps_last_30_details(client: TestClient):
    env = open_live(client, seed=104, players=6, scoring=5)
    rows = env["view"]["players"]
    org_id, m1_id = rows[0]["account_id"], rows[1]["account_id"]
    fake = {
        "partner_rating": 2.5,
        "opp_a": 2.5,
        "opp_b": 2.5,
        "score_w": 5,
        "score_l": 0,
        "won": True,
    }

    # org 埋 30 行、m1 埋 29 行同构明细：结算一场后 org 共 31 行（窗口截回 30）、
    # m1 共 30 行（全在窗）——两人重放输入一致 ⇒ 派生分相等、games 仍见总量
    db = client.app.state.session_factory()
    try:
        for acct, n in ((org_id, 30), (m1_id, 29)):
            for _ in range(n):
                db.add(
                    DuprDetail(
                        account_id=acct,
                        match_id=0,
                        game_id=env["game_id"],
                        ended_at=clock.now(),
                        **fake,
                    )
                )
        db.commit()
    finally:
        db.close()

    v = pt(
        client, env["org"]["token"], env["game_id"], deal_one(client, env), 1, "a", 5
    )
    r = confirm(client, env["org"]["token"], env["game_id"], v)
    assert r.status_code == 200, r.text

    dr = dupr_rows(client, org_id, m1_id)
    assert (dr[org_id].games, dr[m1_id].games) == (31, 30)
    assert dr[org_id].rating == dr[m1_id].rating == dupr.replay(2.5, [fake] * 30)
    assert dr[org_id].rating != dupr.replay(2.5, [fake] * 31)  # 最老一行真被挤出


def test_balance_pairing_snakes_by_dupr(client: TestClient):
    env = open_live(client, seed=105, players=6, rules={"pairing": "balance"})
    rows = env["view"]["players"]
    org, m1, _m2, _m3, m4, m5 = rows
    # 回流发牌在结算事务内、派分行覆写前——代位分靠预埋缓存行拉开档位差
    # （m5 4.0 / m1 3.5 / org 3.0；m4 无行=起步 2.5）
    seed_dupr_row(client, m5["account_id"], 4.0)
    seed_dupr_row(client, m1["account_id"], 3.5)
    seed_dupr_row(client, org["account_id"], 3.0)

    r = confirm(client, env["org"]["token"], env["game_id"], settled_11_9(client, env))
    assert r.status_code == 200, r.text
    v = r.json()
    # 蛇形吃 DUPR：最强 m5(4.0)+最弱 m4(2.5) vs m1(3.5)+org(3.0)
    # （旧 1500 默认会按队序排成 [m4,m5] vs [org,m1]）
    assert side_ids(v, 1, "a") == {m5["id"], m4["id"]}
    assert side_ids(v, 1, "b") == {m1["id"], org["id"]}


def test_settle_only_recomputes_involved(client: TestClient):
    env = open_live(client, seed=107, players=8)
    org_id = env["view"]["players"][0]["account_id"]
    r = confirm(client, env["org"]["token"], env["game_id"], settled_11_9(client, env))
    assert r.status_code == 200, r.text
    first = dupr_rows(client, org_id)[org_id]

    # 第二场（候场首 4 人补位）不涉及 org：他的派生分与明细零动（重算幂等）
    v = pt(client, env["org"]["token"], env["game_id"], r.json(), 1, "a", 11)
    r = confirm(client, env["org"]["token"], env["game_id"], v)
    assert r.status_code == 200, r.text
    again = dupr_rows(client, org_id)[org_id]
    assert (again.rating, again.games) == (first.rating, 1)


def test_confirm_level_score_settles_dupr_min_weight(client: TestClient):
    env = open_live(client, seed=108, players=6)
    rows = env["view"]["players"]
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "settle-open",
        write_body(deal_one(client, env), 1),
    )
    assert r.status_code == 200, r.text
    r = confirm(
        client,
        env["org"]["token"],
        env["game_id"],
        r.json(),
        winner_side="a",
        score_a=0,
        score_b=0,
    )
    assert r.status_code == 200, r.text  # 0:0 平分胜方任选：不炸、照常落明细
    dr = dupr_rows(client, rows[0]["account_id"], rows[2]["account_id"])
    assert dr[rows[0]["account_id"]].rating > 2.5
    assert dr[rows[2]["account_id"]].rating < 2.5


# ---- Elo 娱乐轨新参数（1.4 §3：初始 1200、地板 800、K=24 不动） ----


def test_elo_entertainment_track_new_params_and_floor(client: TestClient):
    env = open_live(client, seed=106, players=6)
    rows = env["view"]["players"]
    org_id, m1_id = rows[0]["account_id"], rows[1]["account_id"]
    m2_id, m3_id = rows[2]["account_id"], rows[3]["account_id"]
    # 败方两人埋成低于地板的存量分：存量不迁移、下次结算自然抬回 800
    db = client.app.state.session_factory()
    try:
        for aid in (m2_id, m3_id):
            db.execute(
                select(EloRating).where(EloRating.account_id == aid)
            ).scalar_one().rating = 795
        db.commit()
    finally:
        db.close()

    r = confirm(client, env["org"]["token"], env["game_id"], settled_11_9(client, env))
    assert r.status_code == 200, r.text

    rt = ratings(client, org_id, m1_id, m2_id, m3_id)
    # 胜队均值 1200 vs 败队 795 → delta=2、败方六成=1（K=24 公式）
    assert (rt[org_id].rating, rt[org_id].play, rt[org_id].win) == (1202, 1, 1)
    assert (rt[m1_id].rating, rt[m1_id].play, rt[m1_id].win) == (1202, 1, 1)
    assert (rt[m2_id].rating, rt[m2_id].play, rt[m2_id].win) == (800, 1, 0)
    assert rt[m3_id].rating == 800
