"""建号 / 认人 / 名片 —— docs/1.1 §4.2、§4.3、验收"不重复建号/重试续上"。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import me, signup


def test_signup_creates_account_and_self_view(client: TestClient):
    out = signup(client, "13800001111", "dev-a", nickname="海淀反手王", nickname_set=True)
    assert out["token"]
    acc = out["account"]
    assert acc["name"] == "海淀反手王"
    assert acc["phone"] == "13800001111"          # 本人见全号
    assert acc["phone_tail"] == "1111"
    assert acc["chibi"]["shirt"] == 5              # 未选形象 → 默认小人
    # 建号直发的钥匙未验证：视图里不给验证标记（对外无此字段即无所谓，自我确认即可）
    assert me(client, out["token"])["name"] == "海淀反手王"


def test_signup_defaults_when_skipped(client: TestClient):
    out = signup(client, "13800002222", "dev-a")  # 昵称/头像全跳过
    assert out["account"]["name"].startswith("球友") and len(out["account"]["name"]) == 6
    assert out["account"]["chibi"] == {"skin": 0, "hair": 0, "hc": 0, "shirt": 5, "face": 0, "acc": 0}


def test_signup_phone_invalid(client: TestClient):
    r = client.post("/api/auth/signup", json={"device_marker": "d", "card": {"phone": "1380000"}})
    assert r.status_code == 422 and r.json()["error"]["code"] == "phone_invalid"


def test_signup_reserved_nickname_rejected(client: TestClient):
    r = client.post(
        "/api/auth/signup",
        json={"device_marker": "d", "card": {"phone": "13800003333", "nickname": "已注销球友", "nickname_set": True}},
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "nickname_invalid"


def test_me_without_token_is_guest_not_error(client: TestClient):
    assert me(client, None) is None                # 认人失败按游客处理，不报错（§B 认人）


def test_phone_taken_and_resume_window(client: TestClient, fake):
    first = signup(client, "13800004444", "dev-a")
    # 别的设备来占这个号 → 报占用
    r = client.post("/api/auth/signup", json={"device_marker": "dev-b", "card": {"phone": "13800004444"}})
    assert r.status_code == 409 and r.json()["error"]["code"] == "phone_taken"
    # 同一台设备 10 分钟内重试（提交卡住场景）→ 续上，不再弹占用
    again = signup(client, "13800004444", "dev-a")
    assert again["account"]["id"] == first["account"]["id"]
    assert me(client, again["token"]) is not None
    # 窗口外同设备 → 占用
    fake.advance(minutes=11)
    r = client.post("/api/auth/signup", json={"device_marker": "dev-a", "card": {"phone": "13800004444"}})
    assert r.status_code == 409


def test_logout_revokes_only_this_device(client: TestClient):
    t1 = signup(client, "13800005555", "dev-a")["token"]
    t2 = signup(client, "13800005555", "dev-a")["token"]  # 续接窗口内第二把
    assert client.post("/api/auth/logout", headers={"Authorization": f"Bearer {t1}"}).status_code == 200
    assert me(client, t1) is None                    # 这台失效
    assert me(client, t2) is not None                # 另一把（同设备续发的）不受影响


def test_profile_update_rules(client: TestClient):
    token = signup(client, "13800006666", "dev-a")["token"]
    h = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/auth/profile", headers=h, json={"nickname": "  亮马河快攻  ", "card_bg": "gold"})
    assert r.status_code == 200
    acc = r.json()["account"]
    assert acc["name"] == "亮马河快攻" and acc["card_bg"] == "gold"   # 昵称去首尾空格
    r = client.post("/api/auth/profile", headers=h, json={"chibi": {"skin": 9}})
    assert r.status_code == 422 and r.json()["error"]["code"] == "chibi_invalid"
    r = client.post("/api/auth/profile", headers=h, json={"nickname": "平台客服"})
    assert r.status_code == 422
    # 未带钥匙改名片 → 401
    assert client.post("/api/auth/profile", json={"nickname": "x"}).status_code == 401
