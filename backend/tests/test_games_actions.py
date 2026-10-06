"""局簿写动作（批2）—— docs/1.2 §4.3 报名 / §4.4 退局 / §4.6 改局 / §4.14 抢坑与截止后进场。

复用 test_games_read 的时刻基准与发局 helper：标准局 10-06 19:00 开打 / 21:00 结束 /
17:00 截止，FakeClock 基点 10-04 12:00（conftest）。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import signup
from .test_games_read import (
    DEADLINE,
    DEADLINE2,
    END,
    END2,
    START2,
    auth,
    detail,
    publish,
)


def join_game(client: TestClient, token: str, game_id: int, bring: int = 0):
    return client.post(
        f"/api/games/{game_id}/join", headers=auth(token), json={"bring": bring}
    )


def join_ok(client: TestClient, token: str, game_id: int, bring: int = 0) -> dict:
    r = join_game(client, token, game_id, bring)
    assert r.status_code == 200, r.text
    return r.json()


def quit_game(client: TestClient, token: str, game_id: int):
    return client.post(f"/api/games/{game_id}/quit", headers=auth(token))


def edit_game(client: TestClient, token: str, game_id: int, **fields):
    return client.post(f"/api/games/{game_id}/edit", headers=auth(token), json=fields)


def row_of(view: dict, account_id: int) -> dict:
    return next(e for e in view["entries"] if e["account"]["id"] == account_id)


def assert_blocked(r, code: str) -> None:
    assert r.status_code in (403, 409, 422) and r.json()["error"]["code"] == code, (
        r.text
    )


# ---- 报名（4.3） ----


def test_join_with_bring_counts_whole_row(client: TestClient):
    org = signup(client, "13800010001", "o")
    b = signup(client, "13800010002", "b")
    g = publish(client, org["token"], visibility="public")
    assert g["slots_left"] == 5
    out = join_ok(client, b["token"], g["id"], bring=2)
    # 报名带 2 人进度减 1+2（§5：剩 5 坑 → 剩 2 坑）
    assert out["heads"] == 4 and out["slots_left"] == 2
    row = row_of(out, b["account"]["id"])
    assert row["bring"] == 2 and row["standing"] == "formal" and row["wait_seq"] is None


def test_join_limit_and_windows(client: TestClient, fake):
    org = signup(client, "13800010011", "o")
    b = signup(client, "13800010012", "b")
    c = signup(client, "13800010013", "c")
    d = signup(client, "13800010014", "d")
    g = publish(client, org["token"], visibility="public", min_players=1)
    assert_blocked(join_game(client, b["token"], g["id"], bring=4), "bring_limit")

    fake.advance(days=2, hours=6)  # → 10-06 18:00：过截止成局（locked）
    assert detail(client, g["id"])["status"] == "locked"
    out = join_ok(client, b["token"], g["id"])  # 截止后加入不拦（4.14 现场空降）
    assert row_of(out, b["account"]["id"])["standing"] == "formal"

    fake.advance(hours=4)  # → 22:00：过结束（done）
    assert_blocked(join_game(client, c["token"], g["id"]), "join_closed")

    g2 = publish(
        client,
        org["token"],
        visibility="public",
        min_players=3,
        start_at=START2,
        end_at=END2,
        deadline_at=DEADLINE2,
    )
    fake.advance(hours=20)  # → 10-07 18:00：过 g2 截止，1<3 判死
    assert detail(client, g2["id"])["status"] == "terminated"
    assert_blocked(join_game(client, d["token"], g2["id"]), "join_closed")


def test_join_full_goes_waitlist_then_promotes_on_quit(client: TestClient):
    org = signup(client, "13800010021", "o")
    b = signup(client, "13800010022", "b")
    c = signup(client, "13800010023", "c")
    g = publish(client, org["token"], visibility="public", max_players=2)
    join_ok(client, b["token"], g["id"])  # 满员
    out = join_ok(client, c["token"], g["id"])  # 满员后再加 → 候补
    assert out["heads"] == 2 and out["slots_left"] == 0
    crow = row_of(out, c["account"]["id"])
    assert crow["standing"] == "waitlist" and crow["wait_seq"] == 1

    r = quit_game(client, b["token"], g["id"])  # 有人退出 → 候补第一行自动转正
    assert r.status_code == 200 and r.json() == {"ok": True}
    out = detail(client, g["id"], org["token"])
    crow = row_of(out, c["account"]["id"])
    assert crow["standing"] == "formal" and crow["wait_seq"] is None
    assert out["heads"] == 2 and out["slots_left"] == 0


def test_join_row_not_fitting_waits_whole(client: TestClient):
    """剩 2 坑带 2 人（整行 3 人）→ 整行落候补，不拆行、正式人头不变（§5 边界）。"""
    org = signup(client, "13800010031", "o")
    b = signup(client, "13800010032", "b")
    c = signup(client, "13800010033", "c")
    g = publish(client, org["token"], visibility="public", max_players=4)
    join_ok(client, b["token"], g["id"])  # heads 2，剩 2 坑
    out = join_ok(client, c["token"], g["id"], bring=2)
    assert out["heads"] == 2 and out["slots_left"] == 2
    crow = row_of(out, c["account"]["id"])
    assert crow["standing"] == "waitlist" and crow["bring"] == 2
    assert crow["wait_seq"] == 1


def test_join_idempotent_keeps_original_row(client: TestClient):
    org = signup(client, "13800010041", "o")
    b = signup(client, "13800010042", "b")
    g = publish(client, org["token"], visibility="public")
    join_ok(client, b["token"], g["id"], bring=1)
    out = join_ok(client, b["token"], g["id"], bring=3)  # 重复 join 换 bring：原行不变
    row = row_of(out, b["account"]["id"])
    assert row["bring"] == 1 and row["standing"] == "formal"
    assert out["heads"] == 3  # 1(org)+2(b 行)，没有重复占坑
    out = join_ok(client, org["token"], g["id"])  # 组织者再 join：幂等无事
    assert out["heads"] == 3 and out["my"]["is_organizer"] is True


def test_race_for_last_pits_never_exceeds_cap(client: TestClient):
    """抢坑不超线（4.14①/B1）：cap=4 已 3 人，两人各带 1 先后 join，后者必候补。"""
    org = signup(client, "13800010051", "o")
    b = signup(client, "13800010052", "b")
    c = signup(client, "13800010053", "c")
    d = signup(client, "13800010054", "d")
    g = publish(client, org["token"], visibility="public", max_players=4)
    join_ok(client, b["token"], g["id"], bring=1)  # heads 3，剩 1 坑
    out = join_ok(client, c["token"], g["id"], bring=1)  # 3+2 装不下 → 候补
    assert row_of(out, c["account"]["id"])["standing"] == "waitlist"
    out = join_ok(client, d["token"], g["id"], bring=1)  # 后者也候补，都不报错
    assert row_of(out, d["account"]["id"])["standing"] == "waitlist"
    assert row_of(out, d["account"]["id"])["wait_seq"] == 2
    assert out["heads"] == 3 and out["slots_left"] == 1  # formal 人头恒 ≤ cap


# ---- 退局（4.4/4.6 解锁窗） ----


def test_quit_after_deadline_blocked(client: TestClient, fake):
    org = signup(client, "13800010061", "o")
    b = signup(client, "13800010062", "b")
    g = publish(client, org["token"], visibility="public", min_players=1)
    join_ok(client, b["token"], g["id"])
    fake.advance(days=2, hours=6)  # 过截止 → locked
    assert_blocked(quit_game(client, b["token"], g["id"]), "game_locked")
    out = detail(client, g["id"], org["token"])
    assert out["heads"] == 2  # 名单没动


def test_quit_unlock_window_full_chain(client: TestClient, fake):
    """改约解锁全链路（4.6）：截止后改时间 → 解锁可退、候补递补；到新开打时刻重新锁死。"""
    org = signup(client, "13800010071", "o")
    b = signup(client, "13800010072", "b")
    c = signup(client, "13800010073", "c")
    g = publish(client, org["token"], visibility="public", max_players=2)
    join_ok(client, b["token"], g["id"])  # 满员
    join_ok(client, c["token"], g["id"])  # c 候补
    assert detail(client, g["id"])["unlocked"] is False

    fake.advance(days=2, hours=6)  # 过截止 → locked，此时退被拦
    assert_blocked(quit_game(client, b["token"], g["id"]), "game_locked")

    r = edit_game(
        client, org["token"], g["id"], start_at=START2, end_at=END2
    )  # 组织者改时间（end 随 start 一起挪，否则结束早于新开打）
    assert r.status_code == 200, r.text
    assert r.json()["unlocked"] is True

    r = quit_game(client, b["token"], g["id"])  # 解锁窗内参加者可退
    assert r.status_code == 200 and r.json() == {"ok": True}
    out = detail(client, g["id"], org["token"])
    crow = row_of(out, c["account"]["id"])
    assert crow["standing"] == "formal" and crow["wait_seq"] is None  # 候补递补
    assert out["heads"] == 2

    fake.advance(days=1, hours=2)  # → 10-07 20:00：过新开打时刻，解锁窗关
    assert detail(client, g["id"])["status"] == "live"
    assert_blocked(quit_game(client, c["token"], g["id"]), "game_locked")


def test_quit_organizer_forbidden_and_idempotent(client: TestClient):
    org = signup(client, "13800010081", "o")
    b = signup(client, "13800010082", "b")
    stranger = signup(client, "13800010083", "s")
    g = publish(client, org["token"], visibility="public")
    r = quit_game(client, org["token"], g["id"])
    assert r.status_code == 403 and r.json()["error"]["code"] == "not_organizer"
    assert r.json()["error"]["message"] == "组织者不能退出，只能撤局"

    r = quit_game(client, stranger["token"], g["id"])  # 没报名 → 幂等 ok
    assert r.status_code == 200 and r.json() == {"ok": True}

    join_ok(client, b["token"], g["id"])
    assert quit_game(client, b["token"], g["id"]).json() == {"ok": True}
    assert quit_game(client, b["token"], g["id"]).json() == {"ok": True}  # 退了再退幂等
    out = detail(client, g["id"], org["token"])
    assert out["heads"] == 1
    assert [e for e in out["entries"] if e["account"]["id"] == b["account"]["id"]] == []


# ---- 改局（4.6） ----


def test_edit_time_inverted_blocked_then_ok(client: TestClient):
    org = signup(client, "13800010091", "o")
    g = publish(client, org["token"], visibility="public")
    # 开打改到截止（17:00）之前 → 倒挂拦
    r = edit_game(
        client, org["token"], g["id"], start_at="2026-10-06T16:00:00+08:00", end_at=END
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "deadline_inverted"
    # 改到截止之后 → 成功，截止原值不动
    r = edit_game(
        client,
        org["token"],
        g["id"],
        start_at="2026-10-06T20:00:00+08:00",
        end_at="2026-10-06T22:00:00+08:00",
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["start_at"] == "2026-10-06T20:00:00+08:00"
    assert out["end_at"] == "2026-10-06T22:00:00+08:00"
    assert out["deadline_at"] == DEADLINE
    assert out["unlocked"] is False  # 报名中改时间不置解锁标记


def test_edit_range_visibility_permission_and_closed(client: TestClient, fake):
    org = signup(client, "13800010101", "o")
    b = signup(client, "13800010102", "b")
    g = publish(client, org["token"], visibility="public")
    r = edit_game(client, org["token"], g["id"], min_players=5, max_players=4)
    assert r.status_code == 422 and r.json()["error"]["code"] == "range_invalid"
    r = edit_game(client, org["token"], g["id"], visibility="friends")
    assert r.status_code == 422 and r.json()["error"]["code"] == "visibility_invalid"
    r = edit_game(client, b["token"], g["id"], name="x")  # 非组织者
    assert r.status_code == 403 and r.json()["error"]["code"] == "not_organizer"

    fake.advance(days=2, hours=6)  # 1<3 判死
    assert detail(client, g["id"])["status"] == "terminated"
    r = edit_game(client, org["token"], g["id"], name="x")
    assert r.status_code == 422 and r.json()["error"]["code"] == "game_not_open"


def test_edit_cap_shrink_demotes_latest_and_grow_restores(client: TestClient):
    org = signup(client, "13800010111", "o")
    b = signup(client, "13800010112", "b")
    c = signup(client, "13800010113", "c")
    d = signup(client, "13800010114", "d")
    g = publish(client, org["token"], visibility="public", min_players=1)
    join_ok(client, b["token"], g["id"], bring=1)  # heads 3
    join_ok(client, c["token"], g["id"], bring=1)  # heads 5
    join_ok(client, d["token"], g["id"])  # heads 6

    r = edit_game(client, org["token"], g["id"], max_players=4)
    assert r.status_code == 200, r.text
    out = r.json()
    # 上限 6→4：最晚报的两行整行落候补（含带的），组织者永不被转
    assert out["heads"] == 3 and out["slots_left"] == 1
    assert row_of(out, org["account"]["id"])["standing"] == "formal"
    assert row_of(out, b["account"]["id"])["standing"] == "formal"
    crow = row_of(out, c["account"]["id"])
    drow = row_of(out, d["account"]["id"])
    assert crow["standing"] == "waitlist" and crow["wait_seq"] == 1
    assert drow["standing"] == "waitlist" and drow["wait_seq"] == 2

    r = edit_game(client, org["token"], g["id"], max_players=6)  # 改回：候补按序转正
    assert r.status_code == 200, r.text
    out = r.json()
    crow = row_of(out, c["account"]["id"])
    drow = row_of(out, d["account"]["id"])
    assert crow["standing"] == "formal" and crow["wait_seq"] is None
    assert drow["standing"] == "formal" and drow["wait_seq"] is None
    assert out["heads"] == 6 and out["slots_left"] == 0


def test_edit_visibility_change_keeps_roster(client: TestClient):
    """改档不赶人（4.6）：换可见档后已在名单里的人一律不动。"""
    org = signup(client, "13800010121", "o")
    b = signup(client, "13800010122", "b")
    g = publish(client, org["token"], visibility="public")
    join_ok(client, b["token"], g["id"], bring=1)
    before = detail(client, g["id"])["entries"]
    r = edit_game(client, org["token"], g["id"], visibility="played")
    assert r.status_code == 200, r.text
    assert r.json()["visibility"] == "played"
    assert r.json()["entries"] == before


def test_edit_venue_before_deadline_does_not_unlock(client: TestClient):
    org = signup(client, "13800010131", "o")
    b = signup(client, "13800010132", "b")
    g = publish(client, org["token"], visibility="public")
    join_ok(client, b["token"], g["id"])
    r = edit_game(client, org["token"], g["id"], venue_name="新场馆")
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["venue_name"] == "新场馆"
    assert out["unlocked"] is False  # 截止前改 venue：不置解锁标记
