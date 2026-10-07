"""组织者工具箱（批3 片A）—— docs/1.2 §4.7 锁必打与订场 / §4.10 撤局 / §4.9 恢复与待处置。

复用批1/批2 的时刻基准与 helper：标准局 10-06 19:00 开打 / 21:00 结束 / 17:00 截止，
FakeClock 基点 10-04 12:00（conftest）。拨到 10-06 18:00 = 过截止未开打；20:00 = 开打后。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import signup
from .test_games_actions import assert_blocked, edit_game, join_ok
from .test_games_read import (
    auth,
    detail,
    ids_of,
    list_games,
    mine,
    post_game,
    publish,
)


def lock_game(client: TestClient, token: str, game_id: int):
    return client.post(f"/api/games/{game_id}/lock", headers=auth(token))


def book_court(
    client: TestClient,
    token: str,
    game_id: int,
    courts: list[str] | None = None,
    fee_total: int = 480,
):
    body = {
        "courts": courts if courts is not None else ["3号", "5号"],
        "fee_total": fee_total,
    }
    return client.post(f"/api/games/{game_id}/booking", headers=auth(token), json=body)


def clear_booking(client: TestClient, token: str, game_id: int):
    return client.post(f"/api/games/{game_id}/booking/clear", headers=auth(token))


def cancel_game(client: TestClient, token: str, game_id: int):
    return client.post(f"/api/games/{game_id}/cancel", headers=auth(token))


def restore_game(client: TestClient, token: str, game_id: int):
    return client.post(f"/api/games/{game_id}/restore", headers=auth(token))


# ---- 锁必打与订场（4.7） ----


def test_empty_lock_forces_poor_game_and_idempotent(client: TestClient, fake):
    """空锁必打：锁后拨过截止，人头不足也成局；重复锁幂等（B1）。"""
    org = signup(client, "13800020001", "o")
    g = publish(client, org["token"], visibility="public", min_players=3)
    r = lock_game(client, org["token"], g["id"])
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["manual_lock"] is True and out["forced"] is True
    assert out["heads"] == 1  # 只有组织者，人数不足也照开

    r = lock_game(client, org["token"], g["id"])  # 已锁再锁：无事、返回现 view
    assert r.status_code == 200 and r.json()["heads"] == 1

    fake.advance(days=2, hours=6)  # → 10-06 18:00 过截止，1 < 3
    d = detail(client, g["id"])
    assert d["status"] == "locked" and d["forced"] is True  # 必打照样成局


def test_courts_also_force_without_manual_lock(client: TestClient, fake):
    """必打 = 手动锁过 或 场上有号：只订场不空锁，人数不足也不终止（4.8 禁止项）。"""
    org = signup(client, "13800020011", "o")
    g = publish(client, org["token"], visibility="public", min_players=3)
    out = book_court(client, org["token"], g["id"], courts=["7号"], fee_total=0).json()
    assert out["manual_lock"] is False and out["forced"] is True  # 订场即必打
    assert out["courts"] == ["7号"] and out["fee_total"] == 0  # 免费填 0

    fake.advance(days=2, hours=6)
    assert detail(client, g["id"])["status"] == "locked"


def test_lock_window_and_permission(client: TestClient, fake):
    org = signup(client, "13800020021", "o")
    stranger = signup(client, "13800020022", "s")
    g = publish(client, org["token"], visibility="public", min_players=1)
    assert_blocked(lock_game(client, stranger["token"], g["id"]), "not_organizer")

    fake.advance(days=2, hours=8)  # → 20:00 已开打（live）
    assert detail(client, g["id"])["status"] == "live"
    assert_blocked(lock_game(client, org["token"], g["id"]), "game_not_open")


def test_booking_fee_half_up_and_editable_after_deadline(client: TestClient, fake):
    """订场登记：人均 half-up；截止后（名单已锁）面板仍可改——名单锁只锁人（4.7）。"""
    org = signup(client, "13800020031", "o")
    b = signup(client, "13800020032", "b")
    g = publish(client, org["token"], visibility="public", min_players=1)
    join_ok(client, b["token"], g["id"])  # heads 2

    out = book_court(client, org["token"], g["id"], fee_total=5).json()
    assert (
        out["per_head"] == 3
    )  # 5/2=2.5 → half-up 3（对齐 JS Math.round，非 banker's）

    fake.advance(days=2, hours=6)  # 过截止 → locked
    out = book_court(client, org["token"], g["id"], courts=["9号"], fee_total=7).json()
    assert out["status"] == "locked"  # 锁名单不拦改登记
    assert out["courts"] == ["9号"] and out["fee_total"] == 7
    assert out["per_head"] == 4  # 3.5 → 4，人均跟着重算

    fake.advance(hours=3)  # 21:00 已过结束时刻（到点未散场）
    # 改价窗口到散场确认为止（1.3 §4.5 修订①）：到点未散场仍可改，不再 game_not_open
    out = book_court(client, org["token"], g["id"], courts=["9号"], fee_total=9).json()
    assert out["status"] == "done" and out["fee_total"] == 9


def test_booking_validation(client: TestClient):
    org = signup(client, "13800020041", "o")
    g = publish(client, org["token"], visibility="public")
    r = book_court(client, org["token"], g["id"], courts=[])
    assert_blocked(r, "booking_invalid")  # 至少一个场地号
    r = book_court(client, org["token"], g["id"], fee_total=-1)
    assert_blocked(r, "booking_invalid")  # 免费填 0，不给负数


def test_clear_booking_keeps_manual_lock(client: TestClient, fake):
    """清空订场：费用回未定、forced 消失，但手动锁保留——截止照常判、必打仍在（4.7）。"""
    org = signup(client, "13800020051", "o")
    g = publish(client, org["token"], visibility="public", min_players=3)
    lock_game(client, org["token"], g["id"])
    book_court(client, org["token"], g["id"])

    out = clear_booking(client, org["token"], g["id"]).json()
    assert out["courts"] is None and out["fee_total"] is None
    assert out["per_head"] is None  # 费用回"未定"
    assert out["manual_lock"] is True and out["forced"] is True  # 手动锁不松

    r = clear_booking(client, org["token"], g["id"])  # 幂等：再清当没事
    assert r.status_code == 200

    fake.advance(days=2, hours=6)  # 拨过截止：1 < 3，手动锁保它成局
    assert detail(client, g["id"])["status"] == "locked"


# ---- 撤局（4.10） ----


def test_cancel_before_start_aftermath(client: TestClient, fake):
    """撤局：从列表撤下、组织者不留痕、参加者当日灰字次日收走、链接 200 带终态。"""
    org = signup(client, "13800020061", "o")
    b = signup(client, "13800020062", "b")
    g = publish(client, org["token"], visibility="public", min_players=1)
    join_ok(client, b["token"], g["id"])

    r = cancel_game(client, org["token"], g["id"])
    assert r.status_code == 200 and r.json() == {"ok": True}

    assert ids_of(list_games(client, b["token"])) == []  # 从约球页撤下
    assert ids_of(mine(client, org["token"])) == []  # 组织者不留痕（撤局无恢复入口）
    grey = mine(client, b["token"])
    assert ids_of(grey) == [g["id"]] and grey[0]["status"] == "cancelled"  # 当日灰字

    fake.advance(days=1)  # → 10-05
    assert ids_of(mine(client, b["token"])) == []  # 次日收走

    d = detail(client, g["id"], b["token"])
    assert d["status"] == "cancelled"  # 链接点开 200 带终态（说明页语义）
    assert d["heads"] == 2  # 底账留档不删（不变承诺 8）


def test_cancel_window_and_permission(client: TestClient, fake):
    org = signup(client, "13800020071", "o")
    stranger = signup(client, "13800020072", "s")
    g = publish(client, org["token"], visibility="public", min_players=1)
    assert_blocked(cancel_game(client, stranger["token"], g["id"]), "not_organizer")

    fake.advance(days=2, hours=8)  # → 20:00 开打后（开打后是现场的事）
    assert detail(client, g["id"])["status"] == "live"
    assert_blocked(cancel_game(client, org["token"], g["id"]), "game_not_open")


# ---- 恢复与待处置（4.9） ----


def test_restore_terminated_to_pending(client: TestClient, fake):
    """救回未成局：terminated → pending；只组织者可见、球友打开不触发判死。"""
    org = signup(client, "13800020081", "o")
    b = signup(client, "13800020082", "b")
    g = publish(client, org["token"], visibility="public", min_players=3)
    join_ok(client, b["token"], g["id"])  # heads 2 < 3
    fake.advance(days=2, hours=6)  # 过截止判死
    assert detail(client, g["id"])["status"] == "terminated"

    r = restore_game(client, org["token"], g["id"])
    assert r.status_code == 200 and r.json()["status"] == "pending"

    m = mine(client, org["token"])
    assert ids_of(m) == [g["id"]] and m[0]["status"] == "pending"  # 未成局区可见
    assert ids_of(list_games(client, b["token"])) == []  # 他人列表翻不到

    d = detail(client, g["id"], b["token"])
    assert d["status"] == "terminated"  # 非组织者见终态语义
    assert (
        detail(client, g["id"], org["token"])["status"] == "pending"
    )  # 没被球友一眼判死


def test_restore_idempotent_and_disposal_lock(client: TestClient, fake):
    """恢复幂等；pending 锁必打处置完回正常列表（4.9 验收）。"""
    org = signup(client, "13800020091", "o")
    b = signup(client, "13800020092", "b")
    g = publish(client, org["token"], visibility="public", min_players=3)
    join_ok(client, b["token"], g["id"])
    fake.advance(days=2, hours=6)
    assert restore_game(client, org["token"], g["id"]).json()["status"] == "pending"
    assert (
        restore_game(client, org["token"], g["id"]).json()["status"] == "pending"
    )  # 幂等

    out = lock_game(client, org["token"], g["id"]).json()  # 处置出口①：锁必打
    assert out["status"] == "locked" and out["forced"] is True
    assert g["id"] in ids_of(list_games(client, b["token"]))  # 回正常列表


def test_pending_book_disposal(client: TestClient, fake):
    org = signup(client, "13800020101", "o")
    g = publish(client, org["token"], visibility="public", min_players=3)
    fake.advance(days=2, hours=6)
    restore_game(client, org["token"], g["id"])
    out = book_court(client, org["token"], g["id"], courts=["1号"], fee_total=0).json()
    assert out["status"] == "locked"  # 处置出口②：订场登记同为待处置出口


def test_pending_zombie_exits_at_start(client: TestClient, fake):
    """待处置拖过开打 = 死局：懒判定落 terminated，参加者灰字按开打日记日。"""
    org = signup(client, "13800020111", "o")
    b = signup(client, "13800020112", "b")
    g = publish(client, org["token"], visibility="public", min_players=3)
    join_ok(client, b["token"], g["id"])
    fake.advance(days=2, hours=6)  # 过截止 → terminated
    restore_game(client, org["token"], g["id"])  # → pending

    fake.advance(hours=3)  # → 21:00 拖过开打（19:00）
    assert (
        detail(client, g["id"], org["token"])["status"] == "terminated"
    )  # 僵尸出口落库
    assert ids_of(mine(client, org["token"])) == []  # 组织者也不留（窗口已关）
    grey = mine(client, b["token"])
    assert ids_of(grey) == [g["id"]] and grey[0]["status"] == "terminated"

    fake.advance(days=1)
    assert ids_of(mine(client, b["token"])) == []  # 灰字次日收走


def test_restore_window_closed_after_start(client: TestClient, fake):
    """恢复窗口 = 开打前；开打后恢复入口消失（开打后想再打发新局）。"""
    org = signup(client, "13800020121", "o")
    g = publish(client, org["token"], visibility="public", min_players=3)
    fake.advance(days=2, hours=6)  # 过截止判死（此时还没到开打）
    assert detail(client, g["id"])["status"] == "terminated"

    fake.advance(hours=3)  # 拖过开打才来恢复
    assert_blocked(restore_game(client, org["token"], g["id"]), "game_not_open")


# ---- 人数下限（批2 Nit 收口） ----


def test_min_max_must_be_at_least_one(client: TestClient):
    org = signup(client, "13800020131", "o")
    r = post_game(client, org["token"], min_players=0)
    assert_blocked(r, "range_invalid")
    r = post_game(client, org["token"], max_players=0)
    assert_blocked(r, "range_invalid")
    g = publish(client, org["token"], visibility="public")
    r = edit_game(client, org["token"], g["id"], max_players=0)
    assert_blocked(r, "range_invalid")
