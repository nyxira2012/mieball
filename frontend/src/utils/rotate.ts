/* 现场展示派生与谓词单一源（2.4 多片并行 · 纯函数：live 状态作为参数传入）。
   取人/分边/补片四件（takeFromQueue/splitSides/fillCourt/fillAllCourts）已随 2.8
   收编后端 live_rotation 单一真值——前端不算牌，「写响应视图落地即排好」；
   旧串行引擎（avail/fillCourts/nextMatch/maxCourts + cur/lastWinners）更早随批2 删。 */
import type { CheckStatus, LiveCourt, LiveState, User } from "@/api/types";

/** 「算到场」谓词单一源（store 转出口给候场条/签到浮层/二维码浮层消费；
    后端取队池同一把尺）：ok 正常 / late 迟到已到 / join 中途加入；
    absent 未到、left 早退不算 */
export const isArrived = (c?: CheckStatus): boolean =>
  c === "ok" || c === "late" || c === "join";

/** 空片谓词单一源（片上 A/B 两半边都没人＝没在打）：myRound 差几轮/
    记分与撤局守卫共用——布尔式散写已收此处，别再手拼 */
export const isIdle = (c: LiveCourt): boolean => !c.A.length && !c.B.length;

/** 按找现场玩家（alpha:1491 pById） */
export function pById(live: LiveState, id: number): User | undefined {
  return live.roster.find((p) => p.id === id);
}

/** 已占片数（非空片：A/B 任一半边有人即在打）——live 顶条场地输入校验
    （在打的片不能收）共用。 */
export function usedCourts(live: LiveState): number {
  return live.courts.filter((c) => !isIdle(c)).length;
}

/** 某名册行此刻在打哪片（A/B 任一半边含之；不在场上 → undefined）——换人出/入
    定向（store.swapPlayers）的场上谓词。
    （store 内另有按片号找片的 courtOf(courtId)，异名防混。） */
export function courtOfPerson(
  live: LiveState,
  id: number,
): LiveCourt | undefined {
  return live.courts.find((c) => c.A.includes(id) || c.B.includes(id));
}

/** 本地到分判定（2.3 记分本地化）：任一方够线且净胜 ≥2——与后端判分同式，
    但吃本机 localScores 账面（服务端已不记进行中比分）；命中即自动开上传窗。
    scoring 吃片分制快照（court.scoring），在打片照旧旧制 */
export function reachedLocal(sa: number, sb: number, scoring: number): boolean {
  return (sa >= scoring || sb >= scoring) && Math.abs(sa - sb) >= 2;
}

/** 每片人数单一源（双打 4 / 单打 2）——myRound/差人卡同口径，消灭 4 人硬编码。
    后端取队同值（live_rotation autofill_idle/requeue 内联按 rules.doubles 取 4/2，
    无独立符号）；前端只作展示换算，不作发牌依据 */
export const courtSize = (singles: boolean): number => (singles ? 2 : 4);

/** 差人一句话（空片差人卡与结算窗一步展示同吃的一句式）：够开一片 / 还差几人两分支 */
export function idleHint(waiting: number, size: number): string {
  return waiting >= size
    ? `候场 ${waiting} 人 · 够开 1 片`
    : `还差 ${size - waiting} 人 · 候场 ${waiting} / 需 ${size} 人`;
}

/** 还差几轮到我（队列位 0 起）：ceil((每片人数 × 空片数 + 位次 + 1) / 每片人数)——
    live store 的 myRound 与教学沙盒候场条同吃，口径改这里一处 */
export function roundsToPlay(
  size: number,
  emptyCourts: number,
  queueIdx: number,
): number {
  return Math.ceil((size * emptyCourts + queueIdx + 1) / size);
}

/** 确认窗胜方联动（「改比分胜方自动跟分高方」的纯函数面，EndSettleModal 与
    SandboxSettle 同吃）：分高方当胜方——分低的一方当不了胜方，落不出「分低的
    赢了」的战报；平分清空预选（返回 null＝禁确认，平分不预选）。
    前端联动、后端 settle-confirm 仍把关 */
export function followWinner(sa: number, sb: number): boolean | null {
  if (sa > sb) return true;
  if (sb > sa) return false;
  return null;
}

/** 确认窗胜方点选闸（分低方选不中；平分双方均可点——点了才有预选） */
export function canPickWinner(
  sa: number,
  sb: number,
  side: "a" | "b",
): boolean {
  return side === "a" ? sa >= sb : sb >= sa;
}

/** 片数单一源：订场登记优先（片数是花钱定下的默认值），未登记回退 maxPlayers≥12 三片否则两片。
    推荐矩阵与建片（store syncCourts）同源消费。 */
export function courtCount(live: LiveState): number {
  return live.g.courts?.length || (live.g.maxPlayers >= 12 ? 3 : 2);
}

/** 可打人数（推荐口径 2.4 §4.2）：片上 + 候场队；absent/left 不算（不进取人池，
    与后端取队同尺） */
export function activePlayers(live: LiveState): number {
  const onCourt = live.courts.reduce((s, c) => s + c.A.length + c.B.length, 0);
  const waiting = live.queue.filter((id) =>
    isArrived(pById(live, id)?.check),
  ).length;
  return onCourt + waiting;
}
