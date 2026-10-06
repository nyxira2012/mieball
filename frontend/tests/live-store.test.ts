import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { U } from "@/api";
import type { EntryRow, Game, User } from "@/api/types";

/* 每个用例重置模块图 → 全新 mock 数据；102（balance · 8 上限）与 101（winner · 12 上限）
   两组真局 fixture 做确定性推演。
   2.1 打球页改版（批1）：终局从「到分自动落账」改为 point→settling 快照→confirmSettle 确认落账。
   1.2 隔离线：startLive 吃重塑后的真局对象（形状与后端 game_view 镜像），名册从 formal
   报名行展开、mock U 同 id 者借真实战绩对象（结算落回战力榜）。
   2.2 批2：开场全员「未到」不发牌——需要场上态的用例经 arrive() 搭（真实代码路径：
   代办到场 → 到场支线自动发牌）；fixture 开球时刻定格在过去，到场按口径归一为「迟到队尾」。 */
beforeEach(async () => {
  vi.resetModules();
  setActivePinia(createPinia());
});

async function load() {
  const liveMod = await import("@/stores/live");
  const uiMod = await import("@/stores/ui");
  return { live: liveMod.useLiveStore(), ui: uiMod.useUiStore() };
}

/** 到场搭态：借管理员身份代办到场（102 我是组织者、外挂无副作用）；过开球 → 归一迟到队尾，
    逐人触发到场支线的自动发牌（4 人即上片顶 cur）。 */
function arrive(
  live: ReturnType<typeof import("@/stores/live").useLiveStore>,
  ids?: number[],
): void {
  const L = live.live!;
  L.admins.push(U.me.id);
  for (const id of ids ?? L.roster.map((p) => p.id)) live.setCheck(id, "ok");
  L.admins.pop();
}

const person = (u: User) => ({ id: u.id, nickname: u.name, chibi: u.chibi });
const entry = (u: User, bring = 0): EntryRow => ({
  account: person(u),
  bring,
  standing: "formal",
  waitSeq: null,
});

/** 102 同构（原 mock 种子口径）：我组织 · li 带 1 · bei，balance，已订场 2 片 */
function g102(): Game {
  return {
    id: 102,
    name: "周末午后局",
    organizer: person(U.me),
    startAt: "2026-10-06T14:00:00+08:00",
    endAt: "2026-10-06T16:00:00+08:00",
    deadlineAt: "2026-10-06T12:00:00+08:00",
    venueName: "望京 · 花家地球馆",
    venueAddress: null,
    minPlayers: 4,
    maxPlayers: 8,
    visibility: "public",
    scoring: 11,
    rotation: "balance",
    scoreRule: "rally",
    manualLock: false,
    courts: ["3号", "5号"],
    feeTotal: 480,
    status: "locked",
    unlocked: false,
    joinable: true,
    heads: 4,
    slotsLeft: 4,
    perHead: 120,
    forced: true,
    entries: [entry(U.me), entry(U.li, 1), entry(U.bei)],
    my: {
      isOrganizer: true,
      myEntry: { bring: 0, standing: "formal", waitSeq: null },
      invited: false,
    },
  };
}

/** 101 同构：11 人报名（hai 带 2 · zhao 随行在 mock U 带阴影标）· winner 模式 · 未订场 */
function g101(): Game {
  return {
    ...g102(),
    id: 101,
    name: "周四夜战",
    organizer: person(U.wang),
    maxPlayers: 12,
    slotsLeft: 1,
    rotation: "winner",
    courts: null,
    feeTotal: 720,
    forced: false,
    entries: [
      entry(U.wang),
      entry(U.hai, 2),
      entry(U.wu),
      entry(U.gu),
      entry(U.li),
      entry(U.me),
      entry(U.shi),
      entry(U.yang),
      entry(U.bei),
      entry(U.tong),
      entry(U.zhao),
    ],
    my: {
      isOrganizer: false,
      myEntry: { bring: 0, standing: "formal", waitSeq: null },
      invited: false,
    },
  };
}

/** 线上满员 8 人局（max 8 · 我未报名 · 已订 2 片）：§5 边界「线上满员空降 → 名册超上限照常发牌」 */
const gFull8Id = 108;
function gFull8(): Game {
  return {
    ...g102(),
    id: gFull8Id,
    name: "满员局",
    organizer: person(U.li),
    maxPlayers: 8,
    slotsLeft: 0,
    rotation: "rotate",
    entries: [
      entry(U.li),
      entry(U.bei),
      entry(U.wu),
      entry(U.gu),
      entry(U.shi),
      entry(U.yang),
      entry(U.tong),
      entry(U.zhang),
    ],
    my: { isOrganizer: false, myEntry: null, invited: false },
  };
}

