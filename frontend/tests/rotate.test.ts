import { describe, expect, it } from "vitest";
import type {
  Game,
  LiveCourt,
  LiveState,
  RotationRules,
  User,
} from "@/api/types";
import {
  activePlayers,
  courtCount,
  courtSize,
  fillAllCourts,
  fillCourt,
  pById,
  rankOf,
  splitSides,
  takeFromQueue,
  usedCourts,
} from "@/utils/rotate";

let seq = 0;
/** 测试玩家：首参=dupr（1.4 §6 均衡配对吃 DUPR）；elo 固定 1200（娱乐轨不进引擎） */
function mkP(dupr: number, extra: Partial<User> = {}): User {
  seq += 1;
  return {
    id: seq,
    name: `P${seq}`,
    elo: 1200,
    dupr,
    play: 1,
    win: 0,
    month: 0,
    chibi: {},
    check: "ok",
    skip: 0,
    fire: false,
    ...extra,
  };
}
const R0 = (): RotationRules => ({
  singles: false,
  down: "all",
  downChosen: true,
  pairing: "queue",
  champCap: 3,
});
function mkLive(
  mode: Game["rotation"],
  players: User[],
  opts: Partial<LiveState> = {},
): LiveState {
  return {
    g: {
      id: 1,
      name: "t",
      organizer: {
        id: players[0]?.id ?? 99,
        nickname: players[0]?.name ?? "P0",
        chibi: {},
      },
      startAt: "2026-10-06T19:00:00+08:00",
      endAt: "2026-10-06T21:00:00+08:00",
      deadlineAt: "2026-10-06T17:00:00+08:00",
      venueName: "x",
      venueAddress: null,
      minPlayers: 4,
      maxPlayers: 8,
      visibility: "public",
      scoring: 11,
      rotation: mode,
      scoreRule: "rally",
      manualLock: false,
      courts: null,
      feeTotal: 100,
      status: "live",
      unlocked: false,
      joinable: true,
      heads: 0,
      slotsLeft: 8,
      perHead: null,
      forced: false,
    },
    roster: players,
    queue: players.map((p) => p.id),
    courts: [],
    history: [],
    round: 0,
    rules: R0(),
    courtSeqNext: 0,
    ...opts,
  };
}

describe("pById / usedCourts（长期保留导出）", () => {
  it("pById 按找 roster", () => {
    const ps = [3.0].map((e) => mkP(e));
    const live = mkLive("rotate", ps);
    expect(pById(live, ps[0].id)?.name).toBe(ps[0].name);
    expect(pById(live, 99999)).toBeUndefined();
  });

  it("usedCourts（2.4 批2 改口径）：数非空片——空片（差人卡）不算已占", () => {
    const ps = Array.from({ length: 8 }, (_, i) => mkP(3.2 - i * 0.1));
    const full = {
      id: 0,
      name: "1号",
      singles: false,
      A: [ps[0].id, ps[1].id],
      B: [ps[2].id, ps[3].id],
      sa: 0,
      sb: 0,
      streakA: 0,
      streakB: 0,
    };
    const idle = {
      id: 1,
      name: "2号",
      singles: false,
      A: [],
      B: [],
      sa: 0,
      sb: 0,
      streakA: 0,
      streakB: 0,
    };
    const live = mkLive("rotate", ps, { courts: [full, idle] });
    expect(usedCourts(live)).toBe(1);
    live.courts[1]!.A = [ps[4].id]; // 半边有人即在打
    expect(usedCourts(live)).toBe(2);
  });
});

/* ───────── 2.4 引擎用例（旧串行引擎段已随批2 删除；endMatch 五式回流段已随
   批5a 确认结算切真退役——真值在后端 live_rotation.py，前端只留发牌引擎用例）───────── */

