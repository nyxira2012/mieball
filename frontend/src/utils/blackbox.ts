/* 黑匣子（6.1 §4.6 / 附录 A）：球友手机本机的环形 30 条轨迹（nav 进出页 / act 核心动作 /
   err 报错带号），纯本地不联网、不记输入框内容（spec 禁止项）；「我的」页一键导出给项目主人排障。
   storage 三件套不复用 http.ts 的——http 要 import 本模块埋 act/err，反向取会成环；
   此处同款 try-catch 降级自持（模式单一源在 http.ts）。 */
import { toIso } from "@/utils/time";

const KEY = "blackbox";
const MAX = 30;

export type BlackboxKind = "nav" | "act" | "err";

export interface BlackboxEntry {
  /** 北京墙钟 ISO（toIso，全站时刻口径单一源） */
  t: string;
  kind: BlackboxKind;
  info: string;
}

function read(): BlackboxEntry[] {
  try {
    const v = uni.getStorageSync(KEY);
    return Array.isArray(v) ? v : [];
  } catch {
    return [];
  }
}

function write(list: BlackboxEntry[]): void {
  try {
    uni.setStorageSync(KEY, list);
  } catch {
    /* 存储失败不阻断业务（隐私模式等），spec 4.7 丢日志不丢功能 */
  }
}

function append(kind: BlackboxKind, info: string): void {
  write([...read(), { t: toIso(new Date()), kind, info }].slice(-MAX));
}

/** 进哪页（initBlackbox 的路由拦截器喂入）；url 连 query 一并留——进的哪局详情页可辨 */
export function trackNav(url: string): void {
  append("nav", url);
}

/** 核心动作（6.1 §8 评审裁决：核心动作=全部 POST，与审计清单同源口径）：POST 才记、
    GET 零记录防心跳/刷新刷屏——判定收在黑匣子，http 调用点免各自把关 */
export function trackAct(
  method: string,
  path: string,
  ok: boolean,
  code?: string,
): void {
  if (method !== "POST") return;
  append("act", `${method} ${path} → ${ok ? "ok" : `fail:${code ?? "?"}`}`);
}

/** 报错记一笔；意外错误带号时 info 首段 ERR-XXX——用户报的号 ↔ 轨迹对上（spec 4.2/4.6）。
    防刷屏：与上一条 err 条目同 info（同 code/同 ERR 号）不 append——现场页 3 秒轮询
    断网每拍一条 err"network"，30 条环 90 秒就滚掉 nav/act 轨迹（spec 4.6 场景失效）；
    连续同码只记第一条，基线看上一条 err（中间夹的 act/nav 不重置），换码才再记。 */
export function trackErr(code: string, errorId?: string): void {
  const info = errorId ? `${errorId} ${code}` : code;
  const list = read();
  const lastErr = list.filter((e) => e.kind === "err").at(-1);
  if (lastErr && lastErr.info === info) return;
  const entry: BlackboxEntry = { t: toIso(new Date()), kind: "err", info };
  write([...list, entry].slice(-MAX));
}

/** 装配（main.ts createApp 一处调）：挂四种跳转的拦截器 + 记一条 launch */
const NAV_METHODS = [
  "navigateTo",
  "switchTab",
  "reLaunch",
  "redirectTo",
] as const;

export function initBlackbox(): void {
  for (const m of NAV_METHODS) {
    uni.addInterceptor(m, {
      invoke: (args: { url?: string }) => trackNav(args.url ?? ""),
    });
  }
  append("nav", "launch");
}

/** 11 位手机号打码（与后端 logs._mask 同式 → 138****1234）：导出门槛上兜一层，
    nav url / 错误文案里带进来的号也罩住（spec 附录 C3：手机号根本不落诊断包） */
const PHONE_RE = /1[3-9]\d{9}/g;

/** 诊断包全文（我的页「复制诊断日志」）：最近报错 → 轨迹逐行 → 环境摘要；空轨迹时是
    「暂无轨迹 + 环境」的短文字（spec 附录 A2）。纯本地不联网，误点无副作用（A3） */
export function exportText(): string {
  const entries = read();
  const lastErr = entries.filter((e) => e.kind === "err").at(-1);
  let env: string;
  try {
    const {
      platform = "?",
      system = "?",
      version = "?",
      appVersion = "?",
    } = uni.getSystemInfoSync();
    env = `platform=${platform} system=${system} uni=${version} app=${appVersion}`;
  } catch {
    env = "环境信息取不到";
  }
  const trace = entries.length
    ? `轨迹（最近 ${entries.length} 步）：\n${entries
        .map((e) => `${e.t} [${e.kind}] ${e.info}`)
        .join("\n")}`
    : "轨迹：暂无";
  return [
    "【mieball 诊断日志】",
    lastErr ? `最近报错：${lastErr.t} ${lastErr.info}` : "最近报错：无",
    trace,
    `环境：${env}`,
  ]
    .join("\n")
    .replace(PHONE_RE, (m) => `${m.slice(0, 3)}****${m.slice(-4)}`);
}
