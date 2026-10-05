/* 页面导航小工具：只收「多处复用的跳转契约」，单处跳转仍写在各自页面（uni.* 不进 store）。
   goLive 例外：live 升为 tab 页后 switchTab 不能带 query，进哪局必须在跳转前于 store 落定，
   故此处引 live store（stores 不反向依赖 nav，无环）。 */
import { useLiveStore } from '@/stores/live';


/** 进球局详情页：路径 + query 契约单一源（meet/bills/logs/signup/live 六处共用） */
export function goGame(id: number): void {
  uni.navigateTo({ url: `/pages/detail/detail?id=${id}` });
}

/** 进现场（detail 页开始打球/回现场共用）：tab 页走 switchTab（navigateTo 跳 tab 页会失败），
    且 switchTab 不传 query——跳转前确保目标局已在打：未开或正打的是别的局都（重）开目标局，
    顺带消掉「A 局在打、点 B 局进现场却显示 A」的错局口径。 */
export function goLive(id: number): void {
  const live = useLiveStore();
  if (!live.live || live.live.g.id !== id) live.startLive(id);
  uni.switchTab({ url: '/pages/live/live' });
}
