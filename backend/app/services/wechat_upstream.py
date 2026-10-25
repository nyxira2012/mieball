"""wechat_upstream —— 微信 cgi GET-JSON 端点的取件与把关小件。

jsapi 签证与小程序码两族通道共用的无状态守卫（第二使用方出现即抽，塑形查3）：
URL 拼接、网络异常归一 wechat_unavailable、errcode≠0 挡回不缓存。两族经此小件
共享把关，但互不 import——通道各自的缓存/钥匙配置仍各住各家。
零 db、零 Settings：只认传入的 fetcher，谁调谁管配置。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from urllib.parse import urlencode

import httpx

from ..core import errors

logger = logging.getLogger(__name__)


def http_fetch_json(url: str) -> dict:
    """默认上游取件器：与钥匙门通道同款短超时——cgi 端点健康时秒回，上游瘫时
    不拖死 worker（5s 而非 httpx 默认，是两族通道实测下来的口径）。"""
    with httpx.Client(timeout=5.0) as client:
        return client.get(url).json()


def fetch_json_guarded(
    fetch_json: Callable[[str], dict], base: str, params: dict, *, log_tag: str
) -> dict:
    """取件与把关：网络异常 / errcode≠0 → warn 后按 wechat_unavailable 挡回
    （不缓存，由调用方下次触发再试）。日志只记端点路径与 tag、不记 params——
    token 端点的查询串带着 app_secret，进日志等于把钥匙写墙上。"""
    url = f"{base}?{urlencode(params)}"
    try:
        data = fetch_json(url)
    except Exception as exc:  # noqa: BLE001 - 网络层任何故障统一按上游不可用
        logger.warning("%s upstream fetch failed url=%s err=%r", log_tag, base, exc)
        raise errors.wechat_unavailable() from None
    if data.get("errcode"):
        logger.warning(
            "%s upstream rejected url=%s errcode=%s errmsg=%s",
            log_tag,
            base,
            data.get("errcode"),
            data.get("errmsg"),
        )
        raise errors.wechat_unavailable()
    return data
