"""装扮三键读侧兜底（1.9 批1）：view/person_view/战力榜/现场名册四个下发口同源。

保存穿戴端点批2 才有，这里直插列值（seed_rating 同一先例）锁读侧契约：
NULL→默认公共款（老账号零迁移）、穿了编号→原样透传、'wechat' 值无记录 URL→
回退默认公共款路径、注销者→默认公共款（列一并清 NULL）、榜单行/现场名册行
带三键（展示位随身份直发、不查权限）。
"""

from __future__ import annotations

from app.db.models import Account
from app.services.accounts import person_view
from fastapi.testclient import TestClient

from .conftest import code_of, send_code, signup
from .test_bills_generate import db_of
from .test_live_score import live_get, open_live


def set_dress(client: TestClient, account_id: int, **cols) -> None:
    """直插账号装扮列（保存端点批2 才有；读侧契约不等写入侧）。"""
    with db_of(client) as db:
        acc = db.get(Account, account_id)
        for k, v in cols.items():
            setattr(acc, k, v)
        db.commit()


def user_view(client: TestClient, uid: int) -> dict:
    r = client.get(f"/api/users/{uid}")
    assert r.status_code == 200, r.text
    return r.json()["account"]


def test_view_null_columns_fall_back_to_defaults(client: TestClient):
    """新建账号列全 NULL（=存量老账号同形）→ 默认款公共头像+默认公共卡背。"""
    acc = signup(client, "13900001001", "d")["account"]
    assert acc["avatar"] == "g-00"
    assert acc["avatar_url"] == "/cosmetics/g-00.webp"
    assert acc["back"] == "b-c1"


def test_view_passes_through_worn_ids(client: TestClient):
    out = signup(client, "13900001002", "d")
    uid = out["account"]["id"]
    set_dress(client, uid, dress_avatar="a-p3", dress_back="b-c2")
    acc = user_view(client, uid)
    assert acc["avatar"] == "a-p3"
    assert acc["avatar_url"] == "/cosmetics/a-p3.webp"
    assert acc["back"] == "b-c2"


def test_view_wechat_value_uses_recorded_url_or_falls_back(client: TestClient):
    out = signup(client, "13900001003", "d")
    uid = out["account"]["id"]
    # 'wechat' 但 URL 还没记下（绑定早、功能上线后未再授权）→ 路径回退默认公共款
    set_dress(client, uid, dress_avatar="wechat")
    acc = user_view(client, uid)
    assert acc["avatar"] == "wechat"
    assert acc["avatar_url"] == "/cosmetics/g-00.webp"
    # 记下 URL 后直出微信图（头像值仍是 'wechat' 语义，不掺路径）
    set_dress(client, uid, wechat_avatar="https://wx.qlogo.cn/me.png")
    acc = user_view(client, uid)
    assert acc["avatar"] == "wechat"
    assert acc["avatar_url"] == "https://wx.qlogo.cn/me.png"


def test_deactivated_shows_default_dress_and_clears_columns(client: TestClient, sent):
    phone = "13900001004"
    out = signup(client, phone, "d")
    token, uid = out["token"], out["account"]["id"]
    set_dress(client, uid, dress_avatar="a-p5", dress_back="b-c3")

    send_code(client, phone, purpose="deactivate")
    r = client.post(
        "/api/auth/deactivate",
        headers={"Authorization": f"Bearer {token}"},
        json={"phone": phone, "code": code_of(sent, phone, "deactivate")},
    )
    assert r.status_code == 200, r.text

    acc = user_view(client, uid)
    assert acc["deactivated"] is True
    assert acc["avatar"] == "g-00" and acc["avatar_url"] == "/cosmetics/g-00.webp"
    assert acc["back"] == "b-c1"

    with db_of(client) as db:
        row = db.get(Account, uid)
        assert (
            row.dress_avatar
            is row.dress_back
            is row.unlocks
            is row.wechat_avatar
            is None
        )  # 四列随注销清空：重新注册从零开始，历史名单由读侧兜默认


def test_person_view_shapes_for_missing_and_deactivated(client: TestClient):
    """person_view（game_views/intents 的"对外一个人"单一出口）三态形状：
    缺行/注销→默认公共款；在册→穿戴原样。"""
    assert person_view(None)["avatar"] == "g-00"
    out = signup(client, "13900001005", "d")
    uid = out["account"]["id"]
    set_dress(client, uid, dress_avatar="a-p6", dress_back="b-c4")
    with db_of(client) as db:
        acc = db.get(Account, uid)
        p = person_view(acc)
        assert (p["avatar"], p["avatar_url"], p["back"]) == (
            "a-p6",
            "/cosmetics/a-p6.webp",
            "b-c4",
        )
        acc.status = "deactivated"  # 不落库：单测注销分支的读侧形状
        p = person_view(acc)
        assert (p["avatar"], p["avatar_url"], p["back"]) == (
            "g-00",
            "/cosmetics/g-00.webp",
            "b-c1",
        )


def test_leaderboard_rows_carry_dress_keys(client: TestClient):
    a = signup(client, "13900001006", "d1")
    b = signup(client, "13900001007", "d2")
    set_dress(client, b["account"]["id"], dress_avatar="a-p4", dress_back="b-c3")

    rows = client.get("/api/stats/leaderboard").json()
    by_id = {r["id"]: r for r in rows}
    assert by_id[a["account"]["id"]]["avatar"] == "g-00"
    assert by_id[a["account"]["id"]]["back"] == "b-c1"
    worn = by_id[b["account"]["id"]]
    assert (worn["avatar"], worn["avatar_url"], worn["back"]) == (
        "a-p4",
        "/cosmetics/a-p4.webp",
        "b-c3",
    )


def test_live_roster_dress_guest_none_member_dressed(client: TestClient):
    """现场名册（_player_row）：注册球友带穿戴三键；访客无账号行全 None——
    前端兜指定公共款素材/素卡。"""
    env = open_live(client, seed=51, bring=1)  # 首位球友带 1 名访客进名册
    view = live_get(client, env["game_id"], env["org"]["token"])

    set_dress(client, env["org"]["account"]["id"], dress_avatar="a-p2")
    view = live_get(client, env["game_id"], env["org"]["token"])
    org_row = next(
        p for p in view["players"] if p["account_id"] == env["org"]["account"]["id"]
    )
    assert org_row["avatar"] == "a-p2"
    assert org_row["avatar_url"] == "/cosmetics/a-p2.webp"
    assert org_row["back"] == "b-c1"  # 只穿了头像，卡背兜默认

    guest_rows = [p for p in view["players"] if p["guest"]]
    assert guest_rows, "open_live(bring=1) 应有名册访客行"
    for g in guest_rows:
        assert g["avatar"] is None and g["avatar_url"] is None and g["back"] is None
