/* 沙盒状态机纯函数族（2.7 批1）——教学示例局的「谁上场谁下场」单一真值。
   轮转语义与后端 live_rotation 同口径（2.8 收编后真码，规格 §8 v2.3）：
   够人自动开赛（签到/带访客/加片/换人/结算出口顺手补满空片）、结算回流 n2
   （先上的先下·资历按上场章、下场入队尾→队首顶坑、无人候场=原班续场）、
   歇轮发牌时跳过并消耗一次保位留队、连战优先、改分等账面动作豁免补片。
   剧本两场下场者与真码一致（tests/sandbox-engine.test.ts 数字账锁死）。
   风格：原地更新（对齐 live_rotation 纯 dict/list 进出）——store 批2 包 reactive
   即得响应性；零框架 import、零网络（I3.2 解耦，可单测）。
   本地记分账不进 engine：比分在各手机本地记（localScores 同款），settle 只吃
   确认窗定死的终局比分。 */
import type { ChibiConfig } from "@/utils/chibi";
import {
  COURT_SIZE,
  ORGANIZE_ROSTER,
  PARTICIPATE_ROSTER,
  SANDBOX_GAME,
  type SandSeed,
} from "./data";

export type SandCheck = "none" | "ok" | "late" | "left";

export interface SandPlayer {
  id: number; // engine 按名册行序编（1 起，稳定）；steps/tests 按名册序拿
  name: string;
  chibi: ChibiConfig;
  you?: boolean;
  guest?: boolean; // 访客：照上场照摊费（份额归担保人），elo 只给展示值
  check: SandCheck;
  skip: number; // 剩余歇轮数：轮到发牌时消耗一次（takeFromQueue），0=不在歇
  fire: boolean; // 连战：候场里排到队首，与歇互斥
  admin: boolean; // 管理员徽章（组织卡第七步封；散场为止）
  mark: number; // 上场章：落位那次动作的 seq（先上的先下判据）；0=从未落位排最后
}

export interface SandCourt {
  no: number; // 片号 1..courtsCount
  a: number[]; // A 半边成员 id
  b: number[];
  scoring: number; // 片分制快照：开赛定格；改分制下一场起生效=续场/新片时刷新
  mark: number; // 片代次：该片开出第几场（开片 1、每次结算续场 +1）
}

export interface SandMatch {
  courtNo: number;
  winners: string[]; // 胜方名单快照（结算窗点选谁赢就是谁——胜负只管涨跌，不影响谁下）
  sa: number;
  sb: number;
}

export interface SandState {
  players: SandPlayer[]; // 名册（行序=资历并列时的稳定序）
  queue: number[]; // 候场队（队首在前，发牌从这里取）
  courts: SandCourt[]; // 恒覆盖 1..courtsCount（空片=差人卡位）；在打与否看 a/b 是否有人
  matches: SandMatch[]; // 战报（按结算序）；全场场数=matches.length
  feed: string[]; // 跑马灯句（新到旧在前）——真码 feed 无开赛/到场句，示例局自造句见各动作
  courtsCount: number;
  scoring: number; // 全局当前分制（改分只影响新开片与续场，在打片照旧）
  organizerId: number; // 组织者名册行（顶条「组织者 · ××」用；参与卡=阿豪、组织卡=你）
  seq: number; // 动作总号：一次动作恰一跳，落位者盖章=当次 seq（真码 total_seq 同款纪律）
  ended: boolean; // 散场收工过（endGame 守门：残局不清完不放行）
}

/* ───────── 内部件（口径镜像 live_rotation）───────── */

/** 到场谓词（真码 ARRIVED 同尺）：ok/late 算，none 未到、left 早退不算。
    沙盒域单一真值，steps/tests 也吃这份，别再手写第二份谓词。 */
export const arrived = (p: SandPlayer) =>
  p.check === "ok" || p.check === "late";

export const pOf = (s: SandState, id: number): SandPlayer => {
  const p = s.players.find((p) => p.id === id);
  if (!p) throw new Error(`沙盒名册里没有 ${id}`);
  return p;
};

/** 资历序（真码 _by_tenure）：上场章升序——先上的先下；没章的（mark 0=从未
    落位）排最后，彼此并列保持名册行序（sort 稳定）。 */
