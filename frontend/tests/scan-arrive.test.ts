/* 扫码自签到链路（2.1·选项A · 1.3 批2 空降切真）+ 「我」id 运行时化回归（1.2 接线重写）：
   - arriveMe：名册没我 → apiLiveDropIn 后端建行入册（dropin 标、队尾，响应视图落地）；
     在册未到 → 到场（apiLiveCheck，口径归一在后端）；已在场 → 幂等；已结束的局 →
     ensureLive 拦在门外；视图无我的行时重扫 → 再走空降通道（原「移出后重扫」，
     2.6 移出退役后用视图重建造该态）
   - 真账号换装身份位（id 非 0）后：isMe 认得出、togglePerson 找得到人（快照常量回归）
   局 fixture 与后端 game_view 镜像；现场链走批5a 同款 vi.mock('@/api/live')：
   读默认 404 live_not_found → ensureLive 落局簿开账路（开账视图 row id=账号 id 镜像），
   空降喂 crafted 响应视图（snake 形状与 services/live.py view 输出对齐）。 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { ApiError } from "@/api/http";
import type { GameViewApi } from "@/api/games";
import type { LivePlayerApi, LiveViewApi } from "@/api/types";
import { useUserStore } from "@/stores/user";
import { useGameStore } from "@/stores/game";
import { useLiveStore } from "@/stores/live";

/** 游客占位（用例后恢复，避免串扰——mock 退役后身份位在 user store me） */
const demo = { id: 0, name: "我" };

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
}));
vi.mock("@/api/games", () => api);

const liveApi = vi.hoisted(() => ({
  apiLiveView: vi.fn(),
  apiLiveStart: vi.fn(),
  apiLiveDeal: vi.fn(),
  apiLiveSettleConfirm: vi.fn(),
  apiLiveCancel: vi.fn(),
  apiLiveCheck: vi.fn(),
  apiLiveDropIn: vi.fn(),
  apiLiveGuests: vi.fn(),
  apiLiveSwap: vi.fn(),
  apiLiveTempo: vi.fn(),
  apiLiveRules: vi.fn(),
  apiLiveSetAdmin: vi.fn(),
  apiLiveUnsetAdmin: vi.fn(),
}));
vi.mock("@/api/live", async (importOriginal) => ({
  ...(await importOriginal<object>()),
  ...liveApi,
}));

/** 107 现场开账视图（row id=账号 id 与局簿镜像；开场全员未到、无片无队不发牌） */
function plv(id: number, nickname: string): LivePlayerApi {
  return {
    id,
    account_id: id,
    name: nickname,
    guest: false,
    guarantor_account_id: null,
    dropin: false,
    check: "absent",
    arrive_at: null,
    left_at: null,
    court_no: null,
    court_side: null,
    skip: 0,
    fire: false,
    queue_pos: null,
  };
}
function liveStartView(): LiveViewApi {
  return {
    game_id: 107,
    started_at: "2026-10-06T21:00:00+08:00",
    ended: false,
    ended_at: null,
    total_seq: 1,
    round: 0,
    admins: [0],
    is_organizer: false, // 身份块（2026-10-08 起）：我(0)非组织者(6)、被列管理员 → 全权（needFull 读视图旗）
    is_full_power: true,
    organizer_account_id: 6,
    feed: [],
    courts_count: 1,
    rules: {
      scoring: 11,
      doubles: true,
      down: "all",
      pairing: "queue",
      streak_max: 3,
    },
    players: [plv(6, "石景山铁腰"), plv(4, "国贸截击手")],
    queue: [],
    courts: [],
    matches: [],
  };
}

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
  // 现场读默认 404 未开账 → ensureLive 落局簿开账路；开账幂等回 107 最小视图
  liveApi.apiLiveView.mockRejectedValue(
    new ApiError("live_not_found", "现场未开始", 404),
  );
  liveApi.apiLiveStart.mockResolvedValue(liveStartView());
});

/** 我的空降行（row id 42 · 账号 0 · dropin 标）：开账后端 dropin 的落库形状 */
function myDropinRow(check: LivePlayerApi["check"] = "ok"): LivePlayerApi {
  return {
    id: 42,
    account_id: 0,
    name: "我",
    guest: false,
    guarantor_account_id: null,
    dropin: true,
    check,
    arrive_at: "2026-10-06T21:05:00+08:00",
    left_at: null,
    court_no: null,
    court_side: null,
    skip: 0,
    fire: false,
    queue_pos: 1,
  };
}

