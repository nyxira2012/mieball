import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { U } from "@/api";
import type { EntryRow, Game, LiveCourt, User } from "@/api/types";

/* 每个用例重置模块图 → 全新 mock 数据；102（2 片 · 我组织）与 101（未订场 3 片 · wang 组织）
   两组真局 fixture 做确定性推演。
   2.4 批2（多片并行）：无 cur/lastWinners——每片自带记分板（courts[i].sa/sb），记分族动作
   全部带 courtId；confirmSettle 幂等闸（两端并发确认只落一次账）；轮换四件套 rules 挂
   LiveState（自选前 down 跟推荐走、自选起冻结）。批3 删 setRuleMode 过渡桥——现场域
   不再消费 g.rotation（LaunchSheet/detail 建局面仍用，3.2 修订才废）。
   1.2 隔离线：startLive 吃重塑后的真局对象；2.2 批2：开场全员「未到」不发牌——需要场上态
   的用例经 arrive() 搭（真实代码路径：代办到场 → 到场支线自动补片）；fixture 开球时刻定格
   在过去，到场按口径归一为「迟到队尾」。 */
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
    逐人触发到场支线的自动补片（4 人即上片，片号先后供给）。 */
function arrive(
  live: ReturnType<typeof import("@/stores/live").useLiveStore>,
  ids?: number[],
): void {
  const L = live.live!;
  L.admins.push(U.me.id);
  for (const id of ids ?? L.roster.map((p) => p.id)) live.setCheck(id, "ok");
  L.admins.pop();
}

/** 直造一片在打（球友身份攒不出场上态时的 guard/开放用例搭态用） */
const mkCourt = (a: number[], b: number[]): LiveCourt => ({
  id: 0,
  name: "1号",
  singles: false,
  A: a,
  B: b,
  sa: 0,
  sb: 0,
  streakA: 0,
  streakB: 0,
});

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

/** 101 同构：11 人报名（hai 带 2 · zhao 随行在 mock U 带阴影标）· winner 模式 · 未订场（→3 片兜底） */
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

/** 12 人 2 片局（多片并行主 fixture）：8 上两片 + 4 候场——全上全下/N人下的落牌都可观测 */
function g12(): Game {
  return {
    ...g102(),
    id: 112,
    name: "十二人双片局",
    organizer: person(U.me),
    maxPlayers: 16,
    courts: ["3号", "5号"],
    entries: [
      entry(U.li),
      entry(U.bei),
      entry(U.wu),
      entry(U.gu),
      entry(U.shi),
      entry(U.yang),
      entry(U.tong),
      entry(U.zhang),
      entry(U.hai),
      entry(U.wang),
      entry(U.ken),
      entry(U.me),
    ],
    my: {
      isOrganizer: true,
      myEntry: { bring: 0, standing: "formal", waitSeq: null },
      invited: false,
    },
  };
}

/** 把 102 局 4 人全部到场（自动补片上片 0），再打到 11:9（到分，settling 已开未落账）。
    返回句柄 + 访客 id（roster[2]）。片 0 首发按队序：A=[me,li] B=[访客,bei]。 */
async function setupSettling() {
  const h = await load();
  h.live.startLive(g102());
  const L = h.live.live!;
  arrive(h.live); // 4 人到场 → 到场支线自动补片 0
  for (let i = 0; i < 9; i++) h.live.point(0, "a");
  for (let i = 0; i < 9; i++) h.live.point(0, "b");
  h.live.point(0, "a");
  h.live.point(0, "a"); // 11:9
  return { ...h, L, guest: L.roster[2].id };
}