/** 把 102 局 4 人全部到场（自动发牌上 cur），再打到 11:9（到分，settling 已开未落账）。
    返回句柄 + 访客 id（roster[2]） */
async function setupSettling() {
  const h = await load();
  h.live.startLive(g102());
  const L = h.live.live!;
  arrive(h.live); // 4 人到场 → 到场支线自动发牌上 cur
  for (let i = 0; i < 9; i++) h.live.point("a");
  for (let i = 0; i < 9; i++) h.live.point("b");
  h.live.point("a");
  h.live.point("a"); // 11:9
  return { ...h, L, guest: L.roster[2].id };
}

describe("startLive（2.2 批2§4.1 开场点亮）", () => {
  it("全员「未到」开场：候场空、不发牌不报错；随行展开成编号访客（·1 起）、底账起笔挂担保人", async () => {
    const { live } = await load();
    expect(live.hasLive).toBe(false);
    const msg = live.startLive(g102()); // entries: me + li(bring 1) + bei → 4 人
    const L = live.live!;
    const guest = L.roster[2];
    expect(msg).toBe("球局开始 · 现场已点亮");
    expect(live.hasLive).toBe(true);
    expect(L.g.id).toBe(102); // 现场克隆局：改动不回写 game store（派生态归后端）
    expect(L.roster).toHaveLength(4);
    expect(L.roster.filter((p) => p.shadow)).toHaveLength(1);
    expect(guest.shadow).toBe(true);
    expect(guest.name).toBe("亮马的球友·1"); // 随行访客编号从 ·1 起（§4.1「小李的球友·1」）
    expect(guest.elo).toBe(1200);
    expect(L.roster.every((p) => p.check === "absent")).toBe(true); // 每人先记未到，谁报到谁亮
    expect(L.roster.every((p) => p.skip === 0)).toBe(true);
    expect(L.startedAt).toBeTruthy(); // 点亮时刻落账
    expect(L.queue).toEqual([]); // 候场区空：报到的人按先后排进
    expect(L.courts).toEqual([]); // 不发牌——够一片的人数是到场攒出来的
    expect(L.cur).toBeNull();
    expect(L.ledger).toEqual([
      { id: 0, name: "我" },
      { id: 5, name: "亮马河快攻" },
      {
        id: guest.id,
        name: "亮马的球友·1",
        shadow: true,
        guarantor: "亮马河快攻",
      },
      { id: 8, name: "北苑小钢炮" },
    ]); // 正式一人一行、随行行挂担保人名
  });
  it("101 开场 13 人（3 随行）全员未到：底账 13 行、候场空不发牌", async () => {
    const { live } = await load();
    live.startLive(g101());
    const L = live.live!;
    expect(L.roster).toHaveLength(13);
    expect(L.roster.filter((p) => p.shadow)).toHaveLength(3); // hai 带 2 访客 + zhao 本就是随行
    expect(L.roster.every((p) => p.check === "absent")).toBe(true);
    expect(L.queue).toEqual([]);
    expect(L.cur).toBeNull();
    expect(L.ledger).toHaveLength(13);
    expect(L.ledger.filter((r) => r.shadow)).toHaveLength(3);
    expect(L.ledger.filter((r) => r.guarantor === "海淀吊小球")).toHaveLength(
      2,
    );
  });
  it("到场攒局（§4.1「够一片的人数就自动发牌上片」）：4 人到场即上 cur", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    live.setCheck(0, "ok"); // 1 人：亮已到、进候场，不够一片
    expect(L.cur).toBeNull();
    expect(L.queue).toEqual([0]);
    arrive(
      live,
      L.roster.slice(1).map((p) => p.id),
    ); // 其余 3 人到场 → 够一片
    expect(L.cur).toEqual({ A: [5, L.roster[2].id], B: [0, 8], sa: 0, sb: 0 }); // balance 蛇形按分降序
    expect(L.queue).toEqual([]); // 全部上场
  });
});