const R = (over: Partial<RotationRules> = {}): RotationRules => ({
  singles: false,
  down: "all",
  downChosen: true,
  pairing: "queue",
  champCap: 3,
  ...over,
});
const mkCourt = (
  a: User[],
  b: User[],
  over: Partial<LiveCourt> = {},
): LiveCourt => ({
  A: a.map((p) => p.id),
  B: b.map((p) => p.id),
  id: 0,
  singles: false,
  sa: 0,
  sb: 0,
  streakA: 0,
  streakB: 0,
  ...over,
});
describe("takeFromQueue（2.4 §4.8：跳轮消耗+保位+坑由下位顶）", () => {
  it("轮到歇轮者：跳过这一轮、消耗一次，坑由下一位顶上；取完保位回队", () => {
    const a = mkP(3.0, { skip: 2 });
    const b = mkP(3.0),
      c = mkP(3.0),
      d = mkP(3.0);
    const live = mkLive("rotate", [a, b, c, d]);
    expect(takeFromQueue(live, 2)).toEqual([b.id, c.id]); // a 让位，b/c 顶坑
    expect(a.skip).toBe(1); // 消耗一次
    expect(live.queue).toEqual([a.id, d.id]); // a 保位在 d 前
  });

  it("取满即停：没轮到的歇轮不消耗（轮到才算）", () => {
    const b = mkP(3.0);
    const a = mkP(3.0, { skip: 1 }); // 排 b 后面，本轮没轮到
    const live = mkLive("rotate", [b, a]);
    expect(takeFromQueue(live, 1)).toEqual([b.id]);
    expect(a.skip).toBe(1);
    expect(live.queue).toEqual([a.id]);
  });

  it("absent/left 不可发但留在队里；连战（fire）优先收——下次发牌排最前", () => {
    const gone = mkP(3.0, { check: "absent" });
    const left = mkP(3.0, { check: "left" });
    const hot = mkP(3.0, { fire: true });
    const b = mkP(3.0),
      c = mkP(3.0);
    const live = mkLive("rotate", [gone, left, b, hot, c]);
    expect(takeFromQueue(live, 2)).toEqual([hot.id, b.id]);
    expect(live.queue).toEqual([gone.id, left.id, c.id]);
  });

  it("余额不足：能取多少取多少，队里不剩已取者", () => {
    const b = mkP(3.0),
      c = mkP(3.0);
    const live = mkLive("rotate", [b, c]);
    expect(takeFromQueue(live, 3)).toEqual([b.id, c.id]);
    expect(live.queue).toEqual([]);
  });
});

describe("splitSides（2.4 §4.5 分边真值）", () => {
  it("按候场队序：第 1、2 位一队，第 3、4 位一队", () => {
    const ps = [3.6, 3.2, 2.8, 2.4].map((e) => mkP(e));
    const live = mkLive("rotate", ps);
    expect(
      splitSides(
        live,
        ps.map((p) => p.id),
        "queue",
      ),
    ).toEqual({
      A: [ps[0].id, ps[1].id],
      B: [ps[2].id, ps[3].id],
    });
  });

  it("均衡配对：最强+最弱 vs 二三（积分强到弱，防两个高手挤同边）", () => {
    const ps = [3.2, 4.0, 3.6, 2.8].map((e) => mkP(e)); // 队序与强弱错开
    const live = mkLive("rotate", ps);
    expect(
      splitSides(
        live,
        ps.map((p) => p.id),
        "balance",
      ),
    ).toEqual({
      A: [ps[1].id, ps[3].id],
      B: [ps[2].id, ps[0].id], // 4.0+2.8 vs 3.6+3.2
    });
  });

  it("均衡同分：按候场队先后 tiebreak（不掷骰子，现场可复述）", () => {
    const ps = [3.0, 4.0, 3.0, 4.0].map((e) => mkP(e));
    const live = mkLive("rotate", ps);
    expect(
      splitSides(
        live,
        ps.map((p) => p.id),
        "balance",
      ),
    ).toEqual({
      A: [ps[1].id, ps[2].id],
      B: [ps[3].id, ps[0].id], // 两个 4.0 里队序前的 ps[1] 排头
    });
  });

  it("缺 dupr 的按 3.0 兜底参与排序（1.4 §6 配对吃 DUPR；3.0=访客/缺数，对齐后端 GUEST_DUPR）", () => {
    expect(rankOf(mkP(3.7))).toBe(3.7);
    expect(rankOf(mkP(3.0, { dupr: undefined }))).toBe(3.0);
    expect(rankOf(undefined)).toBe(3.0);
    const ps = [mkP(4.0), mkP(3.0, { dupr: undefined }), mkP(3.6), mkP(3.2)];
    const live = mkLive("rotate", ps); // 缺数者按 3.0 排：低于 3.2/3.6，垫底与最强一队
    expect(
      splitSides(
        live,
        ps.map((p) => p.id),
        "balance",
      ),
    ).toEqual({
      A: [ps[0].id, ps[1].id],
      B: [ps[2].id, ps[3].id], // 4.0+缺数(3.0) vs 3.6+3.2
    });
  });

  it("单打没有分队：一左一右（怎么配都不分）", () => {
    const ps = [4.0, 3.0].map((e) => mkP(e));
    const live = mkLive("rotate", ps);
    expect(
      splitSides(
        live,
        ps.map((p) => p.id),
        "balance",
      ),
    ).toEqual({ A: [ps[0].id], B: [ps[1].id] });
  });
});

