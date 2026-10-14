"""打球记录三笔规矩与身份定值（2.6 批1）—— docs/2.6 §4.4/§4.3-3 的后端半边：
上过场 ∨ 账单里有份 ∨ 组织者，∩ 已散场（锚 ended_at 不锚派生 done）；空降纯上场
进记录、缺席照摊进列表场数不加、免费局组织者有而板凳无、纯候补无、担保人访客
份额记账同验、账单晚到补填即长、终止/取消/到点未散查无、散场倒序排序、
GET /api/games/playlog 形状与 401、live view is_my_game 同尺定值。

时刻基准 FakeClock 10-04 12:00（conftest）；标准局 10-06 19:00 开打（test_games_read）。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import auth, signup
from .test_bills_generate import book_fee, end_live, set_fee
from .test_games_actions import join_ok
from .test_games_read import (
    DEADLINE2,
    END2,
    START2,
    detail,
    publish,
)
from .test_live_end import seed_rows
from .test_live_score import (
    confirm,
    deal_one,
    live_call,
    live_get,
    lock_game_direct,
    open_live,
)


def settle(client: TestClient, token: str, gid: int, view: dict, **over) -> dict:
    """上传结算一笔并断言 200；no_redeal 定格回流（不自动续场）——本册用例
    结算后就要散场，不留在打残局。同分同位会被当幂等重放不重落，第二场换分。"""
    r = confirm(client, token, gid, view, no_redeal=True, **over)
    assert r.status_code == 200, r.text
    return r.json()


def playlog_of(client: TestClient, token: str) -> dict:
    r = client.get("/api/games/playlog", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def logged_ids(out: dict) -> list[int]:
    """记录列表的局 id 序（保持响应序——排序用例靠它）。"""
    return [g["id"] for g in out["games"]]


def _phone(seed: int, i: int) -> str:
    return f"139{seed:02d}{i:04d}00"


def stage(
    client: TestClient,
    *,
    seed: int,
    players: int = 6,
    absent: tuple[int, ...] = (),
    bench: tuple[int, ...] = (),
    fee: int | None = None,
    org: dict | None = None,
) -> dict:
    """发局→报名→锁→开账→全员到场的环境（仿 test_live_score.open_live，令牌全量
    留在返回值——三笔名单要逐账号验证；org 传入则复用该账号做组织者）。
    absent/bench 按名册行下标摘出候场队（行序=报名序：组织者第 0 行）；
    fee 非 None 时订场登记总价（0=免费局，None=总价未定）。"""
    if org is None:
        org = signup(client, _phone(seed, 0), "o")
    mates = [signup(client, _phone(seed, i + 1), f"m{i}") for i in range(players - 1)]
    g = publish(client, org["token"], visibility="public", max_players=players)
    for u in mates:
        join_ok(client, u["token"], g["id"])
    lock_game_direct(client, g["id"])
    r = live_call(client, org["token"], g["id"], "start", {})
    assert r.status_code == 200, r.text
    patch: dict[int, dict] = {}
    for i in range(players):
        if i in absent:
            patch[i] = {"check": "absent", "queue_pos": None}
        elif i in bench:
            patch[i] = {"check": "ok", "queue_pos": None}  # 签到到场、一场没上
        else:
            patch[i] = {"check": "ok", "queue_pos": i}
    seed_rows(client, g["id"], patch)
    if fee is not None:
        book_fee(client, org["token"], g["id"], fee)
    return {
        "game_id": g["id"],
        "org": org,
        "users": [org, *mates],
        "view": live_get(client, g["id"], org["token"]),
    }


# ---- 第一笔·上过场（空降无报名行也算；老局追溯同此机制——现算零迁移） ----


def test_dropin_never_enrolled_in_list_after_end(client: TestClient):
    env = stage(client, seed=1)  # 不订场：散场无账，纯第一笔
    gid = env["game_id"]
    stranger = signup(client, _phone(1, 9), "s")
    r = live_call(
        client,
        stranger["token"],
        gid,
        "dropin",
        {"base_total_seq": env["view"]["total_seq"]},
    )
    assert r.status_code == 200, r.text
    # 发牌只吃候场队首：先让队首四人打一场回流，空降者轮到队首再上一场
    settle(client, env["org"]["token"], gid, deal_one(client, env))
    v = settle(
        client, env["org"]["token"], gid, deal_one(client, env), score_b=7
    )  # 换分：同分同位会被当幂等重放不重落
    end_live(client, env, v)
    out = playlog_of(client, stranger["token"])
    assert logged_ids(out) == [gid]  # 从未报名（无 Entry 行）纯靠上场进记录
    assert out["matches_count"] == 1
    assert logged_ids(playlog_of(client, env["org"]["token"])) == [gid]  # 组织者第三笔


# ---- 第二笔·账单有份（缺席照摊；场数解耦；账单晚到跟着长） ----


def test_absent_payer_listed_but_matches_count_flat(client: TestClient):
    env = stage(client, seed=2, fee=420, absent=(5,))
    gid = env["game_id"]
    absent_user = env["users"][5]
    v = settle(client, env["org"]["token"], gid, deal_one(client, env))
    end_live(client, env, v)
    out = playlog_of(client, absent_user["token"])
    assert logged_ids(out) == [gid]  # 报名没来、账单里有份
    assert out["matches_count"] == 0  # 场数=上过场的对局数，与列表行数解耦
    assert out["games"][0]["bill"]["my_share"] is not None
    view = live_get(client, gid, absent_user["token"])
    assert view["ended"] is True and view["is_my_game"] is True  # 提示行同尺


def test_late_bill_grows_into_list(client: TestClient):
    env = stage(client, seed=6, absent=(5,))  # 总价未定：散场不出账
    gid = env["game_id"]
    absent_user = env["users"][5]
    v = settle(client, env["org"]["token"], gid, deal_one(client, env))
    end_live(client, env, v)
    assert logged_ids(playlog_of(client, absent_user["token"])) == []
    r = set_fee(client, env["org"]["token"], gid, 420)
    assert r.status_code == 200, r.text
    out = playlog_of(client, absent_user["token"])
    assert logged_ids(out) == [gid]  # 补填出账那一刻自动长进记录（现算天然成立）
    assert out["matches_count"] == 0


# ---- 第三笔·组织者（兜免费局）；免费局的板凳不算 ----


def test_free_game_organizer_in_bench_out(client: TestClient):
    env = stage(client, seed=3, fee=0, bench=(0,))  # 0 元免费局：无账可出
    gid = env["game_id"]
    v = settle(client, env["org"]["token"], gid, deal_one(client, env))
    end_live(client, env, v)
    assert logged_ids(playlog_of(client, env["org"]["token"])) == [gid]  # 没上场也算
    out = playlog_of(client, env["users"][5]["token"])  # 签到没上场的板凳
    assert logged_ids(out) == [] and out["matches_count"] == 0


# ---- 三不进：纯候补 / 终止与取消 / 到点未散 ----


def test_pure_waitlist_listed_nowhere(client: TestClient):
    org = signup(client, _phone(4, 0), "o")
    m1 = signup(client, _phone(4, 1), "m1")
    waiter = signup(client, _phone(4, 2), "w")
    g = publish(client, org["token"], visibility="public", max_players=2)
    join_ok(client, m1["token"], g["id"])
    join_ok(client, waiter["token"], g["id"])  # 满员落候补
    lock_game_direct(client, g["id"])
    r = live_call(client, org["token"], g["id"], "start", {})
    assert r.status_code == 200, r.text
    book_fee(client, org["token"], g["id"], 300)
    end_live(client, {"game_id": g["id"], "org": org, "view": r.json()})
    out = playlog_of(client, waiter["token"])  # 没转正没上场没摊钱
    assert logged_ids(out) == [] and out["matches_count"] == 0
    # 同局对照：m1 没上场但账单有份 → 第二笔进名单
    assert logged_ids(playlog_of(client, m1["token"])) == [g["id"]]


def test_terminated_game_listed_nowhere(client, fake):
    org = signup(client, _phone(8, 0), "o")
    publish(
        client,
        org["token"],
        visibility="public",
        min_players=5,
        max_players=10,
        start_at=START2,
        end_at=END2,
        deadline_at=DEADLINE2,
    )
    fake.advance(days=3, hours=6)  # 过截止：人数不足黄掉（懒判定落 terminated）
    out = playlog_of(client, org["token"])  # playlog 入口先跑懒判定
    assert logged_ids(out) == [] and out["matches_count"] == 0


def test_cancelled_game_listed_nowhere(client: TestClient):
    org = signup(client, _phone(8, 5), "o")
    mate = signup(client, _phone(8, 6), "m")
    g = publish(client, org["token"], visibility="public")
    join_ok(client, mate["token"], g["id"])
    r = client.post(f"/api/games/{g['id']}/cancel", headers=auth(org["token"]))
    assert r.status_code == 200, r.text
    assert logged_ids(playlog_of(client, org["token"])) == []


def test_due_not_ended_not_listed_until_end(client, fake):
    env = stage(client, seed=9, fee=420)
    gid = env["game_id"]
    settle(client, env["org"]["token"], gid, deal_one(client, env))
    fake.advance(days=2, hours=10)  # → 10-06 22:00 过 end_at：派生 done 但没散场
    assert detail(client, gid, env["org"]["token"])["status"] == "done"
    live = live_get(client, gid, env["org"]["token"])
    assert live["ended"] is False and live["is_my_game"] is False  # 名单前提=已散场
    for u in env["users"]:
        assert logged_ids(playlog_of(client, u["token"])) == []  # 派生态不进记录
    end_live(client, env, live_get(client, gid, env["org"]["token"]))  # 补散场
    for u in env["users"]:  # 上场的第一笔、没上场的账单第二笔、组织者第三笔
        assert logged_ids(playlog_of(client, u["token"])) == [gid]


# ---- 担保人与访客（访客份额记账、场数不计访客） ----


def test_guarantor_with_guest_counts_once(client: TestClient):
    env = open_live(client, seed=5, players=4, bring=1)  # 首位球友带 1 访客
    gid = env["game_id"]
    guarantor = env["mate"]
    book_fee(client, env["org"]["token"], gid, 420)
    v = settle(client, env["org"]["token"], gid, deal_one(client, env))
    end_live(client, env, v)
    out = playlog_of(client, guarantor["token"])
    assert logged_ids(out) == [gid]  # 自己上过场（访客份额同记他账上）
    assert out["games"][0]["bill"]["my_guest_count"] == 1
    assert out["matches_count"] == 1  # 访客同场不给他加第二场


# ---- 场数与排序 ----


def test_matches_count_two_matches_one_row(client: TestClient):
    env = stage(client, seed=10, fee=100)
    gid = env["game_id"]
    v = settle(client, env["org"]["token"], gid, deal_one(client, env))
    v = settle(
        client, env["org"]["token"], gid, deal_one(client, env), score_b=7
    )  # 续场再落一账（同分同位是幂等重放）
    end_live(client, env, v)
    out = playlog_of(client, env["users"][1]["token"])
    assert logged_ids(out) == [gid]  # 两场同局：列表一行
    assert out["matches_count"] == 2  # 场数按对局


def test_order_latest_end_first_then_id_desc(client, fake):
    org = signup(client, _phone(11, 0), "o")
    g1 = stage(client, seed=11, org=org)
    g2 = stage(client, seed=12, org=org)
    end_live(client, g2)  # 同刻散场：id desc 兜稳定序
    end_live(client, g1)
    assert logged_ids(playlog_of(client, org["token"])) == [
        g2["game_id"],
        g1["game_id"],
    ]
    fake.advance(hours=1)
    g3 = stage(client, seed=13, org=org)
    end_live(client, g3)
    out = playlog_of(client, org["token"])
    assert logged_ids(out) == [g3["game_id"], g2["game_id"], g1["game_id"]]


# ---- 端点形状与身份定值 ----


def test_playlog_endpoint_shape_and_auth(client: TestClient):
    r = client.get("/api/games/playlog")
    assert r.status_code == 401 and r.json()["error"]["code"] == "no_identity"
    env = stage(client, seed=14, fee=300)
    v = settle(client, env["org"]["token"], env["game_id"], deal_one(client, env))
    end_live(client, env, v)
    out = playlog_of(client, env["org"]["token"])
    assert set(out.keys()) == {"games", "matches_count"}
    row = out["games"][0]
    assert row["id"] == env["game_id"]
    assert row["ended"] is True and row["status"] == "done"
    assert row["venue_name"] and row["bill"]["fee_total"] == 300


def test_live_view_is_my_game(client: TestClient):
    env = stage(client, seed=15, fee=300)
    gid = env["game_id"]
    v = settle(client, env["org"]["token"], gid, deal_one(client, env))
    end_live(client, env, v)
    assert live_get(client, gid, env["org"]["token"])["is_my_game"] is True  # 组织者
    assert (
        live_get(client, gid, env["users"][1]["token"])["is_my_game"] is True
    )  # 上过场
    bystander = signup(client, _phone(15, 9), "b")
    assert (
        live_get(client, gid, bystander["token"])["is_my_game"] is False
    )  # 无关登录者
    assert live_get(client, gid)["is_my_game"] is False  # 未登录（路人）
