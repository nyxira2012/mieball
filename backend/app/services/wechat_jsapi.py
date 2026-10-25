"""wechat_jsapi —— 微信 JS-SDK 签证处：页面地址换 wx.config 签名四件套。

向调用方隐藏 access_token/jsapi_ticket 的取件与缓存，只暴露 sign(url)。
与 services/wechat.py 是两族端点：那边 OAuth 换 openid 认人，这边 cgi 换
ticket 给页面签名，各住各家不互相塞。
"""

from __future__ import annotations

import hashlib
import logging
import threading
from collections.abc import Callable
from datetime import timedelta
from functools import lru_cache

from ..core import clock, errors, security
from ..core.config import Settings, get_settings
from .wechat_upstream import fetch_json_guarded, http_fetch_json

logger = logging.getLogger(__name__)

# cgi 族端点（基础凭据与 JS 票据；与 wechat.py 的 OAuth 族并列）
CGI_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
CGI_TICKET_URL = "https://api.weixin.qq.com/cgi-bin/ticket/getticket"

# 票据名义有效期提前 5 分钟作废：宁可早换一张，不给「签名算得出、微信已判过期」留缝
TICKET_MARGIN = timedelta(seconds=300)


def sign_string(ticket: str, nonce: str, timestamp: int, url: str) -> str:
    """官方算法：四键按字典序拼 kv 串后 sha1（非 keyed 哈希，hashlib 直用）。
    url 必须原样入串——微信按 wx.config 所在页面地址逐字验签，任何归一化都签错。"""
    plain = f"jsapi_ticket={ticket}&noncestr={nonce}&timestamp={timestamp}&url={url}"
    return hashlib.sha1(plain.encode()).hexdigest()


class JsapiSigner:
    """进程内的 ticket 持有人与签名口：sign(url) 出四件套，上游失败不缓存。"""

    def __init__(
        self, settings: Settings, fetch_json: Callable[[str], dict] | None = None
    ):
        self.settings = settings
        # 注入式上游（测试零 httpx mock 债）；默认取件器与小程序码族共用小件
        self._fetch_json = fetch_json or http_fetch_json
        self._lock = threading.Lock()
        self._ticket: str | None = None
        self._ticket_exp = clock.now()

    def sign(self, url: str) -> dict:
        """页面地址 → {app_id, timestamp, nonce_str, signature}（线上 snake_case）。
        通道未点亮（provider 非 real 或钥匙没配齐）按 wechat_off 关死——与登录
        通道同一张「即将开通」脸，前端按 code 静默降级到微信默认卡。"""
        if self.settings.wechat_provider != "real" or not (
            self.settings.wechat_app_id and self.settings.wechat_app_secret
        ):
            raise errors.wechat_off()
        ticket = self._ticket_now()
        # clock.now() 是 naive 北京墙钟，直接 .timestamp() 会按部署机本地时区换算
        # 而整体漂移——显式挂上东八区再取纪元秒
        timestamp = int(clock.now().replace(tzinfo=clock.CN_TZ).timestamp())
        nonce = security.new_nonce()
        return {
            "app_id": self.settings.wechat_app_id,
            "timestamp": timestamp,
            "nonce_str": nonce,
            "signature": sign_string(ticket, nonce, timestamp, url),
        }

    def _ticket_now(self) -> str:
        now = clock.now()
        # 换票全程持锁：并发首签排队换一次、后来者直接复用——两小时才一趟的活，
        # 不值得为它写双检/单飞；等价代价只是冷启动那拨请求多排几秒
        with self._lock:
            if self._ticket is not None and now < self._ticket_exp:
                return self._ticket
            token = fetch_json_guarded(
                self._fetch_json,
                CGI_TOKEN_URL,
                {
                    "grant_type": "client_credential",
                    "appid": self.settings.wechat_app_id,
                    "secret": self.settings.wechat_app_secret,
                },
                log_tag="jsapi",
            ).get("access_token")
            if not token:
                logger.warning("jsapi token ok-errcode 但缺 access_token")
                raise errors.wechat_unavailable()
            data = fetch_json_guarded(
                self._fetch_json,
                CGI_TICKET_URL,
                {"access_token": token, "type": "jsapi"},
                log_tag="jsapi",
            )
            ticket = data.get("ticket")
            try:
                expires_in = int(data.get("expires_in") or 0)
            except ValueError:
                expires_in = 0
            # expires_in 连边距都不够时缓存生来即过期，与缺票同罪按上游不可用挡回
            if not ticket or expires_in <= TICKET_MARGIN.total_seconds():
                logger.warning(
                    "jsapi ticket 响应缺 ticket/expires_in url=%s", CGI_TICKET_URL
                )
                raise errors.wechat_unavailable()
            self._ticket = str(ticket)
            self._ticket_exp = now + timedelta(seconds=expires_in) - TICKET_MARGIN
            return self._ticket


@lru_cache(maxsize=1)
def get_signer() -> JsapiSigner:
    """全进程共享的签证口（随 get_settings() 冻结）。缓存是进程内的：多 worker
    各持一份 ticket 各自两小时一换——微信侧 token 日配额 2000 次，每 worker 每日
    顶多十来次，几个 worker 也花不完，不值得为省这点去上共享仓。"""
    return JsapiSigner(get_settings())
