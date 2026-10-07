"""账单读链与两向记账（1.3 批4）—— GET /api/bills 分权视图：三视角隐私（别人欠
别人不可见）、期间按散场日过滤且三数同随、received 整笔不占三数但 rows 还在、
peer_received 灰字旗两向、debtors 跨场聚合与点收缩水、unfixed（补 0 消失、补 700
出账）、注销占位名；settle/receive 全链：幂等重放、组织者行拦、越权与管理员 403、
无账 404、period 回带。

时刻基准 FakeClock 10-04 12:00（conftest）。
"""

from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core import clock
from app.db.models import Bill, BillRow, Game

from .conftest import signup
from .test_bills_generate import auth, book_fee, db_of, end_live, set_fee
from .test_games_actions import join_ok
from .test_games_read import publish
from .test_live_score import live_call


def bills_get(client: TestClient, token: str, period: str = "all"):
    return client.get("/api/bills", headers=auth(token), params={"period": period})


def settle(client: TestClient, token: str, game_id: int, period: str = "all"):
    return client.post(
        f"/api/bills/{game_id}/settle", headers=auth(token), params={"period": period}
    )


def receive(
    client: TestClient, token: str, game_id: int, account_id: int, period: str = "all"
):
    return client.post(
        f"/api/bills/{game_id}/receive",
        headers=auth(token),
        params={"period": period},
        json={"account_id": account_id},
    )


def stage(
    client: TestClient,
    *,
    seed: int,
    fee: int | None,
    players: int = 3,
    org: dict | None = None,
    mates: list[dict] | None = None,
    bring: int = 0,
    admin_of: int | None = None,
) -> dict:
    """自管 token 的开账散场环境——open_live 只回首位球友，本文件要按人
    settle/receive，故自带 org/mates 全表（fee=None 散场时不订价，挂 unfixed）。"""
    o = org or signup(client, f"1380009{seed:02d}01", "o")
    ms = mates or [
        signup(client, f"1380009{seed:02d}{i + 2:02d}", f"m{i}")
        for i in range(players - 1)
    ]
    # 时刻取假时钟现算（publish 默认 DEADLINE 是常量，advance 后会判 deadline_inverted）
    now = clock.now()
    g = publish(
        client,
        o["token"],
        visibility="public",
        max_players=players + bring,
        start_at=clock.iso(now + timedelta(hours=1)),
        end_at=clock.iso(now + timedelta(hours=3)),
        deadline_at=clock.iso(now + timedelta(minutes=30)),
    )
    join_ok(client, ms[0]["token"], g["id"], bring=bring)
    for m in ms[1:]:
        join_ok(client, m["token"], g["id"])
    # 2.5 开账闸：成局才可开——前置直接定格 locked（沿 open_live 同款 seed 先例）
    db = client.app.state.session_factory()
    try:
        db.get(Game, g["id"]).state = "locked"
        db.commit()
    finally:
        db.close()
    r = live_call(client, o["token"], g["id"], "start", {})
    assert r.status_code == 200, r.text
    view = r.json()
    if admin_of is not None:
        r2 = live_call(
            client,
            o["token"],
            g["id"],
            "set-admin",
            {
                "player_id": view["players"][admin_of]["id"],
                "base_total_seq": view["total_seq"],
            },
        )
        assert r2.status_code == 200, r2.text
        view = r2.json()
    if fee is not None:
        book_fee(client, o["token"], g["id"], fee)
    end_live(client, {"org": o, "game_id": g["id"], "view": view})
    return {"org": o, "mates": ms, "game_id": g["id"]}


def payers_of(client: TestClient, env: dict) -> list[int]:
    """名册里的非组织者账号 id（点收/点结算的靶子）。"""
    from app.db.models import Game

    with db_of(client) as db:
        org_id = db.get(Game, env["game_id"]).organizer_id
    view = client.get(
        f"/api/games/{env['game_id']}/live", headers=auth(env["org"]["token"])
    ).json()
    return [
        p["account_id"]
        for p in view["players"]
        if p["account_id"] is not None and p["account_id"] != org_id
    ]


def row_stamp(client: TestClient, game_id: int, account_id: int, attr: str):
    """两时刻之一的现值 + 行 id（幂等重放断言用）。"""
    with db_of(client) as db:
        bill = db.execute(select(Bill).where(Bill.game_id == game_id)).scalar_one()
        row = db.execute(
            select(BillRow).where(
                BillRow.bill_id == bill.id, BillRow.account_id == account_id
            )
        ).scalar_one()
        return getattr(row, attr), row.id


def stamp_by_id(client: TestClient, row_id: int, attr: str):
    with db_of(client) as db:
        return getattr(db.get(BillRow, row_id), attr)


