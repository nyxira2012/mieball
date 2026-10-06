"""意向簿与邀请（批3 片B）+ users same_game 服务端化（片C）—— docs/1.2 §4.11/4.12/4.13。

复用批1/批2 的时刻基准与 helper。留意向的排序靠 updated_at，假时钟要 advance 拉开先后。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import signup
from .test_games_actions import assert_blocked, join_ok, row_of
from .test_games_read import (
    auth,
    detail,
    mine,
    publish,
)


def save_intent(
    client: TestClient,
    token: str,
    slots: list[str] | None = None,
    frequency: int = 1,
    note: str | None = None,
):
    body = {
        "slots": slots if slots is not None else ["weekend_night"],
        "frequency": frequency,
        "note": note,
    }
    return client.post("/api/intents", headers=auth(token), json=body)


def delete_intent(client: TestClient, token: str):
    return client.post("/api/intents/delete", headers=auth(token))


def my_intent(client: TestClient, token: str) -> dict | None:
    r = client.get("/api/intents/mine", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def list_intents(client: TestClient, token: str | None = None) -> list[dict]:
    r = client.get("/api/intents", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def invite(client: TestClient, token: str, game_id: int, account_id: int):
    return client.post(
        f"/api/games/{game_id}/invite",
        headers=auth(token),
        json={"account_id": account_id},
    )


def account_ids_of(views: list[dict]) -> list[int]:
    return [v["account"]["id"] for v in views]


# ---- 留 / 改 / 删意向（4.13） ----


def test_save_validation_and_view_shape(client: TestClient):
    a = signup(client, "13800030001", "a")
    r = save_intent(client, a["token"], slots=[])
    assert r.status_code == 422 and r.json()["error"]["code"] == "intent_slots_empty"
    r = save_intent(client, a["token"], frequency=3)
    assert r.status_code == 422 and r.json()["error"]["code"] == "frequency_invalid"

    r = save_intent(client, a["token"], slots=["k_night"], frequency=2, note="都行")
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["account"]["id"] == a["account"]["id"]
    assert v["slots"] == ["k_night"] and v["frequency"] == 2 and v["note"] == "都行"
    assert v["updated_at"].endswith("+08:00")  # 出参 ISO +08:00
    assert v["invited"] is False and v["known"] is False


def test_upsert_single_row_and_delete_idempotent(client: TestClient):
    a = signup(client, "13800030011", "a")
    save_intent(client, a["token"], slots=["k1"])
    save_intent(client, a["token"], slots=["k2"], frequency=0)  # 一人一份：改 = 覆盖
    assert my_intent(client, a["token"])["slots"] == ["k2"]
    assert len(list_intents(client)) == 1

    assert delete_intent(client, a["token"]).json() == {"ok": True}
    assert my_intent(client, a["token"]) is None
    assert list_intents(client) == []
    assert delete_intent(client, a["token"]).json() == {
        "ok": True
    }  # 幂等：没意向也当没事


def test_guest_can_browse_list(client: TestClient):
    """意向谁都能翻（含游客，4.13 评审裁决）；游客视角没有已邀/认识语义。"""
    a = signup(client, "13800030021", "a")
    save_intent(client, a["token"])
    views = list_intents(client)  # 无 Bearer
    assert account_ids_of(views) == [a["account"]["id"]]
    assert views[0]["invited"] is False and views[0]["known"] is False


def test_ordering_invited_last_and_save_clears_marker(client: TestClient, fake):
    """未邀在前、已邀靠后（各自 updated_at 倒序）；被邀人改意向 → 标记清、重排回前面。"""
    a = signup(client, "13800030031", "a")
    b = signup(client, "13800030032", "b")
    c = signup(client, "13800030033", "c")
    org = signup(client, "13800030034", "o")
    g = publish(client, org["token"], visibility="public")

    save_intent(client, a["token"])
    fake.advance(minutes=5)
    save_intent(client, b["token"])
    fake.advance(minutes=5)
    save_intent(client, c["token"])
    assert account_ids_of(list_intents(client)) == [
        c["account"]["id"],
        b["account"]["id"],
        a["account"]["id"],
    ]

    assert invite(client, org["token"], g["id"], b["account"]["id"]).status_code == 200
    views = list_intents(client, org["token"])
    assert account_ids_of(views) == [
        c["account"]["id"],
        a["account"]["id"],
        b["account"]["id"],
    ]
    assert views[-1]["invited"] is True  # 已邀标"已邀"并靠后

    fake.advance(minutes=5)
    save_intent(client, b["token"])  # 改了想法 = 可以再来邀我
    views = list_intents(client, org["token"])
    assert account_ids_of(views) == [
        b["account"]["id"],
        c["account"]["id"],
        a["account"]["id"],
    ]
    assert views[0]["invited"] is False


def test_known_played_together(client: TestClient, fake):
    """known = 与 viewer 同在成局正式名单打过（GameBook.played_with 同源）。"""
    x = signup(client, "13800030041", "x")
    a = signup(client, "13800030042", "a")
    b = signup(client, "13800030043", "b")
    c = signup(client, "13800030044", "c")
    g = publish(client, x["token"], visibility="public", min_players=2)
    join_ok(client, a["token"], g["id"])
    join_ok(client, b["token"], g["id"])
    fake.advance(days=2, hours=6)  # 过截止成局 → A、B 互为"打过"
    assert detail(client, g["id"])["status"] == "locked"

    save_intent(client, b["token"])
    save_intent(client, c["token"])
    views = {v["account"]["id"]: v for v in list_intents(client, a["token"])}
    assert views[b["account"]["id"]]["known"] is True
    assert views[c["account"]["id"]]["known"] is False


# ---- 邀请（4.11/4.12） ----


def test_invite_shows_in_invitee_mine_idempotent_then_joins(client: TestClient):
    org = signup(client, "13800030051", "o")
    b = signup(client, "13800030052", "b")
    stranger = signup(client, "13800030053", "s")
    g = publish(client, org["token"], visibility="invite_only")

    assert invite(client, org["token"], g["id"], b["account"]["id"]).json() == {
        "ok": True
    }
    m = [x for x in mine(client, b["token"]) if x["id"] == g["id"]]
    assert len(m) == 1  # 局直接出现在对方"我的局"
    assert (
        m[0]["my"]["invited"] is True and m[0]["my"]["my_entry"] is None
    )  # 被邀不占坑
    d = detail(client, g["id"], org["token"])
    assert all(e["account"]["id"] != b["account"]["id"] for e in d["entries"])

    invite(client, org["token"], g["id"], b["account"]["id"])  # 重复邀：就当没事
    m = [x for x in mine(client, b["token"]) if x["id"] == g["id"]]
    assert len(m) == 1 and m[0]["my"]["invited"] is True

    out = join_ok(client, b["token"], g["id"])  # 对方点了就占坑（与 4.3 同）
    assert row_of(out, b["account"]["id"])["standing"] == "formal"

    r = invite(client, stranger["token"], g["id"], b["account"]["id"])
    assert r.status_code == 403 and r.json()["error"]["code"] == "not_organizer"


def test_invite_window_and_intent_marker_linkage(client: TestClient, fake):
    """终态/待处置不发邀约；已邀标记只给有意向的 invitee 置位（两簿唯一来往）。"""
    org = signup(client, "13800030061", "o")
    b = signup(client, "13800030062", "b")  # 有意向
    c = signup(client, "13800030063", "c")  # 没意向
    g = publish(client, org["token"], visibility="public", min_players=3)

    save_intent(client, b["token"])
    invite(client, org["token"], g["id"], b["account"]["id"])
    views = {v["account"]["id"]: v for v in list_intents(client, org["token"])}
    assert views[b["account"]["id"]]["invited"] is True  # invite 置位

    invite(client, org["token"], g["id"], c["account"]["id"])  # 没意向也照邀
    save_intent(client, c["token"])
    views = {v["account"]["id"]: v for v in list_intents(client, org["token"])}
    assert views[c["account"]["id"]]["invited"] is False  # 只有 invites 行，无标记可置

    save_intent(client, b["token"])  # 被邀人改意向 → 标记清（4.13）
    views = {v["account"]["id"]: v for v in list_intents(client, org["token"])}
    assert views[b["account"]["id"]]["invited"] is False

    join_ok(client, b["token"], g["id"])
    fake.advance(days=2, hours=6)  # 1 < 3 判死
    assert detail(client, g["id"])["status"] == "terminated"
    assert_blocked(
        invite(client, org["token"], g["id"], c["account"]["id"]), "game_not_open"
    )

    r = client.post(f"/api/games/{g['id']}/restore", headers=auth(org["token"]))
    assert r.json()["status"] == "pending"
    assert_blocked(
        invite(client, org["token"], g["id"], c["account"]["id"]), "game_not_open"
    )


# ---- users same_game 服务端化（1.1 尾号规矩的 1.2 收口） ----


def test_users_phone_tail_only_for_same_locked_game(client: TestClient, fake):
    """尾号 4 位仅"同成局正式名单"可见：候补不算、终止局不算、老自报参数废弃。"""
    x = signup(client, "13800030071", "x")
    a = signup(client, "13800030072", "a")
    b = signup(client, "13800030073", "b")
    stranger = signup(client, "13800030074", "s")
    tail = "0073"

    g1 = publish(client, x["token"], visibility="public", min_players=2)
    join_ok(client, a["token"], g1["id"])
    join_ok(client, b["token"], g1["id"])
    fake.advance(days=2, hours=6)  # g1 成局：A、B 同局打过
    assert detail(client, g1["id"])["status"] == "locked"

    acc = client.get(
        f"/api/users/{b['account']['id']}", headers=auth(a["token"])
    ).json()["account"]
    assert acc["phone_tail"] == tail and "phone" not in acc  # 同局：放行尾号

    g2 = publish(
        client,
        b["token"],
        visibility="public",
        min_players=1,
        max_players=1,
        start_at="2026-10-07T19:00:00+08:00",
        end_at="2026-10-07T21:00:00+08:00",
        deadline_at="2026-10-07T17:00:00+08:00",
    )
    join_ok(client, stranger["token"], g2["id"])  # 满员 → 候补
    fake.advance(days=1)  # → 10-07 18:00：g2 截止已过、成局锁定
    assert detail(client, g2["id"])["status"] == "locked"

    acc = client.get(
        f"/api/users/{b['account']['id']}", headers=auth(stranger["token"])
    ).json()["account"]
    assert "phone_tail" not in acc  # 只候补过：不算打过
    acc = client.get(
        f"/api/users/{b['account']['id']}?same_game=true",
        headers=auth(stranger["token"]),
    ).json()["account"]
    assert "phone_tail" not in acc  # 老自报参数被忽略

    acc = client.get(f"/api/users/{b['account']['id']}").json()["account"]
    assert "phone_tail" not in acc  # 匿名永不给尾号

    acc = client.get(
        f"/api/users/{a['account']['id']}", headers=auth(a["token"])
    ).json()["account"]
    assert acc["phone"] == "13800030072"  # 本人：全号（1.1 原样）
