/* 深链 URL 拼装单一源（扫码进现场/分享进详情共用）：
   H5 部署在根路径 + hash 路由（manifest h5: mode hash / base /），
   拼出形如 https://域名/#/pages/live/live?id=3。
   非 H5 端（小程序等）暂无 location，返回裸 path 由端内路由自行消化。 */

/** 页面 path（以 / 开头）→ 可外发的完整 URL */
export const deepUrl = (path: string): string =>
  typeof location === "undefined" ? path : location.origin + "/#" + path;

/** 现场页分享链接（2.6 §4.3：分享落点=现场页回看态，散场局照回 200 回看视图）：
    「页面路径→完整 URL」单一源——现场门牌（签到码）与战报子页两处 shareLink 共用，防字面量漂移。 */
export const liveShareUrl = (id: number): string =>
  deepUrl(`/pages/live/live?id=${id}`);

/** 局详情页分享链接：与 nav.goGame 同一条页面路径契约的单源出口（detail 分享用）。 */
export const gameShareUrl = (id: number): string =>
  deepUrl(`/pages/detail/detail?id=${id}`);