describe("point → settling → confirmSettle（2.1 §5 结算流 · alpha:1688-1728 数值口径）：K=24 / 败方六成 / 随行半权重", () => {
  it("11:9 到点开 settling（cur 不动），confirmSettle(true,11,9) 落账 + 自动排下一场，战力榜联动", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    const guest = L.roster[2].id;
    arrive(live); // 4 人到场 → 到场支线自动发牌上 cur
    for (let i = 0; i < 9; i++) live.point("a");
    for (let i = 0; i < 9; i++) live.point("b"); // 9:9（先到 11 前不收局）
    expect(live.settling).toBeNull();
    live.point("a");
    live.point("a"); // 11:9 → 到点转结算弹窗（不落账）
    expect(live.settling).toEqual({ sa: 11, sb: 9 });
    expect(L.cur).not.toBeNull(); // cur 保持不动，等弹窗确认
    expect(L.cur!.sa).toBe(11);
    live.confirmSettle(true, 11, 9);
    // A=[li,访客] vs B=[me,bei]：人均 1387 vs 1485 → delta=15，loss=9，访客 ceil(15/2)=8
    expect(live.settling).toBeNull();
    expect(L.history[0]).toEqual({
      names: "亮马河快攻 & 亮马的球友·1",
      sa: 11,
      sb: 9,
    });
    const { U } = await import("@/api");
    expect(U.li.elo).toBe(1589); // 1574+15 —— roster 与 mock U 同一对象
    expect(U.li.month).toBe(29); // 14+15
    expect(U.li.win).toBe(30); // 29+1
    expect(U.me.elo).toBe(1509); // 1518-9
    expect(U.bei.elo).toBe(1443); // 1452-9
    expect(U.me.last5).toEqual(["L", "W", "W", "L", "L"]); // 输球 L 入尾（仅我滚动，alpha:1707）
    expect(guest >= 9000).toBe(true);
    expect(L.roster[2].elo).toBe(1208); // 访客 1200+8
    expect(L.lastWinners).toEqual([5]); // 随行不进胜者留场名单
    // 队列口径同旧 endMatch：败者回队尾 + balance ≠ winner 胜者也回队（[0,8,5,guest]），
    // 但 confirmSettle 紧接着 fillCourts+nextMatch —— 4 人正好重排成 1 片上 cur（中间态不可观测）
    expect(L.round).toBe(1);
    expect(L.queue).toEqual([]);
    expect(L.cur).toEqual({ A: [5, guest], B: [0, 8], sa: 0, sb: 0 });
  });
  it("弹窗改胜方：confirmSettle(false, 9, 11) 按新胜方（B 队）结算，改过的比分写回", async () => {
    const { live, L } = await setupSettling();
    live.confirmSettle(false, 9, 11); // 组织者改判 B 胜、比分倒转
    // B=[me,bei] 人均 1485 胜 A=[li,访客] 人均 1387 → delta=9，loss=5，访客 floor(-5/2)=-3
    expect(L.history[0]).toEqual({ names: "我 & 北苑小钢炮", sa: 9, sb: 11 });
    expect(L.lastWinners).toEqual([0, 8]);
    const { U } = await import("@/api");
    expect(U.me.elo).toBe(1527); // 1518+9
    expect(U.bei.elo).toBe(1461); // 1452+9
    expect(U.li.elo).toBe(1569); // 1574-5
    expect(L.roster[2].elo).toBe(1197); // 访客 1200-3（半权重 floor）
    expect(U.me.last5).toEqual(["L", "W", "W", "L", "W"]); // 赢球 W 入尾
  });
  it("closeSettle 不落账：比分保留在 cur，可继续计分重新到点", async () => {
    const { live, L } = await setupSettling();
    live.closeSettle();
    expect(live.settling).toBeNull();
    expect(L.cur).not.toBeNull();
    expect(L.cur!.sa).toBe(11); // 比分保留
    expect(L.cur!.sb).toBe(9);
    expect(L.history).toHaveLength(0); // 未落账
    const { U } = await import("@/api");
    expect(U.li.elo).toBe(1574); // elo 原封
    live.point("b"); // 继续计分：11:10 净胜 1 不收
    expect(live.settling).toBeNull();
    expect(L.cur!.sb).toBe(10);
    live.point("b"); // 11:11
    live.point("b"); // 11:12
    live.point("b"); // 11:13 → 净胜 2 到点，弹窗重开
    expect(live.settling).toEqual({ sa: 11, sb: 13 });
  });
  it("11:10 不收局，undoPoint 按最后得分方回退，12:10 到点开弹窗、确认后入史", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    arrive(live); // 4 人到场 → cur
    for (let i = 0; i < 10; i++) live.point("a");
    for (let i = 0; i < 10; i++) live.point("b");
    expect(L.cur).not.toBeNull(); // 10:10
    live.point("a");
    expect(L.cur!.sa).toBe(11);
    expect(live.settling).toBeNull(); // 11:10 净胜 1 → 继续
    live.undoPoint();
    expect(L.cur!.sa).toBe(10); // 撤回 A 的分
    live.point("a");
    live.point("a"); // 12:10 → 到点
    expect(live.settling).toEqual({ sa: 12, sb: 10 });
    expect(L.cur).not.toBeNull(); // cur 还在，等确认
    live.confirmSettle(true, 12, 10);
    expect(L.history[0].sa).toBe(12);
    expect(L.history[0].sb).toBe(10);
  });
  it("openSettle：手动入口快照当前比分；无 cur 时静默不开", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    arrive(live); // 4 人到场 → cur
    live.point("a");
    live.point("a"); // 2:0 未到分
    expect(live.settling).toBeNull();
    live.openSettle(); // 卡上「终局结算」钮
    expect(live.settling).toEqual({ sa: 2, sb: 0 });
    live.confirmSettle(true, 2, 0); // 手动终局也走同一落账口径
    expect(L.history[0]).toEqual({
      names: "亮马河快攻 & 亮马的球友·1",
      sa: 2,
      sb: 0,
    });
    expect(live.settling).toBeNull();
    live.openSettle(); // 下一场已自动排好（cur 在）→ 可开
    expect(live.settling).toEqual({ sa: 0, sb: 0 });
    live.cancelMatch(); // 取消对局 → 结算弹窗随对局一并关
    expect(live.settling).toBeNull();
    live.openSettle(); // 无 cur → 静默不开
    expect(live.settling).toBeNull();
  });
});

