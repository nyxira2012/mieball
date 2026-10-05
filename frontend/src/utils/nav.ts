/* 页面导航小工具：只收「多处复用的跳转契约」，单处跳转仍写在各自页面（uni.* 不进 store）。 */

/** 进球局详情页：路径 + query 契约单一源（home/meet/bills/logs/signup/live 六处共用） */
export function goGame(id: number): void {
  uni.navigateTo({ url: `/pages/detail/detail?id=${id}` });
}

/** 进现场打球页（detail 页开始打球/回现场共用） */
export function goLive(id: number): void {
  uni.navigateTo({ url: `/pages/live/live?id=${id}` });
}
