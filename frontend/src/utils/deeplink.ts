/* 深链 URL 拼装单一源（扫码进现场/分享进详情共用）：
   H5 部署在根路径 + hash 路由（manifest h5: mode hash / base /），
   拼出形如 https://域名/#/pages/live/live?id=3。
   非 H5 端（小程序等）暂无 location，返回裸 path 由端内路由自行消化。 */

/** 页面 path（以 / 开头）→ 可外发的完整 URL */
export const deepUrl = (path: string): string =>
  typeof location === "undefined" ? path : location.origin + "/#" + path;

/** 现场页深链（2.1·选项A 扫码签到用）：二维码编码 {origin}/#/pages/live/live?id=<球局id>。
    2026-10-12 三处分享统一发详情链接后，战报分享不再走这条——本函数只服务签到码
    （QrOverlay 单一消费方；散场局照回 200 回看视图的老口径仍在，扫码进旧局=回看） */
export const liveShareUrl = (id: number): string =>
  deepUrl(`/pages/live/live?id=${id}`);

/** 局详情页分享链接（2026-10-12 三处统一单一源：详情页/战报子页/现场散场门牌
    都发这条——收链接的人详情+「查看战报」一跳可达）；与 nav.goGame 同一条页面
    路径契约的单源出口。 */
export const gameShareUrl = (id: number): string =>
  deepUrl(`/pages/detail/detail?id=${id}`);

/** 扫现场小程序码进场的 scene 解析：微信把码里的 scene 参数（encode 形态）塞在
    页面启动参数里，协议是 g=<球局id>（与后端生成码的 SCENE_PREFIX 同一字面量）。
    深链 URL 的单一源职责在此——认不出回 null（照旧走 ?id=/信号位分发，坏码不比
    死链接更死）。 */
export function sceneGameId(scene?: string | null): number | null {
  if (!scene) return null;
  let raw: string;
  try {
    raw = decodeURIComponent(scene);
  } catch {
    return null; // 畸形百分号序列：当没扫过
  }
  const m = raw.match(/^g=(\d+)$/);
  return m ? Number(m[1]) : null;
}