describe("setCheck / togglePerson / cancelMatch / clearScore / autoDeal（2.1 §2-4）", () => {
  /** 打完收局再取消：4 人全回候场（queue=[li,访客,me,bei]），从干净队列出发 */
  async function setupQueue() {
    const h = await setupSettling();
    h.live.confirmSettle(true, 11, 9); // 落账 + 自动排下一场 → cur={A:[li,访客],B:[me,bei]}
    h.live.cancelMatch(); // 人回流 → 队列 [li,访客,me,bei]
    return { live: h.live, L: h.L, guest: h.guest };
  }
  /** 队位观察稳态（101）：11 人到场 → cur + 待开片两片全占、3 人候场——
      片满则到场只排队不发牌，统一队尾的次序才可观测 */
  async function setupTails() {
    const h = await load();
    h.live.startLive(g101());
    const L = h.live.live!;
    L.admins.push(U.me.id);
    arrive(
      h.live,
      L.roster.slice(0, 11).map((p) => p.id),
    );
    return { live: h.live, L };
  }
  it("setCheck：迟到重排队尾 / 早退出列 / 中途加入队尾——排队位统一队尾（修订④）", async () => {
    const { live, L } = await setupTails();
    expect(L.queue).toEqual([6, 7, 8]); // shi/yang/bei 候场（winner 顺序按报名序发牌）
    live.setCheck(7, "late"); // 已迟到者重复报到 → 重排队尾，不触发发牌（新到场才发）
    expect(L.queue).toEqual([6, 8, 7]);
    live.setCheck(8, "left"); // 早退 → 出列
    const beiRow = L.roster.find((p) => p.id === 8)!;
    expect(beiRow.check).toBe("left");
    expect(beiRow.leftAt).toBeTruthy(); // 早退当场落离场时刻
    expect(L.ledger.find((r) => r.id === 8)!.leftAt).toBe(beiRow.leftAt);
    expect(L.feed[0]).toBe("北苑小钢炮 早退 · 已记离场时刻");
    expect(L.queue).toEqual([6, 7]); // 候场/在打同清（8 原只在候场）
    live.setCheck(8, "join");
    expect(L.queue).toEqual([6, 7, 8]); // 中途加入 → 队尾（翻案：原插队首）；6、7 守序不变
    expect(beiRow.check).toBe("join");
    live.setCheck(8, "left");
    live.setCheck(8, "ok"); // 早退者再报到 → 「回来也是队尾」（走中途加入口径）
    expect(beiRow.check).toBe("join");
    expect(L.queue[L.queue.length - 1]).toBe(8);
    expect(L.queue[0]).toBe(6);
  });
  it("到场口径归一（§4.2）：未到首报过开球=迟到队尾；未过开球=已到，也一样按先后队尾", async () => {
    const { live } = await load();
    live.startLive({ ...g102(), startAt: "2027-01-01T14:00:00+08:00" }); // 开球在未来
    let L = live.live!;
    live.setCheck(0, "ok");
    expect(L.roster.find((p) => p.id === 0)!.check).toBe("ok");
    expect(L.queue).toEqual([0]);
    live.startLive(g102()); // 开球在过去（fixture 定格）
    L = live.live!;
    live.setCheck(0, "ok");
    expect(L.roster.find((p) => p.id === 0)!.check).toBe("late"); // 归一成迟到
    expect(L.queue).toEqual([0]); // 队位不变：队尾
    expect(L.roster.find((p) => p.id === 0)!.arriveAt).toBeTruthy(); // 几点到当场落账
  });
  it("setCheck late：缺席者（原不在队）到场即从队尾进队（avail 放行的配套口径）", async () => {
    const { live } = await load();
    live.startLive(g101());
    const L = live.live!;
    L.admins.push(U.me.id); // 2.2 权限地基：代办他人到点是收权动作——机制用例以管理员身份跑
    const absentId = L.roster.find((p) => p.check === "absent")!.id;
    expect(L.queue).not.toContain(absentId);
    live.setCheck(absentId, "late");
    expect(L.queue[L.queue.length - 1]).toBe(absentId);
  });
  it("avail 放行迟到（2.1 §3 裁决）：到场攒局自动发牌，迟到者 autoDeal 照样上场", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    expect(L.cur).toBeNull(); // 开场不发牌
    arrive(live); // 4 人到场 → 自动发牌上 cur（balance 蛇形）
    expect(L.cur).toEqual({ A: [5, L.roster[2].id], B: [0, 8], sa: 0, sb: 0 });
    live.cancelMatch(); // 全员候场 [li, 访客, me, bei]
    live.setCheck(5, "late"); // li 迟到 → 队尾、check='late'
    live.autoDeal(); // balance 蛇形重发：li1574 me1518 bei1452 访客1200
    expect(L.cur).toEqual({ A: [5, L.roster[2].id], B: [0, 8], sa: 0, sb: 0 }); // 迟到的 li 照样上场
  });
  it("togglePerson：歇两轮(2/0)与连战互斥、连战队首、任意人可设", async () => {
    const { live, L } = await setupQueue();
    live.togglePerson(0, "skip");
    expect(L.roster.find((p) => p.id === 0)!.skip).toBe(2); // 歇两轮
    live.togglePerson(0, "fire");
    const meP = L.roster.find((p) => p.id === 0)!;
    expect(meP.fire).toBe(true);
    expect(meP.skip).toBe(0); // 互斥
    expect(L.queue[0]).toBe(0); // 连战 → 队首
    live.togglePerson(0, "fire");
    expect(meP.fire).toBe(false);
    live.togglePerson(5, "skip"); // 任意人（组织者代设）
    expect(L.roster.find((p) => p.id === 5)!.skip).toBe(2);
    live.togglePerson(5, "skip");
    expect(L.roster.find((p) => p.id === 5)!.skip).toBe(0);
  });
  it("cancelMatch：人回流队尾、不计积分、无待开片则 cur=null", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    arrive(live); // 4 人到场 → cur
    const guest = L.roster[2].id;
    for (let i = 0; i < 5; i++) live.point("a"); // 5:0 未打完
    live.cancelMatch();
    expect(L.cur).toBeNull();
    expect(L.queue).toEqual([5, guest, 0, 8]); // A、B 依次回队尾
    expect(L.history).toHaveLength(0); // 不计积分
    expect(L.round).toBe(0);
    const { U } = await import("@/api");
    expect(U.li.elo).toBe(1574); // elo 原封
  });
  it("cancelMatch：有待开片则顶上（101：cur 取消 → 待开片上记分板）", async () => {
    const { live } = await load();
    live.startLive(g101());
    const L = live.live!;
    L.admins.push(U.me.id); // 2.2 权限地基：取消对局收权——机制用例以管理员身份跑
    arrive(
      live,
      L.roster.slice(0, 9).map((p) => p.id),
    ); // 前 9 人到场攒出 cur + 待开片
    expect(L.courts).toHaveLength(1); // 一片在打 + 一片待开
    live.cancelMatch();
    expect(L.cur).toEqual({ A: [3, 4], B: [5, 0], sa: 0, sb: 0 }); // 待开片顶上（101 winner 模式按报名序发牌：
    // 3=wu 五道口钉子步 · 4=gu 国贸截击手 / 5=li 亮马河快攻 · 0=me 我；头片 wang/hai/两位随行访客已被取消回队尾）
    expect(L.courts).toHaveLength(0);
    expect(L.queue).toHaveLength(5); // 原场上 4 人回队尾 + 原候场 1 人
  });
  it("clearScore：比分与最后得分方一起清零（undo 不再误撤）", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    arrive(live); // 4 人到场 → cur
    live.point("a");
    live.point("b");
    live.point("a"); // 2:1，last='a'
    live.clearScore();
    expect(L.cur!.sa).toBe(0);
    expect(L.cur!.sb).toBe(0);
    expect(L.last).toBeUndefined();
    live.undoPoint(); // last 已清 → 0:0 原地不动
    expect(L.cur!.sa).toBe(0);
    expect(L.cur!.sb).toBe(0);
  });
  it("autoDeal：空闲时发牌并顶上一场；cur 在则只补片不动 cur", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    const guest = L.roster[2].id;
    arrive(live); // 4 人到场 → 到场支线已自动顶上 cur
    live.cancelMatch(); // 全员候场、无 cur
    live.autoDeal();
    expect(L.cur).toEqual({ A: [5, guest], B: [0, 8], sa: 0, sb: 0 }); // balance 重排
    expect(L.queue).toEqual([]);
    live.point("a");
    live.autoDeal(); // cur 在 → 不顶新场
    expect(L.cur!.sa).toBe(1);
  });
});

