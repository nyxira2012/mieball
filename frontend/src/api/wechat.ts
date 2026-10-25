/* 微信平台件 API（与 auth.ts 的登录钥匙族分家）：现场小程序码。
   PNG 走 base64 JSON 包壳——小程序端免配 downloadFile 合法域名。 */
import { request } from "./http";

/** 现场亮码用：这局的小程序码（后端向微信现生成，scene=g=<id> 扫码直达现场页） */
export function apiWxacode(gameId: number): Promise<{ image_b64: string }> {
  return request("GET", `/wechat/wxacode?game_id=${gameId}`);
}
