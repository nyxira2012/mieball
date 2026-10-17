"""wechat 路由 —— 微信 JS-SDK 签证口：页面地址换 wx.config 四件套。

非鉴权语义（页面打开即调，无 Bearer），不挂在 /auth 下自成一家；
失败体同全站 {"error": {code, message}}，前端按 wechat_off/wechat_unavailable
的 code 静默降级到微信默认卡。
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from ...services.wechat_jsapi import get_signer

router = APIRouter(prefix="/wechat", tags=["wechat"])


@router.get("/jsapi_sign")
def jsapi_sign(url: str = Query(min_length=1)) -> dict:
    # url 不做白名单：给任意字符串签名只是白算一次哈希——签名本身不含票据秘密，
    # 挡了也换不来什么；真正的门禁在微信侧（域名已在公众号后台登记）
    return get_signer().sign(url)
