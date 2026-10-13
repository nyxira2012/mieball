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

/** 挂起动作四个信号位名：hasPending 从这里派生，pendingResume 分发器按名挂钩，
    新增动作种类时在此加一名、分发器接一支，不再各处手抄字段枚举 */
const PENDING_KEYS = [
  "pendingJoin",
  "pendingLaunch",
  "pendingCheckin",
  "pendingIntent",
] as const;

/** 挂起动作是否非空（四种动作一样没带即空）：login.vue 随机名回执排队等判定共用 */
export function hasPending(p: SignupPending): boolean {
  return PENDING_KEYS.some((k) => Boolean(p[k]));
}

/** toast 展示时长单一源（ToastHost 计时与 login.vue 回执排队都吃这个数） */
export const TOAST_VISIBLE_MS = 2200;

export const useUiStore = defineStore("ui", () => {
  /** 全局单例弹层（alpha:836 openSheet：全局唯一 #sheet，按 payload.type 分发渲染） */
  const sheet = ref<SheetPayload | null>(null);
  /** 自绘 toast（alpha:834-835）。key 自增：重复消息也能重触发组件动画。
      2200ms 自动隐藏的计时器由 AppToast 组件按 toastKey 变化自行管理。 */
  const toastMsg = ref("");
  const toastKey = ref(0);

  function openSheet(p: SheetPayload): void {
    sheet.value = p;
    // 1.8 名片卡来源位：经 signupThen 开卡的由其 from 参数落位；约球页绕过
    // signupThen 直开 signup-card 时在此复位 action 兜底
    if (p.type === "signup-card") signupCardFrom.value = "action";
  }
  function closeSheet(): void {
    sheet.value = null;
  }
  /** 1.1 D3「先看后报」统一入口：游客点报名/建局/留意向/到场 → 关当前弹层开名片建号卡，
      建号成功后由 SignupSheet 接着完成挂起动作（pending 原样透传）。
      此前 JoinSheet/LaunchSheet/live 页三处各手写一遍「关-开」门。
      1.8：来源位随参落位（缺省 action）——登录页回跳落卡传 wechat-return，
      不再靠「开卡后在 store 上再覆写一次」的调用顺序耦合。 */
  function signupThen(
    pending: SignupPending,
    from: "action" | "wechat-return" = "action",
  ): void {
    closeSheet();
    openSheet({ ...pending, type: "signup-card" });
    signupCardFrom.value = from;
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

  /* —— 1.8 名片卡来源位（4.7 防误快进护栏）：action=动作弹出（微信内=一颗
     微信授权钮快进）；wechat-return=登录页微信键落下的找回卡（保持表单手填，
     防老球友在找回面被快进岔成临时账号）。内存非持久：signupThen 随参落位，
     绕过 signupThen 的直开卡由 openSheet 复位 action 兜底。 */
  const signupCardFrom = ref<"action" | "wechat-return">("action");

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
    signupCardFrom,
    openSheet,
    closeSheet,
    signupThen,
    toast,
    burst,
  };
});