describe("startLive（2.2 批2§4.1 开场点亮 · 2.4 批2 建片+四件套起笔）", () => {
  it("全员「未到」开场：候场空、按片数建空片（差人卡）、四件套起笔；随行展开成编号访客（·1 起）、底账起笔挂担保人", async () => {
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
    expect(L.courts.map((c) => [c.id, c.name, c.A, c.B])).toEqual([
      [0, "3号", [], []],
      [1, "5号", [], []],
    ]); // 按片数建空片：人不够的片差人卡呈现（2.4 §4.3 空状态）
    expect(L.rules).toEqual({
      singles: false,
      down: "all", // 无人 → 推荐「不荐」→ 挂全上全下占位（§4.2）
      downChosen: false,
      pairing: "queue",
      champCap: 3,
    });
    expect(L.courtSeqNext).toBe(0);
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
  it("101 开场 13 人（3 随行）全员未到：底账 13 行、未订场按人数兜底 3 片", async () => {
    const { live } = await load();
    live.startLive(g101());
    const L = live.live!;
    expect(L.roster).toHaveLength(13);
    expect(L.roster.filter((p) => p.shadow)).toHaveLength(3); // hai 带 2 访客 + zhao 本就是随行
    expect(L.roster.every((p) => p.check === "absent")).toBe(true);
    expect(L.queue).toEqual([]);
    expect(L.courts).toHaveLength(3); // maxPlayers 12 → 三片兜底（courtCount 单一源）
    expect(L.courts.every((c) => !c.A.length && !c.B.length)).toBe(true);
    expect(L.ledger).toHaveLength(13);
    expect(L.ledger.filter((r) => r.shadow)).toHaveLength(3);
    expect(L.ledger.filter((r) => r.guarantor === "海淀吊小球")).toHaveLength(
      2,
    );
  });
  it("到场攒局（§4.1「够一片的人数就自动发牌上片」）：4 人到场即补满片 0，队序分边", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    live.setCheck(0, "ok"); // 1 人：亮已到、进候场，不够一片
    expect(L.courts[0].A).toEqual([]);
    expect(L.queue).toEqual([0]);
    arrive(
      live,
      L.roster.slice(1).map((p) => p.id),
    ); // 其余 3 人到场 → 够一片
    expect(L.courts[0]).toMatchObject({
      A: [0, 5],
      B: [L.roster[2].id, 8],
      sa: 0,
      sb: 0,
    }); // 怎么配默认按候场队序：第 1、2 位一队，第 3、4 位一队（2.4 §4.5）
    expect(L.queue).toEqual([]); // 全部上场
    expect(L.courts[1].A).toEqual([]); // 片 1 差人卡
  });
});

describe("多片并行（2.4 §4.3：够几片开几片、各打各的、各排各的）", () => {
  /** 12 人到场：片 0=[li,bei|wu,gu]、片 1=[shi,yang|tong,zhang]、候场 [hai,wang,ken,me] */
  async function setup12() {
    const h = await load();
    h.live.startLive(g12());
    const L = h.live.live!;
    arrive(h.live);
    return { ...h, L };
  }
  it("8 人 2 片双打开局：两片各有记分板同时开打，互不等待", async () => {
    const { live, L } = await setup12();
    expect(L.courts.map((c) => [c.A, c.B])).toEqual([
      [
        [5, 8],
        [3, 4],
      ], // 片 0：li,bei vs wu,gu
      [
        [6, 7],
        [9, 12],
      ], // 片 1：shi,yang vs tong,zhang
    ]);
    expect(L.courts.every((c) => c.sa === 0 && c.sb === 0)).toBe(true);
    expect(L.queue).toEqual([2, 1, 11, 0]); // hai,wang,ken,me 候场
    for (let i = 0; i < 3; i++) live.point(1, "a"); // 只记片 1
    expect(L.courts[0].sa).toBe(0); // 片 0 记分板不动
    expect(L.courts[1].sa).toBe(3);
  });
  it("一片结束对局另一片不受影响：片 0 落账重排，片 1 比分阵容原样；并发二次确认 no-op（幂等）", async () => {
    const { live } = await load();
    live.startLive(g12());
    const L = live.live!;
    arrive(live);
    live.point(1, "a"); // 片 1 先记一分
    for (let i = 0; i < 9; i++) live.point(0, "a");
    for (let i = 0; i < 9; i++) live.point(0, "b");
    live.point(0, "a");
    live.point(0, "a"); // 片 0 到 11:9 → settling 开在片 0
    expect(live.settling).toEqual({ courtId: 0, sa: 11, sb: 9 });
    live.point(1, "a"); // 别片照打（guard 只拦同片）
    expect(L.courts[1].sa).toBe(2);
    live.confirmSettle(0, true, 11, 9); // 全上全下（12 人 ≥ 满片+4 → 推荐 all，未自选跟推荐）
    expect(live.settling).toBeNull();
    expect(L.courts[0]).toMatchObject({ A: [2, 1], B: [11, 0] }); // 候场首 4 人补全新一队
    expect(L.courts[1]).toMatchObject({ A: [6, 7], B: [9, 12], sa: 2, sb: 0 }); // 片 1 原样（4.4 各片独立）
    expect(L.queue).toEqual([5, 8, 3, 4]); // 片 0 原班按资历序排队尾（先下的排前面）
    expect(L.round).toBe(1);
    expect(L.history[0]).toEqual({
      names: "亮马河快攻 & 北苑小钢炮",
      sa: 11,
      sb: 9,
    });
    // 二次确认（两端并发模拟）：幂等闸直接 return——history/elo/round 都不再动
    const eloAfter = L.roster.find((p) => p.id === 5)!.elo;
    live.confirmSettle(0, true, 11, 9);
    expect(L.history).toHaveLength(1);
    expect(L.round).toBe(1);
    expect(L.courts[0].A).toEqual([2, 1]);
    expect(L.roster.find((p) => p.id === 5)!.elo).toBe(eloAfter);
  });
  it("各谁下方式 store 级落牌——2人下：资历最久的 2 人下、候场首逐个原位顶坑", async () => {
    const { live } = await load();
    live.startLive(g12());
    const L = live.live!;
    arrive(live);
    live.setRules({ down: "n2" }); // 自选 2 人下（冻结推荐跟随）
    live.openSettle(0);
    live.confirmSettle(0, true, 11, 9);
    // 首场四人资历并列按上场先后（seq 1-4）：li、bei 最久先下——候场首 hai、wang 顶 A 坑，
    // wu、gu 保住自己半边不被重新分队（谁下补谁的坑）
    expect(L.courts[0]).toMatchObject({ A: [2, 1], B: [3, 4] });
    expect(L.courts[1]).toMatchObject({ A: [6, 7], B: [9, 12] }); // 别片不动
    expect(L.queue).toEqual([11, 0, 5, 8]); // ken、me 候场余额在前，先下的 li 在 bei 前
    // 第二场：留下的 wu、gu 资历最深（连打两场 tenure 2）——这回他们下、候场首 ken、me 顶 B 坑
    live.setRules({ down: "n2" }); // 已是 n2，重复自选幂等
    live.openSettle(0);
    live.confirmSettle(0, true, 11, 9);
    expect(L.courts[0]).toMatchObject({ A: [2, 1], B: [11, 0] }); // hai、wang 留住半边
    expect(L.queue).toEqual([5, 8, 3, 4]);
  });
});

describe("point → settling → confirmSettle（2.1 §5 · 按片）：K=24 / 败方六成 / 访客同规", () => {
  it("11:9 到点开 settling（片不动），confirmSettle 落账 + 原班再战（候场空坑补不满），战力榜联动", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    const guest = L.roster[2].id;
    arrive(live); // 4 人到场 → 片 0=[me,li | 访客,bei]
    for (let i = 0; i < 9; i++) live.point(0, "a");
    for (let i = 0; i < 9; i++) live.point(0, "b"); // 9:9（先到 11 前不收局）
    expect(live.settling).toBeNull();
    live.point(0, "a");
    live.point(0, "a"); // 11:9 → 到点转结算弹窗（不落账）
    expect(live.settling).toEqual({ courtId: 0, sa: 11, sb: 9 });
    expect(L.courts[0].sa).toBe(11); // 片保持不动，等弹窗确认
    live.confirmSettle(0, true, 11, 9);
    // A=[me,li] 人均 1546 胜 B=[访客(1200 计入期望),bei] 人均 1326 → delta=5，loss=3，访客 floor(-3/2)=-2
    expect(live.settling).toBeNull();
    expect(L.history[0]).toEqual({
      names: "我 & 亮马河快攻",
      sa: 11,
      sb: 9,
    });
    const { U } = await import("@/api");
    expect(U.me.elo).toBe(1523); // 1518+5
    expect(U.li.elo).toBe(1579); // 1574+5
    expect(U.li.month).toBe(19); // 14+5
    expect(U.li.win).toBe(30); // 29+1
    expect(U.bei.elo).toBe(1449); // 1452-3
    expect(U.me.last5).toEqual(["L", "W", "W", "L", "W"]); // 赢球 W 入尾（仅我滚动）
    expect(guest >= 9000).toBe(true);
    expect(L.roster[2].elo).toBe(1198); // 访客 1200-2（同规落账）
    expect(L.round).toBe(1);
    // 候场空、全上全下补不满 4 人 → 原班再战（4.4 坑补不满通用规矩）
    expect(L.courts[0]).toMatchObject({
      A: [0, 5],
      B: [guest, 8],
      sa: 0,
      sb: 0,
    });
    expect(L.queue).toEqual([]);
    expect(L.feed[0]).toBe("我 & 亮马河快攻 拿下 11:9"); // feed 留痕
  });
  it("弹窗改胜方：confirmSettle(false, 9, 11) 按新胜方（B 队）结算，改过的比分写回", async () => {
    const { live, L } = await setupSettling();
    live.confirmSettle(0, false, 9, 11); // 组织者改判 B 胜、比分倒转
    // B=[访客,bei] 人均 1326 胜 A 人均 1546 → delta=19，loss=11，访客 ceil(19/2)=10
    expect(L.history[0]).toEqual({
      names: "亮马的球友·1 & 北苑小钢炮",
      sa: 9,
      sb: 11,
    });
    const { U } = await import("@/api");
    expect(U.me.elo).toBe(1507); // 1518-11
    expect(U.li.elo).toBe(1563); // 1574-11
    expect(U.bei.elo).toBe(1471); // 1452+19
    expect(L.roster[2].elo).toBe(1210); // 访客 1200+10（半权重 ceil）
    expect(U.me.last5).toEqual(["L", "W", "W", "L", "L"]); // 输球 L 入尾
  });
  it("closeSettle 不落账：比分保留在片，可继续计分重新到点", async () => {
    const { live, L } = await setupSettling();
    live.closeSettle();
    expect(live.settling).toBeNull();
    expect(L.courts[0].sa).toBe(11); // 比分保留
    expect(L.courts[0].sb).toBe(9);
    expect(L.history).toHaveLength(0); // 未落账
    const { U } = await import("@/api");
    expect(U.li.elo).toBe(1574); // elo 原封
    live.point(0, "b"); // 继续计分：11:10 净胜 1 不收
    expect(live.settling).toBeNull();
    expect(L.courts[0].sb).toBe(10);
    live.point(0, "b"); // 11:11
    live.point(0, "b"); // 11:12
    live.point(0, "b"); // 11:13 → 净胜 2 到点，弹窗重开
    expect(live.settling).toEqual({ courtId: 0, sa: 11, sb: 13 });
  });
  it("11:10 不收局，undoPoint 按该片最后得分方回退，12:10 到点开弹窗、确认后入史", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    arrive(live); // 4 人到场 → 片 0
    for (let i = 0; i < 10; i++) live.point(0, "a");
    for (let i = 0; i < 10; i++) live.point(0, "b");
    expect(L.courts[0].sa).toBe(10); // 10:10
    live.point(0, "a");
    expect(L.courts[0].sa).toBe(11);
    expect(live.settling).toBeNull(); // 11:10 净胜 1 → 继续
    live.undoPoint(0);
    expect(L.courts[0].sa).toBe(10); // 撤回 A 的分
    live.point(0, "a");
    live.point(0, "a"); // 12:10 → 到点
    expect(live.settling).toEqual({ courtId: 0, sa: 12, sb: 10 });
    live.confirmSettle(0, true, 12, 10);
    expect(L.history[0].sa).toBe(12);
    expect(L.history[0].sb).toBe(10);
  });
  it("openSettle：手动入口快照当前比分；空片静默不开", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    arrive(live); // 4 人到场 → 片 0
    live.point(0, "a");
    live.point(0, "a"); // 2:0 未到分
    expect(live.settling).toBeNull();
    live.openSettle(0); // 卡上「终局结算」钮
    expect(live.settling).toEqual({ courtId: 0, sa: 2, sb: 0 });
    live.confirmSettle(0, true, 2, 0); // 手动终局也走同一落账口径
    expect(L.history[0]).toEqual({
      names: "我 & 亮马河快攻",
      sa: 2,
      sb: 0,
    });
    expect(live.settling).toBeNull();
    live.openSettle(0); // 原班再战（候场空补不满）→ 片还在，可开
    expect(live.settling).toEqual({ courtId: 0, sa: 0, sb: 0 });
    live.cancelMatch(0); // 取消对局 → 结算弹窗随对局一并关
    expect(live.settling).toBeNull();
    live.openSettle(1); // 空片（差人卡）→ 静默不开
    expect(live.settling).toBeNull();
  });
  it("clearScore：比分与该片最后得分方一起清零（undo 不再误撤）", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    arrive(live); // 4 人到场 → 片 0
    live.point(0, "a");
    live.point(0, "b");
    live.point(0, "a"); // 2:1，last='a'
    live.clearScore(0);
    expect(L.courts[0].sa).toBe(0);
    expect(L.courts[0].sb).toBe(0);
    expect(L.courts[0].last).toBeUndefined();
    live.undoPoint(0); // last 已清 → 0:0 原地不动
    expect(L.courts[0].sa).toBe(0);
    expect(L.courts[0].sb).toBe(0);
  });
});

