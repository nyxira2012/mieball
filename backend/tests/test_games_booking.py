"""改价窗口放宽 + 散场确认亮数（1.3 批1）—— docs/1.3 §4.5 修订①② / §5 边界验收：
book/clear_booking 窗口 = 散场确认前（ended_at 空且非终态）——开打后可加钱、到点未
散场仍可改；散场确认后总价定死（game_ended）；撤局/终止局照旧 game_not_open（工具箱
其余动作窗口不动）。live 总账视图 fee 块：total=订场登记真值、heads=账单口径摊钱
人头（正式/空降行每人 1 + 名下访客）、per_head=floor 向下抹零，未定价局 total 与
per_head null 但 heads 照给。

时刻基准沿 test_games_tools：FakeClock 10-04 12:00，标准局 10-06 19:00 开打 /
21:00 结束；拨到 20:00 = 开打后（live）。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import signup
from .test_games_actions import assert_blocked, join_ok
from .test_games_read import auth, detail, publish
from .test_games_tools import book_court, clear_booking, lock_game
from .test_live_score import live_call, live_get, open_live


def test_booking_editable_after_start_and_add_money(client: TestClient, fake):
    """§5 边界验收①：开打后往总价加 100（中场买球买水）——live 态改价照常受理。"""
    org = signup(client, "13800040001", "o")
    b = signup(client, "13800040002", "b")
    g = publish(client, org["token"], visibility="public", min_players=1)
    join_ok(client, b["token"], g["id"])
    book_court(client, org["token"], g["id"], fee_total=700)

    fake.advance(days=2, hours=8)  # → 10-06 20:00 开打中
    assert detail(client, g["id"])["status"] == "live"
    out = book_court(
        client, org["token"], g["id"], courts=["3号", "5号"], fee_total=800
    ).json()
    assert out["status"] == "live" and out["fee_total"] == 800

    clear = clear_booking(client, org["token"], g["id"]).json()  # 清空也随时可
    assert clear["status"] == "live" and clear["fee_total"] is None


def test_booking_editable_until_swept_after_end(client: TestClient, fake):
    """到点未散场（视图 done、ended_at 空）仍在改价窗内——散场确认前随时可改。"""
    org = signup(client, "13800040011", "o")
    g = publish(client, org["token"], visibility="public", min_players=1)
    fake.advance(days=2, hours=9)  # → 21:00 已过结束、没人散场
    assert detail(client, g["id"])["status"] == "done"
    out = book_court(client, org["token"], g["id"], fee_total=800).json()
    assert out["status"] == "done" and out["fee_total"] == 800


def test_booking_blocked_with_game_ended_after_sweep(client: TestClient, fake):
    """散场确认之后总价定死：book/clear_booking 一律 game_ended（422）。"""
    env = open_live(client, seed=41, players=2)
    book_court(client, env["org"]["token"], env["game_id"], fee_total=700)
    v = live_get(client, env["game_id"], env["org"]["token"])
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "end",
        {"base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200, r.text

    assert_blocked(
        book_court(client, env["org"]["token"], env["game_id"], fee_total=800),
        "game_ended",
    )
    assert_blocked(
        clear_booking(client, env["org"]["token"], env["game_id"]), "game_ended"
    )


def test_cancelled_and_terminated_still_block_booking(client: TestClient, fake):
    """终态局语义不变：撤局/判死的局 book/clear 仍 game_not_open（窗口判据不看派生）。"""
    org = signup(client, "13800040021", "o")
    g = publish(client, org["token"], visibility="public", min_players=1)
    lock_game(client, org["token"], g["id"])

    r = client.post(f"/api/games/{g['id']}/cancel", headers=auth(org["token"]))
    assert r.status_code == 200
    assert_blocked(book_court(client, org["token"], g["id"]), "game_not_open")
    assert_blocked(clear_booking(client, org["token"], g["id"]), "game_not_open")

    g2 = publish(client, org["token"], visibility="public", min_players=3)
    fake.advance(days=2, hours=6)  # 过截止人头不足 → terminated
    assert detail(client, g2["id"])["status"] == "terminated"
    assert_blocked(book_court(client, org["token"], g2["id"]), "game_not_open")


# ---- live 总账视图 fee 块（§4.5 修订②：散场确认页亮数） ----


def test_live_view_fee_block_priced_with_guests(client: TestClient, fake):
    """有价局：heads=账单口径（正式/空降行每人 1 + 名下访客行），per_head=floor 抹零。"""
    env = open_live(client, seed=42, players=3, bring=2)  # 3 正式 + 2 访客
    book_court(client, env["org"]["token"], env["game_id"], fee_total=700)
    v = live_get(client, env["game_id"], env["org"]["token"])
    assert v["fee"] == {"total": 700, "heads": 5, "per_head": 140}  # 700//5

    # 改价即时反映（700→800 后 per_head 跟着重算）
    book_court(client, env["org"]["token"], env["game_id"], fee_total=800)
    v = live_get(client, env["game_id"], env["org"]["token"])
    assert v["fee"] == {"total": 800, "heads": 5, "per_head": 160}


def test_live_view_fee_block_unpriced_and_recap(client: TestClient, fake):
    """未定价局：total/per_head null 但 heads 照给（亮「总价未定 · N 人」）；
    散场后回看同一形状（亮数不随封存消失）。"""
    env = open_live(client, seed=43, players=3, bring=1)  # 3 正式 + 1 访客
    v = live_get(client, env["game_id"], env["org"]["token"])
    assert v["fee"] == {"total": None, "heads": 4, "per_head": None}

    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "end",
        {"base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["fee"] == {"total": None, "heads": 4, "per_head": None}