/** 空降响应视图：开账视图 + 我的新行进队尾（总号进一） */
function dropinView(): LiveViewApi {
  const base = liveStartView();
  return {
    ...base,
    total_seq: 2,
    players: [...base.players, myDropinRow()],
    queue: [6, 42],
  };
}

/** 够人版空降视图：候场 4 人全到场（组织者+球友+两位后到+我）——自动发牌支线的靶 */
function dropinDealView(): LiveViewApi {
  const base = liveStartView();
  const extra = (id: number, acc: number): LivePlayerApi => ({
    ...plv(id, `球友${acc}`),
    account_id: acc,
    check: "ok",
  });
  return {
    ...base,
    total_seq: 2,
    players: [
      { ...plv(6, "石景山铁腰"), check: "ok" }, // 先到者已到场，进发牌池
      { ...plv(4, "国贸截击手"), check: "ok" },
      extra(7, 7),
      extra(8, 8),
      myDropinRow(),
    ],
    queue: [6, 4, 7, 42],
  };
}

/** 在册未到视图：开账视图带我的 formal 行（row id 42 · 账号 0 · absent） */
function absentMeView(): LiveViewApi {
  const base = liveStartView();
  return {
    ...base,
    players: [...base.players, { ...myDropinRow("absent"), dropin: false }],
  };
}

/** 模拟真账号换装身份位（session store applyAccount 的等价操作） */
function takeoverAs(id: number, name: string): void {
  Object.assign(useUserStore().me, { id, name });
}

const person = (id: number, nickname: string) => ({ id, nickname, chibi: {} });
const entry = (id: number, nickname: string, bring = 0) => ({
  account: person(id, nickname),
  bring,
  standing: "formal" as const,
  wait_seq: null,
});

/** 107 同构（原「加时夜战」：我未报名 · shi/gu 在册），球友视角 my.myEntry 为空 */
function viewOf(overrides: Partial<GameViewApi> = {}): GameViewApi {
  return {
    id: 107,
    name: "加时夜战 · 临时凑",
    organizer: person(6, "石景山铁腰"),
    start_at: "2026-10-06T21:00:00+08:00",
    end_at: "2026-10-06T22:00:00+08:00",
    deadline_at: "2026-10-06T19:00:00+08:00",
    venue_name: "望京 · 花家地球馆",
    venue_address: null,
    min_players: 4,
    max_players: 6,
    visibility: "played",
    scoring: 11,
    rotation: "balance",
    score_rule: "rally",
    manual_lock: false,
    courts: null,
    fee_total: 300,
    status: "open",
    unlocked: false,
    joinable: true,
    heads: 2,
    slots_left: 4,
    per_head: null,
    forced: false,
    entries: [entry(6, "石景山铁腰"), entry(4, "国贸截击手")],
    my: { is_organizer: false, my_entry: null, invited: false },
    ...overrides,
  };
}

/** 把视图灌进 store（games 列表 + current，等价 loadGames/loadDetail 的落点） */
async function seedStore(...views: GameViewApi[]) {
  api.apiListGames.mockResolvedValue(views);
  api.apiGameDetail.mockResolvedValue(views[0]!);
  const mod = await import("@/stores/game");
  const store = mod.useGameStore();
  await store.loadGames();
  return store;
}

