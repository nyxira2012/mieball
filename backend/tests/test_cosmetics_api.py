"""装扮页 API（1.9 批2）：GET /api/cosmetics 顺手核算+新标+册子裁剪、
POST /api/cosmetics/dress 保存把关（判定真值在服务端）。

三类进度各走真账：matches=playlog 上场场数（stage 造 4 人局真打——no_redeal
回流接队尾，4 人局全员反复上场才数得清）；rating=DuprRating 派生分行直插
（台阶只看当下分数，重放链路 stats 册已锁不重走）；organizes=直插 games +
live_matches 最小夹具（口径=organizer+ended_at+EXISTS，与 recount 同一 SQL，
零对局空散场/撤销局各造一局验证排除）。解锁只增不减：掉分不收回、新标本次
看到下次即摘；核算失败按上次清单照常开门；定制款对未授予者条目层隐身。
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core import clock
from app.db.models import Account, DuprRating, Game, LiveMatch
from app.services import cosmetics as cosmetics_service

from .conftest import auth, signup
from .test_bills_generate import db_of, end_live
from .test_live_score import deal_one
from .test_playlog import settle, stage


def page_of(client: TestClient, token: str) -> dict:
    r = client.get("/api/cosmetics", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def dress_call(client: TestClient, token: str, **body):
    return client.post("/api/cosmetics/dress", headers=auth(token), json=body)


def seed_rating(client: TestClient, uid: int, rating: float, games: int = 5) -> None:
    """直插 DUPR 派生分行：台阶判定只吃当下分数+定级旗，重放链路不归本册。"""
    with db_of(client) as db:
        db.add(
            DuprRating(
                account_id=uid, rating=rating, games=games, updated_at=clock.now()
            )
        )
        db.commit()


def seed_organize_game(
    client: TestClient,
    uid: int,
    *,
    ended: bool,
    match: bool,
    cancelled: bool = False,
) -> None:
    """局簿+战报最小夹具：organizes 口径只认 organizer+ended_at+EXISTS(live_matches)
    （零对局空散场=ended 无 match；撤销局=cancelled 无 ended_at）。"""
    with db_of(client) as db:
        now = clock.now()
        g = Game(
            organizer_id=uid,
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
            created_at=now,
            ended_at=now if ended else None,
            cancelled_at=now if cancelled else None,
        )
        db.add(g)
        db.flush()
        if match:
            db.add(
                LiveMatch(
                    game_id=g.id,
                    court_no=1,
                    seq=1,
                    winners=[],
                    losers=[],
                    sa=11,
                    sb=9,
                    winner_side="a",
                    ended_at=now,
                    elo_rows=[],
                )
            )
        db.commit()


# ---- 端点守卫与空状态 ----


def test_page_and_dress_require_login(client: TestClient):
    r = client.get("/api/cosmetics")
    assert r.status_code == 401 and r.json()["error"]["code"] == "no_identity"
    r = client.post("/api/cosmetics/dress", json={})
    assert r.status_code == 401 and r.json()["error"]["code"] == "no_identity"


def test_new_account_page_shape(client: TestClient):
    """新号零解锁：荣誉款全部带锁、无定制节（条目层隐身）、公共款全在册可选。"""
    out = signup(client, "13920001001", "d")
    page = page_of(client, out["token"])
    assert set(page.keys()) == {
        "items",
        "unlocks",
        "wearing",
        "progress",
        "wechat_avatar_available",
    }
    items = {i["cid"]: i for i in page["items"]}
    # 公共 10 + 荣誉 10 档×2 两族 = 30；定制款 2 件未授予不出现
    assert len(items) == 30
    assert "a-x1" not in items and "b-x1" not in items
    assert items["a-p1"]["asset"] == "/cosmetics/a-p1.png"
    assert items["a-m20"]["lock_text"] == "参与 20 场对局解锁"
    assert len(page["unlocks"]) == 20  # 荣誉款全部列出（含未解锁），定制款不列
    for u in page["unlocks"].values():
        assert u == {"unlocked": False, "is_new": False}
    assert page["wearing"] == {"avatar": "a-p1", "back": "b-c1"}
    assert page["progress"] == {
        "matches": 0,
        "rating": 2.5,
        "rating_provisional": True,
        "organizes": 0,
    }
    assert page["wechat_avatar_available"] is False


# ---- 三类解锁 ----


def test_matches_threshold_unlocks_with_new_flag(client: TestClient):
    """场数族走真打路径：4 人局连打 5 场（比分逐场不同，同分同位是幂等重放）。"""
    env = stage(client, seed=21, players=4)
    gid = env["game_id"]
    v = None
    for over in (
        {},
        {"score_b": 7},
        {"winner_side": "b", "score_a": 5, "score_b": 11},
        {"score_b": 5},
        {"score_b": 3},
    ):
        v = settle(client, env["org"]["token"], gid, deal_one(client, env), **over)
    end_live(client, env, v)
    mate = env["users"][1]
    page = page_of(client, mate["token"])
    assert page["progress"]["matches"] == 5
    assert page["unlocks"]["a-m5"] == {"unlocked": True, "is_new": True}
    assert page["unlocks"]["b-m5"] == {"unlocked": True, "is_new": True}
    assert page["unlocks"]["a-m20"]["unlocked"] is False


def test_rating_threshold_unlocks_and_no_takeback(client: TestClient):
    out = signup(client, "13920001003", "d")
    token, uid = out["token"], out["account"]["id"]
    seed_rating(client, uid, rating=3.2)
    page = page_of(client, token)
    assert page["progress"]["rating"] == 3.2
    assert page["progress"]["rating_provisional"] is False
    assert page["unlocks"]["a-t30"] == {"unlocked": True, "is_new": True}
    assert page["unlocks"]["b-t30"]["unlocked"] is True
    assert page["unlocks"]["a-t35"]["unlocked"] is False  # 3.2 未到 3.5 台阶
    # 只增不减：解锁后掉分不收回——判定只看当下，清单写入口只补不删
    with db_of(client) as db:
        db.execute(
            select(DuprRating).where(DuprRating.account_id == uid)
        ).scalar_one().rating = 2.8
        db.commit()
    page = page_of(client, token)
    assert page["progress"]["rating"] == 2.8
    assert page["unlocks"]["a-t30"] == {"unlocked": True, "is_new": False}


def test_organize_threshold_excludes_empty_and_cancelled(client: TestClient):
    out = signup(client, "13920001004", "d")
    token, uid = out["token"], out["account"]["id"]
    for _ in range(3):
        seed_organize_game(client, uid, ended=True, match=True)
    seed_organize_game(client, uid, ended=True, match=False)  # 零对局空散场不算
    seed_organize_game(client, uid, ended=False, match=True, cancelled=True)  # 撤销局
    page = page_of(client, token)
    assert page["progress"]["organizes"] == 3
    assert page["unlocks"]["a-o3"] == {"unlocked": True, "is_new": True}
    assert page["unlocks"]["b-o3"]["unlocked"] is True
    assert page["unlocks"]["a-o10"]["unlocked"] is False
    # 新标口径：本次看到、下次进页即摘
    assert page_of(client, token)["unlocks"]["a-o3"]["is_new"] is False


# ---- 保存把关（4.11 越权提交） ----


def test_dress_guards_and_save(client: TestClient):
    out = signup(client, "13920001005", "d")
    token, uid = out["token"], out["account"]["id"]
    r = dress_call(client, token, avatar="a-p3", back="b-c2")
    assert r.status_code == 200, r.text
    assert r.json() == {
        "avatar": "a-p3",
        "avatar_url": "/cosmetics/a-p3.png",
        "back": "b-c2",
    }
    assert page_of(client, token)["wearing"] == {"avatar": "a-p3", "back": "b-c2"}

    # 未解锁荣誉款拒（在册但未达标）
    r = dress_call(client, token, avatar="a-m5")
    assert r.status_code == 403 and r.json()["error"]["code"] == "cosmetic_not_unlocked"
    # 不存在编号拒；跨栏编号（头像栏传卡背号）对该栏即查无
    r = dress_call(client, token, avatar="no-such")
    assert r.status_code == 404 and r.json()["error"]["code"] == "cosmetic_not_found"
    r = dress_call(client, token, avatar="b-c3")
    assert r.status_code == 404 and r.json()["error"]["code"] == "cosmetic_not_found"
    # 越权定制款拒（在册但未授予本人）
    r = dress_call(client, token, back="b-x1")
    assert r.status_code == 403 and r.json()["error"]["code"] == "cosmetic_not_unlocked"
    # 失效微信头像拒：还没记录过（绑定早、功能上线后未再授权）
    r = dress_call(client, token, avatar="wechat")
    assert r.status_code == 403 and r.json()["error"]["code"] == "wechat_avatar_missing"
    # 拒过的全不动穿戴（穿戴保持原样）
    assert page_of(client, token)["wearing"] == {"avatar": "a-p3", "back": "b-c2"}

    # 记录过微信头像后可穿；只换头像栏、卡背不动
    with db_of(client) as db:
        db.get(Account, uid).wechat_avatar = "https://wx.qlogo.cn/me.png"
        db.commit()
    r = dress_call(client, token, avatar="wechat")
    assert r.status_code == 200, r.text
    assert r.json()["avatar"] == "wechat"
    assert r.json()["avatar_url"] == "https://wx.qlogo.cn/me.png"
    assert r.json()["back"] == "b-c2"
    page = page_of(client, token)
    assert page["wearing"] == {"avatar": "wechat", "back": "b-c2"}
    assert page["wechat_avatar_available"] is True


# ---- 定制款隐身（4.7 条目层裁剪） ----


def test_custom_items_hidden_until_granted(client: TestClient):
    out = signup(client, "13920001006", "d")
    token, uid = out["token"], out["account"]["id"]
    assert "a-x1" not in {i["cid"] for i in page_of(client, token)["items"]}
    # 运维发卡（批4 的动作）在此直插清单模拟：授予后下一屏即见、可穿
    with db_of(client) as db:
        db.get(Account, uid).unlocks = json.dumps([{"id": "a-x1", "new": True}])
        db.commit()
    page = page_of(client, token)
    cids = {i["cid"] for i in page["items"]}
    assert "a-x1" in cids and "b-x1" not in cids  # 只出现被授予的那件
    assert page["unlocks"]["a-x1"] == {"unlocked": True, "is_new": True}
    r = dress_call(client, token, avatar="a-x1")
    assert r.status_code == 200, r.text  # 授予后跟公共款一样顺畅可穿


# ---- 核算失败不拦路（B2 按上次清单照常开门） ----


def test_recount_failure_shows_last_state(client: TestClient, monkeypatch):
    out = signup(client, "13920001007", "d")
    token, uid = out["token"], out["account"]["id"]
    seed_rating(client, uid, rating=3.1)
    assert page_of(client, token)["unlocks"]["a-t30"]["unlocked"] is True

    def boom(db, account_id):
        raise RuntimeError("ledger down")

    monkeypatch.setattr(cosmetics_service, "playlog_source", boom)
    page = page_of(client, token)
    assert page["unlocks"]["a-t30"]["unlocked"] is True  # 按上次清单
    assert page["progress"] == {  # 兜底进度，页照常开门
        "matches": 0,
        "rating": 2.5,
        "rating_provisional": True,
        "organizes": 0,
    }