def payer_row_of(view: dict, account_id: int) -> dict:
    row = next(r for r in view["rows"] if r.get("payer_rows"))
    return next(p for p in row["payer_rows"] if p["account_id"] == account_id)


def my_row_of(view: dict, game_id: int) -> dict:
    return next(r for r in view["rows"] if r["game_id"] == game_id)


# ---- 三视角互查（§4.6 看账边界 / 不变承诺 4：别人欠别人不可见） ----


def test_three_viewpoints_privacy(client: TestClient):
    env = stage(client, seed=80, fee=6666, players=6, bring=2)
    # 首位球友带 2 访客拉开份额：heads=8，base=833——担保人 2499、平人 833、组织者兜 835
    guarantor, stranger = env["mates"][0], signup(client, "13800099909", "x")

    v_me = bills_get(client, guarantor["token"]).json()
    assert [r["game_id"] for r in v_me["rows"]] == [env["game_id"]]
    row = v_me["rows"][0]
    assert row["kind"] == "payable" and row["amount"] == 2499
    assert row["guest_count"] == 2  # 「含带来的朋友 ×2」的数据半边
    assert "payer_rows" not in row  # 别人的明细一个字节不给
    assert v_me["summary"] == {"due": 2499, "paid": 0, "receivable": 0}
    assert v_me["debtors"] == []

    v_org = bills_get(client, env["org"]["token"]).json()
    assert v_org["summary"] == {"due": 0, "paid": 0, "receivable": 5831}
    assert len(v_org["rows"][0]["payer_rows"]) == 5
    # 应收 == Σ 未收 payer_rows == debtors 加总（不变承诺 5）
    assert v_org["rows"][0]["amount"] == 5831
    assert sum(p["amount"] for p in v_org["rows"][0]["payer_rows"]) == 5831
    assert sum(d["total"] for d in v_org["debtors"]) == 5831

    v_stranger = bills_get(client, stranger["token"]).json()
    assert v_stranger["rows"] == [] and v_stranger["debtors"] == []
    assert v_stranger["unfixed"] == []
    assert v_stranger["summary"] == {"due": 0, "paid": 0, "receivable": 0}
    assert "2499" not in str(v_stranger)  # 别人的份额连数字都不出现


# ---- 期间过滤（按散场日归属，三数与逐笔同随 §4.6） ----


def test_period_filter_by_ended_day(client: TestClient, fake):
    org = signup(client, "13800098101", "o")
    mates = [signup(client, f"1380009810{i}", f"m{i}") for i in (2, 3)]
    old = stage(client, seed=81, fee=400, org=org, mates=mates)
    fake.advance(days=8)  # → 10-12：10-04 散场的那笔滚出 7d、全部里还在
    new = stage(client, seed=82, fee=400, org=org, mates=mates)

    v7 = bills_get(client, org["token"], period="7d").json()
    assert [r["game_id"] for r in v7["rows"]] == [new["game_id"]]
    assert v7["summary"]["receivable"] == 266  # 只剩新局两份 133
    v_all = bills_get(client, org["token"], period="all").json()
    ids = [r["game_id"] for r in v_all["rows"]]
    assert ids == [new["game_id"], old["game_id"]]  # 散场日新到旧
    assert v_all["summary"]["receivable"] == 532
    assert v_all["debtors"] == [
        {
            "account_id": mates[0]["account"]["id"],
            "name": mates[0]["account"]["name"],
            "deactivated": False,
            "total": 266,
            "games": 2,
        },
        {
            "account_id": mates[1]["account"]["id"],
            "name": mates[1]["account"]["name"],
            "deactivated": False,
            "total": 266,
            "games": 2,
        },
    ]


# ---- received 整笔不占三数但 rows 还在（§4.4） ----


def test_received_whole_leaves_summary_but_rows_stay(client: TestClient):
    env = stage(client, seed=83, fee=400)
    org, payers = env["org"], payers_of(client, env)
    for p in payers:
        r = receive(client, org["token"], env["game_id"], p)
        assert r.status_code == 200, r.text
    v = r.json()
    row = my_row_of(v, env["game_id"])
    assert row["kind"] == "received" and row["amount"] == 266  # 整笔翻全额
    assert all(p["received_at"] for p in row["payer_rows"])
    assert v["summary"]["receivable"] == 0  # 不占三数
    assert v["debtors"] == []
    assert len(v["rows"]) == 1  # 翻旧账仍在


# ---- peer_received 灰字旗两向（§4.3b / §4.4，各记各的） ----


