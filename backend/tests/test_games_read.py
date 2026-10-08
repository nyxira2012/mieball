"""局簿读链（批1）—— docs/1.2 §4.1 发局 / §4.2 找局三档 / §4.8 懒判定 / 我的局 / 详情。

批1 没有 join 端点（批2 实现），名单行由 seed_entry 直接落库模拟报名历史。
FakeClock 基点 2026-10-04 12:00（conftest），局的标准时刻：10-06 19:00 开打 / 21:00 结束 / 17:00 截止。
"""

from __future__ import annotations

from app.core import clock
from app.db.models import Entry
from fastapi.testclient import TestClient

from .conftest import signup

START, END, DEADLINE = (
    "2026-10-06T19:00:00+08:00",
    "2026-10-06T21:00:00+08:00",
    "2026-10-06T17:00:00+08:00",
)
# 拨过第一批局截止后再发新局用的第二套时刻（截止必须在现在之后）
START2, END2, DEADLINE2 = (
    "2026-10-07T19:00:00+08:00",
    "2026-10-07T21:00:00+08:00",
    "2026-10-07T17:00:00+08:00",
)


def auth(token: str | None) -> dict:
    return {"Authorization": f"Bearer {token}"} if token else {}


def post_game(client: TestClient, token: str, **over):
    body = {
        "name": "周三夜战",
        "start_at": START,
        "end_at": END,
        "deadline_at": DEADLINE,
        "venue_name": "海淀体育馆",
        "venue_address": "海淀区某路1号",
        "min_players": 2,
        "max_players": 6,
        "visibility": "played",
        "scoring": 21,
        "rotation": "双打轮转",
        "score_rule": "每球得分",
    } | over
    return client.post("/api/games", headers=auth(token), json=body)


def publish(client: TestClient, token: str, **over) -> dict:
    r = post_game(client, token, **over)
    assert r.status_code == 200, r.text
    return r.json()