describe("fillCourt / fillAllCourts（2.4 §4.3 补满即打）", () => {
  it("空片补满：按怎么公分边、比分清零、新队连庄清零、courtSeq/tenure 起算", () => {
    const ps = Array.from({ length: 8 }, (_, i) => mkP(3.2 - i * 0.1));
    const court = mkCourt([], [], {
      id: 0,
      streakA: 5,
      streakB: 2,
      sa: 11,
      sb: 7,
    });
    const live = mkLive("rotate", ps, {
      rules: R({ down: "loser" }),
      courtSeqNext: 4,
      courts: [court],
    });
    fillCourt(live, court);
    expect(court).toMatchObject({
      A: [ps[0].id, ps[1].id],
      B: [ps[2].id, ps[3].id],
      sa: 0,
      sb: 0,
      streakA: 0,
      streakB: 0,
    });
    expect(ps[0].courtSeq).toBe(5); // 新发上场序
    expect(ps[0].tenure).toBe(0); // 资历从 0 起算
    expect(live.queue).toEqual(ps.slice(4).map((p) => p.id));
  });

  it("补不满留空（差人卡呈现）：不动队列、不消耗歇轮", () => {
    const a = mkP(3.0, { skip: 1 });
    const b = mkP(3.0),
      c = mkP(3.0);
    const court = mkCourt([], [], { id: 0 });
    const live = mkLive("rotate", [a, b, c], {
      rules: R(),
      courtSeqNext: 0,
      courts: [court],
    });
    fillCourt(live, court);
    expect(court.A).toEqual([]); // 留空
    expect(court.B).toEqual([]);
    expect(live.queue).toEqual([a.id, b.id, c.id]);
    expect(a.skip).toBe(1); // 没发牌不消耗
  });

  it("片格式说了算（过渡期 court.singles 可 ≠ rules.singles）：单打片只取 2 人", () => {
    const ps = Array.from({ length: 4 }, (_, i) => mkP(3.2 - i * 0.1));
    const court = mkCourt([], [], { id: 0, singles: true });
    const live = mkLive("rotate", ps, {
      rules: R(),
      courtSeqNext: 0,
      courts: [court],
    });
    fillCourt(live, court);
    expect(court.A).toEqual([ps[0].id]);
    expect(court.B).toEqual([ps[1].id]);
  });

  it("fillAllCourts 按片号先后补空片；最后一片补不满留空", () => {
    const ps = Array.from({ length: 11 }, (_, i) => mkP(3.2 - i * 0.1));
    const c0 = mkCourt([], [], { id: 0 });
    const c1 = mkCourt([], [], { id: 1 });
    const c2 = mkCourt([], [], { id: 2 });
    ps[0].fire = true; // 连战者必进首片
    const live = mkLive("rotate", ps, {
      rules: R(),
      courtSeqNext: 0,
      courts: [c0, c1, c2],
    });
    live.g.maxPlayers = 12;
    fillAllCourts(live);
    expect(c0.A).toEqual([ps[0].id, ps[1].id]); // 片 0 先取：连战 ps[0] + 队首 ps[1]
    expect(c0.B).toEqual([ps[2].id, ps[3].id]);
    expect(c1.A).toEqual([ps[4].id, ps[5].id]); // 片 1 随后
    expect(c1.B).toEqual([ps[6].id, ps[7].id]);
    expect(c2.A).toEqual([]); // 只剩 3 人 <4：留空差人卡
    expect(live.queue).toEqual(ps.slice(8).map((p) => p.id));
  });
});

describe("口径单一源（2.4 技术设计 §0.5/§0.6）", () => {
  it("courtSize：双打 4 / 单打 2；courtCount：登记优先、未登记按人数兜底", () => {
    expect(courtSize(false)).toBe(4);
    expect(courtSize(true)).toBe(2);
    const ps = Array.from({ length: 8 }, () => mkP(3.0));
    const live = mkLive("rotate", ps); // courts 未登记、maxPlayers 8 → 2 片
    expect(courtCount(live)).toBe(2);
    live.g.maxPlayers = 12;
    expect(courtCount(live)).toBe(3);
    live.g.courts = ["3号"];
    expect(courtCount(live)).toBe(1);
  });

  it("activePlayers：片上 + 候场队（absent/left 不算，歇轮者算）", () => {
    const a = mkP(3.0, { skip: 1 });
    const gone = mkP(3.0, { check: "left" });
    const b = mkP(3.0),
      c = mkP(3.0);
    const on1 = mkP(3.0),
      on2 = mkP(3.0);
    const live = mkLive("rotate", [on1, on2, a, gone, b, c], {
      courts: [mkCourt([on1], [on2], { id: 0, singles: true })],
      queue: [a.id, gone.id, b.id, c.id],
    });
    expect(activePlayers(live)).toBe(5); // 片上 2 + 候场 3（早退 gone 不算，歇轮 a 算）
  });
});
