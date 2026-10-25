"""wechat_mp —— 小程序码发行处：局编号换微信小程序码 PNG。

与 wechat_jsapi 平行的一族 cgi 通道：那边公众号 AppID 换 JS 签名，这边小程序
AppID 换小程序码。向调用方隐藏 access_token 的取件与缓存、同局码的短时复用，
只暴露 wxacode(game_id)。失败一律 503（wechat_off / wechat_unavailable），不缓存
失败结果、不连环重试——前端按 code 退回网页链接码兜底。
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from datetime import datetime, timedelta
from functools import lru_cache
from urllib.parse import urlencode

import httpx

from ..core import clock, errors
from ..core.config import Settings, get_settings
from .wechat_upstream import fetch_json_guarded, http_fetch_json

logger = logging.getLogger(__name__)

# 跨端深链契约：后端拼 scene、小程序端 live.vue onLoad 解码后按此前缀取局编号，
# 两端字面量互锁（改一个必须连着改另一个，测试各有锁值断言）
SCENE_PREFIX = "g="
LIVE_PAGE = "pages/live/live"

TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
WXACODE_URL = "https://api.weixin.qq.com/wxa/getwxacodeunlimit"

# token 名义有效期提前 5 分钟作废：宁可早换一张，不给「码还在缓存、token 已被
# 微信判过期」留缝（与 jsapi ticket 同款边距）
TOKEN_MARGIN = timedelta(seconds=300)
# 同局码复用窗口：现场频繁开关二维码浮层是常态，一局内反复取码不该每次都打微信
CODE_TTL = timedelta(seconds=600)

# getwxacodeunlimit 用旧 token 调用时回的 errcode——token 缓存已不可信，清掉
# 待下次点击重取；其余 errcode（配额/参数类）与 token 无关，缓存保留
TOKEN_STALE_ERRCODES = {40001, 42001}


class WxacodeMaker:
    """进程内的小程序码口：token 两小时一换、同局码十分钟一换，上游失败不缓存。"""

    def __init__(
        self,
        settings: Settings,
        fetch_json: Callable[[str], dict] | None = None,
        fetch_bytes: Callable[[str, dict], tuple[bytes, str]] | None = None,
    ):
        self.settings = settings
        # 注入式上游（测试零 httpx mock 债）：fetch_json 取 token、fetch_bytes
        # 发码请求（POST，带 JSON body），默认取件器与 jsapi 共用小件
        self._fetch_json = fetch_json or http_fetch_json
        self._fetch_bytes = fetch_bytes or self._http_fetch_bytes
        self._lock = threading.Lock()
        self._token: str | None = None
        self._token_exp = clock.now()
        # 同局码缓存 game_id -> (png_bytes, exp)；过期项在写入新码时顺手扫掉，
        # 字典不随进程寿命无界长
        self._codes: dict[int, tuple[bytes, datetime]] = {}

    @staticmethod
    def _http_fetch_bytes(url: str, body: dict) -> tuple[bytes, str]:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, json=body)
            return resp.content, resp.headers.get("content-type", "")

    def wxacode(self, game_id: int) -> bytes:
        """局编号 → 小程序码 PNG 字节（scene "g=<id>"，扫开直达现场页深链）。

        只读不写：码是深链载体，不查局是否存在、不落任何库——生成失败也不弄脏
        球局/账单/战力。通道未点亮（provider 非 real 或小程序对钥匙未配）按
        wechat_off 关死——与登录通道同一张「即将开通」脸，前端按 code 退链接码。
        fake 通道下同样关死而非伪造一张假码：让前端的兜底路在开发期全程可测。
        """
        if self.settings.wechat_provider != "real" or not (
            self.settings.wechat_mp_app_id and self.settings.wechat_mp_app_secret
        ):
            raise errors.wechat_off()
        now = clock.now()
        cached = self._codes.get(game_id)
        if cached and now < cached[1]:
            return cached[0]
        token = self._access_token()
        body = {
            "scene": f"{SCENE_PREFIX}{game_id}",
            "page": LIVE_PAGE,
            # 上线前页面未必已在正式版存在，先不校验路径（体验版对演必需）
            "check_path": False,
            # release=正式版 / trial=体验版：发布前对演走 trial，发布时切回
            "env_version": self.settings.wechat_mp_env_version,
            "width": 430,
        }
        url = f"{WXACODE_URL}?{urlencode({'access_token': token})}"
        try:
            content, ctype = self._fetch_bytes(url, body)
        except Exception as exc:  # noqa: BLE001 - 网络层任何故障统一按上游不可用
            logger.warning(
                "wxacode upstream fetch failed url=%s err=%r", WXACODE_URL, exc
            )
            raise errors.wechat_unavailable() from None
        # 该端点成功回图片、失败回 JSON errcode——按 content-type 分流（日志只记
        # 端点路径：查询串带着 token，进日志等于把钥匙写墙上）
        if "json" in ctype.lower():
            data = None
            try:
                data = json.loads(content)
                errcode = data.get("errcode") if isinstance(data, dict) else None
            except ValueError:
                errcode = None
            logger.warning(
                "wxacode upstream rejected errcode=%s errmsg=%s",
                errcode,
                data.get("errmsg") if isinstance(data, dict) else None,
            )
            if errcode in TOKEN_STALE_ERRCODES:
                # token 失效：缓存已不可信，清掉但本次不重试（下次点击自然重取）
                with self._lock:
                    self._token = None
            raise errors.wechat_unavailable()
        # 写入前扫掉过期项，缓存字典大小由活跃局数兜住
        self._codes = {k: v for k, v in self._codes.items() if now < v[1]} | {
            game_id: (content, now + CODE_TTL)
        }
        return content

    def _access_token(self) -> str:
        now = clock.now()
        # 换 token 全程持锁：并发首取排队一次、后来者直接复用——两小时一趟的活，
        # 不值得为它写双检/单飞（与 jsapi 同判）
        with self._lock:
            if self._token is not None and now < self._token_exp:
                return self._token
            data = fetch_json_guarded(
                self._fetch_json,
                TOKEN_URL,
                {
                    "grant_type": "client_credential",
                    "appid": self.settings.wechat_mp_app_id,
                    "secret": self.settings.wechat_mp_app_secret,
                },
                log_tag="wxacode",
            )
            token = data.get("access_token")
            try:
                expires_in = int(data.get("expires_in") or 0)
            except ValueError:
                expires_in = 0
            # ok 但缺 token / expires_in 连边距都不够 → 与上游不可用同罪挡回不缓存
            if not token or expires_in <= TOKEN_MARGIN.total_seconds():
                logger.warning("wxacode token ok-errcode 但缺 access_token/expires_in")
                raise errors.wechat_unavailable()
            self._token = str(token)
            self._token_exp = now + timedelta(seconds=expires_in) - TOKEN_MARGIN
            return self._token


@lru_cache(maxsize=1)
def get_wxacode_maker() -> WxacodeMaker:
    """全进程共享的发行口（随 get_settings() 冻结；与 get_signer 同款单例）。"""
    return WxacodeMaker(get_settings())
