"""密码钥匙 —— 1.6 §4.8~§4.11 验收面：设/登/重置/改/密码接管 + 连错锁 + 宽限窗 + 限频同规。
全部走假时钟，不用真等。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.security import hash_password, verify_password

from .conftest import (
    code_of,
    me,
    password_change,
    password_login,
    password_redeem,
    password_reset,
    password_set,
    redeem,
    send_code,
    signup,
)

PHONE = "13800007777"


def _post(client: TestClient, path: str, body: dict, token: str | None = None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.post(f"/api/auth/password/{path}", json=body, headers=headers)


def _setup(
    client: TestClient, sent: list, phone: str, device: str, pwd: str = "123456"
) -> str:
    """建号 → 短信码设密码 → 回设密那台的 token。"""
    token = signup(client, phone, device)["token"]
    send_code(client, phone, "set_password")
    password_set(client, token, code_of(sent, phone, "set_password"), pwd)
    return token


# ---- 哈希原语 ----


def test_hash_roundtrip_and_per_password_salt():
    h1 = hash_password("123456")
    h2 = hash_password("123456")
    assert h1 != h2  # 每密码随机盐：同文不同记
    assert verify_password("123456", h1)
    assert not verify_password("654321", h1)


# ---- 设密码（4.8）----


def test_set_with_sms_code_and_view_has_password(client: TestClient, sent):
    token = signup(client, PHONE, "d1")["token"]
    assert me(client, token)["has_password"] is False
    send_code(client, PHONE, "set_password")
    password_set(client, token, code_of(sent, PHONE, "set_password"))
    assert me(client, token)["has_password"] is True
    r = password_login(client, PHONE, "123456", "d2")  # 设完即能密码登录
    assert r["account"]["has_password"] is True


def test_set_too_short_rejected_then_code_still_usable(client: TestClient, sent):
    """5 位被拦且不烧码（长度闸在验码前），改 6 位同一条码通过。"""
    token = signup(client, PHONE, "d1")["token"]
    send_code(client, PHONE, "set_password")
    code = code_of(sent, PHONE, "set_password")
    r = _post(client, "set", {"code": code, "password": "12345"}, token)
    assert r.status_code == 422 and r.json()["error"]["code"] == "password_too_short"
    password_set(client, token, code, "123456")


def test_set_twice_rejected(client: TestClient, sent):
    """已设拒重设（先挡已设再挡凭据），冒填者抢设的口子只留首设一条。"""
    token = _setup(client, sent, PHONE, "d1")
    r = _post(client, "set", {"code": "", "password": "999999"}, token)
    assert r.status_code == 409 and r.json()["error"]["code"] == "password_exists"


def test_set_without_credential_rejected(client: TestClient):
    """无码且不在宽限窗 → 拒（冒填者没验过正身设不成，§4.8 禁止项）。"""
    token = signup(client, PHONE, "d1")["token"]
    r = _post(client, "set", {"code": "", "password": "123456"}, token)
    assert r.status_code == 400 and r.json()["error"]["code"] == "sms_code_invalid"


# ---- 密码登录（4.9）----


def test_login_kills_unverified_keys_and_issues_verified(client: TestClient, sent):
    a = signup(client, PHONE, "d1")["token"]  # 未验证钥匙（冒填者/首台）
    b = signup(client, PHONE, "d1")["token"]  # 续接窗口内的第二把未验证钥匙
    send_code(client, PHONE, "set_password")
    password_set(client, b, code_of(sent, PHONE, "set_password"))
    r = password_login(client, PHONE, "123456", "d2")
    assert me(client, a) is None  # 未验证钥匙一并作废（与短信验证同待遇）
    assert me(client, b) is None
    assert me(client, r["token"]) is not None  # 密码登录发的钥匙=已验证级


def test_login_fail_count_resets_on_success(client: TestClient, sent):
    _setup(client, sent, PHONE, "d1")
    body = {"phone": PHONE, "password": "wrong", "device_marker": "x"}
    r = _post(client, "login", body)
    assert "还可试 4 次" in r.json()["error"]["message"]
    password_login(client, PHONE, "123456", "d2")  # 对一次 → 计数清零
    r = _post(client, "login", body)
    assert "还可试 4 次" in r.json()["error"]["message"]  # 不是 3：计数确实清过零


def test_login_unknown_phone_and_not_set(client: TestClient):
    r = _post(
        client, "login", {"phone": "13800099999", "password": "x", "device_marker": "d"}
    )
    assert r.status_code == 404 and r.json()["error"]["code"] == "no_account"
    signup(client, PHONE, "d1")  # 有号没设密码
    r = _post(client, "login", {"phone": PHONE, "password": "x", "device_marker": "d"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "password_not_set"


def test_five_fails_lock_15min_sms_path_unaffected(client: TestClient, sent, fake):
    _setup(client, sent, PHONE, "d1")
    for i in range(4):  # 前 4 次：剩余次数逐次递减
        r = _post(
            client,
            "login",
            {"phone": PHONE, "password": f"bad{i}", "device_marker": "x"},
        )
        assert r.status_code == 400 and r.json()["error"]["code"] == "password_wrong"
        assert f"还可试 {4 - i} 次" in r.json()["error"]["message"]
    r = _post(
        client, "login", {"phone": PHONE, "password": "bad5", "device_marker": "x"}
    )
    assert r.status_code == 429 and r.json()["error"]["code"] == "password_locked"
    r = _post(
        client, "login", {"phone": PHONE, "password": "123456", "device_marker": "x"}
    )
    assert r.status_code == 429  # 锁内对的密码也进不去（锁的是整条路）
    # 锁内短信路照常（互不波及，4.9）
    fake.advance(seconds=61)
    send_code(client, PHONE, "recovery")
    good = redeem(client, PHONE, code_of(sent, PHONE, "recovery"), "recovery", "d2")
    assert me(client, good["token"]) is not None
    fake.advance(minutes=15)  # 锁完自动再开
    r = password_login(client, PHONE, "123456", "d3")
    assert me(client, r["token"]) is not None


# ---- 重置=换锁（4.10）----


def test_reset_keeps_only_current_device_and_old_password_dies(
    client: TestClient, sent, fake
):
    _setup(client, sent, PHONE, "d1")
    d2 = password_login(client, PHONE, "123456", "d2")["token"]
    fake.advance(seconds=61)
    send_code(client, PHONE, "reset_password")
    d3 = password_reset(
        client, PHONE, code_of(sent, PHONE, "reset_password"), "222222", "d3"
    )
    assert me(client, d2) is None  # 换锁：所有设备钥匙作废
    assert me(client, d3["token"]) is not None  # 只留正在操作的这台
    r = _post(
        client, "login", {"phone": PHONE, "password": "123456", "device_marker": "d4"}
    )
    assert (
        r.status_code == 400 and r.json()["error"]["code"] == "password_wrong"
    )  # 旧密作废
    assert (
        me(client, password_login(client, PHONE, "222222", "d4")["token"]) is not None
    )


# ---- 修改密码=例行（4.11）----


def test_change_routine_other_devices_unaffected(client: TestClient, sent):
    _setup(client, sent, PHONE, "d1")
    d2 = password_login(client, PHONE, "123456", "d2")["token"]  # 已验证会话去改密
    password_change(client, d2, "123456", "222222")
    assert me(client, d2) is not None  # 例行操作不动他设备（含本台）
    r = _post(
        client, "login", {"phone": PHONE, "password": "123456", "device_marker": "d3"}
    )
    assert r.status_code == 400
    assert (
        me(client, password_login(client, PHONE, "222222", "d3")["token"]) is not None
    )


def test_change_wrong_old_no_lock_no_count(client: TestClient, sent):
    token = _setup(client, sent, PHONE, "d1")
    for _ in range(6):  # 旧密错反复试：不计锁
        r = _post(client, "change", {"old": "wrong", "new": "222222"}, token)
        assert r.status_code == 400 and r.json()["error"]["code"] == "password_wrong"
        assert "还可试" not in r.json()["error"]["message"]
    password_change(client, token, "123456", "222222")  # 改密路本身也没被锁
    r = _post(
        client, "login", {"phone": PHONE, "password": "bad", "device_marker": "x"}
    )
    assert "还可试 4 次" in r.json()["error"]["message"]  # 登录计数全程没动
    assert (
        me(client, password_login(client, PHONE, "222222", "d2")["token"]) is not None
    )


# ---- 密码接管（4.5）与宽限窗 ----


def test_redeem_password_takeover_semantics(client: TestClient, sent):
    old = signup(client, PHONE, "d-old")["token"]
    send_code(client, PHONE, "set_password")
    password_set(client, old, code_of(sent, PHONE, "set_password"), "333333")
    r = password_redeem(
        client,
        PHONE,
        "333333",
        "d-new",
        card={
            "phone": PHONE,
            "nickname": "真主人",
            "nickname_set": True,
            "chibi": None,
            "chibi_set": False,
        },
    )
    assert r["account"]["name"] == "真主人"  # 亲填覆盖、跳过沿用（D5）
    assert me(client, old) is None  # 全设备钥匙作废
    wrong = _post(
        client, "login", {"phone": PHONE, "password": "333333", "device_marker": "x"}
    )
    assert (
        wrong.status_code == 404 and wrong.json()["error"]["code"] == "password_not_set"
    )  # 密码一并作废
    # 宽限窗内设新密免再发码（4.5：接管者随即重设）
    password_set(client, r["token"], "", "444444")
    assert (
        me(client, password_login(client, PHONE, "444444", "d5")["token"]) is not None
    )


def test_grace_window_works_then_expires(client: TestClient, sent, fake):
    signup(client, "13800007778", "a1")
    send_code(client, "13800007778", "recovery")
    r = redeem(client, "13800007778", code_of(sent, "13800007778"), "recovery", "a2")
    password_set(client, r["token"], "", "111111")  # 找回成功 → 宽限窗内免码
    fake.advance(seconds=61)
    signup(client, "13800007779", "b1")
    send_code(client, "13800007779", "recovery")
    r = redeem(client, "13800007779", code_of(sent, "13800007779"), "recovery", "b2")
    fake.advance(minutes=10, seconds=1)  # 宽限 10 分钟已过
    r = _post(client, "set", {"code": "", "password": "222222"}, r["token"])
    assert r.status_code == 400 and r.json()["error"]["code"] == "sms_code_invalid"


def test_shared_fail_count_between_login_and_redeem(client: TestClient, sent):
    _setup(client, sent, PHONE, "d1")
    for i in range(4):
        _post(
            client,
            "login",
            {"phone": PHONE, "password": f"bad{i}", "device_marker": "x"},
        )
    r = _post(
        client, "redeem", {"phone": PHONE, "password": "bad4", "device_marker": "x"}
    )
    assert r.status_code == 429 and r.json()["error"]["code"] == "password_locked"


# ---- 新短信用途限频同规（附录 B1）----


def test_new_purposes_share_sms_limits(client: TestClient, fake):
    signup(client, PHONE, "d1")
    assert (
        client.post(
            "/api/auth/sms", json={"phone": PHONE, "purpose": "set_password"}
        ).status_code
        == 200
    )
    r = client.post("/api/auth/sms", json={"phone": PHONE, "purpose": "reset_password"})
    assert (
        r.status_code == 429 and r.json()["error"]["code"] == "sms_cooldown"
    )  # 60s 同号同规
    fake.advance(seconds=61)
    assert (
        client.post(
            "/api/auth/sms", json={"phone": PHONE, "purpose": "reset_password"}
        ).status_code
        == 200
    )
    r = client.post(
        "/api/auth/sms", json={"phone": "13800099999", "purpose": "set_password"}
    )
    assert (
        r.status_code == 404 and r.json()["error"]["code"] == "no_account"
    )  # 查无账号不发码照常