describe("轮换四件套：setRules / 推荐跟随 / 过渡桥 / 组合回落 / 连庄清零（2.4 §4.1-4.2/4.7）", () => {
  it("推荐跟随：人数变 → down 变（8 人 all → 9 人 n1）；自选后冻结（推荐只亮标签不替改）", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!; // 2 片
    arrive(live); // 4 人上场 → 可打 4 人：够单打铺满、双打铺不满 → 提示换单打（非 down）→ 占位 all
    expect(L.rules.down).toBe("all");
    live.addGuests(4, "帮手", U.me); // 可打 8 人 = 铺满 → all
    expect(L.rules.down).toBe("all");
    expect(L.rules.downChosen).toBe(false);
    live.addGuests(1, "第九人", U.me); // 可打 9 人 = 满片+1 → n1
    expect(L.rules.down).toBe("n1");
    live.setRules({ down: "loser" }); // 组织者自选输家下 → 冻结
    expect(L.rules.downChosen).toBe(true);
    live.addGuests(2, "再两人", U.me); // 可打 11 人（本应 n3）→ 冻结不动
    expect(L.rules.down).toBe("loser");
    expect(live.advice).toMatchObject({ kind: "down", down: "n3" }); // 推荐照算、只亮标签
  });
  it("组合回落：单打×1/2/3人下自动落回全上全下（如实显示、不算自选）；双打自选 n1 后切单打同样回落", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    live.setRules({ singles: true, down: "n1" }); // 并发拼出的非法组合
    expect(L.rules.singles).toBe(true);
    expect(L.rules.down).toBe("all");
    expect(L.rules.downChosen).toBe(false); // 自动回落不算自选（推荐继续跟随）
    live.setRules({ singles: false, down: "n1" }); // 双打下合法自选
    expect(L.rules.down).toBe("n1");
    expect(L.rules.downChosen).toBe(true);
    live.setRules({ singles: true }); // 只换单双打：n1 回落 all，自选状态保留（组织者动过谁下）
    expect(L.rules.down).toBe("all");
    expect(L.rules.downChosen).toBe(true);
  });
  it("换单双打空片格式传导（§5 边界）：一片在打一片空改单打 → 空片 2 人即开、在打片不动", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    arrive(live); // 4 人到场 → 片 0 开打，片 1 双打差 2 人（差人卡）
    live.addGuests(2, "挑战", U.me); // 候场 2 人（addGuests 不自动补片）
    const c1 = L.roster[4]!.id;
    const c2 = L.roster[5]!.id;
    live.setRules({ singles: true });
    expect(L.courts[0]).toMatchObject({
      singles: false,
      A: [0, 5],
      B: [L.roster[2].id, 8],
    }); // 在打片照旧打完（4 人双打、阵容不动）
    expect(L.courts[1]).toMatchObject({ singles: true, A: [c1], B: [c2] }); // 空片当场转新格式、2 人开赛
    expect(L.queue).toEqual([]);
  });
  it("两片全空换单打（§5 边界：2 片 6 人改单打）→ 两片各 2 人开赛、剩 2 人候场", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    live.addGuests(6, "帮手", U.me); // 6 人候场、两片全空（开场未到不发牌、带人也不自动补片）
    const ids = L.roster.slice(4).map((p) => p.id);
    live.setRules({ singles: true });
    expect(L.courts[0]).toMatchObject({
      singles: true,
      A: [ids[0]],
      B: [ids[1]],
    });
    expect(L.courts[1]).toMatchObject({
      singles: true,
      A: [ids[2]],
      B: [ids[3]],
    });
    expect(L.queue).toEqual([ids[4], ids[5]]);
  });
  it("切到输家下 → 全片连庄清零重算；已在输家下重复点不清（他们不是赢上来的才清）", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    arrive(live); // 片 0
    live.addGuests(2, "挑战", U.me); // 候场 2 人——输家下补坑有人
    live.setRules({ down: "loser" });
    live.openSettle(0);
    live.confirmSettle(0, true, 11, 9); // A=[me,li] 胜：streakA=1、B 下来两位挑战者补
    expect(L.courts[0].streakA).toBe(1);
    expect(L.courts[0].A).toEqual([0, 5]); // 赢家留场
    expect(L.courts[0].streakB).toBe(0); // 新挑战者连庄从零
    live.setRules({ down: "loser" }); // 已在输家下：重复点不清连庄
    expect(L.courts[0].streakA).toBe(1);
    live.setRules({ down: "all" }); // 切走
    live.setRules({ down: "loser" }); // 切回 → 清零重算（4.7-2）
    expect(L.courts[0].streakA).toBe(0);
    expect(L.courts[0].streakB).toBe(0);
  });
  it("输家下落牌：赢家留场连庄+1、输家排队尾、候场首 2 人成一队挑战（不重配）", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    arrive(live);
    live.addGuests(2, "挑战", U.me);
    const c1 = L.roster[4]!.id;
    const c2 = L.roster[5]!.id;
    live.setRules({ down: "loser", pairing: "balance" }); // 输家下：均衡只在凑全新一队时生效——挑战两人按队序
    live.openSettle(0);
    live.confirmSettle(0, false, 9, 11); // B=[访客,bei] 胜：A 下
    expect(L.courts[0].streakB).toBe(1); // 赢家边连庄+1
    expect(L.courts[0].A).toEqual([c1, c2]); // 候场首 2 人按队序成一队（不重配）
    expect(L.queue).toEqual([0, 5]); // 输家 me,li 排队尾
    expect(L.courts[0].streakA).toBe(0);
  });
  it("连庄上限 0=不限（§4.1/§4.6）：setRules({champCap:0}) 落值 0（「当前＝不限」文案由组件层呈现），到点判定读现值——0 之下连赢照留", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    arrive(live); // 4 人到场 → 片 0=[me,li|访客,bei]
    live.setRules({ down: "loser", champCap: 0 });
    expect(L.rules.champCap).toBe(0); // store 侧落值：0 原样存，不折成默认 3
    live.openSettle(0);
    live.confirmSettle(0, true, 11, 9); // A 胜（候场空 → 原班再战，连庄照算）
    expect(L.courts[0].streakA).toBe(1);
    live.openSettle(0);
    live.confirmSettle(0, true, 11, 9); // 再赢一场：上限 0 → 永不到点，赢家照留
    expect(L.courts[0].streakA).toBe(2);
    expect(L.courts[0].A).toEqual([0, 5]); // me,li 仍在场上
  });
  it("setRuleMode 过渡桥已删（批3）：src 全仓零引用——旧三模式只剩 g.rotation 契约本体", async () => {
    const { readdirSync, readFileSync, statSync } = await import("node:fs");
    const { fileURLToPath } = await import("node:url");
    const walk = (dir: string): string[] =>
      readdirSync(dir).flatMap((f) => {
        const p = `${dir}/${f}`;
        return statSync(p).isDirectory()
          ? walk(p)
          : /\.(ts|vue)$/.test(f) && readFileSync(p, "utf8").includes("setRuleMode")
            ? [p]
            : [];
      });
    expect(walk(fileURLToPath(new URL("../src", import.meta.url)))).toEqual([]);
  });
});