describe("swapPlayers / addGuests / setCourtsInput / myRound（2.1 §1/§3/§4）", () => {
  it("swapPlayers：场上↔候场互换（cur 的 outId→inId，候场的坑由 outId 顶）", async () => {
    const { live } = await load();
    const { U } = await import("@/api");
    live.startLive(g102());
    const L = live.live!;
    arrive(live); // 4 人到场 → cur
    live.addGuests(1, "小陈", U.me);
    const xin = L.roster[4].id; // 新访客在候场队尾
    live.swapPlayers(8, xin); // 场上的 bei ↔ 候场的小陈
    expect(L.cur!.B).toEqual([0, xin]); // cur.B 里 8 → 小陈
    expect(L.queue).toEqual([8]); // 候场的坑由 bei 顶，次序不乱
  });
  it("addGuests：空名→「介绍人前两字+的球友」；非空多位→name·1/name·2（·1 起）；单位不带序号；shadow 进队尾+底账挂担保人", async () => {
    const { live } = await load();
    const { U } = await import("@/api");
    live.startLive(g102());
    const L = live.live!;
    expect(L.queue).toEqual([]); // 开场候场空
    live.addGuests(2, "", U.li);
    const auto = L.roster.slice(4, 6);
    expect(auto.map((g) => g.name)).toEqual(["亮马的球友", "亮马的球友"]);
    expect(
      auto.every(
        (g) => g.shadow && g.elo === 1200 && g.check === "join" && g.id >= 9000,
      ),
    ).toBe(true);
    expect(L.queue).toEqual(auto.map((g) => g.id)); // 队尾依次进
    expect(
      L.ledger
        .slice(4, 6)
        .every((r) => r.shadow && r.guarantor === "亮马河快攻"),
    ).toBe(true); // 底账加行挂担保人（访客谁带的）
    live.addGuests(2, "小陈", U.me);
    expect(L.roster.slice(6, 8).map((g) => g.name)).toEqual([
      "小陈·1",
      "小陈·2",
    ]);
    live.addGuests(1, "老周", U.bei);
    expect(L.roster[8]!.name).toBe("老周");
    expect(L.queue).toHaveLength(5);
  });
  it("setCourtsInput：『3、4 / 3,4 / 3 4 / 3号、4号』归一成 [3号,4号] 写 booked", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    expect(L.g.courts).toEqual(["3号", "5号"]); // mock 原值
    for (const txt of ["3、4", "3,4", "3 4", "3号、4号"]) {
      expect(live.setCourtsInput(txt)).toBe(true);
      expect(L.g.courts).toEqual(["3号", "4号"]);
    }
  });
  it("setCourtsInput：在打+待开不可收（片数不足拒、booked 不动），够片则过", async () => {
    const { live } = await load();
    live.startLive(g101());
    const L = live.live!;
    L.admins.push(U.me.id); // 2.2 权限地基：场号改写收权——机制用例以管理员身份跑
    arrive(
      live,
      L.roster.slice(0, 9).map((p) => p.id),
    ); // 前 9 人到场攒出 cur + 待开片
    expect(L.cur).not.toBeNull();
    expect(L.courts).toHaveLength(1); // 在打 1 + 待开 1 → 至少 2 片
    expect(live.setCourtsInput("3号")).toBe(false);
    expect(L.g.courts).toBeNull(); // 原值不动
    expect(live.setCourtsInput("3号、5号")).toBe(true);
    expect(L.g.courts).toEqual(["3号", "5号"]);
  });
  it("setCourtsInput：空输入 / 全垃圾 token 拒", async () => {
    const { live } = await load();
    live.startLive(g102());
    expect(live.setCourtsInput("")).toBe(false);
    expect(live.setCourtsInput("   ")).toBe(false);
    expect(live.setCourtsInput("abc")).toBe(false);
    expect(live.live!.g.courts).toEqual(["3号", "5号"]); // 不动
  });
  it("myRound：102 局到场后取消，队列 4 人、我 idx0（连战顶队首）→ 1；未到/在打时 → null", async () => {
    const { live } = await load();
    live.startLive(g102());
    expect(live.myRound).toBeNull(); // 全员未到：我不在队不在场
    const L = live.live!;
    arrive(live); // 4 人到场 → cur（我在场上）
    expect(live.myRound).toBeNull(); // 我在 cur 上，不在队列
    live.cancelMatch();
    expect(L.queue).toHaveLength(4);
    live.togglePerson(0, "fire"); // 我顶到队首 idx0
    expect(L.queue[0]).toBe(0);
    expect(live.myRound).toBe(1); // ceil((4*0 + 0 + 1)/4)
  });
  it("myRound 公式随待开片放大：101 双取消重发 → 我 idx0 + 1 待开片 → 2", async () => {
    const { live } = await load();
    live.startLive(g101());
    live.live!.admins.push(U.me.id); // 2.2 权限地基：取消/排阵收权——机制用例以管理员身份跑
    arrive(
      live,
      live.live!.roster.slice(0, 9).map((p) => p.id),
    );
    expect(live.myRound).toBeNull(); // 我在待开片上（不在队列）
    live.cancelMatch(); // 待开片顶上 → 我又进 cur
    live.cancelMatch(); // 全员回队
    live.autoDeal(); // 重发：8 人上两片、我落单候场
    const L = live.live!;
    expect(L.queue).toEqual([0]);
    expect(L.courts).toHaveLength(1); // cur 之外还有 1 片待开
    expect(live.myRound).toBe(2); // ceil((4*1 + 0 + 1)/4)
  });
});

