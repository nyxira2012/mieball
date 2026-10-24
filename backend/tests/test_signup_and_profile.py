"""建号 / 认人 / 名片 —— docs/1.1 §4.2、§4.3、验收"不重复建号/重试续上"。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import me, signup


def test_signup_creates_account_and_self_view(client: TestClient):
    out = signup(
        client, "13800001111", "dev-a", nickname="海淀反手王", nickname_set=True
    )
    assert out["token"]
    acc = out["account"]
    assert acc["name"] == "海淀反手王"
    assert acc["phone"] == "13800001111"  # 本人见全号
    assert acc["phone_tail"] == "1111"
    assert acc["wechat_bound"] is False  # 纯手机号账号没绑微信（1.8 批3 微信行两态）
    # 建号直发的钥匙未验证：视图里不给验证标记（对外无此字段即无所谓，自我确认即可）
    assert me(client, out["token"])["name"] == "海淀反手王"


def test_signup_defaults_when_skipped(client: TestClient):
    out = signup(client, "13800002222", "dev-a")  # 昵称/头像全跳过
    assert (
        out["account"]["name"].startswith("球友") and len(out["account"]["name"]) == 6
    )


def test_signup_phone_invalid(client: TestClient):
    r = client.post(
        "/api/auth/signup", json={"device_marker": "d", "card": {"phone": "1380000"}}
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "phone_invalid"


def test_signup_reserved_nickname_rejected(client: TestClient):
    r = client.post(
        "/api/auth/signup",
        json={
            "device_marker": "d",
            "card": {
                "phone": "13800003333",
                "nickname": "已注销球友",
                "nickname_set": True,
            },
        },
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "nickname_invalid"


def test_me_without_token_is_guest_not_error(client: TestClient):
    assert me(client, None) is None  # 认人失败按游客处理，不报错（§B 认人）


def test_phone_taken_and_resume_window(client: TestClient, fake):
    first = signup(client, "13800004444", "dev-a")
    # 别的设备来占这个号 → 报占用
    r = client.post(
        "/api/auth/signup",
        json={"device_marker": "dev-b", "card": {"phone": "13800004444"}},
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "phone_taken"
    # 同一台设备 10 分钟内重试（提交卡住场景）→ 续上，不再弹占用
    again = signup(client, "13800004444", "dev-a")
    assert again["account"]["id"] == first["account"]["id"]
    assert me(client, again["token"]) is not None
    # 窗口外同设备 → 占用
    fake.advance(minutes=11)
    r = client.post(
        "/api/auth/signup",
        json={"device_marker": "dev-a", "card": {"phone": "13800004444"}},
    )
    assert r.status_code == 409


def test_logout_revokes_only_this_device(client: TestClient):
    t1 = signup(client, "13800005555", "dev-a")["token"]
    t2 = signup(client, "13800005555", "dev-a")["token"]  # 续接窗口内第二把
    assert (
        client.post(
            "/api/auth/logout", headers={"Authorization": f"Bearer {t1}"}
        ).status_code
        == 200
    )
    assert me(client, t1) is None  # 这台失效
    assert me(client, t2) is not None  # 另一把（同设备续发的）不受影响


# ---- 建号起步分（1.4 §5 修订：自评废除，统一 GUEST_DUPR 2.5） ----


def test_signup_starts_dupr_at_guest_default(client: TestClient):
    out = signup(client, "13800007771", "dev-a")
    acc = out["account"]
    # 新号无派分行：起步分由 dupr 缺行语义出（2.5，不是落库字面值）
    assert acc["dupr_rating"] == 2.5
    assert acc["dupr_provisional"] is True and acc["dupr_games"] == 0
    assert me(client, out["token"])["dupr_rating"] == 2.5  # /me 同一 view 形状


def test_profile_update_rules(client: TestClient):
    token = signup(client, "13800006666", "dev-a")["token"]
    h = {"Authorization": f"Bearer {token}"}
    r = client.post(
        "/api/auth/profile",
        headers=h,
        json={"nickname": "  亮马河快攻  "},
    )
    assert r.status_code == 200
    acc = r.json()["account"]
    assert acc["name"] == "亮马河快攻"  # 昵称去首尾空格
    r = client.post("/api/auth/profile", headers=h, json={"nickname": "平台客服"})
    assert r.status_code == 422
    # 未带钥匙改名片 → 401
    assert client.post("/api/auth/profile", json={"nickname": "x"}).status_code == 401


# ---- 1.9 §4.1 注册卡挑形象：只许公共款头像，选了落档、没选兜默认 ----


def test_signup_with_public_avatar_lands_dress_column(client: TestClient):
    out = signup(client, "13800001121", "dev-a", avatar="a-p3")
    acc = out["account"]
    assert acc["avatar"] == "a-p3"
    assert acc["avatar_url"] == "/cosmetics/a-p3.webp"
    assert me(client, out["token"])["avatar"] == "a-p3"  # /me 同源
    pub = client.get(f"/api/users/{acc['id']}").json()["account"]
    assert pub["avatar"] == "a-p3"  # 公开视图（档案弹层）同一直发源


def test_signup_without_avatar_defaults_first_public(client: TestClient):
    out = signup(client, "13800001122", "dev-a")  # 头像没挑
    acc = out["account"]
    assert acc["avatar"] == "g-00"  # 读侧兜默认款，不另写死列值
    assert acc["avatar_url"] == "/cosmetics/g-00.webp"


def test_signup_rejects_avatar_outside_public_pool(client: TestClient):
    """注册卡不出现荣誉/定制/跨栏/不在册（§4.1 禁止）——一律按查无这件拒。"""
    for bad in ("a-x1", "a-m5", "b-c1", "a-nope"):
        r = client.post(
            "/api/auth/signup",
            json={
                "device_marker": "d",
                "card": {"phone": "13800001123", "avatar": bad},
            },
        )
        assert r.status_code == 404, bad
        assert r.json()["error"]["code"] == "cosmetic_not_found"