describe("换人 / 取消对局 / 自动排阵（2.1 §2/§4 · 2.4 §4.9 手动换人接管）", () => {
  /** 输家下打完一场的片 0：A=[me,li] streakA=1、B=两位挑战者、queue=[访客,bei] */
  async function setupLoser() {
    const h = await load();
    h.live.startLive(g102());
    const L = h.live.live!;
    arrive(h.live);
    h.live.addGuests(2, "挑战", h.live.byId(U.me.id));
    h.live.setRules({ down: "loser" });
    h.live.openSettle(0);
    h.live.confirmSettle(0, true, 11, 9);
    return { ...h, L };
  }
  it("swapPlayers：换下排队尾、换上者原位顶坑资历从换上起算、该半边连庄不动", async () => {
    const { live, L } = await setupLoser();
    const c1 = L.roster.find((p) => p.name === "挑战·1")!;
    const li = L.roster.find((p) => p.id === 5)!;
    expect(li.courtSeq).toBeTruthy(); // li 是首发出场序在身
    live.addGuests(1, "老赵", live.byId(U.me.id));
    const lao = L.roster.find((p) => p.name === "老赵")!;
    expect(L.queue).toEqual([L.roster[2].id, 8, lao.id]);
    live.swapPlayers(5, lao.id); // 场上的 li ↔ 候场队尾的老赵
    expect(L.courts[0].A).toEqual([0, lao.id]); // 原位顶坑（A[1]）
    expect(L.courts[0].streakA).toBe(1); // 手动换人不动该队连庄（4.9）
    expect(L.queue).toEqual([L.roster[2].id, 8, 5]); // 换下的 li 排队尾
    expect(li.courtSeq).toBeUndefined(); // 资历注销
    expect(li.tenure).toBe(0);
    expect(lao.courtSeq).toBeTruthy(); // 新发上场序
    expect(lao.tenure).toBe(0); // 资历从换上起算
  });
  it("cancelMatch：场上 A/B 回候场队首（A 先 B 后原相对序，压到原候场者之前）、feed 留句、不计积分", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    arrive(live); // 片 0=[me,li|访客,bei]
    live.point(0, "a");
    live.addGuests(1, "老赵", live.byId(U.me.id)); // 预置一位候场者：候场不空，队首/队尾才可分辨（修订①钉序）
    const lao = L.roster.find((p) => p.name === "老赵")!;
    lao.skip = 1; // 老赵在歇不可发——候场可发仍只 3 人，重发不触发（差人卡口径不变）
    L.roster.find((p) => p.id === 0)!.skip = 1; // 我在歇：回流后不可发
    live.cancelMatch(0);
    expect(L.queue).toEqual([0, 5, L.roster[2].id, 8, lao.id]); // A 先 B 后回队首，原候场的老赵被压到回流 4 人之后
    expect(L.courts[0].A).toEqual([]); // 可发仅 3 人不够重发 → 差人卡
    expect(L.feed[0]).toBe("对局作废 · 这场不计分 · 场上 4 人回到队首");
    expect(L.history).toHaveLength(0); // 不计积分
    expect(L.round).toBe(0);
    const { U: UA } = await import("@/api");
    expect(UA.li.elo).toBe(1574); // elo 原封（新模块实例上的 mock 原值）
  });
  it("cancelMatch：回流后候场够人 → 该片立刻重发（回流 4 人在队首原地顶上，不吞原候场者）", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    arrive(live); // 片 0=[me,li|访客,bei]
    for (let i = 0; i < 5; i++) live.point(0, "a"); // 5:0 未打完
    live.addGuests(1, "老赵", live.byId(U.me.id)); // 预置一位可发候场者：重发吞的是谁才可分辨（修订①钉序）
    const lao = L.roster.find((p) => p.name === "老赵")!.id;
    live.cancelMatch(0);
    expect(L.courts[0]).toMatchObject({
      A: [0, 5],
      B: [L.roster[2].id, 8],
      sa: 0,
    }); // 回流的 4 人排在老赵之前 → 重发回片 0 的正是原班（若回队尾，老赵会先被顶上）
    expect(L.queue).toEqual([lao]); // 原候场老赵被压到回流 4 人之后
  });
  it("autoDeal：补所有空片（多片同时要人按片号先后），在打片不动", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    arrive(live); // 片 0 已自动补满
    live.addGuests(4, "帮手", U.me); // 候场 4 人（带访客不自动发牌）
    expect(L.courts[1].A).toEqual([]);
    live.autoDeal();
    const g = (i: number) => L.roster[4 + i]!.id;
    expect(L.courts[1]).toMatchObject({ A: [g(0), g(1)], B: [g(2), g(3)] });
    expect(L.courts[0].A).toEqual([0, 5]); // 在打片不动
    expect(L.queue).toEqual([]);
  });
  it("myRound：swap 下场后我排队 idx0 无空片 → 1；有空片 → 随空片放大", async () => {
    const { live } = await load();
    live.startLive(g102());
    expect(live.myRound).toBeNull(); // 全员未到：我不在队不在场
    const L = live.live!;
    live.setCourtsInput("3号"); // 收成 1 片
    arrive(live); // 4 人到场 → 片 0（我在场上）
    expect(live.myRound).toBeNull();
    live.addGuests(1, "小陈", live.byId(U.me.id));
    const xin = L.roster.find((p) => p.name === "小陈")!;
    live.swapPlayers(0, xin.id); // 我被换下排队
    expect(L.queue).toEqual([0]);
    expect(live.myRound).toBe(1); // ceil((4*0 + 0 + 1)/4)——无空片
    live.setCourtsInput("3号、5号"); // 放回 2 片（片 1 空着=差人卡）
    expect(live.myRound).toBe(2); // ceil((4*1 + 0 + 1)/4)——空片算进轮次
  });
});

