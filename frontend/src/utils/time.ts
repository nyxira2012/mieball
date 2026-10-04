/* 时间工具（alpha:958-981） */

const WK: Record<string, number> = { 周日: 0, 周一: 1, 周二: 2, 周三: 3, 周四: 4, 周五: 5, 周六: 6 }; // alpha:963

/** 把「今晚 19:00 / 周六 14:00 / 下周三 20:00」解析成 Date（alpha:959-974 逐字对齐；入参为 g.t）
    判定顺序与 alpha 一致：含「明」→ 明天；「下周X」→ 下周；「周X」→ 本周，今天的周X已过顺延下周（alpha:970）。 */
export function gameTime(t: string): Date {
  const [day, hm] = t.split(' ');
  const [H, M] = hm.split(':').map(Number);
  const now = new Date();
  const d = new Date(now);
  if (/明/.test(day)) d.setDate(d.getDate() + 1);
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