describe("arriveMe（扫码签到）", () => {
  it("空降：名册没我 → apiLiveDropIn 建行入册（dropin 标、队尾）；线上名单/候补原样不动", async () => {
    const store = await seedStore(viewOf()); // 我未报名（my_entry null）
    const live = useLiveStore();
    await live.ensureLive(107); // 先点亮现场，造一位先到者占队
    live.live!.queue.push(6); // 搭态：组织者已在候场
    expect(api.apiJoinGame).not.toHaveBeenCalled();
    liveApi.apiLiveDropIn.mockResolvedValue(dropinView());

    const msg = await live.arriveMe(107);

    expect(msg).toBe("已签到 · 进候场区");
    expect(api.apiJoinGame).not.toHaveBeenCalled(); // 空降不再 joinGame（§4.4：满员/候补都不拦）
    expect(liveApi.apiLiveDropIn).toHaveBeenCalledWith(107, 1); // base 号=出发时总号
    const L = live.live!;
    expect(L.g.id).toBe(107);
    const me = L.roster.find((p) => p.id === 42);
    expect(me?.check).toBe("ok"); // 开球时刻归一在后端
    expect(me?.dropin).toBe(true); // 空降标全场看得到
    expect(L.queue).toEqual([6, 42]); // 排到队尾（视图真值）
    expect(store.findGame(107)?.heads).toBe(2); // 线上名单原样不动
    expect(live.liveView!.players.find((r) => r.id === 42)!.dropin).toBe(true); // 底账带空降标（LedgerSheet 视图行直推）
  });

  it("空降报到够一片人数 → 自动发牌上片（修复批：空降支线此前漏 maybeDeal，要手点 ⚡）", async () => {
    await seedStore(viewOf());
    const live = useLiveStore();
    await live.ensureLive(107);
    liveApi.apiLiveDropIn.mockResolvedValue(dropinDealView());
    liveApi.apiLiveDeal.mockResolvedValue(dropinDealView());

    await live.arriveMe(107);

    expect(liveApi.apiLiveDeal).toHaveBeenCalledTimes(1);
    expect(liveApi.apiLiveDeal).toHaveBeenCalledWith(
      107,
      [{ courtNo: 1, a: [6, 4], b: [7, 42] }], // 队头一拨，queue 分边 1,2 vs 3,4
      2, // 出发号 = 空落后的总号
    );
  });

  it("在册未到（正式球友）→ 走报到通道 apiLiveCheck，不重复空降", async () => {
    await seedStore(viewOf());
    const live = useLiveStore();
    liveApi.apiLiveStart.mockResolvedValue(absentMeView());
    await live.ensureLive(107);
    const seeded = absentMeView();
    liveApi.apiLiveCheck.mockResolvedValue({
      ...seeded,
      total_seq: 2,
      players: seeded.players.map((p) =>
        p.account_id === 0 ? myDropinRow("late") : p,
      ),
      queue: [6, 42],
    });

    const msg = await live.arriveMe(107);

    expect(msg).toBe("已签到 · 进候场区");
    expect(liveApi.apiLiveDropIn).not.toHaveBeenCalled(); // 有行不空降
    expect(liveApi.apiLiveCheck).toHaveBeenCalledWith(107, 42, "ok", 1);
    expect(live.live!.roster.find((p) => p.id === 42)?.check).toBe("late"); // 迟到归一在后端
  });

  it("视图无我的行时重扫（原「移出后重扫」§4.3 对手方；移出本地路已随 2.6 退役，改用视图重建造态）→ 再走空降通道回名册进队尾", async () => {
    await seedStore(viewOf());
    const live = useLiveStore();
    liveApi.apiLiveDropIn.mockResolvedValue(dropinView());
    await live.arriveMe(107); // 首次空降：在场
    // 总账视图重建为无我的行（名册真值随视图）：我的行从名册消失
    const { toLiveView } = await import("@/api/live");
    live.applyLiveView(toLiveView(liveStartView()));
    expect(live.live!.roster.some((p) => p.id === 42)).toBe(false);

    const msg = await live.arriveMe(107); // 重扫

    expect(msg).toBe("已签到 · 进候场区");
    expect(liveApi.apiLiveDropIn).toHaveBeenCalledTimes(2); // 再空降
    const me = live.live!.roster.find((p) => p.id === 42);
    expect(me).toBeTruthy(); // 回到名册
    expect(me!.check).toBe("ok");
    expect(live.live!.queue[live.live!.queue.length - 1]).toBe(42); // 进候场队尾
    expect(live.liveView!.players.filter((r) => r.id === 42)).toHaveLength(1); // 底账一行（视图行直推）
  });

  it("已在场 → 幂等提示，不再发空降/报到", async () => {
    await seedStore(viewOf());
    const live = useLiveStore();
    liveApi.apiLiveDropIn.mockResolvedValue(dropinView());
    await live.arriveMe(107);
    const L1 = live.live!;
    const checkAfterFirst = L1.roster.find((p) => p.id === 42)!.check;
    const queueLen = L1.queue.length;

    const msg = await live.arriveMe(107);

    expect(msg).toBeNull(); // 无新动作
    expect(liveApi.apiLiveDropIn).toHaveBeenCalledTimes(1);
    expect(live.live!.roster.find((p) => p.id === 42)!.check).toBe(
      checkAfterFirst,
    );
    expect(live.live!.queue.length).toBe(queueLen);
  });

  it("行 id 撞账号 id（2026-10-11 扫码注册事故回归）：别人的行恰占我的账号号 → 不认错人，照走空降道", async () => {
    takeoverAs(42, "海淀反手王");
    await seedStore(viewOf());
    const live = useLiveStore();
    // 别人的已到场行恰好占行 id 42（账号 9）——旧「查无回落账号 id」会把它当
    // 「已到场的我」，arriveMe 吃「你已经在场了」直接返回，空降道被堵死
    const base = liveStartView();
    liveApi.apiLiveStart.mockResolvedValue({
      ...base,
      players: [
        ...base.players,
        { ...plv(42, "撞号球友"), account_id: 9, check: "ok", queue_pos: 0 },
      ],
      queue: [42],
    });
    await live.ensureLive(107);
    liveApi.apiLiveDropIn.mockResolvedValue(dropinView());

    const msg = await live.arriveMe(107);

    expect(msg).toBe("已签到 · 进候场区"); // 没被「你已经在场了」挡住
    expect(liveApi.apiLiveDropIn).toHaveBeenCalledWith(107, 1);
    Object.assign(useUserStore().me, demo);
  });

  it("球局不存在 → 返回 null 并提示，不建现场", async () => {
    api.apiGameDetail.mockRejectedValue(new Error("game_not_found"));
    const live = useLiveStore();
    expect(await live.arriveMe(99999)).toBeNull();
    expect(live.hasLive).toBe(false);
  });

  it("已结束的局扫码 → 拦在门外不建现场（§4.2：散场后二维码不能用，本批先拦 ensureLive）", async () => {
    for (const status of ["done", "terminated", "cancelled"] as const) {
      await seedStore(viewOf({ status }));
      const live = useLiveStore();
      expect(await live.arriveMe(107)).toBeNull();
      expect(live.hasLive).toBe(false);
    }
  });
});

