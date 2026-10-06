import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { U } from "@/api";
import type { EntryRow, Game, User } from "@/api/types";

/* 每个用例重置模块图 → 全新 mock 数据；102（balance · 8 上限）与 101（winner · 12 上限）
   两组真局 fixture 做确定性推演。
   2.1 打球页改版（批1）：终局从「到分自动落账」改为 point→settling 快照→confirmSettle 确认落账。
   1.2 隔离线：startLive 吃重塑后的真局对象（形状与后端 game_view 镜像），名册从 formal
   报名行展开、mock U 同 id 者借真实战绩对象（结算落回战力榜）。 */
beforeEach(async () => {
  vi.resetModules();
  setActivePinia(createPinia());
});

async function load() {
  const liveMod = await import("@/stores/live");
  const uiMod = await import("@/stores/ui");
  return { live: liveMod.useLiveStore(), ui: uiMod.useUiStore() };
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
    startAt: "2026-10-10T14:00:00+08:00",
    endAt: "2026-10-10T16:00:00+08:00",
    deadlineAt: "2026-10-10T12:00:00+08:00",
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

/** 把 102 局 cur 打到 11:9（到分，settling 已开未落账）。返回句柄 + 访客 id（roster[2]） */
async function setupSettling() {
  const h = await load();
  h.live.startLive(g102());
  const L = h.live.live!;
  for (let i = 0; i < 9; i++) h.live.point("a");
  for (let i = 0; i < 9; i++) h.live.point("b");
  h.live.point("a");
  h.live.point("a"); // 11:9
  return { ...h, L, guest: L.roster[2].id };
}

describe("startLive（alpha:1471-1490）", () => {
  it("随行展开成 shadow 访客（随机 chibi）· 前 9 人 ok · balance 蛇形发牌 · 红点亮", async () => {
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
    expect(guest.name).toBe("亮马的球友"); // li.name.slice(0,2) + 的球友
    expect(guest.elo).toBe(1200);
    expect(L.roster.every((p) => p.check === "ok")).toBe(true); // 4 < 9 全部到场
    expect(L.roster.every((p) => p.skip === 0)).toBe(true); // 歇两轮计数从 0 起
    // balance 按分降序蛇形：li1574 / me1518 / bei1452 / 访客1200 → A=[li,访客] B=[me,bei]
    // （102 局 entries 顺序的 id：me=0 · li=5 · bei=8，访客 id ≥9000 动态）
    expect(L.cur!.A).toEqual([5, guest.id]);
    expect(L.cur!.B).toEqual([0, 8]);
    expect(L.cur!.sa).toBe(0);
    expect(L.queue).toEqual([]); // 全部上场
  });
  it("超过 9 人时：前 9 ok 其余 absent（101 局：11 报名 + hai 带 2 访客 = 13）", async () => {
    const { live } = await load();
    live.startLive(g101());
    const L = live.live!;
    expect(L.roster).toHaveLength(13);
    expect(L.roster.filter((p) => p.shadow)).toHaveLength(3); // hai 带 2 访客 + zhao 本就是随行
    expect(L.roster.filter((p) => p.check === "ok")).toHaveLength(9);
    expect(L.roster.filter((p) => p.check === "absent")).toHaveLength(4);
    // fillCourts 后队列重建：9 名可上场者中 8 人上两片，余 1 名访客候场（alpha:1519-1522）
    expect(L.queue).toHaveLength(1);
  });
});

describe("point → settling → confirmSettle（2.1 §5 结算流 · alpha:1688-1728 数值口径）：K=24 / 败方六成 / 随行半权重", () => {
  it("11:9 到点开 settling（cur 不动），confirmSettle(true,11,9) 落账 + 自动排下一场，战力榜联动", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
    const guest = L.roster[2].id;
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
      names: "亮马河快攻 & 亮马的球友",
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
    live.point("a");
    live.point("a"); // 2:0 未到分
    expect(live.settling).toBeNull();
    live.openSettle(); // 卡上「终局结算」钮
    expect(live.settling).toEqual({ sa: 2, sb: 0 });
    live.confirmSettle(true, 2, 0); // 手动终局也走同一落账口径
    expect(L.history[0]).toEqual({
      names: "亮马河快攻 & 亮马的球友",
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
  it("setCheck：迟到排队尾 / 早退出列 / 中途加入队首（alpha:1591-1605）", async () => {
    const { live, L, guest } = await setupQueue();
    expect(L.queue).toEqual([5, guest, 0, 8]);
    live.setCheck(5, "late");
    expect(L.queue).toEqual([guest, 0, 8, 5]); // 迟到 → 队尾
    live.setCheck(guest, "left");
    expect(L.queue).toEqual([0, 8, 5]); // 早退 → 出列
    expect(L.roster.find((p) => p.id === guest)!.check).toBe("left");
    live.setCheck(guest, "join");
    expect(L.queue).toEqual([guest, 0, 8, 5]); // 中途加入 → 队首
    expect(L.roster.find((p) => p.id === guest)!.check).toBe("join");
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
  it("avail 放行 late（2.1 §3 裁决）：setCheck(id,late) 后 autoDeal 能把迟到者发上场", async () => {
    const { live } = await load();
    live.startLive(g102());
    const L = live.live!;
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
    live.addGuests(1, "小陈", U.me);
    const xin = L.roster[4].id; // 新访客在候场队尾
    live.swapPlayers(8, xin); // 场上的 bei ↔ 候场的小陈
    expect(L.cur!.B).toEqual([0, xin]); // cur.B 里 8 → 小陈
    expect(L.queue).toEqual([8]); // 候场的坑由 bei 顶，次序不乱
  });
  it("addGuests：空名→「介绍人前两字+的球友」；非空多位→name·2/name·3；单位不带序号；shadow 进队尾", async () => {
    const { live } = await load();
    const { U } = await import("@/api");
    live.startLive(g102());
    const L = live.live!;
    expect(L.queue).toEqual([]); // 全上场 → 队尾即紧接其后
    live.addGuests(2, "", U.li);
    const auto = L.roster.slice(4, 6);
    expect(auto.map((g) => g.name)).toEqual(["亮马的球友", "亮马的球友"]);
    expect(
      auto.every(
        (g) => g.shadow && g.elo === 1200 && g.check === "join" && g.id >= 9000,
      ),
    ).toBe(true);
    expect(L.queue).toEqual(auto.map((g) => g.id)); // 队尾依次进
    live.addGuests(2, "小陈", U.me);
    expect(L.roster.slice(6, 8).map((g) => g.name)).toEqual([
      "小陈·2",
      "小陈·3",
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
  it("myRound：102 局取消后队列 4 人、我 idx0（连战顶队首）→ 1；在打时 → null", async () => {
    const { live } = await load();
    live.startLive(g102());
    expect(live.myRound).toBeNull(); // 我在 cur 上，不在队列
    const L = live.live!;
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
    live.startLive(g101()); // cur={A:[1,2],B:[g,g]} · queue=[6]
    const L = live.live!;
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
    live.startLive(g101()); // 我(0)在待开片 courts[0].B；wang(1) 在 cur.A
    const L = live.live!;
    live.setCheck(1, "late");
    expect(L.roster.find((p) => p.id === 1)!.check).toBe("ok"); // 没改成
    expect(ui.toastMsg).toBe("请找组织者或管理员");
    live.togglePerson(1, "skip");
    expect(L.roster.find((p) => p.id === 1)!.skip).toBeFalsy(); // 没设上
    live.setCheck(U.me.id, "left"); // 自己早退随时可
    expect(L.roster.find((p) => p.id === 0)!.check).toBe("left");
    expect(L.courts[0]!.B).toEqual([5]); // 我在待开片上（cur.B 是 hai 的两位随行）→ 早退出场
    live.togglePerson(U.me.id, "skip"); // 自己歇随时可
    expect(L.roster.find((p) => p.id === 0)!.skip).toBe(2);
  });
  it("管理员获得与组织者同一套手柄（§4.7）：收权动作放行", async () => {
    const { live } = await load();
    live.startLive(g101());
    const L = live.live!;
    L.admins.push(U.me.id);
    live.point("a");
    live.clearScore();
    expect(L.cur!.sa).toBe(0);
    live.setRuleScore(21);
    expect(L.g.scoring).toBe(21);
    expect(live.isFullPower).toBe(true);
  });
});