const byTenure = (ps: SandPlayer[]) =>
  [...ps].sort((x, y) => (x.mark || Infinity) - (y.mark || Infinity));

/** 队首取 n 人发牌（真码 take_from_queue 逐字镜像）：连战优先收（候场序内到场的
    fire 者先取、最多 n 个）；其余按队序扫描——轮到歇轮者跳过这一轮并消耗一次
    （skip-1）、坑由下一位顶、跳过者保位留队；未到者保位不动；取满即停，没被
    轮到的歇轮不消耗。 */
function takeFromQueue(s: SandState, n: number): number[] {
  if (n <= 0) return [];
  const pre = s.queue
    .filter((pid) => {
      const p = pOf(s, pid);
      return p.fire && arrived(p);
    })
    .slice(0, n);
  const taken = [...pre];
  const preSet = new Set(pre);
  const kept: number[] = [];
  for (const pid of s.queue) {
    if (preSet.has(pid)) continue;
    if (taken.length < n) {
      const p = pOf(s, pid);
      if (arrived(p) && !p.skip) {
        taken.push(pid);
        continue;
      }
      if (arrived(p)) p.skip -= 1; // 轮到发牌给他：跳过这一轮、消耗一次
    }
    kept.push(pid); // 让位者/未到者/余额：保位留队
  }
  s.queue.splice(0, s.queue.length, ...kept);
  return taken;
}

/** 空片补满（真码 autofill_idle + 出口语义）：先按 courtsCount 补占位片，再按
    片号序把所有空片补满——候场里可发人数（到场且不在歇）不够一片的留空、
    不动队列（歇不消耗）。补开一片滚一句「人够 4 · 自动开赛」（真码无此事件，
    规格 A4 自认示例局自造句教这条规矩）。 */
function fillIdle(s: SandState): void {
  for (let no = s.courts.length + 1; no <= s.courtsCount; no++) {
    s.courts.push({ no, a: [], b: [], scoring: s.scoring, mark: 0 });
  }
  const idle = [...s.courts].sort((x, y) => x.no - y.no);
  for (const c of idle) {
    if (c.a.length || c.b.length) continue;
    const issuable = s.queue.filter((pid) => {
      const p = pOf(s, pid);
      return arrived(p) && !p.skip;
    }).length;
    if (issuable < COURT_SIZE) continue; // 教学局锁双打 4 人制
    const ids = takeFromQueue(s, COURT_SIZE);
    const half = (ids.length + 1) >> 1; // 按候场队序对半：第 1、2 位一队
    c.a.splice(0, c.a.length, ...ids.slice(0, half));
    c.b.splice(0, c.b.length, ...ids.slice(half));
    for (const pid of ids) pOf(s, pid).mark = s.seq;
    c.mark = 1;
    s.feed.unshift("人够 4 · 自动开赛");
  }
}

const removeFromCourt = (c: SandCourt, pid: number): void => {
  const i = c.a.indexOf(pid);
  if (i >= 0) c.a.splice(i, 1);
  const j = c.b.indexOf(pid);
  if (j >= 0) c.b.splice(j, 1);
};

/* ───────── 动作族（每个动作恰一跳 seq，落位者盖章=当次 seq）───────── */

/** 到场（真码 check_in 镜像，含代办/带访客出口）：入候场队尾（首报进队、重复
    报到不重排；left 回来也是队尾）；'left'=早退——清队列位与片上位置，片上
    缺人打短维持现状（补人归手动换人）。落账后出口补片（够一片人数自动开赛）。 */
export function checkIn(
  s: SandState,
  id: number,
  status: "ok" | "late" | "left" = "ok",
): void {
  // 在打者再报到是空操作：不挡会把场上的人又塞进候场（一人场上一份、队里一份）。
  // 'left' 早退不在此列——它本来就是从场上摘人的正路（见下分支）。
  if (
    status !== "left" &&
    s.courts.some((c) => c.a.includes(id) || c.b.includes(id))
  )
    return;
  s.seq += 1;
  const p = pOf(s, id);
  if (status === "left") {
    p.check = "left";
    const qi = s.queue.indexOf(id);
    if (qi >= 0) s.queue.splice(qi, 1);
    const c = s.courts.find((c) => c.a.includes(id) || c.b.includes(id));
    if (c) removeFromCourt(c, id);
  } else {
    p.check = p.check === "left" ? "ok" : status; // 回来按新到处理，一样排队尾
    if (!s.queue.includes(id)) s.queue.push(id);
  }
  fillIdle(s);
}

