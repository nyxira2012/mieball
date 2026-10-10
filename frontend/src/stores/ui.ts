/* ui 全局状态（alpha:832-847 toast/sheet）
   不触碰任何 uni.* —— 纯状态层；SheetHost/AppToast 组件负责渲染（P1/P3 接线）。
   2.1 打球页改版：WinPopup/showWin/closeWin 退役——终局结算改走 live store 的结算窗
   （2026-10-09 记分本地化后为本地结算窗 settleWindow）。 */
import { ref } from "vue";
import { defineStore } from "pinia";
import type { SheetPayload } from "@/api/types";

/** 名片卡挂起动作快照（1.6 末批）：signup-card payload 去类型的形状——
    信号位与续办单一源（composables/pendingResume）共用 */
export type SignupPending = Omit<
  Extract<SheetPayload, { type: "signup-card" }>,
  "type"
>;

export const useUiStore = defineStore("ui", () => {
  /** 全局单例弹层（alpha:836 openSheet：全局唯一 #sheet，按 payload.type 分发渲染） */
  const sheet = ref<SheetPayload | null>(null);
  /** 自绘 toast（alpha:834-835）。key 自增：重复消息也能重触发组件动画。
      2200ms 自动隐藏的计时器由 AppToast 组件按 toastKey 变化自行管理。 */
  const toastMsg = ref("");
  const toastKey = ref(0);

  function openSheet(p: SheetPayload): void {
    sheet.value = p;
  }
  function closeSheet(): void {
    sheet.value = null;
  }
  /** 1.1 D3「先看后报」统一入口：游客点报名/建局/留意向/到场 → 关当前弹层开名片建号卡，
      建号成功后由 SignupSheet 接着完成挂起动作（pending 原样透传）。
      此前 JoinSheet/LaunchSheet/live 页三处各手写一遍「关-开」门。 */
  function signupThen(pending: SignupPending): void {
    closeSheet();
    openSheet({ ...pending, type: "signup-card" });
  }
  function toast(msg: string): void {
    toastMsg.value = msg;
    toastKey.value++;
  }

  /* —— 1.6 挂起动作跨页信号位（仿 live store pendingLiveId：跨页一次性、内存非持久、消费即清）
     名片卡点【登录】跳登录页前落位。装的是挂起动作快照而非布尔：跳转瞬间 PageShell.onHide
     会关弹层卸载 SignupSheet，props 不可恃，快照进信号位才能在登录页代跑续办。
     卫生：登录页手动返回仍游客由 login 页 onUnload 兜清（why 注释在消费点旁）。 */
  const pendingAfterLogin = ref<SignupPending | null>(null);

  /* —— P3 纯增量：全局撒花触发器（alpha:839-845 confetti(n) 的状态层入口）——
     Confetti.vue（P1）是纯展示件，只接受 trigger 计数 + count 粒数两个 props，
     因此除 confettiKey 计数器外需附带 confettiN 携带本波粒数（14=开下一轮 / 56=收局，P8a/P8b 用）。
     不改动本文件 P2 既有字段与动作。 */
  const confettiKey = ref(0);
  const confettiN = ref(46);
  function burst(n = 46): void {
    confettiN.value = n;
    confettiKey.value++;
  }

  return {
    sheet,
    toastMsg,
    toastKey,
    confettiKey,
    confettiN,
    pendingAfterLogin,
    openSheet,
    closeSheet,
    signupThen,
    toast,
    burst,
  };
});
