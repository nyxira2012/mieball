import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import type { GameViewApi, PlaylogApi } from "@/api/games";

/* 批2 数据层（2.6）：api 层整体 mock，用例喂 crafted playlog 响应（形状与后端
   services/games.py playlog 逐字对齐），测 loadPlaylog 落位（toGame 映射/matchesCount）
   与 liveGame 口径修正（4.1-3 同时在办多个挑最近开打的）。 */
const api = vi.hoisted(() => ({
  apiPublishGame: vi.fn(),
  apiListGames: vi.fn(),
  apiMyGames: vi.fn(),
  apiGameDetail: vi.fn(),
  apiJoinGame: vi.fn(),
  apiQuitGame: vi.fn(),
  apiEditGame: vi.fn(),
  apiLockGame: vi.fn(),
  apiBookCourt: vi.fn(),
  apiClearBooking: vi.fn(),
  apiCancelGame: vi.fn(),
  apiRestoreGame: vi.fn(),
  apiInviteUser: vi.fn(),
  apiListIntents: vi.fn(),
  apiMyIntent: vi.fn(),
  apiSaveIntent: vi.fn(),
  apiDeleteIntent: vi.fn(),
  apiGameFeePreview: vi.fn(),
  apiGameFee: vi.fn(),
  apiPlaylog: vi.fn(),
}));

vi.mock("@/api/games", () => api);

beforeEach(() => {
  vi.clearAllMocks();
  setActivePinia(createPinia());
});

async function loadStore() {
  const mod = await import("@/stores/game");
  return mod.useGameStore();
}

/* ---- 造数（线上 snake 形状，同 game-store.test.ts 款） ---- */
let seq = 600;
function mkView(p: Partial<GameViewApi> = {}): GameViewApi {
  seq += 1;
  return {
    id: seq,
    name: `测试局 ${seq}`,
    organizer: { id: 7, nickname: "朝阳反手王", chibi: {} },
    start_at: "2026-10-08T19:00:00+08:00",
    end_at: "2026-10-08T21:00:00+08:00",
    deadline_at: "2026-10-08T17:00:00+08:00",
    venue_name: "测试球馆",
    venue_address: null,
    min_players: 4,
    max_players: 8,
    visibility: "public",
    scoring: 11,
    rotation: "balance",
    score_rule: "rally",
    manual_lock: false,
    courts: null,
    fee_total: null,
    status: "done",
    unlocked: false,
    joinable: false,
    live_opened: false,
    ended: true,
    heads: 4,
    slots_left: 0,
    per_head: null,
    forced: false,
    ...p,
  };
}

describe("loadPlaylog（打球记录落位，2.6）", () => {
  it("games 逐行 toGame 映射 + matchesCount 落位（后端已倒序，前端不重排）", async () => {
    const body: PlaylogApi = {
      games: [
        mkView({ id: 1, start_at: "2026-10-08T19:00:00+08:00" }),
        mkView({ id: 2, start_at: "2026-10-01T19:00:00+08:00" }),
      ],
      matches_count: 7,
    };
    api.apiPlaylog.mockResolvedValue(body);
    const store = await loadStore();
    await store.loadPlaylog();
    expect(api.apiPlaylog).toHaveBeenCalledTimes(1);
    expect(store.playlog?.matchesCount).toBe(7);
    expect(store.playlog?.games.map((g) => g.id)).toEqual([1, 2]); // 原序整袋
    const g = store.playlog!.games[0]!;
    expect(g.startAt).toBe("2026-10-08T19:00:00+08:00"); // snake→camel 映射抽查
    expect(g.ended).toBe(true);
    expect(g.heads).toBe(4);
  });

  it("空记录：games 空袋、matchesCount 0", async () => {
    api.apiPlaylog.mockResolvedValue({ games: [], matches_count: 0 });
    const store = await loadStore();
    await store.loadPlaylog();
    expect(store.playlog).toEqual({ games: [], matchesCount: 0 });
  });
});

describe("liveGame 口径（4.1-3：同时在办多个挑最近开打的）", () => {
  it("两局在办：取 startAt 大的（开账时刻局簿没有，startAt 是近似口径）", async () => {
    api.apiListGames.mockResolvedValue([
      mkView({
        id: 1,
        status: "live",
        ended: false, // 在办局未散场（本文件 mkView 默认 ended:true 是散场局形状）
        start_at: "2026-10-08T10:00:00+08:00",
      }),
      mkView({
        id: 2,
        status: "live",
        ended: false,
        start_at: "2026-10-08T15:00:00+08:00",
      }),
    ]);
    const store = await loadStore();
    await store.loadGames();
    expect(store.liveGame?.id).toBe(2);
  });

  it("单局在办照旧命中：簿 state 仍 open 但 live_opened 的 manual_lock 局也算（2.5 §4.4）", async () => {
    api.apiListGames.mockResolvedValue([
      mkView({
        id: 5,
        status: "open",
        manual_lock: true,
        live_opened: true,
        ended: false, // 在办局未散场（同上，默认 ended:true 会吃 2.6 修正后的在办口径）
      }),
    ]);
    const store = await loadStore();
    await store.loadGames();
    expect(store.liveGame?.id).toBe(5);
  });

  it("无在办：null（散场局不算在办）", async () => {
    api.apiListGames.mockResolvedValue([mkView({ id: 3, status: "done" })]);
    const store = await loadStore();
    await store.loadGames();
    expect(store.liveGame).toBeNull();
  });
});