describe("setCheck / togglePerson（2.1 §2-3 · 2.2 批2 队位统一队尾）", () => {
  /** 队位观察稳态（101）：11 人到场 → 两片全占、第三片差 1 人、3 人候场——
      片满则到场只排队不补片，统一队尾的次序才可观测 */
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
    expect(L.courts[0].A).toEqual([1, 2]); // 片 0：wang,hai vs 两位随行访客
    expect(L.courts[1]).toMatchObject({ A: [3, 4], B: [5, 0] }); // 片 1：wu,gu vs li,me
    expect(L.courts[2].A).toEqual([]); // 片 2 差 1 人
    expect(L.queue).toEqual([6, 7, 8]); // shi/yang/bei 候场（按报名序供给）
    live.setCheck(7, "late"); // 已迟到者重复报到 → 重排队尾，不触发补片（新到场才补）
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
  it("早退清片（2.4 批2）：人在片上早退 → 该片半边过滤打短（补人归手动换人），资历注销", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    arrive(live); // 片 0=[me,li|访客,bei]
    const bei = L.roster.find((p) => p.id === 8)!;
    expect(bei.courtSeq).toBeTruthy();
    live.setCheck(8, "left");
    expect(L.courts[0].B).toEqual([L.roster[2].id]); // bei 从片上清掉、访客打短
    expect(bei.courtSeq).toBeUndefined(); // 资历注销（再上场从换上起算）
    expect(L.queue).toEqual([]); // 不进候场
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
  it("setCheck late：缺席者（原不在队）到场即从队尾进队（跳轮保位的配套口径）", async () => {
    const { live } = await load();
    live.startLive(g101());
    const L = live.live!;
    L.admins.push(U.me.id); // 2.2 权限地基：代办他人到点是收权动作——机制用例以管理员身份跑
    const absentId = L.roster.find((p) => p.check === "absent")!.id;
    expect(L.queue).not.toContain(absentId);
    live.setCheck(absentId, "late");
    expect(L.queue[L.queue.length - 1]).toBe(absentId);
  });
  it("到场攒局放行迟到（2.1 §3 裁决）：迟到者第 4 个到 → 补满片 0 照样上场", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    L.admins.push(U.me.id);
    live.setCheck(0, "ok"); // 过开球 → 归一 late
    live.setCheck(5, "ok");
    live.setCheck(8, "ok");
    expect(L.courts[0].A).toEqual([]); // 3 人不够一片
    live.setCheck(L.roster[2].id, "ok"); // 第 4 人（随行访客）到场 → 补满
    expect(L.courts[0]).toMatchObject({
      A: [0, 5],
      B: [8, L.roster[2].id],
    }); // 迟到的照样上场（队序分边按到场先后）
    expect(L.roster.every((p) => p.check !== "absent")).toBe(true);
  });
  it("togglePerson：休息按次叠加、随时可取消（§4.10 修订⑨）、互斥双向、连战队首、任意人可设", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    arrive(live); // 片 0
    live.addGuests(2, "帮手", live.byId(U.me.id));
    const c1 = L.roster[4]!.id;
    live.swapPlayers(0, c1); // 我被换下 → queue=[c2, 0]
    live.togglePerson(0, "skip");
    expect(L.roster.find((p) => p.id === 0)!.skip).toBe(1); // 一次跳一轮（引擎发牌时消耗）
    live.togglePerson(0, "skip");
    const meP = L.roster.find((p) => p.id === 0)!;
    expect(meP.skip).toBe(2); // 再按再跳（无上限无冷却）
    live.togglePerson(0, "unskip");
    expect(meP.skip).toBe(0); // 取消休息随时清 0
    live.togglePerson(0, "skip");
    live.togglePerson(0, "fire");
    expect(meP.fire).toBe(true);
    expect(meP.skip).toBe(0); // 设连战清休息（互斥）
    expect(L.queue[0]).toBe(0); // 连战 → 队首
    live.togglePerson(0, "skip"); // 设休息清连战（互斥）
    expect(meP.skip).toBe(1);
    expect(meP.fire).toBe(false);
    live.togglePerson(5, "skip"); // 任意人（组织者代设，li 在场上也能设）
    expect(L.roster.find((p) => p.id === 5)!.skip).toBe(1);
    live.togglePerson(5, "unskip");
    expect(L.roster.find((p) => p.id === 5)!.skip).toBe(0);
  });
});