def list_games(client: TestClient, token: str | None = None) -> list[dict]:
    r = client.get("/api/games", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def mine(client: TestClient, token: str) -> list[dict]:
    r = client.get("/api/games/mine", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def detail(client: TestClient, game_id: int, token: str | None = None) -> dict:
    r = client.get(f"/api/games/{game_id}", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def seed_entry(
    client: TestClient,
    game_id: int,
    account_id: int,
    *,
    bring: int = 0,
    standing: str = "formal",
    wait_seq: int | None = None,
) -> None:
    """直接落一条报名行（join 端点批2 才有）。"""
    db = client.app.state.session_factory()
    try:
        db.add(
            Entry(
                game_id=game_id,
                account_id=account_id,
                bring=bring,
                standing=standing,
                wait_seq=wait_seq,
                joined_at=clock.now(),
            )
        )
        db.commit()
    finally:
        db.close()


def ids_of(games: list[dict]) -> list[int]:
    return [g["id"] for g in games]


# ---- 发局（4.1） ----


def test_publish_organizer_is_first_row_and_fee_undecided(client: TestClient):
    out = signup(client, "13800000001", "d1")
    acc = out["account"]
    g = publish(client, out["token"])
    assert g["status"] == "open" and g["joinable"] is True
    assert g["organizer"] == {
        "id": acc["id"],
        "nickname": acc["name"],
        "chibi": acc["chibi"],
    }
    assert g["entries"][0]["account"]["id"] == acc["id"]  # 名单头一个就是组织者
    assert g["entries"][0]["standing"] == "formal" and g["entries"][0]["bring"] == 0
    assert g["heads"] == 1 and g["slots_left"] == 5
    assert (
        g["fee_total"] is None and g["per_head"] is None and g["forced"] is False
    )  # 费用未定
    assert g["my"] == {
        "is_organizer": True,
        "my_entry": {"bring": 0, "standing": "formal", "wait_seq": None},
        "invited": False,
        # 能力旗（闸旗同源，2026-10-08 债清偿）：新发 open 局——订场窗开着、
        # 没散场没得补填、开打前可空锁
        "can_book": True,
        "can_fill_fee": False,
        "can_lock": True,
    }
    assert g["start_at"] == "2026-10-06T19:00:00+08:00"  # 出参统一补 +08:00


def test_publish_requires_login(client: TestClient):
    r = client.post("/api/games", json={})
    assert r.status_code == 401 and r.json()["error"]["code"] == "no_identity"


def test_publish_rejects_bad_time_window(client: TestClient):
    token = signup(client, "13800000002", "d2")["token"]
    bad = [
        {"deadline_at": "2026-10-06T19:30:00+08:00"},  # 截止晚于开打
        {
            "deadline_at": "2026-10-04T11:00:00+08:00"
        },  # 截止已在过去（现在=10-04 12:00）
        {"end_at": "2026-10-06T18:00:00+08:00"},  # 结束早于开打
    ]
    for over in bad:
        r = post_game(client, token, **over)
        assert (
            r.status_code == 422 and r.json()["error"]["code"] == "deadline_inverted"
        ), over


def test_publish_rejects_range_and_visibility(client: TestClient):
    token = signup(client, "13800000003", "d3")["token"]
    r = post_game(client, token, min_players=5, max_players=4)
    assert r.status_code == 422 and r.json()["error"]["code"] == "range_invalid"
    r = post_game(client, token, visibility="friends")
    assert r.status_code == 422 and r.json()["error"]["code"] == "visibility_invalid"


# ---- 可见性三档（4.2） ----


def test_public_visible_to_all_including_anonymous(client: TestClient):
    org = signup(client, "13800000004", "d4")
    stranger = signup(client, "13800000005", "d5")
    g = publish(client, org["token"], visibility="public")
    assert ids_of(list_games(client)) == [g["id"]]  # 匿名也翻得到 public
    assert ids_of(list_games(client, stranger["token"])) == [g["id"]]


def test_played_visibility_partner_sees_stranger_not(client: TestClient, fake):
    a = signup(client, "13800000011", "da")
    b = signup(client, "13800000012", "db")
    g1 = publish(client, a["token"], visibility="public", min_players=2)
    seed_entry(client, g1["id"], b["account"]["id"])  # A、B 同在正式名单
    fake.advance(days=2, hours=6)  # → 10-06 18:00，过截止
    assert detail(client, g1["id"])["status"] == "locked"  # 打开即判：成局

    g2 = publish(
        client,
        a["token"],
        visibility="played",
        start_at=START2,
        end_at=END2,
        deadline_at=DEADLINE2,
    )
    stranger = signup(client, "13800000013", "dc")
    assert g1["id"] in ids_of(list_games(client, stranger["token"]))
    assert g2["id"] not in ids_of(
        list_games(client, stranger["token"])
    )  # 陌生人翻不到 played 档
    assert g2["id"] in ids_of(list_games(client, b["token"]))  # 同打过的伙伴翻得到
    assert g2["id"] not in ids_of(mine(client, b["token"]))  # 但没报名就不进"我的局"


def test_played_waitlist_does_not_count(client: TestClient, fake):
    a = signup(client, "13800000021", "da")
    b = signup(client, "13800000022", "db")
    g1 = publish(client, a["token"], visibility="public", min_players=1)
    seed_entry(
        client, g1["id"], b["account"]["id"], standing="waitlist", wait_seq=1
    )  # 只候补
    fake.advance(days=2, hours=6)
    assert detail(client, g1["id"])["status"] == "locked"
    g2 = publish(
        client,
        a["token"],
        visibility="played",
        start_at=START2,
        end_at=END2,
        deadline_at=DEADLINE2,
    )
    assert g2["id"] not in ids_of(list_games(client, b["token"]))


def test_played_terminated_game_does_not_count(client: TestClient, fake):
    a = signup(client, "13800000031", "da")
    b = signup(client, "13800000032", "db")
    g1 = publish(client, a["token"], visibility="public", min_players=3)  # 2<3 必终止
    seed_entry(client, g1["id"], b["account"]["id"])
    fake.advance(days=2, hours=6)
    assert (
        detail(client, g1["id"])["status"] == "terminated"
    )  # 同过名单但局没成，不算打过
    g2 = publish(
        client,
        a["token"],
        visibility="played",
        start_at=START2,
        end_at=END2,
        deadline_at=DEADLINE2,
    )
    assert g2["id"] not in ids_of(list_games(client, b["token"]))


# ---- 懒判定（4.8：谁先打开谁触发，当场判完记档） ----


def test_lazy_locks_when_enough_heads(client: TestClient, fake):
    a = signup(client, "13800000041", "da")
    g = publish(client, a["token"], visibility="public", min_players=2)
    seed_entry(client, g["id"], signup(client, "13800000042", "db")["account"]["id"])
    fake.advance(days=2, hours=6)
    d = detail(client, g["id"])
    assert d["status"] == "locked" and d["heads"] == 2  # 名单锁定
    assert d["joinable"] is True  # 截止后照常能加（4.14）


def test_lazy_terminates_and_daily_rules(client: TestClient, fake):
    a = signup(client, "13800000051", "da")
    b = signup(client, "13800000052", "db")
    g = publish(client, a["token"], visibility="public", min_players=3)
    seed_entry(client, g["id"], b["account"]["id"])  # heads=2 < 3
    fake.advance(days=2, hours=6)  # → 10-06 18:00（当日）
    assert ids_of(list_games(client)) == []  # 从列表撤下
    assert (
        detail(client, g["id"])["status"] == "terminated"
    )  # 详情 200 带终态（说明页）
    assert ids_of(mine(client, a["token"])) == [
        g["id"]
    ]  # 组织者留"未成局"（开打前可恢复）
    assert mine(client, b["token"])[0]["status"] == "terminated"  # 参加者当日灰字

    fake.advance(days=1)  # → 10-07 18:00（已过开打）
    assert ids_of(mine(client, b["token"])) == []  # 灰字次日收走
    assert ids_of(mine(client, a["token"])) == []  # 恢复窗口关了，组织者也不留


def test_locked_state_flips_with_time(client: TestClient, fake):
    a = signup(client, "13800000061", "da")
    g = publish(client, a["token"], visibility="public", min_players=1)
    fake.advance(days=2, hours=6)  # 18:00 截止后 → 锁
    assert detail(client, g["id"])["status"] == "locked"
    fake.advance(minutes=90)  # 19:30 开打中
    d = detail(client, g["id"])
    assert d["status"] == "live" and d["joinable"] is True  # 进行中还能现场空降
    fake.advance(minutes=150)  # 22:00 已结束
    d = detail(client, g["id"])
    assert d["status"] == "done" and d["joinable"] is False  # 历史名单只读


# ---- 我的局 / 详情 / 排序 ----


def test_mine_organizer_sees_own_open_game(client: TestClient):
    out = signup(client, "13800000071", "d7")
    g = publish(client, out["token"], visibility="public")
    m = mine(client, out["token"])
    assert ids_of(m) == [g["id"]] and m[0]["my"]["is_organizer"] is True
    other = signup(client, "13800000072", "d8")
    assert mine(client, other["token"]) == []  # 别人的局不进我的局


def test_detail_anonymous_link_is_ticket(client: TestClient):
    out = signup(client, "13800000081", "d8")
    g = publish(client, out["token"], visibility="played")
    d = detail(client, g["id"])  # 无 Bearer 看 played 档详情
    assert d["id"] == g["id"] and "my" not in d  # 匿名不带 my 块
    assert len(d["entries"]) == 1  # 名单照看（只显昵称+小人）


def test_detail_anonymous_link_is_ticket_invite_only(client: TestClient):
    out = signup(client, "13800000082", "d8")
    g = publish(client, out["token"], visibility="invite_only")
    d = detail(client, g["id"])  # 无 Bearer 看 invite_only 档详情：链接即门票（4.2）
    assert d["id"] == g["id"] and "my" not in d


def test_detail_not_found(client: TestClient):
    r = client.get("/api/games/999")
    assert r.status_code == 404 and r.json()["error"]["code"] == "game_not_found"


def test_list_ordered_by_id_desc(client: TestClient):
    out = signup(client, "13800000091", "d9")
    g1 = publish(client, out["token"], visibility="public")
    g2 = publish(client, out["token"], visibility="public")
    assert ids_of(list_games(client)) == [g2["id"], g1["id"]]