describe("2.2 批1 权限地基：isFullPower / store 总账 guard / setAdmin-unsetAdmin / feed", () => {
  it("isFullPower 单一源：组织者 true；球友 false；被封管理员 true", async () => {
    const { live } = await load();
    live.startLive(g102());
    expect(live.isFullPower).toBe(true); // 我是组织者
    live.startLive(g101());
    expect(live.isFullPower).toBe(false); // 球友（101 组织者是 wang）
    live.live!.admins.push(U.me.id); // 直填 admins 验证单一源（封的动作走 org 用例）
    expect(live.isFullPower).toBe(true);
  });
  it("startLive：admins 空表起，feed 开场首句带组织者名", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    expect(L.admins).toEqual([]);
    expect(L.feed).toEqual(["现场已点亮 · 组织者 我"]);
  });
  it("setAdmin/unsetAdmin（§4.6 仅 org）：封/撤 feed+toast 留痕，已封再封/不在册静默幂等", async () => {
    const { live, ui } = await load();
    live.startLive(g102());
    const L = live.live!;
    live.setAdmin(5); // li
    expect(L.admins).toEqual([5]);
    expect(L.feed[0]).toBe("组织者封 亮马河快攻 为管理员");
    expect(ui.toastMsg).toBe("组织者封 亮马河快攻 为管理员");
    live.setAdmin(5); // 已封再封 → 幂等
    expect(L.admins).toEqual([5]);
    expect(L.feed).toHaveLength(2); // 开场句 + 封一句，无重复
    live.setAdmin(999); // 不在册 → 静默
    live.unsetAdmin(8); // 撤不是管理员的 → 静默
    expect(L.admins).toEqual([5]);
    expect(L.feed).toHaveLength(2);
    live.unsetAdmin(5);
    expect(L.admins).toEqual([]);
    expect(L.feed[0]).toBe("组织者收回了 亮马河快攻 的管理员身份");
    expect(ui.toastMsg).toBe("组织者收回了 亮马河快攻 的管理员身份");
  });
  it("管理员不能再封管理员（§4.6 禁止）：非 org 调 setAdmin 拒「只有组织者能做」", async () => {
    const { live, ui } = await load();
    live.startLive(g101());
    const L = live.live!;
    L.admins.push(U.me.id); // 我已是管理员
    live.setAdmin(1);
    expect(L.admins).toEqual([U.me.id]); // 没封上
    expect(ui.toastMsg).toBe("只有组织者能做");
    expect(L.feed).toHaveLength(1); // 无留痕
  });
  it("球友碰收权动作一律拒且回同一句（B1 总账把关）：清零/改分制/开结算/确认终局/带访客/自动排阵/场号", async () => {
    const { live, ui } = await load();
    live.startLive(g101());
    const L = live.live!;
    L.cur = { A: [1, 2], B: [5, 0], sa: 0, sb: 0 }; // 直造在打局（球友身份代办不了到场，攒不出 cur）
    live.point("a"); // 球友先记一分
    live.clearScore();
    expect(L.cur!.sa).toBe(1); // 未清
    live.setRuleScore(21);
    expect(L.g.scoring).toBe(11);
    live.setRuleMode("rotate");
    expect(L.g.rotation).toBe("winner");
    live.openSettle();
    expect(live.settling).toBeNull();
    live.confirmSettle(true, 1, 0);
    expect(L.history).toHaveLength(0); // 未落账
    expect(L.cur).not.toBeNull();
    live.addGuests(1, "小陈", U.me);
    expect(L.roster).toHaveLength(13); // 无人进册
    live.autoDeal();
    expect(L.cur!.sa).toBe(1); // 未重发
    expect(live.setCourtsInput("3号")).toBe(false);
    expect(L.g.courts).toBeNull();
    expect(ui.toastMsg).toBe("请找组织者或管理员"); // 同一句（最后一步落下的）
  });
  it("球友开放（§4.8/4.9）：point/undoPoint/swapPlayers 无 guard", async () => {
    const { live } = await load();
    live.startLive(g101());
    const L = live.live!;
    const g1 = L.roster[2].id;
    const g2 = L.roster[3].id;
    L.cur = { A: [1, 2], B: [g1, g2], sa: 0, sb: 0 }; // 直造在打局 + 候场（球友身份攒不出）
    L.queue = [6];
    live.point("a");
    expect(L.cur!.sa).toBe(1);
    live.undoPoint();
    expect(L.cur!.sa).toBe(0);
    live.swapPlayers(1, 6); // 场上的 wang ↔ 候场的 shi
    expect(L.cur!.A).toEqual([6, 2]);
    expect(L.queue).toEqual([1]);
  });
  it("代办 gate：球友给他人 setCheck/togglePerson 被拒；给自己随时可", async () => {
    const { live, ui } = await load();
    live.startLive(g101()); // 我(0)在册但全员未到
    const L = live.live!;
    L.courts = [{ A: [1, 2], B: [5, 0] }]; // 直造待开片（我在其上）
    live.setCheck(1, "late");
    expect(L.roster.find((p) => p.id === 1)!.check).toBe("absent"); // 没改成
    expect(ui.toastMsg).toBe("请找组织者或管理员");
    live.togglePerson(1, "skip");
    expect(L.roster.find((p) => p.id === 1)!.skip).toBeFalsy(); // 没设上
    live.setCheck(U.me.id, "left"); // 自己早退随时可
    expect(L.roster.find((p) => p.id === 0)!.check).toBe("left");
    expect(L.courts[0]!.B).toEqual([5]); // 我在待开片上 → 早退出场
    live.togglePerson(U.me.id, "skip"); // 自己歇随时可
    expect(L.roster.find((p) => p.id === 0)!.skip).toBe(2);
  });
  it("管理员获得与组织者同一套手柄（§4.7）：收权动作放行", async () => {
    const { live } = await load();
    live.startLive(g101());
    const L = live.live!;
    L.admins.push(U.me.id);
    arrive(
      live,
      L.roster.slice(0, 9).map((p) => p.id),
    ); // 代办到场攒出 cur
    live.point("a");
    live.clearScore();
    expect(L.cur!.sa).toBe(0);
    live.setRuleScore(21);
    expect(L.g.scoring).toBe(21);
    expect(live.isFullPower).toBe(true);
  });
});