describe("setCourtsInput（2.1 顶条 · 2.4 批2 非空片口径）", () => {
  it("『3、4 / 3,4 / 3 4 / 3号、4号』归一成 [3号,4号] 写 booked、空片重建重挂名", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    expect(L.g.courts).toEqual(["3号", "5号"]); // mock 原值
    for (const txt of ["3、4", "3,4", "3 4", "3号、4号"]) {
      expect(live.setCourtsInput(txt)).toBe(true);
      expect(L.g.courts).toEqual(["3号", "4号"]);
      expect(L.courts.map((c) => c.name)).toEqual(["3号", "4号"]); // 场地名重挂
    }
  });
  it("在打的片不能收（非空片数校验、booked 不动），够片则过、空片收敛", async () => {
    const { live } = await load();
    live.startLive(g101());
    const L = live.live!;
    L.admins.push(U.me.id); // 2.2 权限地基：场号改写收权——机制用例以管理员身份跑
    arrive(
      live,
      L.roster.slice(0, 9).map((p) => p.id),
    ); // 前 9 人到场攒出两片在打、第三片空
    expect(usedNonEmpty(L)).toBe(2);
    expect(live.setCourtsInput("3号")).toBe(false);
    expect(L.g.courts).toBeNull(); // 原值不动
    expect(live.setCourtsInput("3号、5号")).toBe(true);
    expect(L.g.courts).toEqual(["3号", "5号"]);
    expect(L.courts).toHaveLength(2); // 空的第三片收敛掉，在打两片重挂名
    expect(L.courts.map((c) => c.name)).toEqual(["3号", "5号"]);
  });
  it("空输入 / 全垃圾 token 拒", async () => {
    const { live } = await load();
    live.startLive(g102());
    expect(live.setCourtsInput("")).toBe(false);
    expect(live.setCourtsInput("   ")).toBe(false);
    expect(live.setCourtsInput("abc")).toBe(false);
    expect(live.live!.g.courts).toEqual(["3号", "5号"]); // 不动
  });
});

function usedNonEmpty(L: { courts: LiveCourt[] }): number {
  return L.courts.filter((c) => c.A.length || c.B.length).length;
}

describe("addGuests / swapPlayers（2.1 §1 · 2.2 批2 底账挂担保人）", () => {
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
  it("球友碰收权动作一律拒且回同一句（B1 总账把关）：清零/改分制/改四件套/开结算/确认终局/带访客/自动排阵/场号", async () => {
    const { live, ui } = await load();
    live.startLive(g101());
    const L = live.live!;
    L.courts = [mkCourt([1, 2], [5, 0])]; // 直造在打片（球友身份代办不了到场，攒不出）
    live.point(0, "a"); // 球友先记一分
    live.clearScore(0);
    expect(L.courts[0].sa).toBe(1); // 未清
    live.setRuleScore(21);
    expect(L.g.scoring).toBe(11);
    live.setRules({ down: "n1" }); // 球友改四件套被拒同句（抽屉只读化的 store 双保险）
    expect(L.rules.down).toBe("all"); // 未改
    expect(L.rules.downChosen).toBe(false);
    live.openSettle(0);
    expect(live.settling).toBeNull();
    live.confirmSettle(0, true, 1, 0); // 幂等闸（无 settling）在前——静默 no-op
    expect(L.history).toHaveLength(0); // 未落账
    expect(L.courts[0].A).toEqual([1, 2]);
    live.addGuests(1, "小陈", U.me);
    expect(L.roster).toHaveLength(13); // 无人进册
    live.autoDeal();
    expect(L.courts[0].sa).toBe(1); // 未重发
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
    L.courts = [mkCourt([1, 2], [g1, g2])]; // 直造在打片 + 候场（球友身份攒不出）
    L.queue = [6];
    live.point(0, "a");
    expect(L.courts[0].sa).toBe(1);
    live.undoPoint(0);
    expect(L.courts[0].sa).toBe(0);
    live.swapPlayers(1, 6); // 场上的 wang ↔ 候场的 shi
    expect(L.courts[0].A).toEqual([6, 2]);
    expect(L.queue).toEqual([1]); // 换下的排队尾
  });
  it("代办 gate：球友给他人 setCheck/togglePerson 被拒；给自己随时可", async () => {
    const { live, ui } = await load();
    live.startLive(g101()); // 我(0)在册但全员未到
    const L = live.live!;
    L.courts = [mkCourt([1, 2], [5, 0])]; // 直造在打片（我在其上）
    live.setCheck(1, "late");
    expect(L.roster.find((p) => p.id === 1)!.check).toBe("absent"); // 没改成
    expect(ui.toastMsg).toBe("请找组织者或管理员");
    live.togglePerson(1, "skip");
    expect(L.roster.find((p) => p.id === 1)!.skip).toBeFalsy(); // 没设上
    live.setCheck(U.me.id, "left"); // 自己早退随时可
    expect(L.roster.find((p) => p.id === 0)!.check).toBe("left");
    expect(L.courts[0]!.B).toEqual([5]); // 我在片上 → 早退出场
    live.togglePerson(U.me.id, "skip"); // 自己歇随时可
    expect(L.roster.find((p) => p.id === 0)!.skip).toBe(1); // 一次跳一轮（修订⑨叠加口径）
  });
  it("管理员获得与组织者同一套手柄（§4.7）：收权动作放行", async () => {
    const { live } = await load();
    live.startLive(g101());
    const L = live.live!;
    L.admins.push(U.me.id);
    arrive(
      live,
      L.roster.slice(0, 9).map((p) => p.id),
    ); // 代办到场攒出两片
    live.point(0, "a");
    live.clearScore(0);
    expect(L.courts[0].sa).toBe(0);
    live.setRuleScore(21);
    expect(L.g.scoring).toBe(21);
    live.setRules({ champCap: 5 });
    expect(L.rules.champCap).toBe(5);
    expect(live.isFullPower).toBe(true);
  });
});

