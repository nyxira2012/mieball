/* wechat —— 微信钥匙的浏览器侧工具（1.7）：环境探测 / 授权跳转编排 / 转场包。
   「跳微信授权页」是整页跳转，SPA 内存态全丢——出发前把回跳要用的东西
   （占卡手机号、挂起动作、原页面位置、防伪记号）存进本机，回来在登录页消费。
   uni 全局不 import（nav.ts 同款例外注记）；存储走 uni.setStorageSync。 */
import { apiWechatUrl } from "@/api/auth";
import { errText } from "@/api/http";
import type { SignupPending } from "@/stores/ui";
import { deepUrl } from "@/utils/deeplink";

/** 微信内置浏览器探测（UA 带 MicroMessenger）——只有微信里才弹得出授权确认页 */
export function isWeChatBrowser(): boolean {
  if (typeof navigator === "undefined") return false;
  return /MicroMessenger/i.test(navigator.userAgent);
}

/** 防伪记号：跳出去之前造一个，回来对得上才认（防授权跳转被顶替） */
export function genState(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

/** 转场包：跳微信往返之间存本机的上下文（1.7 A2 加载中——不存就丢） */
export interface WechatAuthCtx {
  state: string;
  /** 回跳落点（hash 路径含查询串，如 /pages/detail/detail?id=5） */
  back: string;
  /** 占卡「微信验证进入」带着的手机号（登录页一键登录没有它） */
  phone?: string;
  /** 跳走前进行到一半的动作（回来接着办，1.6 接着办承诺不因换通道打折） */
  pending?: SignupPending;
  /** 出发时刻：转场包只活十分钟，与绑定凭条同刻度 */
  ts: number;
}

const CTX_KEY = "wechatAuthCtx";
const CTX_TTL_MS = 10 * 60_000;

export function saveWechatCtx(ctx: WechatAuthCtx): void {
  uni.setStorageSync(CTX_KEY, ctx);
}

export function readWechatCtx(): WechatAuthCtx | null {
  try {
    const v = uni.getStorageSync(CTX_KEY);
    return v && typeof v === "object" ? (v as WechatAuthCtx) : null;
  } catch {
    return null;
  }
}

export function clearWechatCtx(): void {
  try {
    uni.removeStorageSync(CTX_KEY);
  } catch {
    /* 清不掉不拦路：消费侧有 ts/state 双闸兜底 */
  }
}

/** 转场包还新鲜吗：十分钟内且防伪记号对得上（类型收窄守卫：新鲜即非空） */
export function ctxFresh(
  ctx: WechatAuthCtx | null,
  state: string,
): ctx is WechatAuthCtx {
  return (
    ctx !== null && ctx.state === state && Date.now() - ctx.ts <= CTX_TTL_MS
  );
}

/** 回跳落点：栈顶是登录页（登录页上的微信键）→ 取下一层（谁带来的回谁那去）；
    栈顶不是登录页（名片卡上的微信键）→ 栈顶即宿主页，回它自己（1.7 A2「原页面位置」）；
    栈里只有登录页（深链冷开）→ 兜底回约球页 */
export function backPathForAuth(): string {
  try {
    const pages = getCurrentPages();
    if (pages.length) {
      const top = pages[pages.length - 1] as { route?: string };
      const idx =
        top.route === "pages/mine/login" ? pages.length - 2 : pages.length - 1;
      if (idx >= 0) {
        const p = pages[idx];
        const opts = (p as { options?: Record<string, string> }).options ?? {};
        const qs = Object.entries(opts)
          .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
          .join("&");
        const route = (p as { route?: string }).route ?? "pages/meet/meet";
        return `/${route}${qs ? `?${qs}` : ""}`;
      }
    }
  } catch {
    /* 栈读不出就走兜底 */
  }
  return "/pages/meet/meet";
}

const TAB_PATHS = [
  "/pages/live/live",
  "/pages/meet/meet",
  "/pages/power/power",
  "/pages/mine/mine",
];

/** 回跳落点导航：tab 页切 tab（redirectTo 进不了 tabbar），普通页重定向顶掉登录页 */
export function navToPath(path: string): void {
  const pure = path.split("?")[0];
  if (TAB_PATHS.includes(pure)) {
    uni.switchTab({ url: pure });
    return;
  }
  uni.redirectTo({
    url: path,
    fail: () => uni.switchTab({ url: "/pages/meet/meet" }),
  });
}

/** 网页授权回跳地址：纯净 URL，严格不含 #（微信规范：带 # 会被判域名不一致 10003） */
export function authRedirectUrl(path: string): string {
  if (typeof location === "undefined") return path;
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${location.origin}${p}`;
}

/**
 * 出发去微信授权页（1.7 两处微信键共用）：查环境 → 存转场包 → 问后端要授权地址。
 * 返回授权地址由调用方整页跳转（location.href = url）；不在微信里/通道没开时
 * toast 说明并抛出短路（调用方无需分支——本函数已把话说完）。
 * 错误语义：短路时不抛（已 toast）；要地址失败抛 ApiError（wechat_off 等文案后端给全）。
 */
export async function beginWechatAuth(opts: {
  phone?: string;
  pending?: SignupPending;
  toast: (msg: string) => void;
}): Promise<string> {
  if (!isWeChatBrowser()) {
    opts.toast(
      "请在微信里打开本页（把链接发到微信里再点开）才能用微信登录，或直接用短信/密码",
    );
    throw new Error("not-in-wechat");
  }
  const state = genState();
  saveWechatCtx({
    state,
    back: backPathForAuth(),
    phone: opts.phone,
    pending: opts.pending,
    ts: Date.now(),
  });
  try {
    const { url } = await apiWechatUrl(
      authRedirectUrl("/pages/mine/login"),
      state,
    );
    return url;
  } catch (e) {
    clearWechatCtx();
    opts.toast(errText(e)); // wechat_off 的文案即占位说明（4.7），配置一填自动点亮
    throw e;
  }
}
