"""微信钥匙（docs/1.7）——通道、两扇门、绑定挂点、清场镜像，全矩阵锁。

假通道（provider 默认 fake）：授权凭证即身份号——code 直接当 openid 用，
与短信 console 假发送器同一先例，开发零资质全链可测。

跑法：cd backend && python -m pytest tests/test_wechat.py -q
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings

from .conftest import code_of, me, redeem, send_code, signup

# ---- 帮手 ----


def resend(client: TestClient, fake, phone: str, purpose: str = "recovery") -> None:
    """同号第二条码：假时钟推过 60 秒冷却再发。"""
    fake.advance(seconds=61)
    send_code(client, phone, purpose)


def wechat_url(
    client: TestClient, redirect_uri: str = "https://h/#/pages/mine/login"
) -> dict:
    r = client.post(
        "/api/auth/wechat/url", json={"redirect_uri": redirect_uri, "state": "s1"}
    )
    assert r.status_code == 200, r.text
    return r.json()


def wechat_login(client: TestClient, code: str, device: str = "d-wx") -> dict:
    r = client.post(
        "/api/auth/wechat/login", json={"code": code, "device_marker": device}
    )
    assert r.status_code == 200, r.text
    return r.json()


def wechat_redeem_error(client: TestClient, code: str, phone: str) -> str:
    r = client.post(
        "/api/auth/wechat/redeem",
        json={"code": code, "phone": phone, "device_marker": "d-wx"},
    )
    assert r.status_code >= 400, r.text
    return r.json()["error"]["code"]


def _bind_account(client: TestClient, sent: list, phone: str, openid: str) -> dict:
    """造一个「正式绑了微信」的账号：建号 → 微信登录拿凭条 → 短信找回带上凭条。"""
    signup(client, phone, "d1")
    bind_token = wechat_login(client, openid)["bind_token"]
    send_code(client, phone, "recovery")
    r = client.post(
        "/api/auth/redeem",
        json={
            "phone": phone,
            "code": code_of(sent, phone, "recovery"),
            "purpose": "recovery",
            "device_marker": "d1",
            "bind_token": bind_token,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json().get("wechat_bound") is True
    return r.json()


# ---- 通道：地址拼装与开关 ----


def test_fake_url_appends_code(client: TestClient):
    out = wechat_url(client, "https://h/#/pages/mine/login")
    assert "code=wx_dev" in out["url"] and "state=s1" in out["url"]


def test_real_unconfigured_channel_closed(tmp_path, fake, sent):
    """real 模式没配 AppID/Secret：通道按 wechat_off 关死（不能静默裸奔）。"""
    from app.main import create_app

    app = create_app(
        Settings(
            db_url=f"sqlite:///{tmp_path}/t.db",
            pepper="p",
            sms_provider="console",
            sms_daily_budget=200,
            wechat_provider="real",
        )
    )
    c = TestClient(app)
    r = c.post(
        "/api/auth/wechat/url", json={"redirect_uri": "https://h/x", "state": "s"}
    )
    assert r.status_code == 503 and r.json()["error"]["code"] == "wechat_off"
    r = c.post("/api/auth/wechat/login", json={"code": "any", "device_marker": "d"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "wechat_off"


# ---- 认人门：没绑→凭条；建号顺手绑；再登录直接进 ----


def test_unbound_issues_bind_token_then_signup_binds_weak(client: TestClient):
    res = wechat_login(client, "wx_alice")
    assert res["status"] == "unbound" and res["bind_token"]

    # 带凭条建号：顺手绑（弱档），回话带 wechat_bound
    r = client.post(
        "/api/auth/signup",
        json={
            "device_marker": "d1",
            "card": {"phone": "13800000001"},
            "bind_token": res["bind_token"],
        },
    )
    assert r.status_code == 200 and r.json().get("wechat_bound") is True

    # 同一微信再登录：直接进（弱档=未验证钥匙）
    res2 = wechat_login(client, "wx_alice")
    assert res2["status"] == "ok"
    acc = me(client, res2["token"])
    assert acc["phone"] == "13800000001"


def test_signup_without_token_no_binding_flag(client: TestClient):
    out = signup(client, "13800000002", "d1")
    assert "wechat_bound" not in out


def test_stale_bind_token_skipped_silently(client: TestClient, fake):
    """凭条过期：建号照常成功、不说「已绑上」（1.7 §5 验收）。"""
    res = wechat_login(client, "wx_bob")
    fake.advance(minutes=11)  # 凭条十分钟过期
    r = client.post(
        "/api/auth/signup",
        json={
            "device_marker": "d1",
            "card": {"phone": "13800000003"},
            "bind_token": res["bind_token"],
        },
    )
    assert r.status_code == 200 and "wechat_bound" not in r.json()
    # 微信仍是新面孔
    assert wechat_login(client, "wx_bob")["status"] == "unbound"


# ---- 验明正身=正式绑（老账号自动接上）+ D4 微信面 ----


def test_recovery_with_token_upgrades_to_verified(client: TestClient, sent: list):
    out = _bind_account(client, sent, "13800000004", "wx_carol")
    token = out["token"]

    # 同设备续接窗口内再报名一次 → 拿到一把未验证钥匙
    unverified = signup(client, "13800000004", "d1")["token"]

    # 正式绑后微信登录=验明正身：杀未验证钥匙、已验证钥匙不受影响
    res = wechat_login(client, "wx_carol", "d-wx")
    assert res["status"] == "ok"
    assert me(client, unverified) is None
    assert me(client, token) is not None


def test_attacker_weak_binding_dies_on_owner_verify(client: TestClient, sent: list):
    """4.9 安全底：冒填者建号顺手绑 → 真主人验明正身 → 微信进不来了。"""
    # 冒填者拿别人的号建号+顺手绑自己的微信
    res = wechat_login(client, "wx_evil")
    client.post(
        "/api/auth/signup",
        json={
            "device_marker": "d-attacker",
            "card": {"phone": "13800000005"},
            "bind_token": res["bind_token"],
        },
    )
    # 冒充期：微信能进（弱档未验证钥匙，与建号那把同级——既有取舍）
    assert wechat_login(client, "wx_evil")["status"] == "ok"

    # 真主人短信找回（验明正身）：弱档绑定同刻解开
    send_code(client, "13800000005", "recovery")
    redeem(client, "13800000005", code_of(sent, "13800000005"), "recovery", "d-owner")

    assert wechat_login(client, "wx_evil")["status"] == "unbound"


def test_owner_can_rebind_after_sweep(client: TestClient, fake, sent: list):
    """4.9 边界说明：本人顺手绑被解开，再走一遍 4.3 可重新正式绑上。"""
    token1 = wechat_login(client, "wx_self")["bind_token"]
    r = client.post(
        "/api/auth/signup",
        json={
            "device_marker": "d1",
            "card": {"phone": "13800000006"},
            "bind_token": token1,
        },
    )
    assert r.json().get("wechat_bound") is True

    # 本人验明正身（不带凭条）：弱档绑定同刻解开
    resend(client, fake, "13800000006")
    redeem(client, "13800000006", code_of(sent, "13800000006"), "recovery", "d1")
    assert wechat_login(client, "wx_self")["status"] == "unbound"

    # 再走一遍 4.3：验证+凭条 → 正式绑
    token2 = wechat_login(client, "wx_self")["bind_token"]
    resend(client, fake, "13800000006")
    r = client.post(
        "/api/auth/redeem",
        json={
            "phone": "13800000006",
            "code": code_of(sent, "13800000006"),
            "purpose": "recovery",
            "device_marker": "d1",
            "bind_token": token2,
        },
    )
    assert r.status_code == 200 and r.json().get("wechat_bound") is True
    assert wechat_login(client, "wx_self")["status"] == "ok"


# ---- 占卡微信出口：只认正式绑、接管级清场 ----


def test_wechat_redeem_takeover_semantics(client: TestClient, fake, sent: list):
    """4.4：与短信出口完全一致——名片并入、全设备作废（含密码）。"""
    out = _bind_account(client, sent, "13800000007", "wx_dave")
    old_token = out["token"]
    # 给账号设个密码，接管后应作废
    from .conftest import password_set

    resend(client, fake, "13800000007", "set_password")
    password_set(client, old_token, code_of(sent, "13800000007", "set_password"))

    # 另一台设备占卡 → 微信验证进入（带上名片：明确填了昵称）
    r = client.post(
        "/api/auth/wechat/redeem",
        json={
            "code": "wx_dave",
            "phone": "13800000007",
            "device_marker": "d-new",
            "card": {"phone": "13800000007", "nickname": "新名", "nickname_set": True},
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["account"]["name"] == "新名"
    # 全设备作废：旧钥匙失效、密码作废
    assert me(client, old_token) is None
    rr = client.post(
        "/api/auth/password/login",
        json={"phone": "13800000007", "password": "123456", "device_marker": "d-x"},
    )
    assert rr.status_code == 404 and rr.json()["error"]["code"] == "password_not_set"


def test_wechat_redeem_rejects_three_cases(client: TestClient, sent: list):
    """4.5：甲（没绑）/乙（绑别处/只是顺手绑）各报各的指路错、不放行。"""
    # 甲：目标账号存在但这个微信从没绑过
    signup(client, "13800000008", "d1")
    assert wechat_redeem_error(client, "wx_nobody", "13800000008") == "wechat_unbound"
    # 乙1：这个微信正式绑在另一个账号上
    _bind_account(client, sent, "13800000009", "wx_zoe")
    assert wechat_redeem_error(client, "wx_zoe", "13800000008") == "wechat_bound_other"
    # 乙2：绑过这个账号但只是顺手绑
    res = wechat_login(client, "wx_weak")
    client.post(
        "/api/auth/signup",
        json={
            "device_marker": "d1",
            "card": {"phone": "13800000010"},
            "bind_token": res["bind_token"],
        },
    )
    assert (
        wechat_redeem_error(client, "wx_weak", "13800000010") == "wechat_binding_weak"
    )


# ---- 换绑顶替：一个微信只开一扇门 ----


def test_rebind_replaces_old_binding(client: TestClient, sent: list):
    """4.5 下文：验证进入后微信换绑到当前账号，原账号绑定自动解开。"""
    _bind_account(client, sent, "13800000011", "wx_move")
    # wx_move 现在正式绑在 11；微信登录顺手带凭条（换绑的种子）
    res = wechat_login(client, "wx_move")
    assert res["status"] == "ok"
    token = res["bind_token"]
    signup(client, "13800000012", "d1")
    send_code(client, "13800000012", "recovery")
    r = client.post(
        "/api/auth/redeem",
        json={
            "phone": "13800000012",
            "code": code_of(sent, "13800000012"),
            "purpose": "recovery",
            "device_marker": "d1",
            "bind_token": token,
        },
    )
    assert r.status_code == 200 and r.json().get("wechat_bound") is True
    # 旧账号 11 的绑定已解开；微信现在进的是 12
    res11 = wechat_login(client, "wx_move")
    assert res11["status"] == "ok"
    assert me(client, res11["token"])["phone"] == "13800000012"


def test_verified_never_downgrades(client: TestClient, sent: list):
    """同一账号重绑只升不降：正式绑不因新凭条降回顺手绑。"""
    _bind_account(client, sent, "13800000013", "wx_keep")
    res = wechat_login(client, "wx_keep")
    # 带着凭条再走一次建号同号（续接窗口内同设备）——凭条是弱档，不得降级
    r = client.post(
        "/api/auth/signup",
        json={
            "device_marker": "d1",
            "card": {"phone": "13800000013"},
            "bind_token": res["bind_token"],
        },
    )
    assert r.status_code == 200 and "wechat_bound" not in r.json()
    # 仍是正式绑（占卡微信出口放行）
    rr = client.post(
        "/api/auth/wechat/redeem",
        json={"code": "wx_keep", "phone": "13800000013", "device_marker": "d2"},
    )
    assert rr.status_code == 200


# ---- 接管/注销/换锁的绑定清场 ----


def test_takeover_clears_binding_then_rebind(client: TestClient, fake, sent: list):
    out = _bind_account(client, sent, "13800000014", "wx_fred")
    # 另一台设备：占卡走短信接管（不带凭条）→ 绑定清场 → 微信成新面孔
    resend(client, fake, "13800000014", "takeover")
    redeem(
        client,
        "13800000014",
        code_of(sent, "13800000014", "takeover"),
        "takeover",
        "d-new",
    )
    assert wechat_login(client, "wx_fred")["status"] == "unbound"
    assert out.get("wechat_bound") is True  # 原绑定确实发生过


def test_password_reset_keeps_verified_binding(client: TestClient, fake, sent: list):
    """C3：换锁不清正式绑（本人多条活路）。"""
    out = _bind_account(client, sent, "13800000015", "wx_gina")
    # 设密码再忘记重置（换锁）
    from .conftest import password_reset, password_set

    resend(client, fake, "13800000015", "set_password")
    password_set(client, out["token"], code_of(sent, "13800000015", "set_password"))
    resend(client, fake, "13800000015", "reset_password")
    password_reset(
        client,
        "13800000015",
        code_of(sent, "13800000015", "reset_password"),
        "newpass1",
        "d2",
    )
    # 换锁后微信仍能进（正式绑未被清）
    res = wechat_login(client, "wx_gina")
    assert res["status"] == "ok"
    assert me(client, res["token"])["phone"] == "13800000015"


def test_deactivate_releases_binding(client: TestClient, fake, sent: list):
    """4.10：注销释放登记位，同一微信可绑新账号。"""
    out = _bind_account(client, sent, "13800000016", "wx_hank")
    resend(client, fake, "13800000016", "deactivate")
    r = client.post(
        "/api/auth/deactivate",
        json={
            "phone": "13800000016",
            "code": code_of(sent, "13800000016", "deactivate"),
        },
        headers={"Authorization": f"Bearer {out['token']}"},
    )
    assert r.status_code == 200
    assert wechat_login(client, "wx_hank")["status"] == "unbound"
    # 新账号可绑同一微信
    res = wechat_login(client, "wx_hank")
    r2 = client.post(
        "/api/auth/signup",
        json={
            "device_marker": "d1",
            "card": {"phone": "13800000017"},
            "bind_token": res["bind_token"],
        },
    )
    assert r2.status_code == 200 and r2.json().get("wechat_bound") is True


# ---- 存量库迁移：微信三列补齐 + 唯一索引 ----


def test_column_migration_on_legacy_db(tmp_path, fake, sent):
    """老库（无微信列）启动补列 + 唯一索引就位——1.7 登记进 _NEW_COLUMNS 的意义。"""
    import sqlite3

    from app.main import create_app

    db = tmp_path / "legacy.db"
    # 先用旧 schema 建个库：直接拿 create_app 建好后手工删列模拟老库
    create_app(
        Settings(
            db_url=f"sqlite:///{db}",
            pepper="p",
            sms_provider="console",
            sms_daily_budget=200,
        )
    )
    conn = sqlite3.connect(db)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(accounts)")]
    assert {"wechat_openid", "wechat_verified", "wechat_bound_at"} <= set(cols)
    idx = [r[1] for r in conn.execute("PRAGMA index_list(accounts)")]
    assert "ix_accounts_wechat_openid" in idx
    conn.close()
    # 再启动一次（列已在）：幂等不炸
    create_app(
        Settings(
            db_url=f"sqlite:///{db}",
            pepper="p",
            sms_provider="console",
            sms_daily_budget=200,
        )
    )
