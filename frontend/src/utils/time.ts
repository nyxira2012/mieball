/* 时间工具（alpha:958-981） */

const WK: Record<string, number> = {
  周日: 0,
  周一: 1,
  周二: 2,
  周三: 3,
  周四: 4,
  周五: 5,
  周六: 6,
}; // alpha:963

/** 把「今晚 19:00 / 周六 14:00 / 下周三 20:00 / 10.06 周一 19:00」解析成 Date
    （alpha:959-974 逐字对齐；入参为 g.t / g.deadline）
    判定顺序：首段是「M.DD」精确日期 → 当年该日（组局改版后拨盘产物，已过不回绕）；
    含「后天」→ 后天；含「明」→ 明天；「下周X」→ 下周；「周X」→ 本周，今天的周X已过顺延下周（alpha:970）。 */
export function gameTime(t: string): Date {
  const parts = t.split(" ");
  const day = parts[0];
  const [H, M] = (parts[parts.length - 1] ?? "0:00").split(":").map(Number);
  const now = new Date();
  const d = new Date(now);
  if (/^\d{1,2}\.\d{1,2}$/.test(day)) {
    const [m, dd] = day.split(".").map(Number);
    return new Date(now.getFullYear(), m - 1, dd, H, M);
  }
  if (/后天/.test(day)) d.setDate(d.getDate() + 2);
  else if (/明/.test(day)) d.setDate(d.getDate() + 1);
  else if (day.startsWith("下周")) {
    const w = WK[day.slice(1)] ?? 3;
    d.setDate(d.getDate() + ((w - d.getDay() + 7) % 7) + 7);
  } else if (WK[day] !== undefined) {
    const delta = (WK[day] - d.getDay() + 7) % 7;
    d.setDate(d.getDate() + delta);
    d.setHours(H, M, 0, 0);
    if (d <= now) d.setDate(d.getDate() + 7); // 今天的周X已过 → 顺延下周
    return d;
  }
  d.setHours(H, M, 0, 0);
  return d;
}

/** 局时间串拆分（GameCard 时间位与 detail hero 共用）：末段=时刻、前段拼接=日段
    （3.3 改版后 t 可能是「10.06 周一 19:00」三段式；格式再变只改这里）。 */
export function splitGameTime(t: string): { day: string; hm: string } {
  const p = t.split(" ");
  return { day: p.slice(0, -1).join(" "), hm: p[p.length - 1] ?? "" };
}

/** 打多久文案：整/半小时 → 「N 小时」（1.5 这种），其余（拨盘 5 分步进会出 115 分钟这类）→ 「N 分钟」。
    dur 吃小时数（detail 页 endAt-startAt 现算分钟后 /60 喂入） */
export function durTxt(dur: number): string {
  const m = Math.round(dur * 60);
  return m % 30 === 0 ? `${m / 60} 小时` : `${m} 分钟`;
}

/** 'M.DD' → 同年（2026）内可比较的天序：月*100+日 单调递增（I3.2 自 stores/bill.ts 迁入：
    纯日期序函数归 utils；账单/局日期年份恒为当年，mock 无跨年） */
export function dayOrd(date: string): number {
  const [m, d] = date.split(".").map(Number);
  return m * 100 + d;
}

/** 距离某时点还有多久（alpha:975-981；已过 → null）。
    紧凑口径（2026-10-10 用户定，全站剩余时间统一）：「48分」/「12时48分」/「1天」 */
export function untilTxt(d: Date): string | null {
  const mins = Math.round((d.getTime() - new Date().getTime()) / 60000);
  if (mins <= 0) return null;
  if (mins < 60) return `${mins}分`;
  if (mins < 1440) return `${Math.floor(mins / 60)}时${mins % 60}分`;
  return `${Math.round(mins / 1440)}天`;
}

/* ---- 1.2 ISO 时刻 ↔ 展示（真局的 startAt/endAt/deadlineAt 消费面） ---- */

/** Date → ISO 8601 北京时刻：把时刻按东八区墙钟直拼——不随设备时区（走查#1
    同族收口的写侧，2026-10-10 修复批 F2：此前拼设备本地墙钟再盖 +08:00 章，
    非 +8 机器发布/改局整体漂移）。任意时区设备下「拨 19:00」都存成北京 19:00。 */
