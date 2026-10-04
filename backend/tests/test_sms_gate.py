"""短信限频与验证码核销 —— §B1/§5 出错条目：60 秒冷却、一天 10 条、错 5 次作废、过期、查无账号不发码。
全部走假时钟，不用真等。
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import code_of, send_code, signup


def _sms(client: TestClient, phone: str, purpose: str = "recovery"):
    return client.post("/api/auth/sms", json={"phone": phone, "purpose": purpose})


def test_no_account_no_code(client: TestClient):
    r = _sms(client, "13800000000")
    assert r.status_code == 404 and r.json()["error"]["code"] == "no_account"


def test_resend_cooldown_60s(client: TestClient, fake):
    signup(client, "13800001111", "d")
    assert _sms(client, "13800001111").status_code == 200
    r = _sms(client, "13800001111")
    assert r.status_code == 429 and r.json()["error"]["code"] == "sms_cooldown"
    fake.advance(seconds=61)
    assert _sms(client, "13800001111").status_code == 200


def test_phone_daily_limit_10(client: TestClient, fake):
    signup(client, "13800002222", "d")
    for _ in range(10):
        assert _sms(client, "13800002222").status_code == 200
        fake.advance(seconds=61)
    r = _sms(client, "13800002222")
    assert r.status_code == 429 and r.json()["error"]["code"] == "sms_phone_daily"
    fake.advance(days=1)                            # 明天恢复
    assert _sms(client, "13800002222").status_code == 200


def test_ip_daily_limit(client: TestClient, fake):
    """换着号码刷、同 IP：一天 20 条拦住（防刷量，评审补的 IP 维度）。"""
    for i in range(10):                             # 10 个号 × 2 条 = 20 条，同测试 IP
        phone = f"1380001{i:04d}"
        signup(client, phone, "d")
        assert _sms(client, phone).status_code == 200
        fake.advance(seconds=61)
        assert _sms(client, phone).status_code == 200
        fake.advance(seconds=61)
    phone = "13800099999"
    signup(client, phone, "d")
    r = _sms(client, phone)
    assert r.status_code == 429 and r.json()["error"]["code"] == "sms_ip_daily"


def test_wrong_code_five_times_then_invalid(client: TestClient, sent):
    signup(client, "13800003333", "d")
    send_code(client, "13800003333")
    for i in range(4):                              # 前 4 次报剩余次数，逐次递减
        r = client.post("/api/auth/redeem", json={
            "phone": "13800003333", "code": "000000", "purpose": "recovery", "device_marker": "d",
        })
        assert r.status_code == 400 and r.json()["error"]["code"] == "sms_bad_code"
        assert f"还可试 {4 - i} 次" in r.json()["error"]["message"]
    r = client.post("/api/auth/redeem", json={       # 第 5 次错 → 作废
        "phone": "13800003333", "code": "000000", "purpose": "recovery", "device_marker": "d",
    })
    assert r.status_code == 400 and r.json()["error"]["code"] == "sms_code_invalid"
    # 作废后正确的码也进不去了
    r = client.post("/api/auth/redeem", json={
        "phone": "13800003333", "code": code_of(sent, "13800003333"), "purpose": "recovery", "device_marker": "d",
    })
    assert r.status_code == 400


def test_code_expires_in_5_minutes(client: TestClient, sent, fake):
    signup(client, "13800004444", "d")
    send_code(client, "13800004444")
    fake.advance(minutes=5, seconds=1)
    r = client.post("/api/auth/redeem", json={
        "phone": "13800004444", "code": code_of(sent, "13800004444"), "purpose": "recovery", "device_marker": "d",
    })
    assert r.status_code == 400 and r.json()["error"]["code"] == "sms_code_expired"


def test_code_single_use(client: TestClient, sent):
    """一条码只能换一次钥匙。"""
    signup(client, "13800005555", "d")
    send_code(client, "13800005555")
    code = code_of(sent, "13800005555")
    assert client.post("/api/auth/redeem", json={
        "phone": "13800005555", "code": code, "purpose": "recovery", "device_marker": "a",
    }).status_code == 200
    r = client.post("/api/auth/redeem", json={       # 重放同一条码
        "phone": "13800005555", "code": code, "purpose": "recovery", "device_marker": "b",
    })
    assert r.status_code == 400
