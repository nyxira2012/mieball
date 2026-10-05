/* 时间工具（alpha:958-981） */

const WK: Record<string, number> = { 周日: 0, 周一: 1, 周二: 2, 周三: 3, 周四: 4, 周五: 5, 周六: 6 }; // alpha:963

/** 把「今晚 19:00 / 周六 14:00 / 下周三 20:00 / 10.06 周一 19:00」解析成 Date
    （alpha:959-974 逐字对齐；入参为 g.t / g.deadline）
    判定顺序：首段是「M.DD」精确日期 → 当年该日（组局改版后拨盘产物，已过不回绕）；
    含「后天」→ 后天；含「明」→ 明天；「下周X」→ 下周；「周X」→ 本周，今天的周X已过顺延下周（alpha:970）。 */
export function gameTime(t: string): Date {
  const parts = t.split(' ');
  const day = parts[0];
  const [H, M] = (parts[parts.length - 1] ?? '0:00').split(':').map(Number);
  const now = new Date();
  const d = new Date(now);
  if (/^\d{1,2}\.\d{1,2}$/.test(day)) {
    const [m, dd] = day.split('.').map(Number);
    return new Date(now.getFullYear(), m - 1, dd, H, M);
  }
  if (/后天/.test(day)) d.setDate(d.getDate() + 2);
  else if (/明/.test(day)) d.setDate(d.getDate() + 1);
  else if (day.startsWith('下周')) {
    const w = WK[day.slice(1)] ?? 3;
    d.setDate(d.getDate() + (((w - d.getDay()) + 7) % 7) + 7);
  } else if (WK[day] !== undefined) {
    const delta = ((WK[day] - d.getDay()) + 7) % 7;
    d.setDate(d.getDate() + delta);
    d.setHours(H, M, 0, 0);
    if (d <= now) d.setDate(d.getDate() + 7); // 今天的周X已过 → 顺延下周
    return d;
  }
  d.setHours(H, M, 0, 0);
  return d;
}

/** 日期 → 展示日段：距今天 0/1/2 天 → 今天/明天/后天；其余 → 「M.DD 周X」（如 10.06 周一）。
    组局表单拨盘（3.3 改版）用它落 Game.t / deadline 的日段，与 gameTime 的精确日期分支配套。 */
export function dayToken(d: Date): string {
  const off = dayOff(d);
  if (off >= 0 && off <= 2) return ['今天', '明天', '后天'][off];
  return `${d.getMonth() + 1}.${String(d.getDate()).padStart(2, '0')} 周${'日一二三四五六'[d.getDay()]}`;
}

/** Date 距今天的天数偏移（按当日零点差）：dayToken / 拨盘回填 / game store 的 tb 推导共用
    （纯日期算术，此前三处各抄一份）。 */
export function dayOff(d: Date): number {
  const now = new Date();
  const day0 = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round(
    (new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime() - day0.getTime()) / 86400000,
  );
}

/** 局时间串拆分（GameCard 时间位与 detail hero 共用）：末段=时刻、前段拼接=日段
    （3.3 改版后 t 可能是「10.06 周一 19:00」三段式；格式再变只改这里）。 */
export function splitGameTime(t: string): { day: string; hm: string } {
  const p = t.split(' ');
  return { day: p.slice(0, -1).join(' '), hm: p[p.length - 1] ?? '' };
}

/** Date → 「HH:mm」（24 小时制补零；组局表单拨盘用） */
export function hmToken(d: Date): string {
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

/** 打多久文案：整/半小时 → 「N 小时」（1.5 这种），其余（拨盘 5 分步进会出 115 分钟这类）→ 「N 分钟」 */
export function durTxt(dur: number): string {
  const m = Math.round(dur * 60);
  return m % 30 === 0 ? `${m / 60} 小时` : `${m} 分钟`;
}

/** 'M.DD' → 同年（2026）内可比较的天序：月*100+日 单调递增（I3.2 自 stores/bill.ts 迁入：
    纯日期序函数归 utils；账单/局日期年份恒为当年，mock 无跨年） */
export function dayOrd(date: string): number {
  const [m, d] = date.split('.').map(Number);
  return m * 100 + d;
}

/** 距离某时点还有多久（alpha:975-981；已过 → null） */
export function untilTxt(d: Date): string | null {
  const mins = Math.round((d.getTime() - new Date().getTime()) / 60000);
  if (mins <= 0) return null;
  if (mins < 60) return `${mins} 分钟`;
  if (mins < 1440) return `${Math.floor(mins / 60)} 小时 ${mins % 60} 分`;
  return `${Math.round(mins / 1440)} 天`;
}
