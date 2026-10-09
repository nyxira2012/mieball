/* 发牌/轮换引擎（2.4 多片并行 · 纯函数：live 状态作为参数传入、原地更新 —— 与 live store 共用同一份引用）。
   旧串行引擎（avail/fillCourts/nextMatch/maxCourts + cur/lastWinners）已随批2 删除。 */
import type { LiveCourt, LiveState, PairingMode, User } from "@/api/types";
import { GUEST_DUPR } from "./elo";

/** 按找现场玩家（alpha:1491 pById） */
export function pById(live: LiveState, id: number): User | undefined {
  return live.roster.find((p) => p.id === id);
}

/** 已占片数（非空片：A/B 任一半边有人即在打）——live 顶条场地输入校验
    （在打的片不能收）共用。 */
export function usedCourts(live: LiveState): number {
  return live.courts.filter((c) => c.A.length || c.B.length).length;
}

/** 某名册行此刻在打哪片（A/B 任一半边含之；不在场上 → undefined）——换人出/入
    定向（store.swapPlayers）与待确认片冻结判定（PersonSheet）共用的场上谓词。
    （store 内另有按片号找片的 courtOf(courtId)，异名防混。） */
export function courtOfPerson(
  live: LiveState,
  id: number,
): LiveCourt | undefined {
  return live.courts.find((c) => c.A.includes(id) || c.B.includes(id));
}

/* ───────── 2.4 引擎（多片并行 · 纯函数）─────────
   合同 docs/2.4 §4.5/§4.8：只管发牌（分边/队首取人/空片补满），Elo/history/round
   落账归 store 编排；结束对局后的回流补位（§4.4-4.7 五式）真值在后端
   live_rotation.requeue_after_confirm——确认响应视图落地即排好，前端不再镜像。 */

/** 均衡排序用分（1.4 §6 消费矩阵：配对吃 DUPR——未定级以自评档代位）：dupr 直用，
    访客/缺数兜底 3.0（GUEST_DUPR，1.4 §4 访客 DUPR 恒 3.0） */
export function rankOf(p: User | undefined): number {
  return p?.dupr ?? GUEST_DUPR;
}

/** 每片人数单一源（双打 4 / 单打 2）——myRound/差人卡/发牌同口径，消灭 4 人硬编码 */
export const courtSize = (singles: boolean): number => (singles ? 2 : 4);

/** 片数单一源：订场登记优先（片数是花钱定下的默认值），未登记回退 maxPlayers≥12 三片否则两片。
   推荐矩阵与建片（store syncCourts）同源消费。 */
export function courtCount(live: LiveState): number {
  return live.g.courts?.length || (live.g.maxPlayers >= 12 ? 3 : 2);
}

/** 可打人数（推荐口径 2.4 §4.2）：片上 + 候场队；absent/left 不算（不进发牌池） */
export function activePlayers(live: LiveState): number {
  const onCourt = live.courts.reduce((s, c) => s + c.A.length + c.B.length, 0);
  const waiting = live.queue.filter((id) => {
    const p = pById(live, id);
    return p && p.check !== "absent" && p.check !== "left";
  }).length;
  return onCourt + waiting;
}

/** 可发判定（单一口径）：在场且非缺席早退、不在歇轮 */
function issuable(live: LiveState, id: number): boolean {
  const p = pById(live, id);
  return !!p && p.check !== "absent" && p.check !== "left" && !p.skip;
}

/** 候场队里此刻可发人数（在场且非缺席早退、不在歇轮）——补坑前「够不够」的判定源 */
function readyCount(live: LiveState): number {
  return live.queue.filter((id) => issuable(live, id)).length;
}

/** 上场登记：发上场先后序（资历并列的 tiebreak）、资历从 0 起算 */
function enterCourt(live: LiveState, id: number): void {
  const p = pById(live, id);
  if (!p) return;
  live.courtSeqNext += 1;
  p.courtSeq = live.courtSeqNext;
  p.tenure = 0;
}

/** 队首取 n 人发牌（2.4 §4.8）：连战（fire）优先收——「设了的人下次发牌排最前」（与歇互斥）；
    扫描中轮到歇轮者（skip>0）跳过这一轮、消耗一次、坑由下一位顶上，取完保位回队；
    absent/left 不可发但留在队里不动。取满即停——没被轮到的歇轮不消耗。 */
export function takeFromQueue(live: LiveState, n: number): number[] {
  if (n <= 0) return [];
  const ok = (id: number): User | undefined => {
    const p = pById(live, id);
    return p && p.check !== "absent" && p.check !== "left" ? p : undefined;
  };
  const pre = new Set(live.queue.filter((id) => ok(id)?.fire).slice(0, n)); // 连战优先
  const taken: number[] = [...pre];
  const kept: number[] = [];
  for (const id of live.queue) {
    if (pre.has(id)) continue;
    if (taken.length < n) {
      const p = ok(id);
      if (p && !p.skip) {
        taken.push(id);
        continue;
      }
      if (p) p.skip = (p.skip ?? 0) - 1; // 轮到发牌给他：跳过这一轮、消耗一次
    }
    kept.push(id); // 让位者/不可发者/余额：保位留在队里
  }
  live.queue = kept;
  return taken;
}

/** 全新一队分边（2.4 §4.5）：ids 已是队序。
    queue → 第 1、2 位一队、第 3、4 位一队；balance → DUPR 强到弱（同分按队序先后，不掷骰子），
    最强+最弱 vs 二三——不让两个高手挤同一边；上场永远队序，均衡只管分边不越序挑人。
    单打（2 人）没有分队一说：一左一右。 */
export function splitSides(
  live: LiveState,
  ids: number[],
  pairing: PairingMode,
): { A: number[]; B: number[] } {
  if (ids.length < 4) return { A: [ids[0]], B: ids.length > 1 ? [ids[1]] : [] };
  if (pairing === "balance") {
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
  const rules = live.rules;
  if (court.A.length || court.B.length) return;
  const size = courtSize(court.singles);
  if (readyCount(live) < size) return;
  const ids = takeFromQueue(live, size);
  const { A, B } = splitSides(live, ids, rules.pairing);
  court.A = A;
  court.B = B;
  court.sa = 0;
  court.sb = 0;
  court.last = undefined;
  court.streakA = 0;
  court.streakB = 0;
  for (const id of ids) enterCourt(live, id);
}

/** 按片号先后补所有空片（多片同时要人时，候场队按片号先后供给） */
export function fillAllCourts(live: LiveState): void {
  for (const c of live.courts) fillCourt(live, c);
}
