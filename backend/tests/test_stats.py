"""榜单端点（1.4 §8 欠账落账）：GET /api/stats/leaderboard。

锁的契约：匿名可读（战力页游客照看）；裸数组、DUPR 降序同分 id 升序（稳定排序）；
行形状 = 账号身份（id/name/chibi/card_bg）+ card 四件套（rating/provisional/games/
wins/last5/month_net）+ elo_rating（Elo 娱乐轨只读，4.1 战力页切换的娱乐视图）；
0 场新号在列（provisional=true、games=0——前端「参考」区）；
注销账号不列（历史不留痕）；不漏手机号（榜单是公开面，比 /users/{id} 更紧）。
战绩底数直插 DuprRating（seed_demo ④ 同一先例：演示底数没有服务层正路，
card 读的就是这张表，口径不破）。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core import clock
from app.db.models import DuprRating, EloRating

from .conftest import code_of, send_code, signup


def seed_rating(client: TestClient, account_id: int, rating: float, games: int) -> None:
    """直插派生分缓存行（seed_demo ④）：rating/games 定值，不走重放。"""
    db = client.app.state.session_factory()
    db.add(
        DuprRating(
            account_id=account_id, rating=rating, games=games, updated_at=clock.now()
        )
    )
    db.commit()
    db.close()


def seed_elo(client: TestClient, account_id: int, rating: int) -> None:
    """直插 Elo 娱乐轨行（seed_demo 同一先例）：榜单只读不落账。"""
    db = client.app.state.session_factory()
    db.add(EloRating(account_id=account_id, rating=rating))
    db.commit()
    db.close()


def test_leaderboard_anonymous_sorted_and_shaped(client: TestClient):
    a = signup(client, "13900000001", "d1", nickname="张三", nickname_set=True)
    b = signup(client, "13900000002", "d2", nickname="李四", nickname_set=True)
    signup(client, "13900000003", "d3", nickname="王五", nickname_set=True)  # 0 场新号
    seed_rating(client, b["account"]["id"], 4.4, 6)  # 李四榜首
    seed_rating(client, a["account"]["id"], 3.7, 5)  # 张三次席

    res = client.get("/api/stats/leaderboard")  # 匿名
    assert res.status_code == 200
    rows = res.json()
    assert [r["id"] for r in rows[:2]] == [b["account"]["id"], a["account"]["id"]]
    ratings = [r["dupr_rating"] for r in rows]
    assert ratings == sorted(ratings, reverse=True)  # 全表降序
    top = rows[0]
    # 行形状：身份四件 + 装扮三键（1.9）+ 战绩六件 + elo 一件，snake_case（契约总则 §1）
    assert set(top) == {
        "id",
        "name",
        "chibi",
        "card_bg",
        "avatar",
        "avatar_url",
        "back",
        "dupr_rating",
        "dupr_provisional",
        "dupr_games",
        "dupr_wins",
        "dupr_last5",
        "dupr_month_net",
        "elo_rating",
    }
    assert top["name"] == "李四"
    assert top["dupr_games"] == 6 and top["dupr_provisional"] is False
    assert "phone" not in top and "phone_tail" not in top  # 公开面不漏号


def test_leaderboard_elo_rating_field(client: TestClient):
    """elo_rating：有行直读、无行回初始 1200（没打过落账局的新号）；
    排序仍只吃 DUPR——Elo 高的垫底也照样垫底（娱乐视图前端自己排）。"""
    a = signup(client, "13900000001", "d1", nickname="甲", nickname_set=True)
    b = signup(client, "13900000002", "d2", nickname="乙", nickname_set=True)
    aid, bid = a["account"]["id"], b["account"]["id"]
    seed_rating(client, aid, 4.4, 6)  # 甲 DUPR 高 → 榜首
    seed_rating(client, bid, 2.8, 5)  # 乙 DUPR 低 → 次席
    seed_elo(client, bid, 1368)  # 乙 Elo 反超高——榜单序不因 Elo 翻

    rows = client.get("/api/stats/leaderboard").json()
    by_id = {r["id"]: r for r in rows}
    assert [r["id"] for r in rows] == [aid, bid]  # 仍按 DUPR 降序
    assert by_id[bid]["elo_rating"] == 1368  # 有行直读
    assert by_id[aid]["elo_rating"] == 1200  # 无行回初始分


def test_leaderboard_zero_game_tie_and_deactivated(client: TestClient, sent):
    a = signup(client, "13900000001", "d1", nickname="甲", nickname_set=True)
    b = signup(client, "13900000002", "d2", nickname="乙", nickname_set=True)
    c = signup(client, "13900000003", "d3", nickname="丙", nickname_set=True)
    aid, bid, cid = (x["account"]["id"] for x in (a, b, c))

    seed_rating(client, aid, 3.5, 5)
    seed_rating(client, bid, 3.5, 5)  # 与甲同分 → id 升序
    # 丙 0 场：无缓存行也在列（起步分/未定级/0 场——前端「参考」区）

    rows = client.get("/api/stats/leaderboard").json()
    by_id = {r["id"]: r for r in rows}
    assert rows.index(by_id[aid]) < rows.index(by_id[bid])  # 同分 id 升序
    zero = by_id[cid]
    assert zero["dupr_games"] == 0 and zero["dupr_provisional"] is True

    # 注销丙 → 榜单不再列（历史不留痕）；短信验证走真链路（conftest 假发送器）
    send_code(client, "13900000003", purpose="deactivate")
    r = client.post(
        "/api/auth/deactivate",
        headers={"Authorization": f"Bearer {c['token']}"},
        json={
            "phone": "13900000003",
            "code": code_of(sent, "13900000003", "deactivate"),
        },
    )
    assert r.status_code == 200
    ids = [x["id"] for x in client.get("/api/stats/leaderboard").json()]
    assert cid not in ids and aid in ids
