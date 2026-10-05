/* http 传输层（深模块）：uni.request 的 Promise 封装 + 钥匙/设备标记的本机存取。
   - 页面与 store 不直接碰 uni.request，一律经 request()；钥匙只在请求头出现。
   - 错误统一抛 ApiError（带后端 error.code），调用方按 code 分支，不解析中文文案。
   - 网络层细节（H5 走 /api 相对路径、开发期由 vite 代理到 16588）藏在这里。 */

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status = 0) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

/** 调用方兜底文案单一源：ApiError 用后端/网络层给的 message，其余（编程错误等）用通用文案。
    各页 catch 里统一 errText(e)，不再各自手写 instanceof 三元（兜底文案曾分叉两版）。 */
export function errText(e: unknown): string {
  return e instanceof ApiError ? e.message : '网络不给力，请稍后再试';
}

const BASE = '/api';
const TOKEN_KEY = 'mieball.token';
const DEVICE_KEY = 'mieball.device';

/* ---- 本机存取（uni 环境外安全降级，测试可 mock） ---- */

function storageGet(key: string): string | null {
  try {
    const v = uni.getStorageSync(key);
    return typeof v === 'string' && v ? v : null;
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
    m = typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `dev-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    storageSet(DEVICE_KEY, m);
  }
  return m;
}

/** 名片草稿（断网/中断后已填内容不丢，§5 出错条目）：只存本机 */
export const CARD_DRAFT_KEY = 'mieball.cardDraft';

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

export type Method = 'GET' | 'POST';

interface RawResp {
  statusCode: number;
  data: unknown;
}

function rawRequest(method: Method, path: string, data?: unknown): Promise<RawResp> {
  return new Promise((resolve, reject) => {
    uni.request({
      url: BASE + path,
      method,
      data: data as never,
      header: getRequestHeader(),
      success: (res) => resolve(res as unknown as RawResp),
      fail: () => reject(new ApiError('network', '网络不给力，请稍后再试')),
    });
  });
}

function getRequestHeader(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function request<T>(method: Method, path: string, data?: unknown): Promise<T> {
  const res = await rawRequest(method, path, data);
  const body = res.data as { error?: { code?: string; message?: string } } | T;
  if (res.statusCode >= 400) {
    const err = (body as { error?: { code?: string; message?: string } })?.error;
    throw new ApiError(err?.code ?? 'http_error', err?.message ?? '出错了，请稍后再试', res.statusCode);
  }
  return body as T;
}
