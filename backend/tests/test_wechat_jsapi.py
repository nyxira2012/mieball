"""微信 JS-SDK 签证（2.10 B1）——官方算法锁、通道开关两层、票据缓存/过期/上游错、路由形状。

零真连微信：上游全由注入的假 fetcher 顶替，时钟走 conftest 的 FakeClock 拨过期。
跑法：cd backend && python -m pytest tests/test_wechat_jsapi.py -q
"""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.core import errors
from app.core.config import Settings
from app.services.wechat_jsapi import JsapiSigner, sign_string

# ---- 帮手 ----


def real_settings() -> Settings:
    """签证处只在 real 通道干活，测试里钥匙随便给（不会真发请求）。"""
    return Settings(
        db_url="sqlite:///:memory:",
        pepper="p",
        sms_provider="console",
        sms_daily_budget=200,
        wechat_provider="real",
        wechat_app_id="wx-app",
        wechat_app_secret="s3cret",
    )


class FakeFetch:
    """假上游：按端点回话并计数；ticket 可换值以证重取。"""

    def __init__(self, ticket: str = "T-1") -> None:
        self.calls: list[str] = []
        self.ticket = ticket

    def __call__(self, url: str) -> dict:
        self.calls.append(url)
        if "cgi-bin/token" in url:
            return {"access_token": "TK-1", "expires_in": 7200}
        return {"errcode": 0, "ticket": self.ticket, "expires_in": 7200}


# ---- 1. 官方样例向量锁算法 ----


def test_sign_string_official_vector():
    sig = sign_string(
        "sM4AOVdWfPE4DxkXGEs8VMCPGGVi4C3VM0P37wVUCFvkVAy_90u5h9nbSlYy3-Sl-HhTdfl2fzFy1AOcHKP7qg",
        "Wm3WZYTPz0wzccnW",
        1414587457,
        "http://mp.weixin.qq.com?params=value",
    )
    assert sig == "0f9de62fce790f9a083d5c99e95740ceb90c27ed"


# ---- 2. 通道关死：fake / real 缺钥匙 → wechat_off（直调与路由两层） ----


def test_off_when_fake_or_unconfigured(fake):
    fake_signer = JsapiSigner(replace(real_settings(), wechat_provider="fake"))
    with pytest.raises(errors.ApiError) as e1:
        fake_signer.sign("https://h/x")
    assert e1.value.code == "wechat_off" and e1.value.status_code == 503
    for patch in ({"wechat_app_id": ""}, {"wechat_app_secret": ""}):
        with pytest.raises(errors.ApiError) as ei:
            JsapiSigner(replace(real_settings(), **patch)).sign("https://h/x")
        assert ei.value.code == "wechat_off"


def test_route_off_maps_to_503(client: TestClient, monkeypatch):
    signer = JsapiSigner(replace(real_settings(), wechat_provider="fake"))
    monkeypatch.setattr("app.api.routes.wechat.get_signer", lambda: signer)
    r = client.get("/api/wechat/jsapi_sign", params={"url": "https://h/x"})
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "wechat_off"


# ---- 3. real + 假 fetcher：形状、缓存计数、拨钟过期、上游 errcode ----


def test_sign_shape_and_ticket_cache(fake):
    fetch = FakeFetch()
    signer = JsapiSigner(real_settings(), fetch_json=fetch)
    out = signer.sign("https://h/x?a=1")
    assert set(out) == {"app_id", "timestamp", "nonce_str", "signature"}
    assert out["app_id"] == "wx-app" and isinstance(out["timestamp"], int)
    # 签名确实由上游票算出：同一组四件套复算一致
    assert out["signature"] == sign_string(
        "T-1", out["nonce_str"], out["timestamp"], "https://h/x?a=1"
    )
    assert len(fetch.calls) == 2  # token + ticket 各一趟
    # 票据期内再签：换 nonce/timestamp 但零新上游调用
    out2 = signer.sign("https://h/y")
    assert len(fetch.calls) == 2
    assert (
        out2["nonce_str"] != out["nonce_str"] or out2["timestamp"] != out["timestamp"]
    )
    assert out2["signature"] == sign_string(
        "T-1", out2["nonce_str"], out2["timestamp"], "https://h/y"
    )


def test_ticket_refresh_on_expiry(fake):
    fetch = FakeFetch()
    signer = JsapiSigner(real_settings(), fetch_json=fetch)
    signer.sign("https://h/x")
    assert len(fetch.calls) == 2
    fake.advance(seconds=7200 - 300 - 1)  # 边距 300s 内最后 1 秒：仍吃缓存
    signer.sign("https://h/x")
    assert len(fetch.calls) == 2
    fake.advance(seconds=1)  # 过边距即过期
    fetch.ticket = "T-2"
    out = signer.sign("https://h/x")
    assert len(fetch.calls) == 4  # token + ticket 重取
    assert out["signature"] == sign_string(
        "T-2", out["nonce_str"], out["timestamp"], "https://h/x"
    )


def test_upstream_errcode_unavailable_no_cache(fake, caplog):
    class ErrThenOk:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self, url: str) -> dict:
            self.calls += 1
            if "cgi-bin/token" in url:
                return {"access_token": "TK-1", "expires_in": 7200}
            if self.calls == 2:  # 第一趟 ticket 报错
                return {"errcode": 40001, "errmsg": "credential expired"}
            return {"errcode": 0, "ticket": "T-ok", "expires_in": 7200}

    signer = JsapiSigner(real_settings(), fetch_json=ErrThenOk())
    with caplog.at_level(logging.WARNING), pytest.raises(errors.ApiError) as ei:
        signer.sign("https://h/x")
    assert ei.value.code == "wechat_unavailable" and ei.value.status_code == 503
    assert "40001" in caplog.text and "credential expired" in caplog.text
    # 失败不缓存：下一次开页再试即成功
    out = signer.sign("https://h/x")
    assert out["signature"] == sign_string(
        "T-ok", out["nonce_str"], out["timestamp"], "https://h/x"
    )


def test_upstream_network_error_unavailable(fake):
    def boom(url: str) -> dict:
        raise RuntimeError("dns gone")

    signer = JsapiSigner(real_settings(), fetch_json=boom)
    with pytest.raises(errors.ApiError) as ei:
        signer.sign("https://h/x")
    assert ei.value.code == "wechat_unavailable"


# ---- 4. 路由形状：monkeypatch get_signer → 200 四键；url 非空校验 ----


def test_route_sign_shape(client: TestClient, monkeypatch):
    signer = JsapiSigner(real_settings(), fetch_json=FakeFetch())
    monkeypatch.setattr("app.api.routes.wechat.get_signer", lambda: signer)
    r = client.get("/api/wechat/jsapi_sign", params={"url": "https://h/#/pages/game"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"app_id", "timestamp", "nonce_str", "signature"}
    assert body["app_id"] == "wx-app"
    # url 只要求非空：缺参与空串都 422，不做进一步白名单
    assert client.get("/api/wechat/jsapi_sign").status_code == 422
    assert client.get("/api/wechat/jsapi_sign", params={"url": ""}).status_code == 422