describe("2.2 批2 到场与名册：移出名册 / 底账 / 空降超上限", () => {
  it("removeFromRoster（§4.3）：名册/候场/在打全清，底账行留痕落 removedAt，feed+toast 留痕", async () => {
    const { live, ui } = await load();
    live.startLive(g102());
    const L = live.live!;
    arrive(live); // 4 人到场 → cur={A:[5,g],B:[0,8]}
    live.removeFromRoster(8); // bei 在 cur.B 上
    expect(L.roster.some((p) => p.id === 8)).toBe(false); // 人从名册消失
    expect(L.cur!.B).toEqual([0]); // 场上同清
    expect(L.queue).toEqual([]);
    const row = L.ledger.find((r) => r.id === 8)!;
    expect(row.name).toBe("北苑小钢炮");
    expect(row.removedAt).toBeTruthy(); // 底账行保留=留痕
    expect(L.feed[0]).toBe("北苑小钢炮 被移出名册");
    expect(ui.toastMsg).toBe("北苑小钢炮 被移出名册");
    live.setCheck(8, "ok"); // 已不在册 → 静默不动
    expect(L.roster.some((p) => p.id === 8)).toBe(false);
  });
  it("移出是收权动作：球友调 removeFromRoster 被拒「请找组织者或管理员」", async () => {
    const { live, ui } = await load();
    live.startLive(g101());
    const L = live.live!;
    live.removeFromRoster(1);
    expect(L.roster).toHaveLength(13); // 无人被移出
    expect(ui.toastMsg).toBe("请找组织者或管理员");
  });
  it("名册可超线上上限（§5 边界：线上满员空降+带访客 → 名册 10 人照常发牌不炸）", async () => {
    const { live } = await load();
    live.startLive(gFull8()); // 线上 8 人满员（max 8 · 我未在其中）
    const L = live.live!;
    expect(L.roster).toHaveLength(8);
    arrive(live); // 8 人到场 → 两片全开（cur + 待开片）
    expect(L.courts).toHaveLength(1);
    expect(L.cur).not.toBeNull();
    L.admins.push(U.me.id); // 搭态带访客用
    expect(await live.arriveMe(gFull8Id)).toBe("已到场 · 进候场区"); // 空降第 9 人（线上满员不拦）
    live.addGuests(1, "小陈", L.roster[0]); // 第 10 人
    expect(L.roster).toHaveLength(10); // 名册超线上上限
    live.autoDeal();
    expect(L.courts).toHaveLength(1); // 片数已满不炸：8 在场、2 候场
    expect(L.queue).toHaveLength(2);
    const meRow = L.ledger.find((r) => r.id === U.me.id)!;
    expect(meRow.dropin).toBe(true); // 空降底账行
  });
});
