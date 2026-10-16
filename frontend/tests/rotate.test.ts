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
  canPickWinner,
  courtCount,
  courtSize,
  followWinner,
  idleHint,
  pById,
  roundsToPlay,
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
    };
    const idle = {
      id: 1,
      name: "2号",
      singles: false,
      A: [],
      B: [],
    };
    const live = mkLive("rotate", ps, { courts: [full, idle] });
    expect(usedCourts(live)).toBe(1);
    live.courts[1]!.A = [ps[4].id]; // 半边有人即在打
    expect(usedCourts(live)).toBe(2);
  });
});

/* 取人/分边/补片用例段已随 2.8 批3 删除——行为真值迁后端
   backend/tests/test_live_rotation.py（take_from_queue 矩阵），前端只剩展示派生。 */

const mkCourt = (
  a: User[],
  b: User[],
  over: Partial<LiveCourt> = {},
): LiveCourt => ({
  A: a.map((p) => p.id),
  B: b.map((p) => p.id),
  id: 0,
  singles: false,
  ...over,
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

  it("idleHint：差人一句话（空片差人卡与结算窗一步展示同吃）——够开/还差两分支", () => {
    expect(idleHint(4, 4)).toBe("候场 4 人 · 够开 1 片");
    expect(idleHint(5, 4)).toBe("候场 5 人 · 够开 1 片");
    expect(idleHint(1, 4)).toBe("还差 3 人 · 候场 1 / 需 4 人");
    expect(idleHint(0, 2)).toBe("还差 2 人 · 候场 0 / 需 2 人"); // 单打
  });
});

describe("roundsToPlay（live store myRound 与沙盒候场条共用的轮次公式）", () => {
  it("全场在打：队首下一场上，每片人数进一轮", () => {
    expect(roundsToPlay(4, 0, 0)).toBe(1);
    expect(roundsToPlay(4, 0, 3)).toBe(1);
    expect(roundsToPlay(4, 0, 4)).toBe(2);
    expect(roundsToPlay(4, 0, 7)).toBe(2);
  });

  it("有空片：补片先吃的队首段整体进位（与 live store 既有口径逐字同式）", () => {
    expect(roundsToPlay(4, 1, 0)).toBe(2);
    expect(roundsToPlay(4, 1, 3)).toBe(2);
    expect(roundsToPlay(4, 1, 4)).toBe(3);
    expect(roundsToPlay(2, 1, 1)).toBe(2); // 单打：1 空片 + 位 1
  });
});
