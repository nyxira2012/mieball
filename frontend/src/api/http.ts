/* http 传输层（深模块）：uni.request 的 Promise 封装 + 钥匙/设备标记的本机存取。
   - 页面与 store 不直接碰 uni.request，一律经 request()；钥匙只在请求头出现。
   - 错误统一抛 ApiError（带后端 error.code），调用方按 code 分支，不解析中文文案。
   - 网络层细节（H5 走 /api 相对路径、开发期由 vite 代理到 16588）藏在这里。 */
import type { LiveViewApi } from "./types";
import { trackAct, trackErr } from "@/utils/blackbox";

export class ApiError extends Error {
  code: string;
  status: number;
  /** 意外错误编号（6.1：仅 internal_error 带）——报号话术已进 message，此字段供诊断日志记轨迹 */
  errorId?: string;
  /** 两级号防线 409（live_stale_total/court）随错误体带的最新总账视图（2.3 附录 B1）——
      拿它直接对表，不用再拉一次读；其余错误恒缺省 */
  view?: LiveViewApi;

  constructor(
    code: string,
    message: string,
    status = 0,
    view?: LiveViewApi,
    errorId?: string,
  ) {
    super(message);
    this.code = code;
    this.status = status;
    this.view = view;
    this.errorId = errorId;
  }
}

/** 调用方兜底文案单一源：ApiError 用后端/网络层给的 message，其余（编程错误等）用通用文案。
    各页 catch 里统一 errText(e)，不再各自手写 instanceof 三元（兜底文案曾分叉两版）。 */
export function errText(e: unknown): string {
  return e instanceof ApiError ? e.message : "网络不给力，请稍后再试";
}

const BASE = "/api";
const TOKEN_KEY = "mieball.token";
const DEVICE_KEY = "mieball.device";

/* ---- 本机存取（uni 环境外安全降级，测试可 mock） ---- */

function storageGet(key: string): string | null {
  try {
    const v = uni.getStorageSync(key);
    return typeof v === "string" && v ? v : null;
  } catch {
    return null;
  }
}

function storageSet(key: string, val: string): void {
  try {
    uni.setStorageSync(key, val);
  } catch {
    /* 存储失败不阻断主流程（如隐私模式） */
  }
}

export function getToken(): string | null {
  return storageGet(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) storageSet(TOKEN_KEY, token);
  else {
    try {
      uni.removeStorageSync(TOKEN_KEY);
    } catch {
      /* 同上 */
    }
  }
}

/** 设备标记：建号/续接窗口与"同一台设备"判断用；UUID 首次生成后长期留在本机 */
export function deviceMarker(): string {
  let m = storageGet(DEVICE_KEY);
  if (!m) {
    m =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `dev-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    storageSet(DEVICE_KEY, m);
  }
  return m;
}

/** 名片草稿（断网/中断后已填内容不丢，§5 出错条目）：只存本机 */
export const CARD_DRAFT_KEY = "mieball.cardDraft";

export function readCardDraft<T>(): T | null {
  try {
    const v = uni.getStorageSync(CARD_DRAFT_KEY);
    return v || null;
  } catch {
    return null;
  }
}

export function writeCardDraft(draft: unknown): void {
  try {
    uni.setStorageSync(CARD_DRAFT_KEY, draft);
  } catch {
    /* 忽略 */
  }
}

export function clearCardDraft(): void {
  try {
    uni.removeStorageSync(CARD_DRAFT_KEY);
  } catch {
    /* 忽略 */
  }
}

/* ---- 请求 ---- */

export type Method = "GET" | "POST";

interface RawResp {
  statusCode: number;
  data: unknown;
}

function rawRequest(
  method: Method,
  path: string,
  data?: unknown,
): Promise<RawResp> {
  return new Promise((resolve, reject) => {
    uni.request({
      url: BASE + path,
      method,
      data: data as never,
      header: getRequestHeader(),
      success: (res) => resolve(res as unknown as RawResp),
      fail: () => reject(new ApiError("network", "网络不给力，请稍后再试")),
    });
  });
}

function getRequestHeader(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function request<T>(
  method: Method,
  path: string,
  data?: unknown,
): Promise<T> {
  try {
    const res = await rawRequest(method, path, data);
    const body = res.data as
      | {
          error?: { code?: string; message?: string; error_id?: string };
          view?: LiveViewApi;
        }
      | T;
    if (res.statusCode >= 400) {
      const err = (
        body as {
          error?: { code?: string; message?: string; error_id?: string };
        }
      )?.error;
      // 意外错误带号（契约总则 §3 / 6.1 裁决，仅 internal_error 有 error_id）：
      // 换成报号话术让用户照着报，errText 原样透出；业务错误与断网分支不带号
      throw err?.error_id
        ? new ApiError(
            "internal_error",
            `出错了，请把编号 ${err.error_id} 发到反馈群或告诉群主`,
            res.statusCode,
            undefined,
            err.error_id,
          )
        : new ApiError(
            err?.code ?? "http_error",
            err?.message ?? "出错了，请稍后再试",
            res.statusCode,
            (body as { view?: LiveViewApi })?.view,
          );
    }
    // 条件拉取空拍（2.8 §4.6）：204 无体，回 null 哨兵——目前唯一消费方是
    // apiLiveView 带 since 的轮询快路，其余调用不带参不会拿到 204
    if (res.statusCode === 204) return null as unknown as T;
    trackAct(method, path, true);
    return body as T;
  } catch (e) {
    // 失败统一埋点（6.1 §4.5/§4.6）：先在上游构造好 ApiError、在此用 e.code/e.errorId
    // 记一笔——err 行带号时含 ERR-XXX（errorId「供诊断日志记轨迹」由此成真）、act 行只
    // POST（GET 零记录防刷新刷屏）；断网同款走这（服务器日志看不见的手机侧失败黑匣子
    // 兜底，提示不带号 spec 4.1 禁止项），原错误原样上抛
    const apiErr =
      e instanceof ApiError
        ? e
        : new ApiError("network", "网络不给力，请稍后再试");
    trackErr(apiErr.code, apiErr.errorId);
    trackAct(method, path, false, apiErr.code);
    throw e;
  }
}