def test_peer_flags_two_directions(client: TestClient):
    env = stage(client, seed=84, fee=400)
    org = env["org"]
    payer_id = payers_of(client, env)[0]
    payer_tok = env["mates"][0]["token"]

    # 组织者先点「已收」：payer 的行亮 peer_received，三数照旧挂在应付
    assert receive(client, org["token"], env["game_id"], payer_id).status_code == 200
    v = bills_get(client, payer_tok).json()
    row = my_row_of(v, env["game_id"])
    assert row["peer_received"] is True and row["kind"] == "payable"
    assert v["summary"]["due"] == 133  # 系统不替我点结算

    # payer 后点「结算」：组织者明细里两时刻并存（「已转 · 待收」的数据半边已过，
    # 此处断言的是收后再结的终局并存形态）
    assert settle(client, payer_tok, env["game_id"]).status_code == 200
    v_org = bills_get(client, org["token"]).json()
    prow = payer_row_of(v_org, payer_id)
    assert prow["paid_at"] and prow["received_at"]


def test_paid_then_unreceived_shows_pending_flag(client: TestClient):
    """反方向：payer 先「结算」、组织者还没点收 → payer_rows 亮 paid_at + received_at 空。"""
    env = stage(client, seed=94, fee=400)
    payer = env["mates"][0]
    assert settle(client, payer["token"], env["game_id"]).status_code == 200
    v_org = bills_get(client, env["org"]["token"]).json()
    prow = payer_row_of(v_org, payer["account"]["id"])
    assert prow["paid_at"] and prow["received_at"] is None
    # 三数不受「他自称转了」影响：应收仍挂全额，等组织者点收
    assert v_org["summary"]["receivable"] == 266


# ---- debtors 跨场聚合与点收后缩水（§4.2 / 验收「谁还欠你」跨场加总） ----


def test_debtors_aggregate_and_shrink(client: TestClient):
    org = signup(client, "13800098201", "o")
    shared = [signup(client, f"1380009820{i}", f"m{i}") for i in (2, 3)]
    g1 = stage(client, seed=85, fee=400, org=org, mates=shared)  # 各 133
    stage(client, seed=86, fee=320, org=org, mates=shared)  # 各 106
    debtor = shared[0]["account"]["id"]

    v = bills_get(client, org["token"]).json()
    assert next(d for d in v["debtors"] if d["account_id"] == debtor) == {
        "account_id": debtor,
        "name": shared[0]["account"]["name"],
        "deactivated": False,
        "total": 239,
        "games": 2,
    }
    assert v["summary"]["receivable"] == sum(d["total"] for d in v["debtors"])
    # 点掉一场：合计与场数同步缩水（筛选不是结清的另一场还在）
    assert receive(client, org["token"], g1["game_id"], debtor).status_code == 200
    v2 = bills_get(client, org["token"]).json()
    d = next(x for x in v2["debtors"] if x["account_id"] == debtor)
    assert (d["total"], d["games"]) == (106, 1)


# ---- unfixed 费用未定提醒（§4.5：补 0 消失不出账、补 700 出账日期记散场日） ----


def test_unfixed_reminder_and_backfill(client: TestClient):
    org = signup(client, "13800098301", "o")
    mate = signup(client, "13800098302", "m")
    g_free = stage(client, seed=87, fee=None, org=org, mates=[mate])

    v = bills_get(client, org["token"]).json()
    assert v["unfixed"] == [
        {
            "game_id": g_free["game_id"],
            "game_name": "周三夜战",
            "ended_day": "2026-10-04",
        }
    ]
    assert bills_get(client, mate["token"]).json()["unfixed"] == []  # 只组织者见

    # 补 0：提醒消失、无账无行
    assert set_fee(client, org["token"], g_free["game_id"], 0).status_code == 200
    v0 = bills_get(client, org["token"]).json()
    assert v0["unfixed"] == []
    assert all(r["game_id"] != g_free["game_id"] for r in v0["rows"])

    # 另一局补 700：出账、提醒消失、日期仍记散场那天（billed_at 是补填刻）
    g_paid = stage(client, seed=88, fee=None, org=org, mates=[mate])
    assert set_fee(client, org["token"], g_paid["game_id"], 700).status_code == 200
    v7 = bills_get(client, org["token"]).json()
    assert v7["unfixed"] == []
    row = my_row_of(v7, g_paid["game_id"])
    assert row["ended_day"] == "2026-10-04" and row["fee_total"] == 700
    assert row["my_share"] == 350  # 两人局：350+350，零头无处可兜也恒等
    assert len(row["payer_rows"]) == 1 and row["payer_rows"][0]["amount"] == 350


# ---- 注销占位名（§4.8：留档不删、匿名显示、金额照旧） ----