describe("2.2 批2 到场与名册：移出名册 / 底账 / 空降超上限", () => {
  it("removeFromRoster（§4.3）：名册/候场/在打全清，底账行留痕落 removedAt，feed+toast 留痕", async () => {
    const { live, ui } = await load();
    live.startLive(g102());
    const L = live.live!;
    arrive(live); // 4 人到场 → 片 0=[me,li|访客,bei]
    live.removeFromRoster(8); // bei 在片 0.B 上
    expect(L.roster.some((p) => p.id === 8)).toBe(false); // 人从名册消失
    expect(L.courts[0].B).toEqual([L.roster[2].id]); // 场上同清、访客打短
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
    arrive(live); // 8 人到场 → 两片全开
    expect(L.courts).toHaveLength(2);
    expect(L.courts.every((c) => c.A.length && c.B.length)).toBe(true);
    L.admins.push(U.me.id); // 搭态带访客用
    expect(await live.arriveMe(gFull8Id)).toBe("已到场 · 进候场区"); // 空降第 9 人（线上满员不拦）
    live.addGuests(1, "小陈", L.roster[0]); // 第 10 人
    expect(L.roster).toHaveLength(10); // 名册超线上上限
    live.autoDeal();
    expect(L.courts).toHaveLength(2); // 片数已满不炸：8 在场、2 候场
    expect(L.queue).toHaveLength(2);
    const meRow = L.ledger.find((r) => r.id === U.me.id)!;
    expect(meRow.dropin).toBe(true); // 空降底账行
  });
});

describe("2.2 批3b 移植：找替补 subFirst / 换人 feed 留名句", () => {
  /** 片 0 打短搭态：102 全员到场开片 0 → bei 早退 B 半边打短；候场补 2 位访客（帮手·1/·2） */
  async function setupShort() {
    const h = await load();
    h.live.startLive(g102());
    const L = h.live.live!;
    L.admins.push(U.me.id);
    for (const id of L.roster.map((p) => p.id)) h.live.setCheck(id, "ok");
    L.admins.pop();
    h.live.setCheck(8, "left"); // bei 早退 → B=[访客] 打短（§4.11 前提：场上有人缺）
    h.live.addGuests(2, "帮手", U.me); // 候场 2 人（不自动补片）
    return { ...h, L };
  }
  it("subFirst：候场队首可用者顶上人数少的一队、courtSeq 新发资历从换上起算、feed 留句", async () => {
    const { live, L } = await setupShort();
    const s1 = L.roster.find((p) => p.name === "帮手·1")!;
    expect(L.courts[0].B).toEqual([L.roster[2].id]); // B 缺 1 人
    live.subFirst(0);
    expect(L.courts[0].B).toEqual([L.roster[2].id, s1.id]); // 人数少的 B 队补上，这局接着打
    const s2 = L.roster.find((p) => p.name === "帮手·2")!;
    expect(L.queue).toEqual([s2.id]); // 队首出队
    expect(s1.courtSeq).toBeTruthy(); // 换上口径：上场序新发
    expect(s1.tenure).toBe(0);
    expect(L.feed[0]).toBe("替补：帮手·1 顶上 · 比赛继续");
  });
  it("subFirst：候场只剩歇轮者不补也不消耗其歇轮；满员兜底「场上没有缺位」", async () => {
    const { live, L, ui } = await setupShort();
    const s1 = L.roster.find((p) => p.name === "帮手·1")!;
    const s2 = L.roster.find((p) => p.name === "帮手·2")!;
    live.togglePerson(s1.id, "skip");
    live.togglePerson(s2.id, "skip"); // 候场两位全在歇
    live.subFirst(0);
    expect(ui.toastMsg).toBe("候场没人能顶 · 先拉人吧"); // 歇轮者不可补
    expect(s2.skip).toBe(1); // 且歇轮不被空耗（没轮到发牌就不消耗）
    expect(L.queue).toEqual([s1.id, s2.id]);
    expect(L.courts[0].B).toEqual([L.roster[2].id]); // 仍打短
    live.togglePerson(s1.id, "unskip"); // s1 取消休息 → 下次可补
    live.subFirst(0);
    expect(L.courts[0].B).toEqual([L.roster[2].id, s1.id]);
    live.subFirst(0); // 满员再按 → 兜底
    expect(ui.toastMsg).toBe("场上没有缺位");
  });
  it("subFirst 是收权动作：球友调被拒（§4.11 组织者/管理员手柄）", async () => {
    const { live, ui } = await load();
    live.startLive(g101()); // 我非组织者
    const L = live.live!;
    L.courts = [mkCourt([1], [2])]; // 直造打短片（球友身份攒不出）
    L.queue = [6];
    live.subFirst(0);
    expect(L.courts[0].A).toEqual([1]); // 没补上
    expect(ui.toastMsg).toBe("请找组织者或管理员");
  });
  it("swapPlayers feed 留名句（§4.9）：操作者=我，全场看得到是谁换的", async () => {
    const { live, L } = await setupShort();
    const s1 = L.roster.find((p) => p.name === "帮手·1")!;
    live.swapPlayers(5, s1.id); // 场上的 li ↔ 候场队首的帮手·1
    expect(L.feed[0]).toBe("我 把 亮马河快攻 换下 · 帮手·1 上");
  });
});

