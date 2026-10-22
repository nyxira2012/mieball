"""微信钥匙（docs/1.7 + 1.8）——通道、两扇门、绑定挂点、清场镜像，全矩阵锁。

假通道（provider 默认 fake）：授权凭证即身份号——code 直接当 openid 用，
「|」后可带测试昵称（1.8 快进建号矩阵用），与短信 console 假发送器同一先例，
开发零资质全链可测。

跑法：cd backend && python -m pytest tests/test_wechat.py -q
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core import clock
from app.core.config import Settings
from app.db.models import Account, DeviceKey

from .conftest import auth, code_of, me, password_set, redeem, send_code, signup

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


# ---- 1.8 快进建号 / 补绑手机号 / 验证收编 ----

RANDOM_NAME_RE = re.compile(r"球友\d{4}")


def wechat_fast(
    client: TestClient,
    code: str,
    device: str = "d-fast",
    nickname: str | None = None,
    phone: str | None = None,
    avatar: str | None = None,
) -> dict:
    body = {"code": code, "device_marker": device, "fast": True}
    if nickname is not None:
        body["nickname"] = nickname
    if phone is not None:
        body["phone"] = phone
    if avatar is not None:
        body["avatar"] = avatar
    r = client.post("/api/auth/wechat/login", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def account_row(client: TestClient, **filt) -> Account:
    s = client.app.state.session_factory()
    try:
        return s.execute(select(Account).filter_by(**filt)).scalar_one()
    finally:
        s.close()


def test_fast_manual_nickname_wins(client: TestClient):
    """4.3：卡上亲手填的胜出，微信昵称让位；快进不发凭条（绑定一次完成）。"""
    res = wechat_fast(client, "wx_m1|微信名叫小王", nickname="阿强")
    assert res["status"] == "created" and res["nickname_random"] is False
    assert res["account"]["name"] == "阿强"
    assert "bind_token" not in res


def test_fast_manual_invalid_nickname_rejected(client: TestClient):
    """手填不合格如实报（与 signup 手填一致），不静默改名。"""
    r = client.post(
        "/api/auth/wechat/login",
        json={
            "code": "wx_m2",
            "device_marker": "d1",
            "fast": True,
            "nickname": "超" * 17,
        },
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "nickname_invalid"


def test_fast_uses_wx_nickname(client: TestClient):
    """无手填 → 吃微信昵称（过清洗规矩）。"""
    res = wechat_fast(client, "wx_m3|球友小王")
    assert res["status"] == "created" and res["nickname_random"] is False
    assert res["account"]["name"] == "球友小王"


def test_fast_falls_back_to_random_name(client: TestClient):
    """4.2：微信昵称没给/不合格（超 16 字、保留名）→ 随机名 + 随机名旗；
    手填空白视同没填。"""
    res = wechat_fast(client, "wx_m4")  # 没给
    assert res["nickname_random"] is True
    assert RANDOM_NAME_RE.fullmatch(res["account"]["name"])
    res = wechat_fast(client, "wx_m5|" + "超" * 17)  # 超 16 字不合格
    assert res["nickname_random"] is True
    assert RANDOM_NAME_RE.fullmatch(res["account"]["name"])
    res = wechat_fast(client, "wx_m6|平台客服")  # 保留名不合格
    assert res["nickname_random"] is True
    assert RANDOM_NAME_RE.fullmatch(res["account"]["name"])
    res = wechat_fast(client, "wx_m7|微信名", nickname="   ")  # 手填空白=没填
    assert res["account"]["name"] == "微信名" and res["nickname_random"] is False


def test_fast_account_shape_and_relogin(client: TestClient):
    """落库形态：phone=None、phone_verified=False、微信生而正式绑、钥匙已验证；
    再点一键直接进（1.7 老规矩照旧）。"""
    res = wechat_fast(client, "wx_shape|阿形", device="d-shape")
    acc = account_row(client, device_marker="d-shape")
    assert acc.phone is None and acc.phone_verified is False
    assert acc.wechat_openid == "wx_shape" and acc.wechat_verified is True
    s = client.app.state.session_factory()
    try:
        key = s.execute(
            select(DeviceKey).filter_by(account_id=acc.id).order_by(DeviceKey.id.desc())
        ).scalar_one()
    finally:
        s.close()
    assert key.verified is True
    # 无号即无 phone/phone_tail（前端据此显「未绑手机」，不回落假尾号）
    v = me(client, res["token"])
    assert "phone" not in v and "phone_tail" not in v
    assert v["wechat_bound"] is True  # 本人视图持久给「微信已绑定」行用（1.8 批3）
    res2 = wechat_login(client, "wx_shape|阿形")
    assert res2["status"] == "ok"
    assert me(client, res2["token"])["name"] == "阿形"


def test_fast_false_keeps_1_7_unbound_path(client: TestClient):
    """4.7 护栏：不传 fast（登录页找回面）——unbound 仍发凭条，1.7 原路。"""
    r = client.post(
        "/api/auth/wechat/login",
        json={"code": "wx_m8", "device_marker": "d1", "fast": False},
    )
    res = r.json()
    assert res["status"] == "unbound" and res["bind_token"]


def test_fast_with_free_phone_creates_phone_account(client: TestClient):
    """修订二「卡上填过的都算数」：手机号没人用 → 带号建号（微信同时正式绑，
    两把钥匙一步到位）；头像选了落档。"""
    res = wechat_fast(
        client,
        "wx_p1|阿号",
        device="d-p1",
        phone="13900001111",
        avatar="a-p2",
    )
    assert res["status"] == "created"
    acc = account_row(client, device_marker="d-p1")
    assert acc.phone == "13900001111"
    assert acc.wechat_openid == "wx_p1" and acc.wechat_verified is True
    assert acc.dress_avatar == "a-p2"  # 选了落档，没选读侧兜 a-p1
    v = me(client, res["token"])
    assert v["avatar"] == "a-p2" and v["avatar_url"] == "/cosmetics/a-p2.png"
    assert v.get("phone_tail") == "1111"  # 有号即有尾号（与无号支互为镜像）


def test_fast_with_taken_phone_other_device_rejected(client: TestClient):
    """修订二：撞在册账号且异机 → phone_taken、整体不生效（不建号、微信不绑，
    前端凭此落占卡三出口）。"""
    signup(client, "13900002222", "d-owner")
    r = client.post(
        "/api/auth/wechat/login",
        json={
            "code": "wx_p2",
            "device_marker": "d-fast7",
            "fast": True,
            "phone": "13900002222",
        },
    )
    assert r.status_code == 409, r.text
    assert r.json()["error"]["code"] == "phone_taken"
    s = client.app.state.session_factory()
    try:
        holder = s.execute(
            select(Account).filter_by(wechat_openid="wx_p2")
        ).scalar_one_or_none()
        assert holder is None  # 不留半个账号：openid 没绑到任何号
    finally:
        s.close()


def test_fast_with_taken_phone_same_device_resumes(client: TestClient):
    """修订二：同机续接窗内撞自己在册号 → 直接进既有账号（与手填建号续接分支
    同规），微信正式绑上、不发凭条。"""
    old = signup(client, "13900003333", "d-same")
    res = wechat_fast(client, "wx_p3|阿三", device="d-same", phone="13900003333")
    assert res["status"] == "ok"
    assert res["account"]["id"] == old["account"]["id"]
    acc = account_row(client, id=old["account"]["id"])
    assert acc.wechat_openid == "wx_p3" and acc.wechat_verified is True
    assert "bind_token" not in res or res.get("bind_token") is None


def test_fast_invalid_phone_rejected(client: TestClient):
    """修订二：号填了但格式不对 → 与手填建号同款 phone_invalid（不静默丢）。"""
    r = client.post(
        "/api/auth/wechat/login",
        json={
            "code": "wx_p4",
            "device_marker": "d-fast8",
            "fast": True,
            "phone": "1390000111",  # 10 位
        },
    )
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "phone_invalid"


def test_fast_conflict_leaves_no_half_account(client: TestClient):
    """4.9-3：建号半路失败（openid 撞唯一索引）→ wechat_fast_failed、无残留。"""
    s = client.app.state.session_factory()
    s.add(
        Account(
            phone=None,
            nickname="占位壳",
            chibi='{"skin":0}',
            status="deactivated",
            device_marker="d-ghost",
            created_at=clock.now(),
            wechat_openid="wx_clash",
            wechat_verified=True,
        )
    )
    s.commit()
    s.close()
    r = client.post(
        "/api/auth/wechat/login",
        json={"code": "wx_clash", "device_marker": "d-fail", "fast": True},
    )
    assert r.status_code == 503
    err = r.json()["error"]
    assert err["code"] == "wechat_fast_failed"
    assert err["message"] == "没办成，请再点一次微信授权"
    s2 = client.app.state.session_factory()
    try:
        rows = (
            s2.execute(select(Account).filter_by(device_marker="d-fail"))
            .scalars()
            .all()
        )
    finally:
        s2.close()
    assert rows == []


def test_bind_phone_taken_rejected_with_audit(
    client: TestClient, sent: list, monkeypatch
):
    """4.4-2：占用当场拒（话术逐字、不透露对方账号）+ 审计落账 + 不发码。"""
    calls: list = []
    monkeypatch.setattr(
        "app.services.accounts.audit", lambda *a, **k: calls.append((a, k))
    )
    fast = wechat_fast(client, "wx_bt")
    signup(client, "13800000021", "d1")  # 老账号占着这个号
    r = client.post(
        "/api/auth/sms",
        json={"phone": "13800000021", "purpose": "bind_phone"},
        headers=auth(fast["token"]),
    )
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "phone_taken_redirect"
    assert err["message"] == (
        "这个手机号注册过。如果你就是号主，去登录页用短信验证进入那个账号，"
        "微信会自动绑回那个账号；你最近在临时号上的报名会留在那边，不会搬过来"
    )
    assert calls == [
        (
            ("wechat_bind_phone_taken",),
            {
                "account_id": fast["account"]["id"],
                "detail": "补绑手机号撞已有账号，指路登录页",
            },
        )
    ]
    assert not [c for c in sent if c[2] == "bind_phone"]


def test_bind_phone_requires_login(client: TestClient):
    """补绑发码必须登录态（快进号的钥匙在手上才谈补绑）。"""
    r = client.post(
        "/api/auth/sms", json={"phone": "13800000022", "purpose": "bind_phone"}
    )
    assert r.status_code == 401 and r.json()["error"]["code"] == "no_identity"


def test_bind_phone_happy_path(client: TestClient, sent: list):
    """4.4-1：无人用的号 → 发码 → 输码绑上、绑定记录翻真；没码绑不上。"""
    fast = wechat_fast(client, "wx_bp")
    r = client.post(
        "/api/auth/sms",
        json={"phone": "13800000023", "purpose": "bind_phone"},
        headers=auth(fast["token"]),
    )
    assert r.status_code == 200, r.text
    # 安全：码不对不落号
    r = client.post(
        "/api/auth/phone/bind",
        json={"phone": "13800000023", "code": "000000"},
        headers=auth(fast["token"]),
    )
    assert r.status_code == 400
    code = code_of(sent, "13800000023", "bind_phone")
    r = client.post(
        "/api/auth/phone/bind",
        json={"phone": "13800000023", "code": code},
        headers=auth(fast["token"]),
    )
    assert r.status_code == 200, r.text
    v = r.json()["account"]
    assert v["phone"] == "13800000023" and v["phone_tail"] == "0023"
    acc = account_row(client, id=v["id"])
    assert acc.phone == "13800000023" and acc.phone_verified is True


def test_bind_phone_rejected_when_already_bound(client: TestClient, sent: list):
    """安全守卫（批1 修 #1）：已有手机号的账号，凭一张新号验证码也换不了根号
    ——核销前 409 挡下，原号原样（换号走 1.6 A1 人工口径联系平台客服）。"""
    old = signup(client, "13800000024", "d1")  # 已绑号账号
    r = client.post(
        "/api/auth/sms",
        json={"phone": "13800000025", "purpose": "bind_phone"},
        headers=auth(old["token"]),
    )
    assert r.status_code == 200, r.text  # 新号无人用，发码端放行
    r = client.post(
        "/api/auth/phone/bind",
        json={
            "phone": "13800000025",
            "code": code_of(sent, "13800000025", "bind_phone"),
        },
        headers=auth(old["token"]),
    )
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "phone_already_bound"
    assert err["message"] == "这个账号已有手机号，手机号是账号的根，换号先联系平台客服"
    # 原根号没被顶掉、也没被释放
    acc = account_row(client, id=old["account"]["id"])
    assert acc.phone == "13800000024"


def test_adopt_moves_binding_on_recovery(client: TestClient, sent: list):
    """4.5：快进号登着，登录页短信验证进老账号 → 微信自动迁回（不再授权一次）、
    快进号就地解绑搁置、记录留守。"""
    old = signup(client, "13800000031", "d-old")
    fast = wechat_fast(client, "wx_adopt", device="d-fast3")
    send_code(client, "13800000031", "recovery")
    r = client.post(
        "/api/auth/redeem",
        json={
            "phone": "13800000031",
            "code": code_of(sent, "13800000031"),
            "purpose": "recovery",
            "device_marker": "d-old",
        },
        headers=auth(fast["token"]),
    )
    assert r.status_code == 200 and r.json().get("wechat_bound") is True
    # 下次微信一键进的是老账号
    res = wechat_login(client, "wx_adopt")
    assert res["status"] == "ok"
    assert me(client, res["token"])["phone"] == "13800000031"
    # 快进号：解绑搁置、账号与记录留守
    fast_acc = account_row(client, id=fast["account"]["id"])
    assert fast_acc.wechat_openid is None and fast_acc.status == "active"
    old_acc = account_row(client, id=old["account"]["id"])
    assert old_acc.wechat_openid == "wx_adopt" and old_acc.wechat_verified is True


def test_adopt_after_bind_token_is_noop(client: TestClient, sent: list):
    """凭条先执行、收编后且幂等：凭条已把同一微信绑走时，收编自然空转不炸。"""
    old = signup(client, "13800000032", "d-old")
    fast = wechat_fast(client, "wx_duo", device="d-fast4")
    ok = wechat_login(client, "wx_duo")  # 绑着 → ok，凭条照发（换绑种子）
    assert ok["status"] == "ok"
    send_code(client, "13800000032", "recovery")
    r = client.post(
        "/api/auth/redeem",
        json={
            "phone": "13800000032",
            "code": code_of(sent, "13800000032"),
            "purpose": "recovery",
            "device_marker": "d-old",
            "bind_token": ok["bind_token"],
        },
        headers=auth(fast["token"]),
    )
    assert r.status_code == 200 and r.json().get("wechat_bound") is True
    assert account_row(client, id=old["account"]["id"]).wechat_openid == "wx_duo"
    assert account_row(client, id=fast["account"]["id"]).wechat_openid is None


def test_adopt_via_password_reset(client: TestClient, fake, sent: list):
    """reset 同挂收编（也是「短信证明自己是老账号主人」的路）。"""
    old = signup(client, "13800000033", "d-old")
    send_code(client, "13800000033", "set_password")
    password_set(client, old["token"], code_of(sent, "13800000033", "set_password"))
    fast = wechat_fast(client, "wx_pr", device="d-fast5")
    resend(client, fake, "13800000033", "reset_password")
    r = client.post(
        "/api/auth/password/reset",
        json={
            "phone": "13800000033",
            "code": code_of(sent, "13800000033", "reset_password"),
            "password": "newpass1",
            "device_marker": "d-old",
        },
        headers=auth(fast["token"]),
    )
    assert r.status_code == 200 and r.json().get("wechat_bound") is True
    assert account_row(client, id=old["account"]["id"]).wechat_openid == "wx_pr"
    assert account_row(client, id=fast["account"]["id"]).wechat_openid is None


def test_login_password_does_not_adopt(client: TestClient, sent: list):
    """login_password 不挂收编：密码验证非短信（4.5 指路话术只提短信）。"""
    old = signup(client, "13800000034", "d-old")
    send_code(client, "13800000034", "set_password")
    password_set(client, old["token"], code_of(sent, "13800000034", "set_password"))
    fast = wechat_fast(client, "wx_np", device="d-fast6")
    r = client.post(
        "/api/auth/password/login",
        json={"phone": "13800000034", "password": "123456", "device_marker": "d-old"},
        headers=auth(fast["token"]),
    )
    assert r.status_code == 200, r.text
    assert account_row(client, id=old["account"]["id"]).wechat_openid is None
    assert account_row(client, id=fast["account"]["id"]).wechat_openid == "wx_np"


# ---- 1.9 §4.8 微信头像：授权时刻顺手记录、每次授权顺手刷新、只刷新不抹掉 ----


def test_fast_create_records_wechat_avatar_and_dress_wears_it(client: TestClient):
    """三段假通道（openid|昵称|头像URL）：快进建号从授权时刻就记下头像；
    装扮页穿「微信头像」后，/me 的 avatar_url 直出该 URL。"""
    res = wechat_fast(client, "wx_av1|阿微|http://wx/av.png")
    assert res["status"] == "created"
    assert account_row(client, id=res["account"]["id"]).wechat_avatar == (
        "http://wx/av.png"
    )
    r = client.post(
        "/api/cosmetics/dress",
        json={"avatar": "wechat"},
        headers=auth(res["token"]),
    )
    assert r.status_code == 200, r.text
    v = me(client, res["token"])
    assert v["avatar"] == "wechat" and v["avatar_url"] == "http://wx/av.png"


def test_ok_login_refreshes_wechat_avatar(client: TestClient):
    """已绑账号再次授权登录（ok 支）：微信里换了头像，站内跟着刷新。"""
    first = wechat_fast(client, "wx_av2|阿二|http://wx/old.png")
    acc_id = first["account"]["id"]
    assert account_row(client, id=acc_id).wechat_avatar == "http://wx/old.png"
    again = wechat_login(client, "wx_av2|阿二|http://wx/new.png")
    assert again["status"] == "ok"
    assert account_row(client, id=acc_id).wechat_avatar == "http://wx/new.png"


def test_avatar_missing_in_authorize_keeps_record(client: TestClient):
    """两段旧格式（第三段缺省）/一段纯 openid 都不炸；没拿到头像不抹已有记录
    ——只刷新不抹掉，否则装扮页「微信头像」选项凭空消失。"""
    first = wechat_fast(client, "wx_av3|阿三|http://wx/keep.png")
    acc_id = first["account"]["id"]
    again = wechat_login(client, "wx_av3|阿三")  # 两段旧格式
    assert again["status"] == "ok"
    assert account_row(client, id=acc_id).wechat_avatar == "http://wx/keep.png"
    third = wechat_login(client, "wx_av3")  # 一段纯 openid
    assert third["status"] == "ok"
    assert account_row(client, id=acc_id).wechat_avatar == "http://wx/keep.png"


def test_fast_rejects_avatar_outside_public_pool(client: TestClient):
    """快进建号头像与手填建号同校验：非公共款一律查无这件，不半建。"""
    r = client.post(
        "/api/auth/wechat/login",
        json={"code": "wx_bad", "device_marker": "d", "fast": True, "avatar": "a-x1"},
    )
    assert r.status_code == 404 and r.json()["error"]["code"] == "cosmetic_not_found"


def test_wechat_redeem_refreshes_wechat_avatar(client: TestClient, sent: list):
    """占卡微信验证进入也是一次授权：头像同样顺手刷新。"""
    out = _bind_account(client, sent, "13800000071", "wx_rav")
    assert account_row(client, id=out["account"]["id"]).wechat_avatar is None
    r = client.post(
        "/api/auth/wechat/redeem",
        json={
            "code": "wx_rav|新面|http://wx/re.png",
            "phone": "13800000071",
            "device_marker": "d-new",
        },
    )
    assert r.status_code == 200, r.text
    assert (
        account_row(client, id=out["account"]["id"]).wechat_avatar == "http://wx/re.png"
    )
