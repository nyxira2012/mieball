/* 发牌引擎（alpha:1491-1530 纯函数化：live 状态作为参数传入、原地更新 —— 与 live store 共用同一份引用） */
import type { LiveState, User } from '@/api/types';

/** 按找现场玩家（alpha:1491 pById） */
export function pById(live: LiveState, id: number): User | undefined {
  return live.roster.find((p) => p.id === id);
}

/** 队列中可上场者：消耗 skip，只拦 absent/left（2.1 §3 放行裁决·主 agent 已裁：到场者都该被发牌——
    迟到排队尾等一轮、中途加入/访客进候场区，下一轮发牌即可上场；absent 未到 / left 早退不发）。
    歇两轮（2.1 文档+原型）：skip=剩余歇轮数，每次发牌消耗一轮（递减 1），归 0 自动归队。 */
export function avail(live: LiveState): number[] {
  const out: number[] = [];
  for (const id of live.queue) {
    const p = pById(live, id);
    if (!p || p.check === 'absent' || p.check === 'left') continue;
    if (p.skip) { p.skip -= 1; continue; } // 歇 N 轮：本轮跳过，消耗一轮；归 0 自动归队
    out.push(id);
  }
  return out;
}

/** 片数上限单一源：订场登记优先（booked 片数是花钱定下的默认值，2026-10-04 订场改版），
    未登记回退 cap≥12 三片否则两片。发牌（fillCourts）与打球页空闲卡（还有几片可开）共用。 */
export function maxCourts(g: LiveState['g']): number {
  return g.booked?.length || (g.cap >= 12 ? 3 : 2);
}

/** 发牌（alpha:1501-1523 逐字对齐）：只补片不清场——已在场上待打的片永远保留；
    胜者留场只在头片空缺时生效；balance 蛇形按分降序（A=[首,末] B=[二,三]）；
    片数口径见 maxCourts；发完队列重排且 fire（连战）优先回队。 */
export function fillCourts(live: LiveState): void {
  let pool = avail(live).slice();
  if (live.g.mode === 'balance') {
    pool.sort((a, b) => (pById(live, b)?.elo || 1100) - (pById(live, a)?.elo || 1100));
  }
  const maxC = maxCourts(live.g);
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
