/* 发牌引擎（alpha:1491-1530 纯函数化：live 状态作为参数传入、原地更新 —— 与 live store 共用同一份引用） */
import type { LiveState, User } from '@/api/types';

/** 按找现场玩家（alpha:1491 pById） */
export function pById(live: LiveState, id: number): User | undefined {
  return live.roster.find((p) => p.id === id);
}

/** 队列中可上场者：消耗 skip，排除非 ok（alpha:1492-1500 逐字对齐）。
    歇一轮：本轮跳过，徽章消耗（skip 置回 false）。
    注意 alpha 原样口径：check 非 'ok'（迟到/早退/未到/中途加入）都不进发牌池。 */
export function avail(live: LiveState): number[] {
  const out: number[] = [];
  for (const id of live.queue) {
    const p = pById(live, id);
    if (!p || p.check !== 'ok') continue;
    if (p.skip) { p.skip = false; continue; } // 歇一轮：本轮跳过，徽章消耗
    out.push(id);
  }
  return out;
}

/** 发牌（alpha:1501-1523 逐字对齐）：只补片不清场——已在场上待打的片永远保留；
    胜者留场只在头片空缺时生效；balance 蛇形按分降序（A=[首,末] B=[二,三]）；
    cap≥12 三片否则两片；发完队列重排且 fire（连战）优先回队。 */
export function fillCourts(live: LiveState): void {
  let pool = avail(live).slice();
  if (live.g.mode === 'balance') {
    pool.sort((a, b) => (pById(live, b)?.elo || 1100) - (pById(live, a)?.elo || 1100));
  }
  const maxC = live.g.cap >= 12 ? 3 : 2;
  while (live.courts.length < maxC && pool.length >= 4) {
    if (live.g.mode === 'winner' && live.courts.length === 0 && live.lastWinners && live.lastWinners.length === 2) {
      const ch = pool.splice(0, 2);
      live.courts.push({ A: [...live.lastWinners], B: ch });
      continue;
    }
    const four = pool.splice(0, 4);
    live.courts.push(live.g.mode === 'balance'
      ? { A: [four[0], four[3]], B: [four[1], four[2]] }
      : { A: [four[0], four[1]], B: [four[2], four[3]] });
  }
  const used = new Set(live.courts.flatMap((c) => [...c.A, ...c.B]));
  const remaining = live.queue.filter((id) => !used.has(id));
  remaining.sort((a, b) => (pById(live, b)?.fire ? 1 : 0) - (pById(live, a)?.fire ? 1 : 0));
  live.queue = [...new Set(remaining)];
}

/** 开下一场：取头片上记分板（alpha:1524-1529）。
    alpha 的 dealQuiet() 是空实现，无副作用，不搬。 */
export function nextMatch(live: LiveState): void {
  const c = live.courts.shift();
  if (!c) { live.cur = null; return; }
  live.cur = { A: c.A, B: c.B, sa: 0, sb: 0 };
}