def _deactivate(client: TestClient, sent: list, who: dict) -> None:
    """走 1.1 注销流程（短信验证本人；带本人钥匙——端点只认自己的号）。"""
    phone = who["account"]["phone"]
    client.post("/api/auth/sms", json={"phone": phone, "purpose": "deactivate"})
    code = next(c for p, c, pu in reversed(sent) if p == phone and pu == "deactivate")
    r = client.post(
        "/api/auth/deactivate",
        headers=auth(who["token"]),
        json={"phone": phone, "code": code},
    )
    assert r.status_code == 200, r.text


def test_deactivated_placeholder_names(client: TestClient, sent):
    env = stage(client, seed=89, fee=300)
    payer = env["mates"][0]
    _deactivate(client, sent, payer)

    v_org = bills_get(client, env["org"]["token"]).json()
    prow = payer_row_of(v_org, payer["account"]["id"])
    assert (prow["name"], prow["deactivated"], prow["amount"]) == (
        "已注销球友",
        True,
        100,
    )
    d = next(x for x in v_org["debtors"] if x["account_id"] == payer["account"]["id"])
    assert (d["name"], d["deactivated"]) == ("已注销球友", True)

    # 组织者注销：参加者的待付行 payee 变占位、金额照旧
    mate = env["mates"][1]
    _deactivate(client, sent, env["org"])
    v_me = bills_get(client, mate["token"]).json()
    row = my_row_of(v_me, env["game_id"])
    assert (row["payee_name"], row["payee_deactivated"]) == ("已注销球友", True)
    assert row["amount"] == 100


# ---- settle 全链（§4.3：幂等重放 / 组织者行拦 / 无账与不在名单 404） ----


def test_settle_flow_and_guards(client: TestClient):
    env = stage(client, seed=90, fee=300)
    payer = env["mates"][0]
    stranger = signup(client, "13800099910", "x")

    v0 = bills_get(client, payer["token"]).json()
    assert my_row_of(v0, env["game_id"])["kind"] == "payable"

    r = settle(client, payer["token"], env["game_id"], period="7d")
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["period"] == "7d"  # 回带请求的期间档
    assert my_row_of(v, env["game_id"])["kind"] == "paid"
    assert v["summary"] == {"due": 0, "paid": 100, "receivable": 0}

    # 幂等重放：200，paid_at 停在第一次（终态只有第一个时刻）
    first_at, row_id = row_stamp(
        client, env["game_id"], payer["account"]["id"], "paid_at"
    )
    assert first_at is not None
    assert settle(client, payer["token"], env["game_id"]).status_code == 200
    assert stamp_by_id(client, row_id, "paid_at") == first_at

    # 组织者点自己那份 → 404 同码分支；不在名单 → 404；无账局 → 404
    r = settle(client, env["org"]["token"], env["game_id"])
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_on_bill"
    r = settle(client, stranger["token"], env["game_id"])
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_on_bill"
    g_free = stage(client, seed=91, fee=None, org=env["org"], mates=env["mates"])
    r = settle(client, payer["token"], g_free["game_id"])
    assert r.status_code == 404 and r.json()["error"]["code"] == "bill_not_found"


# ---- receive 全链（§4.4 / C2：组织者本人独占，管理员 403，幂等） ----


def test_receive_flow_and_guards(client: TestClient):
    env = stage(client, seed=92, fee=300, admin_of=2)
    org = env["org"]
    admin = env["mates"][1]  # admin_of=2：开账后封的管理员（players[0]=org）
    debtor = env["mates"][0]

    # 球友收 → 403；管理员收 → 403（同权管现场，不沾账）
    r = receive(client, debtor["token"], env["game_id"], debtor["account"]["id"])
    assert r.status_code == 403 and r.json()["error"]["code"] == "not_organizer"
    r = receive(client, admin["token"], env["game_id"], debtor["account"]["id"])
    assert r.status_code == 403 and r.json()["error"]["code"] == "not_organizer"

    # 组织者本人收 → 200 视图缩水；重放幂等 received_at 停在第一次
    r = receive(
        client, org["token"], env["game_id"], debtor["account"]["id"], period="30d"
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["period"] == "30d"
    prow = payer_row_of(v, debtor["account"]["id"])
    assert prow["received_at"] and prow["paid_at"] is None
    first_at, row_id = row_stamp(
        client, env["game_id"], debtor["account"]["id"], "received_at"
    )
    assert (
        receive(
            client, org["token"], env["game_id"], debtor["account"]["id"]
        ).status_code
        == 200
    )
    assert stamp_by_id(client, row_id, "received_at") == first_at

    # 收组织者自己那份 → 404；无账局 → 404
    r = receive(client, org["token"], env["game_id"], org["account"]["id"])
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_on_bill"
    g_free = stage(client, seed=93, fee=None, org=org, mates=env["mates"])
    r = receive(client, org["token"], g_free["game_id"], debtor["account"]["id"])
    assert r.status_code == 404 and r.json()["error"]["code"] == "bill_not_found"