/** 结算确认（真码 settle_confirm 的回流半边，规矩锁定 n2·按候场队序）：记战报
    （胜方名单+定死比分）→ 比上资历取先上者 2 人下场入队尾 → 队首顶进他们
    让出的半边；无人候场=下场者随即被取回→原班续场（取回者不重盖章——真码
    ORM 行比对「全下全上又回来的算没离开过」同款）。供给不足坑位留空。
    续场即新场：片分制快照刷新（改分「下一场起生效」的兑现点）、片代次 +1。
    出口顺手补满别的空片（真码 _finish 默认档）。 */
export function settle(
  s: SandState,
  courtNo: number,
  winner: "a" | "b",
  sa: number,
  sb: number,
): void {
  const c = s.courts.find((c) => c.no === courtNo);
  if (!c || (!c.a.length && !c.b.length)) return; // 空片无局可结（教学剧本不走到，防呆）
  s.seq += 1;
  const winIds = winner === "a" ? c.a : c.b;
  s.matches.push({
    courtNo,
    winners: winIds.map((pid) => pOf(s, pid).name),
    sa,
    sb,
  });
  s.feed.unshift(
    `${winIds.map((pid) => pOf(s, pid).name).join(" & ")} ${sa}:${sb} 拿下`,
  );
  const oncourt = s.players.filter(
    (p) => c.a.includes(p.id) || c.b.includes(p.id),
  );
  const sideOf = (pid: number): "a" | "b" => (c.a.includes(pid) ? "a" : "b");
  const downs = byTenure(oncourt).slice(0, 2); // 先上的先下（并列按名册行序）
  const sides = downs.map((p) => sideOf(p.id));
  for (const p of downs) {
    removeFromCourt(c, p.id);
    s.queue.push(p.id);
  }
  const downSet = new Set(downs.map((p) => p.id));
  // N 个坑一次取齐（真码注释同款：逐坑取会让队首歇者被第一坑消耗后又被第二坑捞上）
  takeFromQueue(s, downs.length).forEach((pid, i) => {
    (sides[i] === "a" ? c.a : c.b).push(pid);
    if (!downSet.has(pid)) pOf(s, pid).mark = s.seq;
  });
  c.mark += 1;
  c.scoring = s.scoring;
  fillIdle(s);
}

/** 换人（真码 swap 镜像）：候场者出队原位顶场上者的坑、被换下者回队尾；
    换上即落位盖章（资历从此刻起算）。出口补片。 */
export function swap(s: SandState, outId: number, inId: number): void {
  const c = s.courts.find((c) => c.a.includes(outId) || c.b.includes(outId));
  if (!c) return; // 被换的人不在场上（教学剧本不走到，防呆）
  s.seq += 1;
  const side = c.a.includes(outId) ? c.a : c.b;
  side.splice(side.indexOf(outId), 1, inId);
  const qi = s.queue.indexOf(inId);
  if (qi >= 0) s.queue.splice(qi, 1);
  s.queue.push(outId);
  pOf(s, inId).mark = s.seq;
  s.feed.unshift(`你 把 ${pOf(s, outId).name} 换下 · ${pOf(s, inId).name} 上`); // 句式照真码 feedSentences
  fillIdle(s);
}

/** 加片（组织卡第八步「加片即自动开」）：片数 +1，出口顺手补满所有空片——
    新片分制快照用当前全局分制（2.8 写路径公共出口语义）。 */
export function addCourt(s: SandState): void {
  s.seq += 1;
  s.courtsCount += 1;
  fillIdle(s);
}

/** 改分制（真码 rules 账面动作）：全局生效，在打片照旧打完、续场与新片用新制
    （settle 刷新快照兑现「下一场起生效」）。账面动作豁免补片（2.8 口径）。 */
export function setScoring(s: SandState, scoring: number): void {
  s.seq += 1;
  s.scoring = scoring;
}

