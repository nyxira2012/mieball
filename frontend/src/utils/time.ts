/* 时间工具（alpha:958-981；1.2 切真后端 ISO 时刻后，mock 时代的中文日段解析
   三件 gameTime/splitGameTime/dayOrd 已随 2026-10-12 精简批退役——src 零消费） */

/** 周名（isoDay 日段与 meet 头部日期行同消费） */
export const WD_CN = "日一二三四五六";

/** 打多久文案：整/半小时 → 「N 小时」（1.5 这种），其余（拨盘 5 分步进会出 115 分钟这类）→ 「N 分钟」。
    dur 吃小时数（detail 页 endAt-startAt 现算分钟后 /60 喂入） */
export function durTxt(dur: number): string {
  const m = Math.round(dur * 60);
  return m % 30 === 0 ? `${m / 60} 小时` : `${m} 分钟`;
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
  return `${p.m}.${String(p.d).padStart(2, "0")} 周${WD_CN[p.wd]}`;
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