describe("真账号接管「我」位后的识别回归", () => {
  it("isMe 运行时读 me.id：换装后旧 id 不再算我、新 id 认得出", () => {
    const user = useUserStore();
    expect(user.isMe(0)).toBe(true);
    takeoverAs(42, "海淀反手王");
    expect(user.isMe(0)).toBe(false);
    expect(user.isMe(42)).toBe(true);
    Object.assign(user.me, demo);
  });

  it("togglePerson 在真 id 下找得到「我」行（快照常量回归；视图行路）", async () => {
    takeoverAs(42, "海淀反手王");
    await seedStore(viewOf());
    const live = useLiveStore();
    // 行 42 挂上我的账号 42：myRowId 按 accountId 认行（查无回落账号 id 已删——
    // 那是 2026-10-11 撞号事故源，两套自增数值撞车会认错人）
    const mine = (v: LiveViewApi): LiveViewApi => ({
      ...v,
      players: v.players.map((p) =>
        p.id === 42 ? { ...p, account_id: 42 } : p,
      ),
    });
    liveApi.apiLiveStart.mockResolvedValue(mine(absentMeView())); // 在册未到的我的行（row 42）
    await live.startLive(
      (await import("@/stores/game")).useGameStore().games[0]!,
    );
    // 自服务守卫：myRowId() 按 accountId=42 命中行 42，非全权也办得了自己的事
    liveApi.apiLiveCheck.mockResolvedValue(mine(dropinView()));
    await live.setCheck(42, "ok");
    expect(liveApi.apiLiveCheck).toHaveBeenCalledWith(107, 42, "ok", 1);
    liveApi.apiLiveTempo.mockResolvedValue(mine(dropinView()));
    await live.togglePerson(42, "fire");
    expect(liveApi.apiLiveTempo).toHaveBeenCalledWith(107, 42, "fire", 2);
    Object.assign(useUserStore().me, demo);
  });
});
