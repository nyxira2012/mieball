"""wechat 路由 —— 微信侧两个只读口：JS-SDK 签证、现场小程序码。

jsapi_sign 非鉴权（页面打开即调，无 Bearer）；wxacode 挂 require_account——到场
才点得了二维码钮，省微信额度。失败体同全站 {"error": {code, message}}，前端按
wechat_off/wechat_unavailable 的 code 静默降级（微信默认卡 / 网页链接码）。
"""

from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, Query

from ...db.models import Account
from ...services.wechat_jsapi import get_signer
from ...services.wechat_mp import get_wxacode_maker
from ..deps import require_account

router = APIRouter(prefix="/wechat", tags=["wechat"])


@router.get("/jsapi_sign")
def jsapi_sign(url: str = Query(min_length=1)) -> dict:
    # url 不做白名单：给任意字符串签名只是白算一次哈希——签名本身不含票据秘密，
    # 挡了也换不来什么；真正的门禁在微信侧（域名已在公众号后台登记）
    return get_signer().sign(url)


@router.get("/wxacode")
def wxacode(
    game_id: int = Query(ge=1), _account: Account = Depends(require_account)
) -> dict:
    # 码只是深链载体：不查局是否存在、不落任何库——生成失败也不弄脏球局/账单/
    # 战力；图走 base64 JSON 包壳，小程序端免配 downloadFile 合法域名
    png = get_wxacode_maker().wxacode(game_id)
    return {"image_b64": base64.b64encode(png).decode()}
