"""小程序码发行处（1.10 B1/B2）——通道开关、scene 契约锁、token/同局码两级缓存、
上游 errcode 分流（token 失效清缓存不重试）、路由形状（401/422/503/200）。

零真连微信：上游全由注入的假 fetcher 顶替，时钟走 conftest 的 FakeClock 拨过期。
跑法：cd backend && python -m pytest tests/test_wechat_mp.py -q
"""

from __future__ import annotations

import base64
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.core import errors
from app.core.config import Settings
from app.services.wechat_mp import LIVE_PAGE, SCENE_PREFIX, WxacodeMaker

from .conftest import signup

PNG = b"\x89PNG\r\n\x1a\nfake-wxacode-bytes"


# ---- 帮手 ----


def real_settings(**over: str) -> Settings:
    """发行处只在 real 通道干活，测试里小程序对钥匙随便给（不会真发请求）。"""
    base: dict[str, str | int] = {
        "db_url": "sqlite:///:memory:",
        "pepper": "p",
        "sms_provider": "console",
        "sms_daily_budget": "200",
        "wechat_provider": "real",
        "wechat_app_id": "wx-app",
        "wechat_app_secret": "s3cret",
        "wechat_mp_app_id": "wx-mp",
        "wechat_mp_app_secret": "mp-s3cret",
    }
    base.update(over)
    return Settings(**base)


class FakeUpstream:
    """假微信：token 走 GET、码走 POST，全程计数；码响应可切「图/errcode」。"""

    def __init__(self) -> None:
        self.json_calls: list[str] = []
        self.post_calls: list[dict] = []
        self.reply: bytes | tuple[bytes, str] = (PNG, "image/png")

    def fetch_json(self, url: str) -> dict:
        self.json_calls.append(url)
        assert "cgi-bin/token" in url and "wx-mp" in url and "mp-s3cret" in url
        return {"access_token": "TK-1", "expires_in": 7200}

    def fetch_bytes(self, url: str, body: dict) -> tuple[bytes, str]:
        self.post_calls.append(body)
        assert "getwxacodeunlimit" in url and "access_token=TK-1" in url
        if isinstance(self.reply, tuple):
            return self.reply
        return self.reply, "application/json"


def maker(settings: Settings | None = None, upstream: FakeUpstream | None = None):
    up = upstream or FakeUpstream()
    return WxacodeMaker(settings or real_settings(), up.fetch_json, up.fetch_bytes), up


# ---- 1. 跨端契约字面量锁（前端 live.vue 按同一写法解析 scene） ----


def test_scene_contract_literals():
    assert SCENE_PREFIX == "g="
    assert LIVE_PAGE == "pages/live/live"


# ---- 2. 通道关死：fake / real 缺小程序对钥匙 → wechat_off（直调与路由两层） ----


def test_off_when_fake_or_mp_pair_missing(fake):
    for patch in (
        {"wechat_provider": "fake"},
        {"wechat_mp_app_id": ""},
        {"wechat_mp_app_secret": ""},
    ):
        with pytest.raises(errors.ApiError) as ei:
            WxacodeMaker(real_settings(**patch)).wxacode(7)
        assert ei.value.code == "wechat_off" and ei.value.status_code == 503


