import { describe, expect, it } from "vitest";
import { toLiveView } from "@/api/live";
import type { LiveViewApi } from "@/api/types";

/* toLiveView 战报边序换算单一源：线上快照只记胜败两堆（winners/losers）+winner_side，
   camel 侧只给按边摆好的 sideA/sideB（与 sa/sb 同序）——战报行「B 面赢的场次名字
   顶错比分、高亮落输家」的展示错位由此堵死，组件层不再自推。 */

const P = { id: 1, name: "甲", guest: false };
const Q = { id: 2, name: "乙", guest: false };
const ELO = [
  {
    account_id: 1,
    name: "甲",
    guest: false,
    rating_before: 1200,
    rating_after: 1212,
    delta: 12,
  },
  {
    account_id: 2,
    name: "乙",
    guest: false,
    rating_before: 1200,
    rating_after: 1193,
    delta: -7,
  },
];

const view = (winner_side: "a" | "b"): LiveViewApi => ({
  game_id: 1,
  started_at: "2026-10-16T19:00:00+08:00",
  ended: true,
  ended_at: "2026-10-16T22:00:00+08:00",
  total_seq: 1,
  round: 0,
  admins: [],
  is_organizer: false,
  is_full_power: false,
  organizer_account_id: -1,
  feed: [],
  courts_count: 1,
  rules: {
    scoring: 15,
    doubles: true,
    down: "all",
    pairing: "queue",
    streak_max: 2,
  },
  players: [],
  queue: [],
  courts: [],
  matches: [
    {
      court_no: 1,
      seq: 1,
      winners: [P],
      losers: [Q],
      score_a: 4,
      score_b: 15,
      winner_side,
      ended_at: "2026-10-16T20:00:00+08:00",
      elo_rows: ELO,
    },
  ],
});

describe("toLiveView 战报边序（sideA/sideB 与 sa/sb 同序）", () => {
  it("B 面赢：sideA 是败方快照、sideB 是胜方——比分 4:15 左右不再顶错名字", () => {
    const m = toLiveView(view("b")).matches[0]!;
    expect(m.sideA.map((p) => p.name)).toEqual(["乙"]);
    expect(m.sideB.map((p) => p.name)).toEqual(["甲"]);
    expect(m.winA).toBe(false);
    expect([m.sa, m.sb]).toEqual([4, 15]);
  });

  it("A 面赢：sideA 即胜方快照", () => {
    const m = toLiveView(view("a")).matches[0]!;
    expect(m.sideA.map((p) => p.name)).toEqual(["甲"]);
    expect(m.sideB.map((p) => p.name)).toEqual(["乙"]);
    expect(m.winA).toBe(true);
  });

  it("eloRows 原样透传（胜队在前，与边序无关）", () => {
    const m = toLiveView(view("b")).matches[0]!;
    expect(m.eloRows.map((r) => r.delta)).toEqual([12, -7]);
  });
});

/* 1.9 装扮三键透传：名册行身份块 snake→camel 单点直落（snake_url→avatarUrl），
   访客三键 null 原样——展示组件各兜各的默认（圆章公共款/素卡） */
describe("toLiveView 装扮三键（avatar/avatarUrl/back）", () => {
  it("注册球友三键直落、访客 null 原样", () => {
    const v = view("a");
    v.players = [
      {
        id: 7,
        account_id: 5,
        name: "老金",
        avatar: "a-p3",
        avatar_url: "/cosmetics/a-p3.webp",
        back: "b-c2",
        guest: false,
        dupr: 3.1,
        guarantor_account_id: null,
        dropin: false,
        check: "ok",
        arrive_at: null,
        left_at: null,
        court_no: null,
        court_side: null,
        skip: 0,
        fire: false,
        queue_pos: null,
        tonight: 0,
      },
      {
        id: 8,
        account_id: null,
        name: "访客8",
        avatar: null,
        avatar_url: null,
        back: null,
        guest: true,
        dupr: 2.5,
        guarantor_account_id: 5,
        dropin: false,
        check: "ok",
        arrive_at: null,
        left_at: null,
        court_no: null,
        court_side: null,
        skip: 0,
        fire: false,
        queue_pos: null,
        tonight: 0,
      },
    ];
    const ps = toLiveView(v).players;
    expect(ps[0]).toMatchObject({
      avatar: "a-p3",
      avatarUrl: "/cosmetics/a-p3.webp",
      back: "b-c2",
    });
    expect(ps[1]).toMatchObject({
      avatar: null,
      avatarUrl: null,
      back: null,
    });
  });
});