describe("2.2 批4 散场与底账：endLive / 底账定格 / 扫码拦（§4.14 · §4.2）", () => {
  it("endLive guard 矩阵：球友拒、组织者在场时管理员拒（「只有组织者能收局」）；组织者已早退 → 管理员代收可", async () => {
    const { live, ui } = await load();
    live.startLive(g101()); // 我非组织者（wang 组织），三片全空
    const L = live.live!;
    const orgId = L.g.organizer.id;
    expect(live.canEndLive).toBe(false);
    live.endLive(); // 球友
    expect(L.endedAt).toBeUndefined();
    expect(ui.toastMsg).toBe("只有组织者能收局");
    L.admins.push(U.me.id);
    live.endLive(); // 管理员 · 组织者还在场（absent）
    expect(L.endedAt).toBeUndefined();
    expect(ui.toastMsg).toBe("只有组织者能收局");
    live.setCheck(orgId, "left"); // 组织者标早退（管理员代办）
    expect(live.canEndLive).toBe(true);
    live.endLive(); // 代收兜底：否则没人能收局
    expect(L.endedAt).toBeTruthy();
    expect(ui.toastMsg).toBe("已散场 · 底账定格");
  });
  it("防线（§4.14 禁止还有片在打直接散）：在打时拦「还有片在打 · 先收局或作废」不出 endedAt；作废后过闸收局", async () => {
    const { live, ui } = await load();
    live.startLive(g102());
    const L = live.live!;
    arrive(live); // 片 0 在打
    live.endLive();
    expect(L.endedAt).toBeUndefined();
    expect(ui.toastMsg).toBe("还有片在打 · 先收局或作废");
    for (const p of L.roster) live.setCheck(p.id, "left"); // 全员早退清片（作废会原地重发、空不出片）
    live.endLive(); // 过两道闸（权限+防线）→ 执行（确认流的执行步）
    expect(L.endedAt).toBeTruthy();
  });
  it("底账定格（§4.14）：已到未走者 leftAt=endedAt、早退者保留自己时刻、移出留痕不复活、未到者空着；访客挂担保人", async () => {
    const { live, ui } = await load();
    live.startLive(g102());
    const L = live.live!;
    const [me, li, guest, bei] = L.roster;
    for (const p of [me, li, guest]) live.setCheck(p.id, "ok"); // 3 人到场（<4 不开片）
    live.setCheck(li.id, "left"); // li 早退（我是组织者，代办合法）
    const liLeftAt = li.leftAt!;
    live.removeFromRoster(bei.id); // 未到的 bei 被移出 → 底账行留痕
    live.endLive();
    expect(L.endedAt).toBeTruthy();
    expect(L.feed[0]).toBe("现场已散 · 二维码失效");
    expect(ui.toastMsg).toBe("已散场 · 底账定格");
    const row = (id: number) => L.ledger.find((r) => r.id === id)!;
    expect(me.leftAt).toBe(L.endedAt); // 几点到几点走齐了
    expect(row(me.id).leftAt).toBe(L.endedAt);
    expect(row(guest.id).leftAt).toBe(L.endedAt);
    expect(row(guest.id).guarantor).toBe(U.li.name); // 访客是谁带的
    expect(row(li.id).leftAt).toBe(liLeftAt); // 早退时刻不被覆盖
    expect(li.leftAt).toBe(liLeftAt);
    expect(row(bei.id).removedAt).toBeTruthy(); // 移出留痕
    expect(row(bei.id).leftAt).toBeUndefined(); // 移出者不落离场
    expect(row(bei.id).arriveAt).toBeUndefined(); // 未到者到时刻空着
  });
  it("散场后扫码拦（§4.2）：ensureLive 同局 toast「球局不存在或已结束」、arriveMe 拦回 null；现场态保留可查、重复收局不重放", async () => {
    const { live, ui } = await load();
    live.startLive(g102());
    const L = live.live!;
    live.setCheck(U.me.id, "ok"); // 1 人到场，无片在打
    live.endLive();
    const feedLen = L.feed.length;
    await live.ensureLive(102); // 散场后同局再扫
    expect(ui.toastMsg).toBe("球局不存在或已结束");
    expect(L.endedAt).toBeTruthy(); // live 态保留：底账抽屉还查得到
    expect(L.ledger).toHaveLength(4);
    expect(await live.arriveMe(102)).toBeNull(); // 扫码进场同链路被拦
    live.endLive(); // 已封存直调不重放
    expect(L.feed).toHaveLength(feedLen);
  });
  it("封存闸（§4.14 底账定格）：散场后自报 setCheck（报到/早退）与歇连被拒「现场已散 · 不能再操作」——定格时刻不被改写", async () => {
    const { live, ui } = await load();
    live.startLive(g102());
    const L = live.live!;
    live.setCheck(U.me.id, "ok"); // 过开球归一迟到 · 我 1 人候场，无片在打
    live.endLive();
    const endedAt = L.endedAt!;
    expect(endedAt).toBeTruthy();
    const meP = L.roster.find((p) => p.id === U.me.id)!;
    live.setCheck(U.me.id, "left"); // 散场后自己也不能早退
    expect(meP.check).toBe("late"); // 未改成
    expect(meP.leftAt).toBe(endedAt); // 定格的离场时刻不被改写
    live.setCheck(U.me.id, "ok"); // 散场后自己也不能再报到
    expect(meP.check).toBe("late");
    expect(L.queue).toEqual([U.me.id]); // 队位不动
    live.togglePerson(U.me.id, "skip"); // 歇连同封（同一自报免检路径）
    expect(meP.skip).toBeFalsy();
    expect(ui.toastMsg).toBe("现场已散 · 不能再操作");
  });
  it("封存闸（§4.14）：散场后收权动作（带访客/自动排阵/改规则/改分制）一律拒——全权在手也封", async () => {
    const { live, ui } = await load();
    live.startLive(g102());
    const L = live.live!;
    live.setCheck(U.me.id, "ok"); // 我候场（无片在打才能收局）
    live.addGuests(2, "帮手", U.me); // 候场 3 人，不够一片不开打
    live.endLive(); // 收局 → 底账定格
    const ledgerLen = L.ledger.length;
    live.addGuests(1, "散场客", U.me);
    expect(L.roster).toHaveLength(6); // 无人进册
    expect(L.ledger).toHaveLength(ledgerLen); // 底账不加行
    live.autoDeal(); // 自动排阵重发牌
    expect(L.courts.every((c) => !c.A.length && !c.B.length)).toBe(true); // 不重发
    expect(L.queue).toHaveLength(3); // 候场不被吞
    live.setRules({ champCap: 5 });
    expect(L.rules.champCap).toBe(3); // 四件套不动
    live.setRuleScore(21);
    expect(L.g.scoring).toBe(11); // 分制不动
    expect(ui.toastMsg).toBe("现场已散 · 不能再操作");
  });
  it("底账入口散场后可查（§4.14 底账留给事后摊钱）：isFullPower 不含封存——live.vue onLedger 走纯权限闸不被拦", async () => {
    const { live } = await load();
    live.startLive(g102());
    live.setCheck(U.me.id, "ok"); // 候场无片在打，可收局
    live.endLive();
    expect(live.live!.endedAt).toBeTruthy(); // 已封存
    expect(live.isFullPower).toBe(true); // 权限单一源不被封存改写 → onLedger 的 full 闸仍可过
    expect(live.live!.ledger.length).toBeGreaterThan(0); // 底账定格留现场态可查
  });
  it("封存闸（§4.14）：散场后组织者封/撤管理员被拒「现场已散 · 不能再操作」——admins 名单定格", async () => {
    const { live, ui } = await load();
    live.startLive(g102());
    const L = live.live!;
    const [, li, , bei] = L.roster;
    live.setCheck(U.me.id, "ok"); // 候场无片在打，可收局
    live.setAdmin(li.id); // 散场前封得上
    expect(L.admins).toEqual([li.id]);
    live.endLive();
    const feedLen = L.feed.length;
    live.setAdmin(bei.id); // 散场后再封被拒
    expect(L.admins).toEqual([li.id]);
    live.unsetAdmin(li.id); // 散场后再撤也被拒
    expect(L.admins).toEqual([li.id]); // 定格不动
    expect(ui.toastMsg).toBe("现场已散 · 不能再操作");
    expect(L.feed).toHaveLength(feedLen); // 无新留痕
  });
});
