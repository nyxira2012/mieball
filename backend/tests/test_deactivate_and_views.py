"""注销与隐私出口 —— §4.6 匿名化/手机号释放/全钥匙失效；§C2 三种身份看到的字段逐个核。
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import me, signup


def test_deactivate_anonymizes_and_releases_phone(client: TestClient, sent, fake):
    phone = "13800001111"
    out = signup(client, phone, "dev-a")
    token, uid = out["token"], out["account"]["id"]

    r = client.post("/api/auth/sms", json={"phone": phone, "purpose": "deactivate"})
    assert r.status_code == 200
    code = next(c for p, c, pu in reversed(sent) if p == phone and pu == "deactivate")
    r = client.post("/api/auth/deactivate", headers={"Authorization": f"Bearer {token}"},
                    json={"phone": phone, "code": code})
    assert r.status_code == 200, r.text

    assert me(client, token) is None                    # 所有钥匙失效

    # 任何人（含本人旧钥匙）看这个号 → 已注销占位，无尾号无全号
    r = client.get(f"/api/users/{uid}?same_game=1")
    acc = r.json()["account"]
    assert acc["name"] == "已注销球友" and acc["deactivated"] is True
    assert "phone_tail" not in acc and "phone" not in acc

    # 同一个号重新注册 → 全新账号（历史不继承）
    again = signup(client, phone, "dev-new")
    assert again["account"]["id"] != uid
    assert again["account"]["name"].startswith("球友")   # 新号新名片


def test_deactivate_requires_own_phone_and_code(client: TestClient, sent):
    phone = "13800002222"
    token = signup(client, phone, "d")["token"]
    r = client.post("/api/auth/deactivate", headers={"Authorization": f"Bearer {token}"},
                    json={"phone": "13800003333", "code": "123456"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "phone_mismatch"
    # 未带钥匙 → 401
    assert client.post("/api/auth/deactivate", json={"phone": phone, "code": "123456"}).status_code == 401


def test_privacy_outlet_three_viewers(client: TestClient):
    phone = "13800005555"
    out = signup(client, phone, "dev-a", nickname="国贸截击手", nickname_set=True)
    uid, token = out["account"]["id"], out["token"]

    # 游客/陌生人：只有昵称+小人（+卡背），无尾号无全号
    acc = client.get(f"/api/users/{uid}").json()["account"]
    assert acc["name"] == "国贸截击手"
    assert "phone" not in acc and "phone_tail" not in acc

    # 同局视角：加尾号 4 位，仍无全号
    acc = client.get(f"/api/users/{uid}?same_game=1").json()["account"]
    assert acc["phone_tail"] == "5555" and "phone" not in acc

    # 本人：全号可见
    acc = client.get(f"/api/users/{uid}", headers={"Authorization": f"Bearer {token}"}).json()["account"]
    assert acc["phone"] == phone and acc["phone_tail"] == "5555"

    # 查无此人 → 404 no_account
    assert client.get("/api/users/99999").status_code == 404
