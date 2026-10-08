"""my 块能力旗（闸旗同源，2026-10-08 债清偿）—— can_book/can_fill_fee/can_lock 与
顶层 ended：写窗真值直读，前端不再拿派生 status 拼窗口。验收锚定当年踩不到雷的裂缝
场景「到点未散场」（派生 done 但 ended_at 空）：订场窗仍开（can_book 真）、补填窗
仍关（can_fill_fee 假）——散场确认后整组反转。

时刻基准沿 test_games_tools：FakeClock 10-04 12:00，标准局 10-06 19:00 开打 /
21:00 结束；拨 days=2, hours=9 = 21:00 已过结束、没人散场。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import signup
from .test_bills_generate import set_fee
from .test_games_read import auth, detail, publish
from .test_games_tools import lock_game
from .test_live_score import live_call, live_get, open_live


def _ph(seed: int) -> str:
    return f"1380005{seed:04d}"


def test_flags_until_swept_after_end_done_view(client: TestClient, fake):
    """裂缝主场景：到点未散场（视图 done、ended 假）——can_book 仍真、补填仍假。
    旗不随派生 done 翻转，锚的是散场确认（ended_at）。"""
    org = signup(client, _ph(1), "o")
    g = publish(client, org["token"], visibility="public", min_players=1)
    lock_game(client, org["token"], g["id"])
    fake.advance(days=2, hours=9)  # → 10-06 21:00 过结束点、没人散场
    v = detail(client, g["id"], org["token"])
    assert v["status"] == "done" and v["ended"] is False  # 显示态≠流程态
    assert v["my"]["can_book"] is True  # 后端窗开着，前端照旗亮钮（功能不再失踪）
    assert (
        v["my"]["can_fill_fee"] is False
    )  # 散场没确认，补填不亮（不再「亮钮必 422」）
    assert v["my"]["can_lock"] is False  # 开打后空锁关窗


def test_flags_non_organizer_and_anonymous_all_false_or_absent(
    client: TestClient,
    fake,
):
    """能力旗折了组织者身份：正式成员三旗全假；匿名请求不带 my 块。"""
    org = signup(client, _ph(11), "o")
    mate = signup(client, _ph(12), "m")
    g = publish(client, org["token"], visibility="public", min_players=1)
    r = client.post(
        f"/api/games/{g['id']}/join", headers=auth(mate["token"]), json={"bring": 0}
    )
    assert r.status_code == 200, r.text

    mine = detail(client, g["id"], mate["token"])["my"]
    assert mine["is_organizer"] is False
    assert mine["can_book"] is False
    assert mine["can_fill_fee"] is False
    assert mine["can_lock"] is False

    anon = detail(client, g["id"])
    assert "my" not in anon


def test_flags_flip_after_sweep_and_fill_fee(client: TestClient, fake):
    """散场确认后整组反转：can_book 关、can_fill_fee 开（从未填价）——补填落定后
    补填窗也关（填过一次就定死）。"""
    env = open_live(client, seed=51, players=2)  # 未定价就散场
    v = live_get(client, env["game_id"], env["org"]["token"])
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "end",
        {"base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200, r.text

    after = detail(client, env["game_id"], env["org"]["token"])
    assert after["status"] == "done" and after["ended"] is True
    assert after["my"]["can_book"] is False  # 总价定死
    assert after["my"]["can_fill_fee"] is True  # 从未填价，一口补填亮出

    assert set_fee(client, env["org"]["token"], env["game_id"], 600).status_code == 200
    filled = detail(client, env["game_id"], env["org"]["token"])
    assert filled["my"]["can_fill_fee"] is False  # 补填口只留一次
    assert filled["my"]["can_book"] is False


def test_flags_pending_restore_keeps_disposal_exits(client: TestClient, fake):
    """恢复局的待处置出口（4.9）：pending 态 can_book/can_lock 都真——锁必打与
    订场登记都是处置门（详情页照旗亮钮，不再只靠约球页待处置卡）。"""
    org = signup(client, _ph(21), "o")
    g = publish(client, org["token"], visibility="public", min_players=3)
    fake.advance(days=2, hours=6)  # 过截止人头不足 → terminated
    assert detail(client, g["id"], org["token"])["status"] == "terminated"

    r = client.post(f"/api/games/{g['id']}/restore", headers=auth(org["token"]))
    assert r.status_code == 200, r.text
    v = detail(client, g["id"], org["token"])
    assert v["status"] == "pending"
    assert v["my"]["can_book"] is True
    assert v["my"]["can_lock"] is True
    assert v["my"]["can_fill_fee"] is False


def test_flags_live_state_booking_open_lock_closed(client: TestClient, fake):
    """开打中（live）：订场/改价照常（1.3 §4.5 修订①），空锁关窗（422 语义同旗）。"""
    org = signup(client, _ph(31), "o")
    g = publish(client, org["token"], visibility="public", min_players=1)
    lock_game(client, org["token"], g["id"])
    fake.advance(days=2, hours=8)  # → 20:00 开打中
    v = detail(client, g["id"], org["token"])
    assert v["status"] == "live" and v["ended"] is False
    assert v["my"]["can_book"] is True
    assert v["my"]["can_lock"] is False
