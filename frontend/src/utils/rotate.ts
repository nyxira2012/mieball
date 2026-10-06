/* 发牌引擎（alpha:1491-1530 纯函数化：live 状态作为参数传入、原地更新 —— 与 live store 共用同一份引用） */
import type { LiveCourt, LiveState, PairingMode, RotationRules, User } from '@/api/types';

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

/** 片数上限单一源：订场登记优先（courts 片数是花钱定下的默认值，2026-10-04 订场改版），
    未登记回退 maxPlayers≥12 三片否则两片。发牌（fillCourts）与打球页空闲卡共用。 */
export function maxCourts(g: LiveState['g']): number {
  return g.courts?.length || (g.maxPlayers >= 12 ? 3 : 2);
}

/** 已占片数（在打 1 片 + 待开片数）：maxCourts 的镜像概念——live 顶条场地输入校验
    （在打和待开的片不能收）与打球页空闲卡下标共用。 */
export function usedCourts(live: LiveState): number {
  return (live.cur ? 1 : 0) + live.courts.length;
}

/** 发牌（alpha:1501-1523 逐字对齐）：只补片不清场——已在场上待打的片永远保留；
    胜者留场只在头片空缺时生效；balance 蛇形按分降序（A=[首,末] B=[二,三]）；
    片数口径见 maxCourts；发完队列重排且 fire（连战）优先回队。 */