export function toIso(d: Date): string {
  const p = (n: number): string => String(n).padStart(2, "0");
  const t = new Date(d.getTime() + 8 * 3600_000); // 时刻 + 8h = 北京墙钟（UTC 分量直读）
  return `${t.getUTCFullYear()}-${p(t.getUTCMonth() + 1)}-${p(t.getUTCDate())}T${p(t.getUTCHours())}:${p(t.getUTCMinutes())}:${p(t.getUTCSeconds())}+08:00`;
}

/** 北京墙钟「y/m/d 日 + 距午夜分钟数」→ 时刻（toIso 的逆向伴：UTC = 北京 − 8h 的
    定差算术，不随设备时区；日溢出滚动交给 Date.UTC，LaunchSheet 拨盘日列 n.d+i
    直接喂）。拨盘「D 日 19:00」落成北京 19:00 的唯一源——锚是北京**午夜**，拨盘
    分钟数正是距午夜，锚上加分钟才不漂（正午锚 + 午夜分钟 = +12h，2026-10-10
    修复批 F2 的坑）。 */
export function beijingAt(
  y: number,
  m: number,
  d: number,
  minutes: number,
): Date {
  return new Date(Date.UTC(y, m - 1, d) - 8 * 3600_000 + minutes * 60000);
}

/* 走查裁决（2026-10-06 #1）：ISO 展示一律北京墙钟，不随设备时区——
   全产品面向中国用户，new Date(iso) 后的本地化取数只准经 isoParts 这一个口；
   之前 isoDay/isoHm 直吃设备本地 getHours/getDay，非东八区机器全漂（detail 页 19:00 显 22:00）。 */

const BJ_FMT = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Shanghai",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

/** 时刻 → 北京墙钟分量（y/m/d/h/min + wd=周几 0-6）。ISO 展示/筛选/回填的统一取数口。 */
export function isoParts(t: string | Date): {
  y: number;
  m: number;
  d: number;
  h: number;
  min: number;
  wd: number;
} {
  const p: Record<string, string> = {};
  for (const x of BJ_FMT.formatToParts(t instanceof Date ? t : new Date(t)))
    p[x.type] = x.value;
  const y = Number(p.year);
  const m = Number(p.month);
  const d = Number(p.day);
  return {
    y,
    m,
    d,
    h: Number(p.hour),
    min: Number(p.minute),
    // 周几由公历日期唯一决定，与时区无关：取当日 UTC 正午的 UTC 周几
    wd: new Date(Date.UTC(y, m - 1, d, 12)).getUTCDay(),
  };
}

/** 时刻距北京今天的天数偏移（meet 时间筛选 / LaunchSheet 编辑回填与 isoDay 共用） */
export function isoDayOff(t: string | Date): number {
  const p = isoParts(t);
  const n = isoParts(new Date());
  return Math.round(
    (Date.UTC(p.y, p.m - 1, p.d) - Date.UTC(n.y, n.m - 1, n.d)) / 86400000,
  );
}

/** ISO → 展示日段（今天/明天/后天/M.DD 周X，按北京墙钟）——真局卡面与详情 hero 小字共用 */
export function isoDay(t: string | Date): string {
  const p = isoParts(t);
  const off = isoDayOff(t);
  if (off >= 0 && off <= 2) return ["今天", "明天", "后天"][off];
  return `${p.m}.${String(p.d).padStart(2, "0")} 周${"日一二三四五六"[p.wd]}`;
}

/** ISO → 北京墙钟 'HH:mm'——真局卡面与 detail hero 大字共用 */
export function isoHm(iso: string): string {
  const p = isoParts(iso);
  return `${String(p.h).padStart(2, "0")}:${String(p.min).padStart(2, "0")}`;
}

/** ISO → 北京墙钟 'HH:mm'，未落账/缺值显 '—'（LedgerSheet/LiveRecap 考勤时刻段共用） */
export function isoHmOrDash(iso?: string | null): string {
  return iso ? isoHm(iso) : "—";
}