def test_route_off_maps_to_503(client: TestClient, monkeypatch):
    m, _ = maker(replace(real_settings(), wechat_provider="fake"))
    monkeypatch.setattr("app.api.routes.wechat.get_wxacode_maker", lambda: m)
    tok = signup(client, "13800001234", "dev-1")["token"]
    r = client.get(
        "/api/wechat/wxacode",
        params={"game_id": 7},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "wechat_off"


# ---- 3. real + 假上游：图字节往返、请求 body 契约、token/同局码两级缓存 ----


def test_route_shape_and_body_contract(client: TestClient, fake, monkeypatch):
    m, up = maker()
    monkeypatch.setattr("app.api.routes.wechat.get_wxacode_maker", lambda: m)
    tok = signup(client, "13800001234", "dev-1")["token"]
    r = client.get(
        "/api/wechat/wxacode",
        params={"game_id": 7},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200, r.text
    assert set(r.json()) == {"image_b64"}
    assert base64.b64decode(r.json()["image_b64"]) == PNG
    body = up.post_calls[0]
    assert body["scene"] == "g=7" and body["page"] == LIVE_PAGE
    assert body["check_path"] is False
    assert body["env_version"] == "release" and body["width"] == 430


def test_token_cached_across_games_and_code_cached_per_game(fake):
    m, up = maker()
    m.wxacode(7)
    m.wxacode(8)  # 另一局：码各取各的，token 只有一份
    assert len(up.json_calls) == 1 and len(up.post_calls) == 2
    m.wxacode(7)  # 同局 600s 内直回缓存：token 与码都零新请求
    assert len(up.json_calls) == 1 and len(up.post_calls) == 2
    fake.advance(seconds=601)  # 过同局复用窗：重打一次码，token 仍在两小时窗内
    assert m.wxacode(7) == PNG
    assert len(up.json_calls) == 1 and len(up.post_calls) == 3


def test_token_refresh_after_margin(fake):
    m, up = maker()
    m.wxacode(7)
    assert len(up.json_calls) == 1
    fake.advance(seconds=7200 - 300)  # 过 7200-300s：余量恰被边距吃光，重取
    m.wxacode(8)
    assert len(up.json_calls) == 2


# ---- 4. 上游失败：errcode 分流——token 失效清缓存、其余原样挡回；失败不缓存 ----


def test_errcode_unavailable_and_not_cached(fake):
    m, up = maker()
    m.wxacode(7)
    up.reply = b'{"errcode": 45009, "errmsg": "reach max api daily quota"}'
    with pytest.raises(errors.ApiError) as ei:
        m.wxacode(8)
    assert ei.value.code == "wechat_unavailable" and ei.value.status_code == 503
    # 非 token 类 errcode：token 缓存保留，失败码不缓存（下次点击再打）
    assert len(up.json_calls) == 1
    up.reply = (PNG, "image/png")
    assert m.wxacode(8) == PNG and len(up.post_calls) == 3


def test_stale_token_cleared_no_retry_then_refetched(fake):
    m, up = maker()
    m.wxacode(7)
    fake.advance(seconds=601)  # 出同局码复用窗，逼下一趟真打码
    up.reply = b'{"errcode": 42001, "errmsg": "access_token expired"}'
    with pytest.raises(errors.ApiError) as ei:
        m.wxacode(7)  # 本次 503 且不连环重试
    assert ei.value.code == "wechat_unavailable"
    assert len(up.json_calls) == 1 and len(up.post_calls) == 2
    up.reply = (PNG, "image/png")
    assert m.wxacode(7) == PNG  # 下次点击：token 缓存已清，自然重取后再取码
    assert len(up.json_calls) == 2 and len(up.post_calls) == 3


def test_upstream_network_error_unavailable(fake):
    def boom(url: str, body: dict) -> tuple[bytes, str]:
        raise RuntimeError("dns gone")

    def ok_json(url: str) -> dict:
        return {"access_token": "TK-1", "expires_in": 7200}

    m = WxacodeMaker(real_settings(), ok_json, boom)
    with pytest.raises(errors.ApiError) as ei:
        m.wxacode(7)
    assert ei.value.code == "wechat_unavailable"
    with pytest.raises(errors.ApiError) as ei2:  # 失败不缓存
        m.wxacode(7)
    assert ei2.value.code == "wechat_unavailable"


# ---- 5. 路由守卫：未登录 401、game_id 非正整数 422 ----


def test_route_requires_login_and_positive_game_id(client: TestClient, monkeypatch):
    m, _ = maker()
    monkeypatch.setattr("app.api.routes.wechat.get_wxacode_maker", lambda: m)
    assert client.get("/api/wechat/wxacode", params={"game_id": 7}).status_code == 401
    tok = signup(client, "13800001234", "dev-1")["token"]
    assert (
        client.get(
            "/api/wechat/wxacode",
            params={"game_id": 0},
            headers={"Authorization": f"Bearer {tok}"},
        ).status_code
        == 422
    )
