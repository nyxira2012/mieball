/* 页面导航小工具：只收「多处复用的跳转契约」，单处跳转仍写在各自页面（uni.* 不进 store）。
   tab 键/路径/切 tab（TabBar 渲染与页面层跳转）也归这里单一源。
   goLive 例外：live 升为 tab 页后 switchTab 不能带 query，进哪局必须在跳转前于 store 落定，
   故此处引 live store（stores 不反向依赖 nav，无环）。 */
import { useLiveStore } from "@/stores/live";

/** tab 键（与 pages.json tabBar 顺序一致，home 页已退役、现场为首 tab） */
export type TabKey = "live" | "meet" | "power" | "mine";

/** tab 页路径契约单一源（TabBar 渲染、goTab/goLive 跳转共用） */
export const TAB_ROUTES: Record<TabKey, string> = {
  live: "/pages/live/live",
  meet: "/pages/meet/meet",
  power: "/pages/power/power",
  mine: "/pages/mine/mine",
};

/** 切 tab：已在目标 tab 页则不重跳（uni.switchTab 到当前页会重触发 onShow/重排，
    语义应等价「不动」——原 ConfirmSheet 的本地守卫收敛于此） */
export function goTab(k: TabKey): void {
  const pages = getCurrentPages();
  const cur = pages[pages.length - 1];
  if (cur && cur.route === TAB_ROUTES[k].slice(1)) return;
  uni.switchTab({ url: TAB_ROUTES[k] });
}

/** 回约球页（发局/建局/退局/撤局/拉人/现场入口分发共用） */
export function goMeet(): void {
  goTab("meet");
}

/** 进球局详情页：路径 + query 契约单一源（meet/bills/logs/signup/live 六处共用） */
export function goGame(id: number): void {
  uni.navigateTo({ url: `/pages/detail/detail?id=${id}` });
}

/** 进现场（detail 页开始打球/回现场与 meet 卡片入口共用）：tab 页走 switchTab（navigateTo
    跳 tab 页会失败），且 switchTab 不传 query——先在 store 落 pendingLiveId 信号位
    （live.vue 弹回判定与 onShow 取 id 认它，2.5 修「点回现场被弹回约球页」），
    再由 ensureLive 确保目标局已在打，顺带消掉「A 局在打、点 B 局进现场却显示 A」的错局口径。 */
export function goLive(id: number): void {
  const live = useLiveStore();
  live.pendingLiveId = id;
  // 消费兜底在 live.vue onShow；这里挂 finally 保证位必清（跳转被拦/页面没接也不残留，
  // 散场后回 live tab 不会被动接上旧目标局）
  live.ensureLive(id).finally(() => {
    live.pendingLiveId = null;
  });
  uni.switchTab({ url: TAB_ROUTES.live });
}
