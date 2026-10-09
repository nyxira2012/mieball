/* 会话 store（1.1 账号域的前端深模块）：身份生命周期全在这——
   启动认人 / 名片建号 / 短信找回与接管 / 退出 / 注销 / 改名片。

   身份位单一源在 user store（me 对象原位换装：applyAccount/resetGuest），
   本 store 只管钥匙生命周期与账号档案镜像。组件层不直接碰 http/api，
   只消费本 store 的动作与状态。 */
import { computed, ref } from "vue";
import { defineStore } from "pinia";
import {
  apiDeactivate,
  apiLogout,
  apiMe,
  apiRedeem,
  apiSendCode,
  apiSignup,
  apiUpdateProfile,
  type AccountView,
  type CardPayload,
  type SmsPurpose,
} from "@/api/auth";
import { clearCardDraft, deviceMarker, getToken, setToken } from "@/api/http";
import type { CardBg, ChibiConfig } from "@/api/types";
import { useUiStore } from "./ui";
import { useUserStore } from "./user";

export const useSessionStore = defineStore("session", () => {
  const ui = useUiStore();

  /** guest=游客（含启动认人失败静默降级）；ready=已带有效钥匙 */
  const status = ref<"guest" | "ready" | "init">("init");
  const account = ref<AccountView | null>(null);

  const isGuest = computed(() => status.value !== "ready");
  /** 名片尾号（游客回落到演示尾号，页面 chip 不断色） */
  const phoneTail = computed(() => account.value?.phone_tail ?? "4721");
  /** 本人手机号打码（139****1234）：我的页账号区与注销短信步共用展示口径；无账号 → null */
  const maskedPhone = computed<string | null>(() => {
    const p = account.value?.phone ?? "";
    return p ? `${p.slice(0, 3)}****${p.slice(-4)}` : null;
  });

  /* ---- 动作 ---- */

  /** 启动认人：有钥匙→换本人档案；没钥匙/钥匙失效/网络失败→游客，不报错（§B 认人） */
  async function init(): Promise<void> {
    if (!getToken()) {
      status.value = "guest";
      return;
    }
    try {
      const { account: view } = await apiMe();
      if (view) {
        account.value = view;
        status.value = "ready";
        useUserStore().applyAccount(view);
      } else {
        resetToGuest(); // 钥匙已作废（被接管/注销/退出）→ 静默降级游客
      }
    } catch {
      status.value = "guest"; // 网络问题不拦启动，按游客先进场
    }
  }

  /** 名片建号（4.2）：成功落钥匙+档案并清草稿；手机号被占抛 ApiError('phone_taken') 由弹层接 */
  async function signupWithCard(card: CardPayload): Promise<AccountView> {
    const res = await apiSignup(card, deviceMarker());
    setToken(res.token);
    account.value = res.account;
    status.value = "ready";
    useUserStore().applyAccount(res.account);
    clearCardDraft();
    return res.account;
  }

  /** 发验证码（60 秒冷却/一天上限等错误原样抛，弹层按 code 提示） */
  async function requestCode(
    phone: string,
    purpose: SmsPurpose,
  ): Promise<void> {
    await apiSendCode(phone, purpose);
  }

  /** 验证码换钥匙（4.4 找回 / 4.5 接管）：接管带名片做 D5 合并 */
  async function redeemCode(
    phone: string,
    code: string,
    purpose: "recovery" | "takeover",
    card?: CardPayload,
  ): Promise<AccountView> {
    const res = await apiRedeem(phone, code, purpose, deviceMarker(), card);
    setToken(res.token);
    account.value = res.account;
    status.value = "ready";
    useUserStore().applyAccount(res.account);
    clearCardDraft();
    return res.account;
  }

  /** 退出登录（4.3/A3）：服务端作废本机钥匙 + 本机清记忆；网络失败也照样退出本机 */
  async function logout(): Promise<void> {
    try {
      await apiLogout();
    } catch {
      /* 服务端作废失败不拦退出：钥匙失效重于提示 */
    }
    resetToGuest();
    ui.toast("已退出本机登录 · 数据都在云端");
  }

  /** 注销（4.6）：短信验证本人后由后端匿名化+释放手机号+全钥匙失效 */
  async function deactivateAccount(phone: string, code: string): Promise<void> {
    await apiDeactivate(phone, code);
    resetToGuest();
    ui.toast("已注销 · 档案匿名化 · 手机号已释放");
  }

  /** 退出/注销共用回落：身份位复位游客占位（user store 单点） */
  function resetToGuest(): void {
    setToken(null);
    account.value = null;
    status.value = "guest";
    useUserStore().resetGuest();
  }

  /** 改名片（A3）：昵称/小人/卡背随时可改。游客态走本地演示保存（不接后端） */
  async function saveProfile(patch: {
    nickname?: string;
    chibi?: ChibiConfig;
    card_bg?: CardBg;
  }): Promise<string> {
    const n = (patch.nickname ?? "").trim();
    if (!n) {
      const m = "昵称不能为空";
      ui.toast(m);
      return m;
    }
    if (status.value !== "ready" || !account.value) {
      useUserStore().me.name = n; // 游客：演示态本地改名
      const msg = "已保存（演示态 · 登录后云端同步）";
      ui.toast(msg);
      return msg;
    }
    const { account: view } = await apiUpdateProfile({
      nickname: n,
      chibi: patch.chibi,
      card_bg: patch.card_bg,
    });
    account.value = view;
    useUserStore().applyAccount(view);
    const msg = "已保存 · 全局同步换新";
    ui.toast(msg);
    return msg;
  }

  return {
    status,
    account,
    isGuest,
    phoneTail,
    maskedPhone,
    init,
    signupWithCard,
    requestCode,
    redeemCode,
    logout,
    deactivateAccount,
    saveProfile,
  };
});
