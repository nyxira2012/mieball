"""cgi 守卫小件（1.10 B2 修复批）——jsapi 与小程序码两族共用的取件把关。

三例锁形状：成功透传（URL 拼接）/ 网络异常归一 503 / errcode 挡回且日志不落
params 值（secret 不写墙）。两族的缓存与钥匙行为各归各的测试文件，此处只锁小件。
跑法：cd backend && python -m pytest tests/test_wechat_upstream.py -q
"""

from __future__ import annotations

import logging

import pytest

from app.core import errors
from app.services.wechat_upstream import fetch_json_guarded

BASE = "https://api.weixin.qq.com/cgi-bin/token"
PARAMS = {"grant_type": "client_credential", "appid": "wx-app", "secret": "s3cret"}


def test_success_passthrough_and_url_joining():
    seen: list[str] = []

    def fetch(url: str) -> dict:
        seen.append(url)
        return {"access_token": "TK-1", "expires_in": 7200}

    out = fetch_json_guarded(fetch, BASE, PARAMS, log_tag="jsapi")
    assert out["access_token"] == "TK-1"
    assert seen == [f"{BASE}?grant_type=client_credential&appid=wx-app&secret=s3cret"]


def test_network_error_maps_to_unavailable():
    def boom(url: str) -> dict:
        raise RuntimeError("dns gone")

    with pytest.raises(errors.ApiError) as ei:
        fetch_json_guarded(boom, BASE, PARAMS, log_tag="wxacode")
    assert ei.value.code == "wechat_unavailable" and ei.value.status_code == 503


def test_errcode_blocked_and_params_never_logged(caplog):
    def rejected(url: str) -> dict:
        return {"errcode": 40001, "errmsg": "credential expired"}

    with caplog.at_level(logging.WARNING), pytest.raises(errors.ApiError) as ei:
        fetch_json_guarded(rejected, BASE, PARAMS, log_tag="jsapi")
    assert ei.value.code == "wechat_unavailable"
    assert "40001" in caplog.text and BASE in caplog.text
    assert "s3cret" not in caplog.text  # 查询串带 secret，日志只许记端点路径
