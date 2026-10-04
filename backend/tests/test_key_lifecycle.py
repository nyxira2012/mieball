"""钥匙生命周期 —— 评审 D4 规则的验收面：
建号 → 找回杀未验证钥匙 → 多台已验证共存 → 接管杀全部（含前主人已验证钥匙）→ 注销全失效。
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import code_of, me, redeem, send_code, signup


def _code(sent, phone, purpose="recovery"):
    return code_of(sent, phone, purpose)


def test_recovery_kills_squatters_unverified_key(client: TestClient, sent):
    """冒填者占号后，真主人走"找回"也能把冒填者的钥匙踢掉（D4 补的口子）。"""
    squatter = signup(client, "13800001111", "dev-squatter")["token"]
    send_code(client, "13800001111", "recovery")
    owner = redeem(client, "13800001111", _code(sent, "13800001111"), "recovery", "dev-owner")
    assert me(client, squatter) is None            # 冒填者的未验证钥匙已作废
    assert me(client, owner["token"]) is not None  # 真主人进来了


def test_verified_keys_coexist_across_recoveries(client: TestClient, sent, fake):
    """真主人多台设备各自找回后共存：已验证钥匙不被后续找回误杀（D4 的另一半）。"""
    signup(client, "13800002222", "dev-1")
    send_code(client, "13800002222", "recovery")
    d2 = redeem(client, "13800002222", _code(sent, "13800002222"), "recovery", "dev-2")

    fake.advance(seconds=61)                       # 过 60 秒冷却再给第二台发码
    send_code(client, "13800002222", "recovery")
    d3 = redeem(client, "13800002222", _code(sent, "13800002222"), "recovery", "dev-3")

    assert me(client, d2["token"]) is not None     # 早先验证过的设备不被踢
    assert me(client, d3["token"]) is not None


def test_takeover_kills_even_verified_keys_and_merges_card(client: TestClient, sent, fake):
    """接管=号码易主：前主人（含已验证）钥匙全清场；真主人名片按显式标志覆盖（D5）。"""
    signup(client, "13800003333", "dev-old")
    send_code(client, "13800003333", "recovery")
    old_verified = redeem(client, "13800003333", _code(sent, "13800003333"), "recovery", "dev-old2")

    fake.advance(seconds=61)
    send_code(client, "13800003333", "takeover")
    new_owner = redeem(
        client, "13800003333", _code(sent, "13800003333", "takeover"), "takeover", "dev-new",
        card={"phone": "13800003333", "nickname": "真主人", "nickname_set": True, "chibi": {"skin": 2}, "chibi_set": False},
    )
    acc = new_owner["account"]
    assert acc["name"] == "真主人"                  # 填过的昵称覆盖冒填者起的
    assert me(client, old_verified["token"]) is None  # 前主人已验证钥匙也被清（号码回收场景）
    assert me(client, new_owner["token"]) is not None
    # chibi_set=False → 不覆盖：形象保持原账号的默认（D5：只动用户明确填过的字段）
    from app.services.accounts import DEFAULT_CHIBI  # noqa: PLC0415

    assert acc["chibi"] == DEFAULT_CHIBI


def test_signup_key_is_unverified_and_dies_on_any_sms_verify(client: TestClient, sent):
    """自己首台设备（报名直发、未验证）在首次短信验证后也要重拿钥匙（D4 的已知代价）。"""
    first = signup(client, "13800004444", "dev-1")
    send_code(client, "13800004444", "recovery")
    redeem(client, "13800004444", _code(sent, "13800004444"), "recovery", "dev-2")
    assert me(client, first["token"]) is None
