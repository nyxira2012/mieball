"""出账引擎与补填（1.3 批3）—— docs/1.3 §4.1/4.2/4.5/4.7/4.11 的后端半边：
散场即出账（end 同一 commit 落 Bill/BillRow）、出账只挂散场（未散场/到点未散场/
撤局/黄掉永不出账）、除不尽组织者兜底（合计恒等于总价）、访客份额归担保人、
缺席/早退/空降照摊而候补不算、定格（出账后动名册不动账）、幂等（重复 generate
不重算）、补填（>0 出账 billed_at=补填刻而账期仍散场日、=0 只定值、三码拦截、
管理员不碰钱）、fee-preview 定值不落库、game_view bill 块两视角、组织者兜底行。

时刻基准 FakeClock 10-04 12:00（conftest）；标准局 10-06 19:00 开打（test_games_read）。
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core import clock
from app.db.models import Account, Bill, BillRow, Game, LivePlayer
from app.services.bills import BillBook

from .conftest import signup
from .test_games_actions import join_ok
from .test_games_read import DEADLINE2, END2, START2, detail, publish
from .test_live_end import seed_rows
from .test_live_score import live_call, open_live


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def book_fee(client: TestClient, token: str, game_id: int, fee_total: int) -> dict:
    r = client.post(
        f"/api/games/{game_id}/booking",
        headers=auth(token),
        json={"courts": ["3号", "5号"], "fee_total": fee_total},
    )
    assert r.status_code == 200, r.text
    return r.json()


def end_live(client: TestClient, env: dict, view: dict | None = None) -> dict:
    v = view or env["view"]
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "end",
        {"base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200, r.text
    return r.json()


def set_fee(client: TestClient, token: str, game_id: int, fee_total: object):
    return client.post(
        f"/api/games/{game_id}/fee", headers=auth(token), json={"fee_total": fee_total}
    )


def fee_preview(client: TestClient, token: str, game_id: int, amount: int):
    return client.get(
        f"/api/games/{game_id}/fee-preview",
        headers=auth(token),
        params={"amount": amount},
    )


@contextmanager
def db_of(client: TestClient):
    db = client.app.state.session_factory()
    try:
        yield db
    finally:
        db.close()


def get_bill(db, game_id: int) -> Bill | None:
    return db.execute(select(Bill).where(Bill.game_id == game_id)).scalar_one_or_none()


def bill_rows(db, game_id: int) -> list[BillRow]:
    bill = get_bill(db, game_id)
    if bill is None:
        return []
    return (
        db.execute(
            select(BillRow).where(BillRow.bill_id == bill.id).order_by(BillRow.id)
        )
        .scalars()
        .all()
    )


def org_id_of(db, game_id: int) -> int:
    return db.get(Game, game_id).organizer_id


# ---- 算例与合计恒等（§7 不变 1：除不尽零头组织者兜底） ----


def test_end_bills_700_for_12(client: TestClient):
    env = open_live(client, seed=51, players=12)
    book_fee(client, env["org"]["token"], env["game_id"], 700)
    end_live(client, env)
    with db_of(client) as db:
        bill = get_bill(db, env["game_id"])
        assert bill is not None
        assert (bill.fee_total, bill.heads, bill.per_head) == (700, 12, 58)
        rows = bill_rows(db, env["game_id"])
        assert len(rows) == 12
        org = org_id_of(db, env["game_id"])
        assert next(r for r in rows if r.account_id == org).amount == 62
        assert all(r.amount == 58 for r in rows if r.account_id != org)
        assert sum(r.amount for r in rows) == 700  # 合计恒等：638+62
        assert all(r.guest_count == 0 and r.share_count == 1 for r in rows)
        assert all(r.paid_at is None and r.received_at is None for r in rows)
        assert all(r.display_name for r in rows)


def test_bills_650_for_9(client: TestClient):
    env = open_live(client, seed=52, players=9)
    book_fee(client, env["org"]["token"], env["game_id"], 650)
    end_live(client, env)
    with db_of(client) as db:
        bill = get_bill(db, env["game_id"])
        assert (bill.fee_total, bill.heads, bill.per_head) == (650, 9, 72)
        rows = bill_rows(db, env["game_id"])
        org = org_id_of(db, env["game_id"])
        assert next(r for r in rows if r.account_id == org).amount == 74
        assert sum(r.amount for r in rows) == 650  # 576+74


def test_bills_1000_for_13_with_guests_on_guarantor(client: TestClient):
    """访客不单独成行：份额归担保人（1+名下访客数），只出账号行。"""
    env = open_live(client, seed=53, players=13, bring=2)  # 13 账号行 + 2 访客行
    guarantor = env["view"]["players"][1]["account_id"]  # 首位球友带 2 人
    book_fee(client, env["org"]["token"], env["game_id"], 1000)
    end_live(client, env)
    with db_of(client) as db:
        bill = get_bill(db, env["game_id"])
        assert (bill.fee_total, bill.heads, bill.per_head) == (1000, 15, 66)
        rows = bill_rows(db, env["game_id"])
        assert len(rows) == 13  # 访客行不进账
        grow = next(r for r in rows if r.account_id == guarantor)
        assert (grow.guest_count, grow.share_count, grow.amount) == (2, 3, 198)
        org = org_id_of(db, env["game_id"])
        assert next(r for r in rows if r.account_id == org).amount == 76
        assert sum(r.amount for r in rows) == 1000  # 198+11×66+76
        assert sum(r.share_count for r in rows) == bill.heads


# ---- 出账只挂散场（§7 不变 2；§4.7 / §4.11） ----


def test_no_bill_until_end_even_when_derived_done(client: TestClient, fake):
    """到点未散场的局 derive 也出 done——出账锚 ended_at 不锚派生态；
    补散场那一刻账照常出（4.11）。"""
    env = open_live(client, seed=54, players=6)
    book_fee(client, env["org"]["token"], env["game_id"], 420)
    with db_of(client) as db:
        assert get_bill(db, env["game_id"]) is None  # 进行中不出账
    fake.advance(days=3)
    assert detail(client, env["game_id"])["status"] == "done"
    with db_of(client) as db:
        assert get_bill(db, env["game_id"]) is None  # 视图 done ≠ 散场
    v = end_live(client, env)  # 忘了点的散场补上
    assert v["ended"] is True
    with db_of(client) as db:
        bill = get_bill(db, env["game_id"])
        assert bill.billed_at == datetime(2026, 10, 7, 12, 0)  # 出账时刻=散场补办刻
        assert sum(r.amount for r in bill_rows(db, env["game_id"])) == 420


def test_cancelled_and_terminated_never_bill(client: TestClient, fake):
    org = signup(client, "13800060001", "o")
    mate = signup(client, "13800060002", "b")
    g = publish(client, org["token"], visibility="public")
    join_ok(client, mate["token"], g["id"])
    book_fee(client, org["token"], g["id"], 500)
    r = client.post(f"/api/games/{g['id']}/cancel", headers=auth(org["token"]))
    assert r.status_code == 200, r.text
    # 人数不足黄掉：必打没锁、没订场 → 截止判死（第二套时刻：现在之后，test_games_read）
    org2 = signup(client, "13800060003", "o2")
    mate2 = signup(client, "13800060004", "c")
    g2 = publish(
        client,
        org2["token"],
        visibility="public",
        min_players=5,
        max_players=10,
        start_at=START2,
        end_at=END2,
        deadline_at=DEADLINE2,
    )
    join_ok(client, mate2["token"], g2["id"])
    fake.advance(days=3, hours=6)  # → 10-07 18:00：过了 g2 的截止
    assert detail(client, g2["id"])["status"] == "terminated"
    detail(client, g["id"])  # 撤掉的局翻多少遍也没有账（4.7）
    with db_of(client) as db:
        assert get_bill(db, g["id"]) is None
        assert get_bill(db, g2["id"]) is None


def test_absent_left_dropin_all_billed_waitlist_never(client: TestClient):
    """摊钱名单（§5 边界）：缺席照摊、早退整份、空降照摊——候补没占坑没打球不算。"""
    env = open_live(client, seed=55, players=6)
    gid = env["game_id"]
    seed_rows(
        client,
        gid,
        {
            4: {"check": "left"},  # 早退
            5: {"check": "absent", "queue_pos": None},  # 缺席
        },
    )
    stranger = signup(client, "13800060005", "s")
    r = live_call(
        client,
        stranger["token"],
        gid,
        "dropin",
        {"base_total_seq": env["view"]["total_seq"]},
    )
    assert r.status_code == 200, r.text
    book_fee(client, env["org"]["token"], gid, 430)
    end_live(client, env, view=r.json())
    with db_of(client) as db:
        bill = get_bill(db, gid)
        assert bill.heads == 7  # 6 正式（含早退缺席）+ 1 空降
        rows = bill_rows(db, gid)
        assert len(rows) == 7
        assert all(r.amount in (61, 64) for r in rows)  # base=61，组织者兜 64
        assert sum(r.amount for r in rows) == 430
        assert (
            next(r for r in rows if r.account_id == stranger["account"]["id"]).amount
            == 61
        )
        org = org_id_of(db, gid)
        assert next(r for r in rows if r.account_id == org).amount == 64


def test_waitlist_never_billed(client: TestClient):
    org = signup(client, "13800060006", "o")
    mates = [signup(client, f"1380006001{i}", f"m{i}") for i in (1, 2, 3)]
    g = publish(client, org["token"], visibility="public", min_players=2, max_players=3)
    for m in mates:
        join_ok(client, m["token"], g["id"])
    # 2.5 开账闸：成局才可开（本测的是候补不进摊钱人头，成局前置直落 seed）
    with db_of(client) as db:
        db.get(Game, g["id"]).state = "locked"
        db.commit()
    out = detail(client, g["id"], org["token"])
    assert (
        next(
            e for e in out["entries"] if e["account"]["id"] == mates[2]["account"]["id"]
        )["standing"]
        == "waitlist"
    )
    r = live_call(client, org["token"], g["id"], "start", {})
    assert r.status_code == 200, r.text
    book_fee(client, org["token"], g["id"], 300)
    v = end_live(client, {"org": org, "game_id": g["id"], "view": r.json()})
    assert v["ended"] is True
    with db_of(client) as db:
        bill = get_bill(db, g["id"])
        assert bill.heads == 3  # 候补不进摊钱人头
        rows = bill_rows(db, g["id"])
        assert {r.account_id for r in rows} == {
            org["account"]["id"],
            mates[0]["account"]["id"],
            mates[1]["account"]["id"],
        }
        assert sum(r.amount for r in rows) == 300


# ---- 定格与幂等（§7 不变 3） ----


def test_bill_frozen_after_generate(client: TestClient):
    env = open_live(client, seed=56, players=6)
    gid = env["game_id"]
    book_fee(client, env["org"]["token"], gid, 420)
    end_live(client, env)
    with db_of(client) as db:
        before = [(r.account_id, r.amount, r.display_name) for r in bill_rows(db, gid)]
        heads = get_bill(db, gid).heads
        # 出账后名册怎么动都不动账：改定格名、翻考勤、塞访客行
        roster = (
            db.execute(select(LivePlayer).where(LivePlayer.game_id == gid))
            .scalars()
            .all()
        )
        roster[0].display_name = "改名了"
        roster[1].check = "absent"
        db.add(
            LivePlayer(
                game_id=gid,
                account_id=None,
                display_name="塞进来的",
                guest=True,
                guarantor_account_id=roster[0].account_id,
                check="ok",
            )
        )
        db.commit()
    with db_of(client) as db:
        rows = bill_rows(db, gid)
        assert [(r.account_id, r.amount, r.display_name) for r in rows] == before
        assert get_bill(db, gid).heads == heads


def test_generate_idempotent_after_end(client: TestClient):
    """end 后再触发引擎（竞态/重放的等价物）：查到已出账直接返回，不重算。"""
    env = open_live(client, seed=57, players=6)
    gid = env["game_id"]
    book_fee(client, env["org"]["token"], gid, 700)
    end_live(client, env)
    with db_of(client) as db:
        game = db.get(Game, gid)
        b1 = BillBook(db).generate(game=game)
        b2 = BillBook(db).generate(game=game)
        assert b1.id == b2.id
        assert len(bill_rows(db, gid)) == 6


def test_organizer_fallback_row_when_no_roster(client: TestClient):
    """防御兜底（理论不可达，技术设计 §2）：散场局名册为空也能出账，总额归组织者。"""
    signup(client, "13800060007", "o")
    with db_of(client) as db:
        account = (
            db.execute(select(Account).where(Account.phone == "13800060007"))
            .scalars()
            .one()
        )
        now = clock.now()
        game = Game(
            organizer_id=account.id,
            start_at=now,
            end_at=now,
            deadline_at=now,
            venue_name="t",
            min_players=1,
            max_players=4,
            visibility="public",
            scoring=11,
            rotation="queue",
            score_rule="fixed",
            state="locked",
            ended_at=now,
            fee_total=700,
            created_at=now,
        )
        db.add(game)
        db.flush()
        bill = BillBook(db).generate(game=game)
        db.commit()
        gid = game.id
        assert (bill.fee_total, bill.heads, bill.per_head) == (700, 1, 700)
    with db_of(client) as db:
        rows = bill_rows(db, gid)
        assert len(rows) == 1
        assert (rows[0].account_id, rows[0].amount, rows[0].share_count) == (
            account.id,
            700,
            1,
        )


# ---- 补填（§4.5）：出账口子、0 元、三码拦截、管理员不碰钱 ----


def test_open_game_end_seals_state_and_fee_backfill(client: TestClient):
    """账开着而局簿停在 open 的旧账散场：end 把 state 定格成 locked，派生态经
    masked 翻 done——补填入口（前端 status=='done' 才亮）在这条路径不丢（1.3 走查
    补漏）；定格后 POST fee 照常出账。（2.5 收紧后 API 造不出这种局，兼容分支靠
    seed 复刻旧账形保活。）"""
    env = open_live(client, seed=65, players=6)
    gid = env["game_id"]
    with db_of(client) as db:
        db.get(Game, gid).state = "open"  # 复刻旧账：账开着、局簿还没定格
        db.commit()
    v = end_live(client, env)
    assert v["ended"] is True
    assert detail(client, gid)["status"] == "done"  # masked/derive 路径
    r = set_fee(client, env["org"]["token"], gid, 420)
    assert r.status_code == 200, r.text
    assert r.json()["bill"] == {
        "fee_total": 420,
        "per_head": 70,
        "heads": 6,
        "my_share": 70,
        "my_guest_count": 0,
    }
    with db_of(client) as db:
        bill = get_bill(db, gid)
        assert bill.fee_total == 420
        assert sum(r_.amount for r_ in bill_rows(db, gid)) == 420


def test_fee_fill_bills_with_backfill_time(client: TestClient, fake):
    env = open_live(client, seed=58, players=12)
    gid = env["game_id"]
    end_live(client, env)  # 总价未定散场：不出账，等补填
    with db_of(client) as db:
        assert get_bill(db, gid) is None
        assert db.get(Game, gid).fee_total is None
    fake.advance(minutes=30)
    r = set_fee(client, env["org"]["token"], gid, 700)
    assert r.status_code == 200, r.text
    view = r.json()
    assert view["fee_total"] == 700
    assert view["bill"] == {
        "fee_total": 700,
        "per_head": 58,
        "heads": 12,
        "my_share": 62,
        "my_guest_count": 0,
    }
    with db_of(client) as db:
        bill = get_bill(db, gid)
        assert bill.billed_at == datetime(2026, 10, 4, 12, 30)  # billed_at=补填刻
        assert db.get(Game, gid).ended_at == datetime(
            2026, 10, 4, 12, 0
        )  # 账期仍散场日


def test_fee_zero_sets_without_bill_then_locked(client: TestClient):
    env = open_live(client, seed=59, players=6)
    gid = env["game_id"]
    end_live(client, env)
    r = set_fee(client, env["org"]["token"], gid, 0)  # 真免费填 0：只定值不出账
    assert r.status_code == 200, r.text
    view = r.json()
    assert view["fee_total"] == 0 and view["bill"] is None
    with db_of(client) as db:
        assert get_bill(db, gid) is None
    r = set_fee(client, env["org"]["token"], gid, 700)  # 填过（含 0）即定死
    assert r.status_code == 409 and r.json()["error"]["code"] == "fee_already_set"


def test_fee_guards(client: TestClient):
    env = open_live(client, seed=60, players=6)
    gid = env["game_id"]
    org_tok, mate = env["org"]["token"], env["mate"]
    rows = env["view"]["players"]
    r = set_fee(client, org_tok, gid, 700)  # 未散场：组织者本人也拦
    assert r.status_code == 422 and r.json()["error"]["code"] == "game_not_ended"
    r = set_fee(client, mate["token"], gid, 700)  # 球友不碰钱
    assert r.status_code == 403 and r.json()["error"]["code"] == "not_organizer"
    # 管理员同权管现场、但不沾账（C2）：封了管理员照样 403
    v = live_call(
        client,
        org_tok,
        gid,
        "set-admin",
        {"player_id": rows[1]["id"], "base_total_seq": env["view"]["total_seq"]},
    ).json()
    r = set_fee(client, mate["token"], gid, 700)
    assert r.status_code == 403 and r.json()["error"]["code"] == "not_organizer"
    end_live(client, env, view=v)
    r = set_fee(client, org_tok, gid, -5)
    assert r.status_code == 422 and r.json()["error"]["code"] == "fee_invalid"
    r = set_fee(client, org_tok, gid, "abc")  # 非整数：入参校验 422（全项目先例形状）
    assert r.status_code == 422
    assert set_fee(client, org_tok, gid, 700).status_code == 200
    r = set_fee(client, org_tok, gid, 800)  # 散场后填过价的局再补 → 定死
    assert r.status_code == 409 and r.json()["error"]["code"] == "fee_already_set"


# ---- 补填确认步定值（fee-preview）：现算不落库 ----


def test_fee_preview_values_without_writing(client: TestClient):
    env = open_live(client, seed=61, players=12)
    gid = env["game_id"]
    end_live(client, env)
    r = fee_preview(client, env["org"]["token"], gid, 700)
    assert r.status_code == 200, r.text
    assert r.json() == {"heads": 12, "per_head": 58, "organizer_share": 62}
    with db_of(client) as db:
        assert get_bill(db, gid) is None  # 确认步不落库
    r = fee_preview(client, env["mate"]["token"], gid, 700)  # 只给组织者看
    assert r.status_code == 403 and r.json()["error"]["code"] == "not_organizer"


def test_fee_preview_counts_guest_shares(client: TestClient):
    env = open_live(client, seed=62, players=5, bring=1)  # 5 账号行 + 1 访客
    end_live(client, env)
    r = fee_preview(client, env["org"]["token"], env["game_id"], 650)
    assert r.json() == {"heads": 6, "per_head": 108, "organizer_share": 110}


# ---- game_view bill 块（§4.1「我自己那份」：局页与账单行同一个数） ----


def test_game_view_bill_block_viewpoints(client: TestClient):
    env = open_live(client, seed=63, players=12)
    gid = env["game_id"]
    book_fee(client, env["org"]["token"], gid, 700)
    end_live(client, env)
    stranger = signup(client, "13800060008", "x")
    block = detail(client, gid, env["org"]["token"])["bill"]
    assert block == {
        "fee_total": 700,
        "per_head": 58,
        "heads": 12,
        "my_share": 62,  # 组织者自己那份（兜零头）
        "my_guest_count": 0,
    }
    block = detail(client, gid, env["mate"]["token"])["bill"]
    assert (block["my_share"], block["my_guest_count"]) == (58, 0)
    block = detail(client, gid, stranger["token"])["bill"]  # 不在名单：看不到自己份
    assert block["my_share"] is None and block["my_guest_count"] is None
    assert block["fee_total"] == 700 and block["heads"] == 12
    block = detail(client, gid)["bill"]  # 游客同
    assert block["my_share"] is None
    # 未出账的局：bill 块整体为 null（前端以块有无区分预估/实摊）
    # （seed 隔开：63 的 12 人手机号尾段已用到 642，64 会撞号）
    env2 = open_live(client, seed=66, players=6)
    assert detail(client, env2["game_id"])["bill"] is None