/** 歇/连（真码 tempo 镜像）：'skip' 按一次叠一轮、与连战互斥；'unskip' 清零；
    'fire' 连战——候场里的人排到队首、再按一次取消（队列不动）。出口恒开：
    取消歇恰好凑齐最后一人时点亮空片（真码验收同款）。 */
export function tempo(
  s: SandState,
  id: number,
  action: "skip" | "unskip" | "fire",
): void {
  s.seq += 1;
  const p = pOf(s, id);
  if (action === "unskip") {
    p.skip = 0;
  } else if (action === "skip") {
    p.fire = false;
    p.skip += 1;
  } else {
    p.fire = !p.fire;
    if (p.fire) {
      p.skip = 0;
      const qi = s.queue.indexOf(id);
      if (qi >= 0) {
        s.queue.splice(qi, 1);
        s.queue.unshift(id);
      }
    }
  }
  fillIdle(s);
}

/** 封管理员（组织卡第七步）：带徽章、与组织者同权、散场为止（不可收——教学
    剧本不需要收回出口）。句式照真码 feedSentences。 */
export function setAdmin(s: SandState, id: number): void {
  s.seq += 1;
  const p = pOf(s, id);
  p.admin = true;
  s.feed.unshift(`组织者封 ${p.name} 为管理员`);
}

/** 「未完对局全部取消」一键（真码 sweep_cancel_all 镜像）：全部在打片按片号
    序作废——场上的人原样回流队首（保名册行序）、不计分不留战报、片转空。
    豁免补片（一键清完要能散场，重发会变出残局）。 */
export function sweepCancelAll(s: SandState): void {
  const head: number[] = [];
  for (const c of [...s.courts].sort((x, y) => x.no - y.no)) {
    if (!c.a.length && !c.b.length) continue;
    head.push(
      ...s.players
        .filter((p) => c.a.includes(p.id) || c.b.includes(p.id))
        .map((p) => p.id),
    );
    c.a.splice(0, c.a.length);
    c.b.splice(0, c.b.length);
    c.mark += 1; // 片号前进（真码 _void_court 落 _bump_court 同款）
  }
  if (!head.length) return; // 无残局不动（重试幂等）
  s.queue.unshift(...head);
  s.seq += 1;
}

/** 散场收工（真码 end 镜像的守门半边）：残局不清完不放行；清完落 ended=true，
    收工账单是写死常量（data.ORG_FINAL_BILL），engine 不算账。 */
export function endGame(s: SandState): boolean {
  if (s.courts.some((c) => c.a.length || c.b.length)) return false;
  s.seq += 1;
  s.ended = true;
  return true;
}

/** 跑马灯剧本句入口（「凯文 · 迟到了」等 NPC 调度表的 feed 句从这进——
    真码 feed 无此文体，示例局自造句与动作内置句在这里会合）。 */
export function pushFeed(s: SandState, sentence: string): void {
  s.feed.unshift(sentence);
}

/* ───────── 开局 ───────── */

function initState(seeds: SandSeed[]): SandState {
  const players: SandPlayer[] = seeds.map((sd, i) => ({
    id: i + 1,
    name: sd.name,
    chibi: sd.chibi,
    you: sd.you,
    guest: sd.guest,
    check: sd.check,
    skip: 0,
    fire: false,
    admin: false,
    mark: 0,
  }));
  const orgIdx = seeds.findIndex((sd) => sd.organizer);
  return {
    players,
    queue: players.filter((p) => arrived(p)).map((p) => p.id), // 开场候场=已到者按名册序
    courts: [{ no: 1, a: [], b: [], scoring: SANDBOX_GAME.scoring, mark: 0 }],
    matches: [],
    feed: [],
    courtsCount: 1, // 两卡都 1 片起步（组织卡第八步加到 2）
    scoring: SANDBOX_GAME.scoring,
    organizerId: orgIdx >= 0 ? orgIdx + 1 : 1,
    seq: 0,
    ended: false,
  };
}

/** 参与卡开局：一片场、阿豪老周在等、你未签到（幕一差人卡「还差 2 人」）。 */
export const initParticipate = (): SandState => initState(PARTICIPATE_ROSTER);

/** 组织卡开局：已开账、签到序老周→小敏→你在候场、你是组织者、无人任管理员。 */
export const initOrganize = (): SandState => initState(ORGANIZE_ROSTER);
