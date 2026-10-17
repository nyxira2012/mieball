"""现场域地基（2.3 批1）—— docs/2.3 附录 B：开账展开（正式+访客行）、view 分权
（考勤时刻 org/本人见）、两级号机制、EloRating 首见 1200（1.4 §3 调参）。

批1 无路由（批2 挂），全部直调 LiveBook（沿 seed_entry 的 session_factory 取法）；
时刻基准与发局 helper 复用 test_games_read（FakeClock 基点 10-04 12:00）。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core import clock
from app.core.errors import ApiError
from app.db.models import EloRating, LiveCourt, LivePlayer, LiveState
from app.services import live_rotation
from app.services.live import RATING_INIT, LiveBook

from .conftest import signup
from .test_games_actions import join_ok
from .test_games_read import detail, publish, seed_entry

ARRIVE_ISO = "2026-10-06T19:02:00+08:00"


def with_book(client: TestClient, fn) -> object:
    db = client.app.state.session_factory()
    try:
        return fn(LiveBook(db))
    finally:
        db.close()


def start_live(client: TestClient, game_id: int, organizer_id: int) -> dict:
    return with_book(
        client, lambda book: book.start(game_id=game_id, organizer_id=organizer_id)
    )


def view_live(client: TestClient, game_id: int, viewer_id: int | None) -> dict:
    return with_book(
        client, lambda book: book.view(game_id=game_id, viewer_id=viewer_id)
    )


def lock_past_deadline(client: TestClient, fake, game_id: int) -> None:
    """拨过截止并触发一次局簿读：懒判定把 open 局落成 locked（2.5 开账前提）。
    标准局时刻（test_games_read）：→ 10-06 18:00，过 17:00 截止、开打前 1h。"""
    fake.advance(days=2, hours=6)
    detail(client, game_id)


def started_by_of(client: TestClient, game_id: int) -> int | None:
    def probe(book: LiveBook):
        state = book._state_or_none(game_id)
        return state.started_by if state else None

    return with_book(client, probe)


def seed_attendance(client: TestClient, game_id: int, account_id: int) -> None:
    """直接落一条考勤时刻（check 端点批3 才有）——分权断言要真值。"""
    db = client.app.state.session_factory()
    try:
        row = db.execute(
            select(LivePlayer).where(
                LivePlayer.game_id == game_id, LivePlayer.account_id == account_id
            )
        ).scalar_one()
        row.arrive_at = clock.wall(datetime(2026, 10, 6, 19, 2, 0, tzinfo=clock.CN_TZ))
        db.commit()
    finally:
        db.close()


def row_of(view: dict, account_id: int) -> dict:
    return next(r for r in view["players"] if r["account_id"] == account_id)


# ---- 开账：名册展开 ----


def test_start_expands_roster_formal_and_guests(client: TestClient, fake):
    org = signup(client, "13800020001", "o")
    b = signup(client, "13800020002", "b", nickname="小李", nickname_set=True)
    c = signup(client, "13800020003", "c")
    g = publish(client, org["token"], visibility="public")
    join_ok(client, b["token"], g["id"], bring=2)
    join_ok(client, c["token"], g["id"])
    lock_past_deadline(client, fake, g["id"])  # 2.5：成局才可开账

    out = start_live(client, g["id"], org["account"]["id"])

    rows = out["players"]
    assert len(rows) == 5  # org + b(1) + 2 访客 + c
    assert all(r["check"] == "absent" for r in rows)  # 全员先记未到（2.2 §4.1）
    assert out["queue"] == []  # 候场队空：报到驱动
    assert out["courts"] == [] and out["matches"] == []
    guests = [r for r in rows if r["guest"]]
    assert [r["name"] for r in guests] == ["小李的球友·1", "小李的球友·2"]
    assert all(
        r["account_id"] is None and r["guarantor_account_id"] == b["account"]["id"]
        for r in guests
    )
    formals = [r for r in rows if not r["guest"]]
    assert {r["account_id"] for r in formals} == {
        org["account"]["id"],
        b["account"]["id"],
        c["account"]["id"],
    }
    # rules 快照从 game 默认（scoring 复用局列；pairing 吃 game.rotation，旧值回落 partner；
    # 谁下默认 n2、streak_max 起笔=2）
    assert out["rules"] == {
        "scoring": 21,
        "doubles": True,
        "down": "n2",
        "pairing": "partner",
        "streak_max": 2,
    }
    assert out["total_seq"] == 1 and out["round"] == 0


def test_start_inherits_game_rotation_and_set_rules_syncs_back(
    client: TestClient, fake
):
    """组局选的配对规则（game.rotation）开账落入 rules.pairing；现场改 pairing 同步回写局簿。"""
    org = signup(client, "13800020009", "o")
    b = signup(client, "13800020010", "b")
    g = publish(client, org["token"], visibility="public", rotation="balance")
    join_ok(client, b["token"], g["id"])
    lock_past_deadline(client, fake, g["id"])

    out = start_live(client, g["id"], org["account"]["id"])
    assert out["rules"]["pairing"] == "balance"

    updated = with_book(
        client,
        lambda book: book.rules(
            game_id=g["id"],
            actor_id=org["account"]["id"],
            base_total_seq=out["total_seq"],
            pairing="even",
        ),
    )
    assert updated["rules"]["pairing"] == "even"
    assert detail(client, g["id"])["rotation"] == "even"


def test_start_idempotent_keeps_single_roster(client: TestClient, fake):
    org = signup(client, "13800020011", "o")
    b = signup(client, "13800020012", "b")
    g = publish(client, org["token"], visibility="public")
    join_ok(client, b["token"], g["id"], bring=1)
    lock_past_deadline(client, fake, g["id"])  # 2.5：成局才可开账

    first = start_live(client, g["id"], org["account"]["id"])
    second = start_live(client, g["id"], org["account"]["id"])  # 再点开账当没事

    assert second == first
    assert len(second["players"]) == 3  # 名册不重展、访客不重造

    def state_count(book: LiveBook) -> int:
        return len(
            book.db.execute(
                select(LiveState.id).where(LiveState.game_id == g["id"])
            ).all()
        )

    assert with_book(client, state_count) == 1


# ---- 开账触发权（2.5 §4/§8）：成局才可开、组织者随时、正式成员两小时窗 ----


def test_start_member_within_window_opens(client: TestClient, fake):
    """成员窗内可开账：正式球友开打前 1h 点开始 → 现场亮起、started_by=成员。"""
    org = signup(client, "13800020021", "o")
    b = signup(client, "13800020022", "b")
    g = publish(client, org["token"], visibility="public")
    join_ok(client, b["token"], g["id"])
    lock_past_deadline(client, fake, g["id"])  # → 开打前 1h，成局

    out = start_live(client, g["id"], b["account"]["id"])

    assert {r["account_id"] for r in out["players"]} == {
        org["account"]["id"],
        b["account"]["id"],
    }
    assert started_by_of(client, g["id"]) == b["account"]["id"]


def test_start_member_outside_window_too_early(client: TestClient, fake):
    org = signup(client, "13800020023", "o")
    b = signup(client, "13800020024", "b")
    # 截止提前到 14:00，16:00（开打前 3h）已成局——拒的是窗不是成局
    g = publish(
        client,
        org["token"],
        visibility="public",
        deadline_at="2026-10-06T14:00:00+08:00",
    )
    join_ok(client, b["token"], g["id"])
    fake.advance(days=2, hours=4)  # → 10-06 16:00 = 开打前 3h
    detail(client, g["id"])  # 懒判定成局

    with pytest.raises(ApiError) as e:
        start_live(client, g["id"], b["account"]["id"])
    assert e.value.status_code == 403 and e.value.code == "live_too_early"


def test_start_waitlist_entry_required(client: TestClient, fake):
    """候补不触发开账（2.5 §4.8：app 内一律不服务）。"""
    org = signup(client, "13800020025", "o")
    b = signup(client, "13800020026", "b")
    g = publish(client, org["token"], visibility="public", min_players=1)
    seed_entry(client, g["id"], b["account"]["id"], standing="waitlist", wait_seq=1)
    lock_past_deadline(client, fake, g["id"])  # org 自成一局（min=1）

    with pytest.raises(ApiError) as e:
        start_live(client, g["id"], b["account"]["id"])
    assert e.value.status_code == 403 and e.value.code == "live_entry_required"


def test_start_open_game_requires_forced(client: TestClient):
    """报名中的局谁都不能开账（2.5 §4.4 收紧：组织者旧路就此关闭）。"""
    org = signup(client, "13800020027", "o")
    g = publish(client, org["token"], visibility="public")
    with pytest.raises(ApiError) as e:
        start_live(client, g["id"], org["account"]["id"])
    assert e.value.status_code == 403 and e.value.code == "live_requires_forced"


def _org_headers(client: TestClient, token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_start_manual_lock_before_deadline_opens(client: TestClient, fake):
    """手动锁必打即刻成局（2.5 §4.4）：未到截止、state 仍 open，组织者开账放行。"""
    org = signup(client, "13800020081", "o")
    b = signup(client, "13800020082", "b")
    g = publish(client, org["token"], visibility="public")
    join_ok(client, b["token"], g["id"])
    r = client.post(
        f"/api/games/{g['id']}/lock", headers=_org_headers(client, org["token"])
    )
    assert r.status_code == 200, r.text

    out = start_live(client, g["id"], org["account"]["id"])

    assert out["players"]
    assert started_by_of(client, g["id"]) == org["account"]["id"]


def test_start_courts_booked_opens_before_deadline(client: TestClient, fake):
    """订场登记即刻成局（2.5 §4.4）：courts 非空即必打，不等截止懒判定。"""
    org = signup(client, "13800020083", "o")
    b = signup(client, "13800020084", "b")
    g = publish(client, org["token"], visibility="public")
    join_ok(client, b["token"], g["id"])
    r = client.post(
        f"/api/games/{g['id']}/booking",
        headers=_org_headers(client, org["token"]),
        json={"courts": ["3号"], "fee_total": 100},
    )
    assert r.status_code == 200, r.text

    out = start_live(client, g["id"], org["account"]["id"])

    assert out["players"]
    assert started_by_of(client, g["id"]) == org["account"]["id"]


def test_start_cancelled_game_rejected_even_locked(client: TestClient, fake):
    """撤局后即便锁过必打也不开账（死局先拒，2.5 §8）。"""
    org = signup(client, "13800020085", "o")
    b = signup(client, "13800020086", "b")
    g = publish(client, org["token"], visibility="public")
    join_ok(client, b["token"], g["id"])
    headers = _org_headers(client, org["token"])
    assert client.post(f"/api/games/{g['id']}/lock", headers=headers).status_code == 200
    assert (
        client.post(f"/api/games/{g['id']}/cancel", headers=headers).status_code == 200
    )

    with pytest.raises(ApiError) as e:
        start_live(client, g["id"], org["account"]["id"])
    assert e.value.status_code == 403 and e.value.code == "live_requires_forced"


def test_start_after_end_at_rejected_even_locked(client: TestClient, fake):
    """锁定局过了散场时刻仍没人开账 → 再开不出新账（done 也是死局，2.5 修B）。"""
    org = signup(client, "13800020087", "o")
    b = signup(client, "13800020088", "b")
    g = publish(client, org["token"], visibility="public")
    join_ok(client, b["token"], g["id"])
    headers = _org_headers(client, org["token"])
    assert client.post(f"/api/games/{g['id']}/lock", headers=headers).status_code == 200
    fake.advance(days=2, hours=10)  # → 10-06 22:00，过 21:00 散场、从未开账
    detail(client, g["id"])  # 懒判定翻 locked

    with pytest.raises(ApiError) as e:
        start_live(client, g["id"], org["account"]["id"])
    assert e.value.status_code == 403 and e.value.code == "live_requires_forced"


def test_start_member_window_boundary_inclusive(client: TestClient, fake):
    """两小时窗含整点（2.5 §5）：恰 start_at-2h 整点，成员开账放行。"""
    org = signup(client, "13800020089", "o")
    b = signup(client, "13800020090", "b")
    g = publish(client, org["token"], visibility="public")
    join_ok(client, b["token"], g["id"])
    headers = _org_headers(client, org["token"])
    assert client.post(f"/api/games/{g['id']}/lock", headers=headers).status_code == 200
    fake.advance(days=2, hours=5)  # → 10-06 17:00 整点（必开即刻成局，只验窗）

    start_live(client, g["id"], b["account"]["id"])

    assert started_by_of(client, g["id"]) == b["account"]["id"]


def test_start_member_window_one_second_early_rejected(client: TestClient, fake):
    org = signup(client, "13800020091", "o")
    b = signup(client, "13800020092", "b")
    g = publish(client, org["token"], visibility="public")
    join_ok(client, b["token"], g["id"])
    headers = _org_headers(client, org["token"])
    assert client.post(f"/api/games/{g['id']}/lock", headers=headers).status_code == 200
    fake.advance(days=2, hours=4, seconds=3599)  # → 16:59:59，差一秒

    with pytest.raises(ApiError) as e:
        start_live(client, g["id"], b["account"]["id"])
    assert e.value.status_code == 403 and e.value.code == "live_too_early"


def test_start_organizer_anytime_after_locked(client: TestClient, fake):
    """组织者成局后随时开账，不受两小时窗限（2.5 场景 4.4）。"""
    org = signup(client, "13800020028", "o")
    b = signup(client, "13800020029", "b")
    g = publish(
        client,
        org["token"],
        visibility="public",
        deadline_at="2026-10-06T14:00:00+08:00",
    )
    join_ok(client, b["token"], g["id"])
    fake.advance(days=2, hours=4)  # → 开打前 3h（已过截止成局）
    detail(client, g["id"])

    out = start_live(client, g["id"], org["account"]["id"])

    assert out["total_seq"] == 1 and out["players"]
    assert started_by_of(client, g["id"]) == org["account"]["id"]


def test_start_idempotent_keeps_started_by(client: TestClient, fake):
    """已开账重复调（换人也一样）→ 幂等回视图，started_by 不改写；
    身份两旗随 viewer 各算各的（2026-10-08 身份块起视图含 viewer 旗）。"""
    org = signup(client, "13800020101", "o")
    b = signup(client, "13800020102", "b")
    g = publish(client, org["token"], visibility="public")
    join_ok(client, b["token"], g["id"])
    lock_past_deadline(client, fake, g["id"])

    first = start_live(client, g["id"], b["account"]["id"])
    second = start_live(client, g["id"], org["account"]["id"])

    def strip_flags(v: dict) -> dict:
        return {
            k: w for k, w in v.items() if k not in ("is_organizer", "is_full_power")
        }

    assert strip_flags(second) == strip_flags(first)  # 账面全同（幂等）
    assert (
        first["is_organizer"] is False and second["is_organizer"] is True
    )  # 旗随 viewer
    assert started_by_of(client, g["id"]) == b["account"]["id"]


def test_game_view_live_opened_flag(client: TestClient, fake):
    """账开标志（2.5 B1「账开没开」送到卡片）：开账前 False、开账后 True。"""
    org = signup(client, "13800020103", "o")
    b = signup(client, "13800020104", "b")
    g = publish(client, org["token"], visibility="public")
    join_ok(client, b["token"], g["id"])
    assert detail(client, g["id"], org["token"])["live_opened"] is False
    lock_past_deadline(client, fake, g["id"])

    start_live(client, g["id"], org["account"]["id"])

    assert detail(client, g["id"], org["token"])["live_opened"] is True


def test_view_before_start_404(client: TestClient):
    org = signup(client, "13800020031", "o")
    g = publish(client, org["token"], visibility="public")
    with pytest.raises(ApiError) as e:
        view_live(client, g["id"], org["account"]["id"])
    assert e.value.status_code == 404 and e.value.code == "live_not_found"


# ---- view 分权：考勤时刻 org/本人见、他人 null（2.3 裁决 Q2） ----


def test_view_attendance_visibility(client: TestClient, fake):
    org = signup(client, "13800020041", "o")
    b = signup(client, "13800020042", "b")
    c = signup(client, "13800020043", "c")
    g = publish(client, org["token"], visibility="public")
    join_ok(client, b["token"], g["id"])
    join_ok(client, c["token"], g["id"])
    lock_past_deadline(client, fake, g["id"])  # 2.5：成局才可开账
    start_live(client, g["id"], org["account"]["id"])
    seed_attendance(client, g["id"], c["account"]["id"])  # c 19:02 到场

    as_org = view_live(client, g["id"], org["account"]["id"])
    assert row_of(as_org, c["account"]["id"])["arrive_at"] == ARRIVE_ISO
    as_me = view_live(client, g["id"], c["account"]["id"])  # 本人也见自己的
    assert row_of(as_me, c["account"]["id"])["arrive_at"] == ARRIVE_ISO
    as_other = view_live(client, g["id"], b["account"]["id"])  # 其他球友
    assert row_of(as_other, c["account"]["id"])["arrive_at"] is None
    as_anon = view_live(client, g["id"], None)  # 随便扫到的人
    assert row_of(as_anon, c["account"]["id"])["arrive_at"] is None


# ---- view 身份块：两旗+组织者账号随视图直读（2026-10-08 修订，翻批4a） ----


def test_view_identity_flags(client: TestClient, fake):
    org = signup(client, "13800020061", "o")
    b = signup(client, "13800020062", "b")
    c = signup(client, "13800020063", "c")
    g = publish(client, org["token"], visibility="public")
    join_ok(client, b["token"], g["id"])
    join_ok(client, c["token"], g["id"])
    lock_past_deadline(client, fake, g["id"])  # 2.5：成局才可开账
    start_live(client, g["id"], org["account"]["id"])
    db = client.app.state.session_factory()  # 直落一任管理员（授予链路归 2.5 册测）
    try:
        state = db.get(LiveState, g["id"])
        state.admins = [b["account"]["id"]]
        db.commit()
    finally:
        db.close()

    as_org = view_live(client, g["id"], org["account"]["id"])
    assert as_org["is_organizer"] is True and as_org["is_full_power"] is True
    assert as_org["organizer_account_id"] == org["account"]["id"]
    as_admin = view_live(client, g["id"], b["account"]["id"])  # 管理员：非组织者但全权
    assert as_admin["is_organizer"] is False and as_admin["is_full_power"] is True
    as_player = view_live(client, g["id"], c["account"]["id"])  # 普通球友两旗皆 false
    assert as_player["is_organizer"] is False and as_player["is_full_power"] is False
    assert as_player["organizer_account_id"] == org["account"]["id"]
    as_anon = view_live(client, g["id"], None)  # 游客恒 false（组织者账号照给）
    assert as_anon["is_organizer"] is False and as_anon["is_full_power"] is False


# ---- EloRating 首见 1200（访客不入行） ----


def test_elo_first_seen_init_1200(client: TestClient, fake):
    org = signup(client, "13800020051", "o")
    b = signup(client, "13800020052", "b")
    g = publish(client, org["token"], visibility="public")
    join_ok(client, b["token"], g["id"], bring=1)  # 访客不该有积分行
    lock_past_deadline(client, fake, g["id"])  # 2.5：成局才可开账
    start_live(client, g["id"], org["account"]["id"])

    db = client.app.state.session_factory()
    try:
        rows = {r.account_id: r for r in db.execute(select(EloRating)).scalars().all()}
    finally:
        db.close()
    assert set(rows) == {org["account"]["id"], b["account"]["id"]}
    assert all(
        r.rating == RATING_INIT and r.play == 0 and r.win == 0 for r in rows.values()
    )


# ---- 两级号机制（附录 B1）：写入口校验 + 号前进 ----


def test_two_level_seq_mechanism(client: TestClient, fake):
    org = signup(client, "13800020061", "o")
    g = publish(client, org["token"], visibility="public", min_players=1)
    lock_past_deadline(client, fake, g["id"])  # 2.5：成局才可开账
    start_live(client, g["id"], org["account"]["id"])

    def probe(book: LiveBook) -> None:
        state = book._state_or_none(g["id"])
        assert state is not None and state.total_seq == 1
        book._check_total(state, 1)  # 号对得上：放行
        book._bump_total(state)
        assert state.total_seq == 2
        with pytest.raises(ApiError) as stale:
            book._check_total(state, 1)  # 旧号重放：退回（弱网重发/连击防线）
        assert stale.value.status_code == 409
        assert stale.value.code == "live_stale_total"

        # 未落库片行只试号机制（列 default 在 INSERT 才生效，这里显式给起笔 0）
        court = LiveCourt(game_id=g["id"], court_no=1, court_seq=0)
        book._check_court(court, 0)
        book._bump_court(court)
        with pytest.raises(ApiError) as court_stale:
            book._check_court(court, 0)  # 同片并发：只拦该片
        assert court_stale.value.code == "live_stale_court"

    with_book(client, probe)


# ---- 回流纯逻辑（live_rotation，四件套按 2.4 真值；纯函数不带 app 夹具） ----
# 取队本体（歇/连战/考勤）与补片矩阵在 test_live_rotation 册；这里只锁四件套的去留格局


def _p(
    pid: int,
    side: str | None = None,
    *,
    mark: int | None = None,
    rating: int | None = None,
) -> dict:
    """喂行契约最小行（2.8）：check=ok 可发；mark=上场章（小=先上=先下，None=最新）。"""
    row = {
        "id": pid,
        "court_no": 1 if side else None,
        "court_side": side,
        "check": "ok",
        "court_mark": mark,
    }
    if rating is not None:
        row["rating"] = rating
    return row


def test_requeue_loser_mode_winners_stay():
    players = [_p(1, "a"), _p(2, "a"), _p(3, "b"), _p(4, "b"), _p(5), _p(6)]
    queue = [5, 6]
    live_rotation.requeue_after_confirm(
        players, 1, "a", {"down": "loser", "pairing": "queue", "doubles": True}, queue
    )
    # 败方 b 两人回队尾、胜方 a 留场；候场首两人补成新挑战队（不重配）
    assert players[2]["court_side"] is None and players[3]["court_side"] is None
    assert queue == [3, 4]  # 下场的两人接在队尾
    assert players[4]["court_side"] == "b" and players[5]["court_side"] == "b"
    assert players[0]["court_side"] == "a" and players[1]["court_side"] == "a"


def test_requeue_all_mode_queue_pairing():
    players = [
        _p(1, "a", mark=2),
        _p(2, "b", mark=1),
        _p(3, "a", mark=3),
        _p(4, "b"),
        _p(5),
        _p(6),
        _p(7),
        _p(8),
    ]
    queue = [5, 6, 7, 8]
    live_rotation.requeue_after_confirm(
        players, 1, "a", {"down": "all", "pairing": "queue", "doubles": True}, queue
    )
    # 全场按资历序下（上场章小的先下、没章的最后）、候场首补全新一队：第 1、2 位一队
    assert queue == [2, 1, 3, 4]
    assert all(p["court_side"] is None for p in players[:4])
    assert [p["id"] for p in players if p["court_side"] == "a"] == [5, 6]
    assert [p["id"] for p in players if p["court_side"] == "b"] == [7, 8]


def test_requeue_all_mode_balance_snakes_by_rating():
    players = [
        _p(1, "a"),
        _p(2, "b"),
        _p(3, "a"),
        _p(4, "b"),
        _p(5, rating=1600),
        _p(6, rating=1500),
        _p(7, rating=1400),
        _p(8, rating=1300),
    ]
    queue = [5, 6, 7, 8]
    live_rotation.requeue_after_confirm(
        players, 1, "a", {"down": "all", "pairing": "balance", "doubles": True}, queue
    )
    # 均衡配对：最强+最弱 vs 二三，不让两个高手挤同边（2.4 §4.5）
    assert [p["id"] for p in players if p["court_side"] == "a"] == [5, 8]
    assert [p["id"] for p in players if p["court_side"] == "b"] == [6, 7]


def test_requeue_n2_replaces_in_place():
    players = [
        _p(1, "a", mark=2),
        _p(2, "a"),
        _p(3, "b", mark=1),
        _p(4, "b"),
        _p(5),
        _p(6),
    ]
    queue = [5, 6]
    live_rotation.requeue_after_confirm(
        players, 1, "b", {"down": "n2", "pairing": "queue", "doubles": True}, queue
    )
    # 上场章最小的 2 人下（p3、p1）、候场首原位顶坑：留下的保住半边
    assert queue == [3, 1]
    assert players[0]["court_side"] is None and players[2]["court_side"] is None
    assert players[1]["court_side"] == "a" and players[3]["court_side"] == "b"
    assert players[4]["court_side"] == "b" and players[5]["court_side"] == "a"


def test_roster_seqs_arrival_then_id_tiebreak():
    """到场先后键（排位第④档）：签到落账时刻升序、同刻行 id 决胜；未到过的
    行共享队尾名次。"""
    from types import SimpleNamespace

    from app.services.live import _roster_seqs

    t = clock.wall(datetime(2026, 10, 6, 19, 0, tzinfo=clock.CN_TZ))
    rows = [
        SimpleNamespace(id=3, arrive_at=t),
        SimpleNamespace(id=1, arrive_at=t),  # 同刻：行 id 决胜
        SimpleNamespace(id=2, arrive_at=t + timedelta(minutes=1)),
        SimpleNamespace(id=4, arrive_at=None),  # 未到：不参与排位，共享 0 保序
    ]
    assert _roster_seqs(rows) == {1: 1, 3: 2, 2: 3, 4: 0}