export function fillCourts(live: LiveState): void {
  let pool = avail(live).slice();
  if (live.g.rotation === 'balance') {
    pool.sort((a, b) => (pById(live, b)?.elo || 1100) - (pById(live, a)?.elo || 1100));
  }
  const maxC = maxCourts(live.g);
  while (live.courts.length < maxC && pool.length >= 4) {
    if (live.g.rotation === 'winner' && live.courts.length === 0 && live.lastWinners && live.lastWinners.length === 2) {
      const ch = pool.splice(0, 2);
      live.courts.push({ A: [...live.lastWinners], B: ch });
      continue;
    }
    const four = pool.splice(0, 4);
    live.courts.push(live.g.rotation === 'balance'
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

/* ───────── 2.4 新引擎（多片并行 · 纯函数；上方旧导出共存，批2 删）─────────
   合同 docs/2.4 §4.4-4.8：只管轮换，Elo/history/round 落账归 store 编排。
   批1 过渡约束：rules/courtSeqNext 及 LiveCourt 新字段在 types.ts 皆可选（加法式），
   引擎内部用 DEFAULT_RULES / ?? 兜底收窄，批2 翻必填后收紧。 */

/** 均衡排序的初始分（2.4 §8 定值：没打过的新人与访客按 1500 参与排序；战力册将来沿用） */
export const RANK_INIT = 1500;

/** 每片人数单一源（双打 4 / 单打 2）——myRound/差人卡/发牌同口径，消灭 4 人硬编码 */
export const courtSize = (singles: boolean): number => (singles ? 2 : 4);

/** 均衡排序用分：打过的按 elo，没打过按初始分（2.4 §4.5） */
export function rankOf(p: User | undefined): number {
  return p && p.play > 0 ? p.elo : RANK_INIT;
}

/** 片数单一源：登记场地优先，未登记回退 maxCourts 兜底（推荐矩阵与发牌同源消费） */
export function courtCount(live: LiveState): number {
  return maxCourts(live.g);
}

/** 可打人数（推荐口径 2.4 §4.2）：片上 + 候场队；absent/left 不算（不进发牌池） */
export function activePlayers(live: LiveState): number {
  const onCourt = live.courts.reduce((s, c) => s + c.A.length + c.B.length, 0);
  const waiting = live.queue.filter((id) => {
    const p = pById(live, id);
    return p && p.check !== 'absent' && p.check !== 'left';
  }).length;
  return onCourt + waiting;
}

/** 批1 过渡默认四件套（rules 未挂时引擎兜底；批2 store 重写后 startLive 初始化，此表消亡） */
const DEFAULT_RULES: RotationRules = { singles: false, down: 'all', downChosen: false, pairing: 'queue', champCap: 3 };

/** 候场队里此刻可发人数（在场且非缺席早退、不在歇轮）——补坑前「够不够」的判定源 */
function readyCount(live: LiveState): number {
  return live.queue.filter((id) => {
    const p = pById(live, id);
    return p && p.check !== 'absent' && p.check !== 'left' && !p.skip;
  }).length;
}

/** 上场登记：发上场先后序（资历并列的 tiebreak）、资历从 0 起算 */
function enterCourt(live: LiveState, id: number): void {
  const p = pById(live, id);
  if (!p) return;
  live.courtSeqNext = (live.courtSeqNext ?? 0) + 1;
  p.courtSeq = live.courtSeqNext;
  p.tenure = 0;
}

/** 下场清账：资历清零、先后序注销（中途换上从换上起算由此兑现） */
function leaveCourt(live: LiveState, id: number): void {
  const p = pById(live, id);
  if (!p) return;
  p.tenure = 0;
  p.courtSeq = undefined;
}

/** 队首取 n 人发牌（2.4 §4.8）：连战（fire）优先收——「设了的人下次发牌排最前」（与歇互斥）；
    扫描中轮到歇轮者（skip>0）跳过这一轮、消耗一次、坑由下一位顶上，取完保位回队；
    absent/left 不可发但留在队里不动。取满即停——没被轮到的歇轮不消耗。 */
export function takeFromQueue(live: LiveState, n: number): number[] {
  if (n <= 0) return [];
  const ok = (id: number): User | undefined => {
    const p = pById(live, id);
    return p && p.check !== 'absent' && p.check !== 'left' ? p : undefined;
  };
  const pre = new Set(live.queue.filter((id) => ok(id)?.fire).slice(0, n)); // 连战优先
  const taken: number[] = [...pre];
  const kept: number[] = [];
  for (const id of live.queue) {
    if (pre.has(id)) continue;
    if (taken.length < n) {
      const p = ok(id);
      if (p && !p.skip) { taken.push(id); continue; }
      if (p) p.skip = (p.skip ?? 0) - 1; // 轮到发牌给他：跳过这一轮、消耗一次
    }
    kept.push(id); // 让位者/不可发者/余额：保位留在队里
  }
  live.queue = kept;
  return taken;
}

/** 全新一队分边（2.4 §4.5）：ids 已是队序。
    queue → 第 1、2 位一队、第 3、4 位一队；balance → 积分强到弱（同分按队序先后，不掷骰子），
    最强+最弱 vs 二三——不让两个高手挤同一边；上场永远队序，均衡只管分边不越序挑人。
    单打（2 人）没有分队一说：一左一右。 */
export function splitSides(live: LiveState, ids: number[], pairing: PairingMode): { A: number[]; B: number[] } {
  if (ids.length < 4) return { A: [ids[0]], B: ids.length > 1 ? [ids[1]] : [] };
  if (pairing === 'balance') {
    const order = ids
      .map((id, i) => ({ id, i, r: rankOf(pById(live, id)) }))
      .sort((a, b) => b.r - a.r || a.i - b.i);
    return { A: [order[0].id, order[3].id], B: [order[1].id, order[2].id] };
  }
  return { A: [ids[0], ids[1]], B: [ids[2], ids[3]] };
}

/** 空片补满即打（2.4 §4.3）：按 court.singles（过渡期可 ≠ rules.singles）取一整片，
    按当前怎么配分边，新队连庄清零、courtSeq/tenure 起算。补不满留空（差人卡呈现），不动队列。 */
export function fillCourt(live: LiveState, court: LiveCourt): void {
  const rules = live.rules ?? DEFAULT_RULES;
  if (court.A.length || court.B.length) return;
  const size = courtSize(court.singles ?? rules.singles);
  if (readyCount(live) < size) return;
  const ids = takeFromQueue(live, size);
  const { A, B } = splitSides(live, ids, rules.pairing);
  court.A = A;
  court.B = B;
  court.sa = 0;
  court.sb = 0;
  court.streakA = 0;
  court.streakB = 0;
  for (const id of ids) enterCourt(live, id);
}

/** 按片号先后补所有空片（多片同时要人时，候场队按片号先后供给） */
export function fillAllCourts(live: LiveState): void {
  for (const c of live.courts) fillCourt(live, c);
}

/** 资历序（2.4 §4.4「待得最久」）：tenure 降序、并列按当初上场先后（courtSeq 升）——先上的先下 */
function byTenure(live: LiveState, ids: number[]): number[] {
  return ids.slice().sort((a, b) => {
    const pa = pById(live, a);
    const pb = pById(live, b);
    return (pb?.tenure ?? 0) - (pa?.tenure ?? 0) || (pa?.courtSeq ?? 0) - (pb?.courtSeq ?? 0);
  });
}

/** 结束对局后的轮换（2.4 §4.4-4.7 五式真值）：只动这片，别片各排各的。
    次序：① 资历/连庄落账（全员 tenure+1；输家下模式胜边连庄+1——原班再战这场也赢了，照算）
    ② 坑补不满 → 原班再战（各方式通用：谁也不下、比分清零、连庄资历不清零、队列不动）
    ③ 格式过渡（court.singles ≠ rules.singles）：全场按资历序下、按新格式凑全新一队
    ④ 按谁下处理：all/连庄到点 → 全场按资历序下+补全新一队（怎么配生效）；
    loser 未到点 → 输家边下、候场首补空边成一队（不重配、新边连庄=0）；
    n1/2/3 → 资历最久的 N 人下、候场首逐个原位顶坑（谁下补谁的坑，留下的保住半边）。 */
export function endMatch(live: LiveState, courtId: number, winner: 'A' | 'B'): void {
  const rules = live.rules ?? DEFAULT_RULES;
  const court = live.courts.find((c) => c.id === courtId) ?? live.courts[courtId]; // id 未设按片序兜底
  if (!court) return;
  const singles = court.singles ?? rules.singles;
  const winSide = winner;
  const loseSide = winner === 'A' ? 'B' : 'A';

  // ① 资历/连庄落账
  const streakKey = winSide === 'A' ? 'streakA' : 'streakB';
  for (const id of [...court.A, ...court.B]) {
    const p = pById(live, id);
    if (p) p.tenure = (p.tenure ?? 0) + 1;
  }
  if (rules.down === 'loser') court[streakKey] = (court[streakKey] ?? 0) + 1;

  // 坑位数：过渡按新格式整片；all/到点=整片；loser=输家边；n 系=N
  const atCap = rules.down === 'loser' && rules.champCap > 0
    && (court[streakKey] ?? 0) >= rules.champCap; // 上限改了立即生效（读现值）
  const transition = singles !== rules.singles;
  const pits = transition ? courtSize(rules.singles)
    : rules.down === 'all' || atCap ? courtSize(singles)
    : rules.down === 'loser' ? court[loseSide].length
    : rules.down === 'n1' ? 1 : rules.down === 'n2' ? 2 : 3;

  // ② 坑补不满：原班再战
  if (readyCount(live) < pits) {
    court.sa = 0;
    court.sb = 0;
    return;
  }

  const toTail = (ids: number[]): void => {
    for (const id of ids) {
      leaveCourt(live, id);
      live.queue.push(id); // 下场的人排队尾（先下的排前面）
    }
  };

  // ③ 格式过渡（4.7-3）：全场下、按新格式凑全新一队
  if (transition) {
    toTail(byTenure(live, [...court.A, ...court.B]));
    court.A = [];
    court.B = [];
    court.singles = rules.singles;
    fillCourt(live, court);
    return;
  }

  // ④ 按谁下处理
  if (rules.down === 'all' || atCap) {
    // 全上全下 / 连庄到点：全场按资历序下，候场首补全新一队（怎么配生效、连庄清零）
    toTail(byTenure(live, [...court.A, ...court.B]));
    court.A = [];
    court.B = [];
    fillCourt(live, court);
    return;
  }
  if (rules.down === 'loser') {
    // 未到点：赢家留场（连庄已 +1），输家边下排队尾，候场首补空边成一队挑战（不重配）
    toTail(byTenure(live, court[loseSide]));
    const holes = court[loseSide].length;
    court[loseSide] = takeFromQueue(live, holes);
    for (const id of court[loseSide]) enterCourt(live, id);
    court[winSide === 'A' ? 'streakB' : 'streakA'] = 0; // 新挑战者连庄从零
    court.sa = 0;
    court.sb = 0;
    return;
  }
  // n1/n2/n3：资历最久的 N 人下，候场首逐个原位顶坑
  const n = rules.down === 'n1' ? 1 : rules.down === 'n2' ? 2 : 3;
  for (const id of byTenure(live, [...court.A, ...court.B]).slice(0, n)) {
    const side = court.A.includes(id) ? 'A' : 'B';
    const slot = court[side].indexOf(id);
    const rep = takeFromQueue(live, 1)[0];
    toTail([id]);
    if (rep !== undefined) {
      court[side][slot] = rep; // 谁下补谁的坑：留下的保住半边，不重新分队
      enterCourt(live, rep);
    }
  }
  court.sa = 0;
  court.sb = 0;
}
