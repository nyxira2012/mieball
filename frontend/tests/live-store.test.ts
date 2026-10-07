import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { U } from "@/api";
import type { GameViewApi } from "@/api/games";
import type {
  Game,
  LiveCourtApi,
  LivePlayerApi,
  LiveViewApi,
} from "@/api/types";

/* 2.3 批5a 写链·全切后端（批5b 确认窗按片化收口；批6 散场清扫链+回看；1.3 批2 空降/
   带访客切真）：vi.mock('@/api/live') 路数（toLiveView 保留真实现——store 对表链吃同一
   映射），写动作用例喂 crafted 响应视图（snake 形状与后端 services/live.py view 输出逐字
   对齐）断言 applyLiveView 落地 + toast；409 stale 携视图对表、断网走 errText 文案。
   本地遗留路（后端无对应端点：subFirst/removeFromRoster/setRuleScore）在视图态上
   直测保留；setCheck/togglePerson/swapPlayers 的视图外行支线已随批6 切真退役删除；
   空降/带访客走
   apiLiveDropIn/apiLiveGuests 专例。散场链（startSweep/sweepCancelAll/endGame/
   noRedeal 透传/回看落地停轮询）各有专例。批5b 增补：settlingCourtId 按片渲染窗、
   确认窗联动纯函数（followWinner/canPickWinner）、验收官补测销号 G1-G3（G4 并入
   openSettle）。每个用例重置模块图 → 全新 mock 数据。 */

const liveApi = vi.hoisted(() => ({
  apiLiveView: vi.fn(),
  apiLiveStart: vi.fn(),
  apiLiveDeal: vi.fn(),
  apiLivePoint: vi.fn(),
  apiLiveUndo: vi.fn(),
  apiLiveClear: vi.fn(),
  apiLiveSettleOpen: vi.fn(),
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
  apiLiveSweepCancelAll: vi.fn(),
  apiLiveEnd: vi.fn(),
}));

/** 批6 P2 深链回填用：ensureLive 200 路顺手 loadDetail——局详情接口替身
    （game store 本体保持真实现，current/findGame 链路照真走） */
const gamesApi = vi.hoisted(() => ({ apiGameDetail: vi.fn() }));

vi.mock("@/api/live", async (importOriginal) => ({
  ...(await importOriginal<object>()),
  ...liveApi,
}));

vi.mock("@/api/games", async (importOriginal) => ({
  ...(await importOriginal<object>()),
  ...gamesApi,
}));

beforeEach(async () => {
  vi.resetModules();
  setActivePinia(createPinia());
  Object.values(liveApi).forEach((m) => m.mockReset());
  gamesApi.apiGameDetail.mockReset();
});

async function load() {
  const liveMod = await import("@/stores/live");
  const uiMod = await import("@/stores/ui");
  return { live: liveMod.useLiveStore(), ui: uiMod.useUiStore() };
}

/** 应用一版视图进 store（多数写用例的出发点）——viewer 上下文按局簿解组织者
    （seed 过 900 的用例即得 isOrganizer；查无 -1 降级、全权看 admins），与 store
    内部 viewerCtx 同一口径，否则权限旗烤不进视图、needFull 全被误拦 */
async function apply(v: LiveViewApi) {
  const h = await load();
  const { toLiveView } = await import("@/api/live");
  const gs = (await import("@/stores/game")).useGameStore();
  const org = gs.findGame(v.game_id)?.organizer.id ?? -1;
  h.live.applyLiveView(toLiveView(v, { myId: U.me.id, organizerId: org }));
  return h;
}

/** 局簿造一格（needOrg/isOrg/ensureLive 404 路读局簿 organizer/status） */
async function seedGame(g: Game) {
  const gs = (await import("@/stores/game")).useGameStore();
  gs.games.push(g);
}

let viewSeq = 800;
function mkLiveView(p: Partial<LiveViewApi> = {}): LiveViewApi {
  viewSeq += 1;
  return {
    game_id: viewSeq,
    started_at: "2026-10-07T19:00:00+08:00",
    ended: false,
    ended_at: null,
    total_seq: 1,
    round: 0,
    admins: [],
    feed: [],
    courts_count: 1,
    rules: {
      scoring: 11,
      doubles: true,
      down: "all",
      pairing: "queue",
      streak_max: 3,
    },
    players: [],
    queue: [],
    courts: [],
    matches: [],
    ...p,
  };
}

/** 名册行速造（arrived 起笔；不在片不在队；dupr 默认 3.0=后端访客/缺档兜底） */
const pl = (
  id: number,
  accountId: number | null,
  o: Partial<LivePlayerApi> = {},
): LivePlayerApi => ({
  id,
  account_id: accountId,
  name: accountId != null ? `u${accountId}` : `访客${id}`,
  guest: accountId == null,
  guarantor_account_id: null,
  dupr: 3.0,
  dropin: false,
  check: "ok",
  arrive_at: null,
  left_at: null,
  court_no: null,
  court_side: null,
  skip: 0,
  fire: false,
  queue_pos: null,
  ...o,
});

/** 片行速造（court_seq=5 与总号 7 可分辨） */
const ct = (
  no: number,
  status: "idle" | "playing" | "pending",
  sa = 0,
  sb = 0,
  origin: "auto" | "manual" | null = null,
): LiveCourtApi => ({
  court_no: no,
  status,
  seq: 1,
  score_a: sa,
  score_b: sb,
  last_winner_side: null,
  court_seq: 5,
  pending_origin: status === "pending" ? (origin ?? "auto") : null,
  preselect: null,
});

/** 中场快照（900 局）：li(101) 与访客(102) 在 1 号片在打 3:2、我(103) 候场队首；
    已落一场战报 + 两条 feed（swap → set_admin 按发生序）；zhao(104) 未到（借属性
    覆写对称的靶行——mock U.zhao 自带 shadow） */
function vMid(seq = 7): LiveViewApi {
  return mkLiveView({
    game_id: 900,
    total_seq: seq,
    round: 2,
    admins: [5],
    courts_count: 2,
    rules: {
      scoring: 11,
      doubles: true,
      down: "loser",
      pairing: "balance",
      streak_max: 2,
    },
    players: [
      {
        id: 101,
        account_id: 5,
        name: "亮马河快攻",
        guest: false,
        dupr: 3.42,
        guarantor_account_id: null,
        dropin: false,
        check: "ok",
        arrive_at: "2026-10-07T19:02:00+08:00",
        left_at: null,
        court_no: 1,
        court_side: "a",
        skip: 0,
        fire: false,
        queue_pos: null,
      },
      {
        id: 102,
        account_id: null,
        name: "亮的球友·1",
        guest: true,
        dupr: 3.0,
        guarantor_account_id: 5,
        dropin: false,
        check: "join",
        arrive_at: null,
        left_at: null,
        court_no: 1,
        court_side: "b",
        skip: 0,
        fire: false,
        queue_pos: null,
      },
      {
        id: 103,
        account_id: 0,
        name: "我",
        guest: false,
        dupr: 3.28,
        guarantor_account_id: null,
        dropin: true,
        check: "ok",
        arrive_at: null,
        left_at: null,
        court_no: null,
        court_side: null,
        skip: 0,
        fire: false,
        queue_pos: 0,
      },
      pl(104, 10, { name: "赵姐的朋友", check: "absent", guest: false }),
    ],
    queue: [103],
    courts: [
      {
        court_no: 1,
        status: "playing",
        seq: 2,
        score_a: 3,
        score_b: 2,
        last_winner_side: "a",
        court_seq: 5,
        pending_origin: null,
        preselect: null,
      },
    ],
    matches: [
      {
        court_no: 1,
        seq: 1,
        winners: [
          { id: 101, name: "亮马河快攻", guest: false },
          { id: 102, name: "亮的球友·1", guest: true },
        ],
        losers: [{ id: 103, name: "我", guest: false }],
        score_a: 11,
        score_b: 9,
        winner_side: "a",
        ended_at: "2026-10-07T19:40:00+08:00",
        elo_rows: [],
      },
    ],
    feed: [
      {
        kind: "swap",
        actor: "我",
        out: "小张",
        in: "老赵",
        at: "2026-10-07T19:30:00+08:00",
      },
      {
        kind: "set_admin",
        actor: "我",
        target: "亮马河快攻",
        at: "2026-10-07T19:35:00+08:00",
      },
    ],
  });
}

/** 在打基态（900 局 · 我全权 admins[0]）：1 号片 4 人对打 3:2、总号 7、片号 5 */
function vPlay(seq = 7, over: Partial<LiveViewApi> = {}): LiveViewApi {
  return mkLiveView({
    game_id: 900,
    total_seq: seq,
    admins: [0],
    courts_count: 1,
    players: [
      pl(101, 0, { name: "我", court_no: 1, court_side: "a" }),
      pl(102, 5, { name: "亮马河快攻", court_no: 1, court_side: "a" }),
      pl(103, 8, { name: "北苑小钢炮", court_no: 1, court_side: "b" }),
      pl(104, null, {
        name: "亮的球友·1",
        guarantor_account_id: 5,
        court_no: 1,
        court_side: "b",
      }),
    ],
    courts: [ct(1, "playing", 3, 2)],
    ...over,
  });
}

/** 视图态句柄（写用例出发点） */
async function inPlay(v: LiveViewApi = vPlay()) {
  return apply(v);
}

const person = (id: number, nickname: string) => ({ id, nickname, chibi: {} });

/** 900 局详情（snake，apiGameDetail 替身回包；与 g900 同一局的线上形状） */
function d900(): GameViewApi {
  return {
    id: 900,
    name: "九百局",
    organizer: person(0, "我"),
    start_at: "2026-10-07T19:00:00+08:00",
    end_at: "2026-10-07T21:00:00+08:00",
    deadline_at: "2026-10-07T17:00:00+08:00",
    venue_name: "望京球馆",
    venue_address: null,
    min_players: 4,
    max_players: 8,
    visibility: "public",
    scoring: 11,
    rotation: "winner",
    score_rule: "",
    manual_lock: false,
    courts: null,
    fee_total: null,
    status: "live",
    unlocked: false,
    joinable: true,
    heads: 4,
    slots_left: 4,
    per_head: null,
    forced: false,
  };
}

/** 900 局簿格（entries 一行保 ensureLive 404 路不必拉详情；status/组织者可覆写——
    isOrg 读 g.my.isOrganizer 视角块，随 orgId 派生） */
function g900(status: Game["status"] = "locked", orgId = 0): Game {
  return {
    id: 900,
    name: "九百局",
    organizer: person(orgId, orgId === 0 ? "我" : "别人"),
    startAt: "2026-10-07T19:00:00+08:00",
    endAt: "2026-10-07T21:00:00+08:00",
    deadlineAt: "2026-10-07T17:00:00+08:00",
    venueName: "望京球馆",
    venueAddress: null,
    minPlayers: 4,
    maxPlayers: 8,
    visibility: "public",
    scoring: 11,
    rotation: "winner",
    scoreRule: "",
    manualLock: false,
    courts: null,
    feeTotal: null,
    status,
    unlocked: false,
    joinable: true,
    heads: 1,
    slotsLeft: 7,
    perHead: null,
    forced: false,
    entries: [
      { account: person(0, "我"), bring: 0, standing: "formal", waitSeq: null },
    ],
    my: {
      isOrganizer: orgId === 0,
      myEntry: { bring: 0, standing: "formal", waitSeq: null },
      invited: false,
    },
  };
}

describe("applyLiveView（批4 阶段2：总账视图 → 本地 LiveState 幂等重建）", () => {
  it("roster 借 mock U 同 accountId 者的展示位（整拷不回写）、访客 shadow+默认位、覆写对称（借来的 shadow 不残留）、片/队列/战报/feed/规则/底账全回填", async () => {
    const { live } = await apply(vMid());
    const L = live.live!;
    expect(L.g.id).toBe(900); // 局簿没有 → 冷扫兜底局仍可重建
    expect(L.g.scoring).toBe(11); // 分制回填 L.g
    expect(L.g.courts).toEqual(["1号", "2号"]); // 片数吃 courts_count 真值
    const [li, guest, me, zhao] = L.roster;
    expect(li.id).toBe(101); // User.id = 名册行 id（写动作靶位，与 queue/片位同键）
    expect(li.elo).toBe(1574); // accountId 5 → 借 U.li 展示位
    expect(li.dupr).toBe(3.42); // dupr 吃视图行真值（> mock U.li 借位 3.3）
    expect(li.chibi).toEqual(U.li.chibi);
    expect(li.check).toBe("ok");
    expect(li.arriveAt).toBe("2026-10-07T19:02:00+08:00");
    expect(guest.shadow).toBe(true); // 访客 shadow 标记
    expect(guest.elo).toBe(1200); // 查无者默认展示位＝后端初始等第（ELO_INIT）
    expect(guest.dupr).toBe(3.0); // 访客 dupr 后端回 GUEST_DUPR
    expect(guest.chibi).toEqual({});
    expect(me.elo).toBe(1518); // accountId 0 → 借 U.me
    expect(me.dupr).toBe(3.28); // 视图真值覆写 mock U.me 的 3.2（整拷上改）
    expect(me.dropin).toBe(true);
    expect(zhao.shadow).toBeUndefined(); // 覆写对称：mock U.zhao 自带 shadow、行非访客 → 清掉（批5a Nit）
    expect(L.queue).toEqual([103]); // 候场队序
    expect(L.courts).toHaveLength(2); // 视图只带 1 片 → 按片数补空片（差人卡）
    expect(L.courts[0]).toMatchObject({
      id: 0, // 视图 1 起片号 → 旧 0 起片序
      name: "1号",
      A: [101],
      B: [102],
      sa: 3,
      sb: 2,
      last: "a",
    });
    expect(L.courts[1]).toMatchObject({ id: 1, name: "2号", A: [], B: [] });
    expect(L.history).toEqual([
      { names: "亮马河快攻 & 亮的球友·1", sa: 11, sb: 9 }, // 胜者名拼接（旧形状适配）
    ]);
    expect(L.feed).toEqual([
      "组织者封 亮马河快攻 为管理员",
      "我 把 小张 换下 · 老赵 上", // view 发生序 → 旧 feed 新到旧
    ]);
    expect(L.rules).toEqual({
      singles: false,
      down: "loser",
      downChosen: true, // 总账定值：冻结本地推荐跟随
      pairing: "balance",
      champCap: 2,
    });
    expect(L.admins).toEqual([5]);
    expect(L.round).toBe(2);
    expect(L.ledger.find((r) => r.id === 102)!.guarantor).toBe(
      "亮马河快攻", // guarantorAccountId → 册内行名解析（底账「谁带的」）
    );
    expect(live.settling).toEqual({}); // 无 pending 片：空 Record（批5a 按片多值）
    expect(live.liveView?.totalSeq).toBe(7); // 最近视图持有
    expect(live.recap).toBeNull(); // 未散场不持有回看
    expect(U.li.elo).toBe(1574); // 整拷：mock U 不被重建污染
    expect(U.me.dupr).toBe(3.2); // dupr 回填同样只改拷贝
    // 幂等：同视图重放不漂移（空片不重复补、队列不重排）
    const { toLiveView } = await import("@/api/live");
    live.applyLiveView(toLiveView(vMid()));
    expect(L.courts).toHaveLength(2);
    expect(L.queue).toEqual([103]);
  });
  it("settling 按片多值（§4.3 三片同待确认是正常情况）：各片进 Record、渲染窗取片号最小；窗位纯随视图 pending 起落（store 无关窗出口——遮罩禁关，批5b 验收官销号）", async () => {
    const { toLiveView } = await import("@/api/live");
    const { live } = await load();
    const v3 = (st: LiveCourtApi[], seq = 20): LiveViewApi =>
      mkLiveView({ game_id: 900, courts_count: 3, total_seq: seq, courts: st });
    live.applyLiveView(
      toLiveView(
        v3([
          ct(1, "pending", 9, 9),
          ct(2, "pending", 11, 5, "manual"),
          ct(3, "pending", 21, 15),
        ]),
      ),
    );
    expect(live.settling).toEqual({
      0: { origin: "auto" },
      1: { origin: "manual" },
      2: { origin: "auto" },
    });
    expect(live.settlingCourtId).toBe(0); // 窗一次一扇：片号最小者顶上
    expect(live.isPending(0)).toBe(true);
    // 遮罩禁关（§4.3-2 出口全在窗内）：store 不导出任何前端关窗动作可调
    expect(
      (live as unknown as Record<string, unknown>).closeSettle,
    ).toBeUndefined();
    live.applyLiveView(
      toLiveView(
        v3([ct(1, "pending", 9, 9), ct(2, "pending", 11, 5, "manual")]),
      ),
    ); // 片 3 走合同出口（确认/清零/取消/auto 撤到分线同路）：视图 pending 消失
    expect(live.settling).toEqual({
      0: { origin: "auto" },
      1: { origin: "manual" },
    }); // 剩余片窗位不受牵连
    live.applyLiveView(toLiveView(v3([ct(1, "playing", 9, 9)]))); // 片 1 退出 pending
    expect(live.isPending(0)).toBe(false); // 冻结解除
    expect(live.settlingCourtId).toBeNull(); // 窗随视图关
    live.applyLiveView(toLiveView(v3([ct(1, "pending", 12, 10)]))); // 再到分
    expect(live.settlingCourtId).toBe(0); // 窗重开（无 hide 位残留可挡）
  });
  it("散场视图：endedAt 落封存位、recap 持有回看视图（轮询一并停）；进进行中视图 recap 清——上一局的回看不泄漏", async () => {
    const { toLiveView } = await import("@/api/live");
    const { live } = await apply(
      mkLiveView({
        game_id: 900,
        ended: true,
        ended_at: "2026-10-07T21:30:00+08:00",
      }),
    );
    expect(live.live!.endedAt).toBe("2026-10-07T21:30:00+08:00");
    expect(live.recap?.ended).toBe(true);
    live.applyLiveView(toLiveView(vMid(8), null)); // 同局又回进行中（回放/换机重进的对账面）
    expect(live.recap).toBeNull();
  });
});

describe("pollLiveView（拉读对表：totalSeq 变才重建 · 返回是否更新）", () => {
  it("首拉重建返 true；同号不重建返 false（roster 引用不动）；变号重建返 true；拉读失败静默 false 不动现场", async () => {
    const { live } = await load();
    liveApi.apiLiveView.mockResolvedValue(vMid(7));
    await expect(live.pollLiveView(900)).resolves.toBe(true);
    expect(live.live!.g.id).toBe(900);
    const before = live.live!.roster;
    liveApi.apiLiveView.mockResolvedValue(vMid(7)); // 同号
    await expect(live.pollLiveView(900)).resolves.toBe(false);
    expect(live.live!.roster).toBe(before); // 没换画面
    liveApi.apiLiveView.mockResolvedValue(vMid(8));
    await expect(live.pollLiveView(900)).resolves.toBe(true);
    expect(live.live!.roster).not.toBe(before);
    expect(live.liveView!.totalSeq).toBe(8);
    // ApiError 与 store 同一模块图取（resetModules 后静态导入是另一个类实例，instanceof 会假阴性）
    const { ApiError } = await import("@/api/http");
    liveApi.apiLiveView.mockRejectedValue(
      new ApiError("network", "网络不给力，请稍后再试"),
    );
    await expect(live.pollLiveView(900)).resolves.toBe(false);
    expect(live.liveView!.totalSeq).toBe(8); // 失败不动现场（下一拍再试）
  });
  it("viewer 两旗随视图派生：admins 含我 → isFullPower；组织者未知（局簿没有）→ isOrganizer 降级 false", async () => {
    const { live } = await load();
    liveApi.apiLiveView.mockResolvedValue(
      mkLiveView({ game_id: 900, admins: [U.me.id, 5] }),
    );
    await live.pollLiveView(900);
    expect(live.liveView!.isFullPower).toBe(true); // 管理员表含我
    expect(live.liveView!.isOrganizer).toBe(false); // 组织者 -1 降级
  });
});

describe("applyStaleView（409 两码携视图对表）", () => {
  it("live_stale_total / live_stale_court 带 view → 映射重建返 true；他码、不带 view、非 ApiError → false 不动现场", async () => {
    const { ApiError } = await import("@/api/http");
    const { live } = await apply(vMid(7));
    expect(
      live.applyStaleView(
        new ApiError("live_stale_total", "现场已更新", 409, vMid(9)),
      ),
    ).toBe(true);
    expect(live.liveView!.totalSeq).toBe(9);
    expect(
      live.applyStaleView(
        new ApiError("live_stale_court", "现场已更新", 409, vMid(10)),
      ),
    ).toBe(true);
    expect(live.liveView!.totalSeq).toBe(10);
    expect(
      live.applyStaleView(
        new ApiError("live_ended", "球局已结束", 409, vMid(11)),
      ),
    ).toBe(false); // 他码不对表
    expect(
      live.applyStaleView(new ApiError("live_stale_total", "x", 409)),
    ).toBe(false); // 不带视图
    expect(live.applyStaleView(new Error("boom"))).toBe(false); // 非 ApiError
    expect(live.liveView!.totalSeq).toBe(10); // 现场原样
  });
});

describe("startPolling / stopPolling（3s 轮询器）", () => {
  it("3s 一拍拉读对表、幂等启动不双开、stop 清计时器", async () => {
    vi.useFakeTimers();
    try {
      const { live } = await load();
      liveApi.apiLiveView.mockResolvedValue(vMid(7));
      live.startPolling(900);
      live.startPolling(900); // 幂等：同局再调不开第二只计时器
      expect(liveApi.apiLiveView).not.toHaveBeenCalled(); // 到点才拉（首拍归页面直调）
      await vi.advanceTimersByTimeAsync(3000);
      expect(liveApi.apiLiveView).toHaveBeenCalledTimes(1);
      await vi.advanceTimersByTimeAsync(6000);
      expect(liveApi.apiLiveView).toHaveBeenCalledTimes(3); // 3s 一拍
      expect(live.liveView!.totalSeq).toBe(7); // 拉到的视图已对表
      live.stopPolling();
      await vi.advanceTimersByTimeAsync(9000);
      expect(liveApi.apiLiveView).toHaveBeenCalledTimes(3); // 停后不再拉
    } finally {
      vi.useRealTimers();
    }
  });
});

/* ─────────── 批5a：写链（组载荷 → api → 响应视图落地；stale/断网两防线） ─────────── */

describe("point / undoPoint / clearScore（§4.1/4.2 记分链片级写）", () => {
  it("point：载荷带两级 base 号（出发时看到的号）、响应视图落地比分跳动，无成功 toast", async () => {
    const { live, ui } = await inPlay();
    liveApi.apiLivePoint.mockResolvedValue(
      vPlay(8, { courts: [ct(1, "playing", 4, 2)] }),
    );
    await live.point(0, "a");
    expect(liveApi.apiLivePoint).toHaveBeenCalledWith(900, 1, "a", 7, 5);
    expect(live.live!.courts[0].sa).toBe(4); // 写后回画面（免二次拉读）
    expect(live.liveView!.totalSeq).toBe(8);
    expect(ui.toastMsg).toBeFalsy(); // 比分即反馈（沿旧：point 无 toast）
  });
  it("point 409 stale_court 携视图：对表落地 + toast「现场已更新」（§4.8 同片并发以先到为准）", async () => {
    const { ApiError } = await import("@/api/http");
    const { live, ui } = await inPlay();
    liveApi.apiLivePoint.mockRejectedValue(
      new ApiError(
        "live_stale_court",
        "这片现场已更新，请看最新画面再操作",
        409,
        vPlay(9, { courts: [ct(1, "playing", 10, 2)] }),
      ),
    );
    await live.point(0, "a");
    expect(live.live!.courts[0].sa).toBe(10); // 错误体自带的最新视图已对表
    expect(live.liveView!.totalSeq).toBe(9);
    expect(ui.toastMsg).toBe("现场已更新");
  });
  it("point 断网：toast「网络不给力，请稍后再试」可重试、现场不动（重试幂等由两级号保证）", async () => {
    const { live, ui } = await inPlay();
    liveApi.apiLivePoint.mockRejectedValue(new TypeError("boom"));
    await live.point(0, "a");
    expect(ui.toastMsg).toBe("网络不给力，请稍后再试");
    expect(live.live!.courts[0].sa).toBe(3); // 未落地
    expect(live.liveView!.totalSeq).toBe(7);
  });
  it("point 待确认片冻结（§4.3）：不发请求（后端 court_frozen 兜底）", async () => {
    const { live } = await inPlay(
      vPlay(7, { courts: [ct(1, "pending", 11, 9)] }),
    );
    await live.point(0, "a");
    expect(liveApi.apiLivePoint).not.toHaveBeenCalled();
  });
  it("undoPoint：撤该片最后得分方那 1 分——载荷 + 响应视图落地", async () => {
    const { live } = await inPlay();
    liveApi.apiLiveUndo.mockResolvedValue(
      vPlay(8, { courts: [ct(1, "playing", 2, 2)] }),
    );
    await live.undoPoint(0);
    expect(liveApi.apiLiveUndo).toHaveBeenCalledWith(900, 1, 7, 5);
    expect(live.live!.courts[0].sa).toBe(2);
  });
  it("clearScore 收权（§4.2）：球友被拒「请找组织者或管理员」不发；全权过 → toast「记分已清零 · 重开一盘」", async () => {
    const denied = await inPlay(vPlay(7, { admins: [] }));
    await denied.live.clearScore(0);
    expect(denied.ui.toastMsg).toBe("请找组织者或管理员");
    expect(liveApi.apiLiveClear).not.toHaveBeenCalled();
    const ok = await inPlay();
    liveApi.apiLiveClear.mockResolvedValue(
      vPlay(8, { courts: [ct(1, "playing", 0, 0)] }),
    );
    await ok.live.clearScore(0);
    expect(liveApi.apiLiveClear).toHaveBeenCalledWith(900, 1, 7, 5);
    expect(ok.live.live!.courts[0].sa).toBe(0);
    expect(ok.ui.toastMsg).toBe("记分已清零 · 重开一盘");
  });
});

describe("待确认窗（§4.3-4.6：到分 auto / 提前结算 manual / 窗内撤分两路 / 确认一本账）", () => {
  it("openSettle 提前结算（§4.4）：上报后片转 pending(origin='manual')、窗即反馈无 toast；空片静默不开（G4）", async () => {
    const { live, ui } = await inPlay();
    liveApi.apiLiveSettleOpen.mockResolvedValue(
      vPlay(8, { courts: [ct(1, "pending", 3, 2, "manual")] }),
    );
    await live.openSettle(0);
    expect(liveApi.apiLiveSettleOpen).toHaveBeenCalledWith(900, 1, 7, 5);
    expect(live.settlingCourtId).toBe(0);
    expect(live.settling[0]).toEqual({ origin: "manual" });
    expect(ui.toastMsg).toBeFalsy(); // 窗开即反馈
    const empty = await apply(mkLiveView({ game_id: 900, admins: [0] })); // 无片行=空片
    await empty.live.openSettle(0);
    expect(liveApi.apiLiveSettleOpen).toHaveBeenCalledTimes(1); // 空片不发、不 toast
    expect(empty.ui.toastMsg).toBeFalsy();
  });
  it("到分自动进待确认（§4.3）：判定在后端落账时当即办——前端吃响应视图 origin='auto' 开窗", async () => {
    const { live } = await inPlay();
    liveApi.apiLivePoint.mockResolvedValue(
      vPlay(8, { courts: [ct(1, "pending", 11, 9)] }),
    );
    await live.point(0, "a");
    expect(live.settlingCourtId).toBe(0); // 视图 origin='auto' 驱动开窗
    expect(live.settling[0]).toEqual({ origin: "auto" });
  });
  it("窗内撤分两路（§4.5）：auto 窗撤到分线下自动关回在打；manual 窗撤一分只改比分不关窗", async () => {
    const { live } = await inPlay(
      vPlay(7, { courts: [ct(1, "pending", 11, 9)] }),
    );
    liveApi.apiLiveUndo.mockResolvedValue(
      vPlay(8, { courts: [ct(1, "playing", 10, 9)] }),
    );
    await live.undoPoint(0); // 窗内撤分（后端判分线关窗）
    expect(live.settlingCourtId).toBeNull(); // 窗自动关、回在打
    expect(live.live!.courts[0].sa).toBe(10);
    liveApi.apiLiveUndo.mockResolvedValue(
      vPlay(9, { courts: [ct(1, "pending", 4, 3, "manual")] }),
    );
    await live.undoPoint(0); // 人工开的窗：撤一分只改比分
    expect(live.settlingCourtId).toBe(0); // 窗不关
    expect(live.settling[0]).toEqual({ origin: "manual" });
    expect(live.live!.courts[0].sa).toBe(4);
  });
  it("confirmSettle 确认一本账（§4.6）：幂等闸无窗不发；有窗 → 载荷 + 战报/elo_rows 回填（§4.11 落账以结算回来的数为准）+ toast", async () => {
    const noWindow = await inPlay(); // 无窗（在打态）
    await noWindow.live.confirmSettle(0, true, 11, 9); // 幂等闸
    expect(liveApi.apiLiveSettleConfirm).not.toHaveBeenCalled();
    const started = await inPlay(
      vPlay(7, { courts: [ct(1, "pending", 11, 9)] }),
    );
    liveApi.apiLiveSettleConfirm.mockResolvedValue(
      vPlay(8, {
        round: 1,
        courts: [ct(1, "playing", 0, 0)],
        matches: [
          {
            court_no: 1,
            seq: 1,
            winners: [
              { id: 101, name: "我", guest: false },
              { id: 102, name: "亮马河快攻", guest: false },
            ],
            losers: [
              { id: 103, name: "北苑小钢炮", guest: false },
              { id: 104, name: "亮的球友·1", guest: true },
            ],
            score_a: 11,
            score_b: 9,
            winner_side: "a",
            ended_at: "2026-10-07T20:00:00+08:00",
            elo_rows: [
              {
                account_id: 0,
                name: "我",
                guest: false,
                rating_before: 1200,
                rating_after: 1222,
                delta: 22,
              },
              {
                account_id: null,
                name: "亮的球友·1",
                guest: true,
                rating_before: 1200,
                rating_after: 1210,
                delta: 10,
              },
            ],
          },
        ],
      }),
    );
    await started.live.confirmSettle(0, true, 11, 9);
    expect(liveApi.apiLiveSettleConfirm).toHaveBeenCalledWith(900, {
      courtNo: 1,
      winnerSide: "a",
      scoreA: 11,
      scoreB: 9,
      noRedeal: false, // 默认平时路：排下一场
      baseTotalSeq: 7,
      baseCourtSeq: 5,
    });
    expect(started.live.settlingCourtId).toBeNull(); // 窗随落账关
    expect(started.live.live!.history[0]).toEqual({
      names: "我 & 亮马河快攻",
      sa: 11,
      sb: 9,
    });
    const rows = started.live.liveView!.matches[0]!.eloRows; // 确认响应 elo_rows 随视图持有（预览修正消费面）
    expect(rows).toHaveLength(2);
    expect(rows[1]).toMatchObject({ guest: true, delta: 10 }); // 访客行有展示值不落账
    expect(started.live.live!.round).toBe(1); // 排下一场由确认响应视图驱动
    expect(started.ui.toastMsg).toBe("积分落账 · 下一场已排好");
  });
});

describe("cancelMatch（§4.7 取消对局：回流队首归总账、片腾出来本地重发）", () => {
  it("取消：载荷带 no_redeal=false + 两级号、toast 带出发时场上人数；回流够人 → maybeDeal 重发该片", async () => {
    const { live, ui } = await inPlay();
    const back = vPlay(8, {
      courts: [],
      players: vPlay().players.map((p) => ({
        ...p,
        court_no: null,
        court_side: null,
        queue_pos: p.id - 101,
      })),
      queue: [101, 102, 103, 104],
    });
    liveApi.apiLiveCancel.mockResolvedValue(back);
    liveApi.apiLiveDeal.mockResolvedValue(
      vPlay(9, { courts: [ct(1, "playing", 0, 0)] }),
    );
    await live.cancelMatch(0);
    expect(liveApi.apiLiveCancel).toHaveBeenCalledWith(900, 1, 7, 5);
    expect(ui.toastMsg).toBe("对局作废 · 这场不计分 · 场上 4 人回到队首");
    expect(liveApi.apiLiveDeal).toHaveBeenCalledWith(
      900,
      [{ courtNo: 1, a: [101, 102], b: [103, 104] }], // 发牌算法在前端：队首四人对半分边
      8,
    );
    expect(live.live!.courts[0].A).toEqual([101, 102]); // 重发落定
  });
  it("取消收权：球友被拒不发", async () => {
    const { live, ui } = await inPlay(vPlay(7, { admins: [] }));
    await live.cancelMatch(0);
    expect(ui.toastMsg).toBe("请找组织者或管理员");
    expect(liveApi.apiLiveCancel).not.toHaveBeenCalled();
  });
});

describe("setCheck（§4.2/4.3 报到四态：归一与队位归总账，发牌归前端）", () => {
  /** 报到基态：我(101)未到、1 号片空闲 */
  function vCheck(over: Partial<LiveViewApi> = {}): LiveViewApi {
    return mkLiveView({
      game_id: 900,
      total_seq: 7,
      admins: [0],
      players: [pl(101, 0, { name: "我", check: "absent" })],
      ...over,
    });
  }
  it("到场：载荷带总号；迟到归一与队尾由响应视图落定，toast 按落定态拼", async () => {
    const { live, ui } = await apply(vCheck());
    liveApi.apiLiveCheck.mockResolvedValue(
      vCheck({
        total_seq: 8,
        players: [pl(101, 0, { name: "我", check: "late", queue_pos: 0 })],
        queue: [101],
      }),
    );
    await live.setCheck(101, "ok");
    expect(liveApi.apiLiveCheck).toHaveBeenCalledWith(900, 101, "ok", 7);
    expect(live.live!.roster[0]!.check).toBe("late"); // 后端归一（过开球时刻）
    expect(live.live!.queue).toEqual([101]); // 排队尾
    expect(ui.toastMsg).toBe("我 迟到 · 自动排到队尾等一轮");
    expect(liveApi.apiLiveDeal).not.toHaveBeenCalled(); // 1 人不够一片：不发牌
  });
  it("到场驱动发牌（§4.1 够一片的人数就上片）：第 4 人报到 → 本地算完 apiLiveDeal 上报", async () => {
    const { live, ui } = await apply(
      vCheck({
        players: [
          pl(101, 0, { name: "我", check: "absent" }),
          pl(102, 5, { name: "亮马河快攻", queue_pos: 0 }),
          pl(103, 8, { name: "北苑小钢炮", queue_pos: 1 }),
          pl(104, null, { name: "亮的球友·1", queue_pos: 2 }),
        ],
        queue: [102, 103, 104],
      }),
    );
    liveApi.apiLiveCheck.mockResolvedValue(
      vCheck({
        total_seq: 8,
        players: [
          pl(101, 0, { name: "我", queue_pos: 3 }),
          pl(102, 5, { name: "亮马河快攻", queue_pos: 0 }),
          pl(103, 8, { name: "北苑小钢炮", queue_pos: 1 }),
          pl(104, null, { name: "亮的球友·1", queue_pos: 2 }),
        ],
        queue: [102, 103, 104, 101],
      }),
    );
    liveApi.apiLiveDeal.mockResolvedValue(vPlay(9));
    await live.setCheck(101, "ok");
    expect(ui.toastMsg).toBe("我 已到场 · 排进候场队");
    expect(liveApi.apiLiveDeal).toHaveBeenCalledWith(
      900,
      [{ courtNo: 1, a: [102, 103], b: [104, 101] }],
      8,
    );
  });
  it("早退（§4.5）：toast 早退句；视图落定清队列位/片位", async () => {
    const { live, ui } = await inPlay();
    liveApi.apiLiveCheck.mockResolvedValue(
      vPlay(8, {
        players: vPlay().players.map((p, i) => ({
          ...p,
          court_no: i === 2 ? null : p.court_no, // 北苑小钢炮(103) 早退出片
          court_side: i === 2 ? null : p.court_side,
          left_at: i === 2 ? "2026-10-07T20:10:00+08:00" : null,
          check: i === 2 ? ("left" as const) : p.check,
        })),
        courts: [ct(1, "playing", 3, 2)],
      }),
    );
    await live.setCheck(103, "left");
    expect(liveApi.apiLiveCheck).toHaveBeenCalledWith(900, 103, "left", 7);
    expect(ui.toastMsg).toBe("北苑小钢炮 早退 · 已记离场时刻");
    expect(live.live!.courts[0].B).toEqual([104]); // 片上同清
    expect(live.live!.queue).toEqual([]); // 不进候场
  });
  it("代办 gate（§4.3）：球友给他人 setCheck 拒「请找组织者或管理员」；给自己随时可", async () => {
    const { live, ui } = await inPlay(vPlay(7, { admins: [] }));
    await live.setCheck(102, "ok");
    expect(ui.toastMsg).toBe("请找组织者或管理员");
    expect(liveApi.apiLiveCheck).not.toHaveBeenCalled();
    liveApi.apiLiveCheck.mockResolvedValue(vPlay(8));
    await live.setCheck(101, "ok"); // 自己（row 101 = 我的行）
    expect(liveApi.apiLiveCheck).toHaveBeenCalledWith(900, 101, "ok", 7);
  });
});

describe("togglePerson（§4.10 歇连：叠帐归总账，toast 按落定态拼）", () => {
  async function withQueue() {
    return apply(
      vPlay(7, {
        players: [
          ...vPlay().players,
          pl(105, 6, { name: "老赵", queue_pos: 0 }),
        ],
        queue: [105],
      }),
    );
  }
  it("skip 叠加 / unskip 清零 / fire 连战与取消：apiLiveTempo 载荷 + toast 三态", async () => {
    const { live, ui } = await withQueue();
    const view = (skip: number, fire: boolean, seq: number): LiveViewApi =>
      vPlay(seq, {
        players: [
          ...vPlay().players,
          pl(105, 6, { name: "老赵", queue_pos: 0, skip, fire }),
        ],
        queue: [105],
      });
    liveApi.apiLiveTempo.mockResolvedValueOnce(view(1, false, 8));
    await live.togglePerson(105, "skip");
    expect(liveApi.apiLiveTempo).toHaveBeenCalledWith(900, 105, "skip", 7);
    expect(ui.toastMsg).toBe("已设休息 · 轮到你时自动跳一轮");
    liveApi.apiLiveTempo.mockResolvedValueOnce(view(2, false, 9));
    await live.togglePerson(105, "skip");
    expect(ui.toastMsg).toBe("已再跳一轮 · 共跳 2 轮");
    liveApi.apiLiveTempo.mockResolvedValueOnce(view(2, false, 10));
    await live.togglePerson(105, "unskip");
    expect(ui.toastMsg).toBe("取消休息 · 下轮照常");
    liveApi.apiLiveTempo.mockResolvedValueOnce(view(0, true, 11));
    await live.togglePerson(105, "fire");
    expect(ui.toastMsg).toBe("连战 · 排到队首");
    liveApi.apiLiveTempo.mockResolvedValueOnce(view(0, false, 12));
    await live.togglePerson(105, "fire");
    expect(ui.toastMsg).toBe("取消连战");
  });
  it("代办 gate（§4.10 禁止球友代设）：给他人拒；给自己随时可", async () => {
    const denied = await apply(
      mkLiveView({
        game_id: 900,
        total_seq: 7,
        admins: [],
        courts: [ct(1, "playing")],
        players: [
          pl(101, 0, { name: "我", check: "absent" }),
          pl(102, 5, { name: "亮马河快攻", court_no: 1, court_side: "a" }), // 片上有人=无空片
        ],
        queue: [],
      }),
    );
    await denied.live.togglePerson(102, "skip");
    expect(denied.ui.toastMsg).toBe("请找组织者或管理员");
    expect(liveApi.apiLiveTempo).not.toHaveBeenCalled();
    liveApi.apiLiveTempo.mockResolvedValue(
      mkLiveView({
        game_id: 900,
        total_seq: 8,
        admins: [],
        courts: [ct(1, "playing")],
        players: [
          pl(101, 0, { name: "我", skip: 1, queue_pos: 0 }),
          pl(102, 5, { name: "亮马河快攻", court_no: 1, court_side: "a" }),
        ],
        queue: [101],
      }),
    );
    await denied.live.togglePerson(101, "skip"); // 自己（row 101 = 我的行）
    expect(liveApi.apiLiveTempo).toHaveBeenCalledWith(900, 101, "skip", 7);
    expect(denied.live.myRound).toBe(1); // 键位修正：myRound 按我的行 id 算（无空片只看队列位）
  });
});

describe("swapPlayers（§4.9 球友开放：无 guard、全场写只带总号）", () => {
  it("视图行：apiLiveSwap 载荷 + 响应视图落地 + toast「已换人 · 对阵重排」", async () => {
    const { live, ui } = await apply(
      vPlay(7, {
        players: [
          ...vPlay().players,
          pl(105, 6, { name: "老赵", queue_pos: 0 }),
        ],
        queue: [105],
      }),
    );
    liveApi.apiLiveSwap.mockResolvedValue(
      vPlay(8, {
        players: [
          pl(101, 0, { name: "我", court_no: 1, court_side: "a" }),
          pl(102, 5, { name: "亮马河快攻", court_no: 1, court_side: "a" }),
          pl(103, 8, { name: "北苑小钢炮", queue_pos: 0 }),
          pl(104, null, {
            name: "亮的球友·1",
            guarantor_account_id: 5,
            court_no: 1,
            court_side: "b",
          }),
          pl(105, 6, { name: "老赵", court_no: 1, court_side: "b" }),
        ],
        queue: [103],
      }),
    );
    await live.swapPlayers(103, 105); // 场上的北苑小钢炮 ↔ 候场的老赵
    expect(liveApi.apiLiveSwap).toHaveBeenCalledWith(900, 103, 105, 7);
    expect(live.live!.courts[0].B).toEqual([104, 105]); // 原位顶坑
    expect(live.live!.queue).toEqual([103]); // 换下排队尾
    expect(ui.toastMsg).toBe("已换人 · 对阵重排");
  });
});

describe("setRules / setCourtsInput / autoDeal（§4.7 规则与场地 · 发牌在前端）", () => {
  it("setRules：四件套映射上报（singles→doubles 取反）+ toast「规则已更新 · 下一场起按新规」", async () => {
    const { live, ui } = await inPlay();
    liveApi.apiLiveRules.mockResolvedValue(
      vPlay(8, { rules: { ...vPlay().rules, doubles: false } }),
    );
    await live.setRules({ singles: true });
    expect(liveApi.apiLiveRules).toHaveBeenCalledWith(
      900,
      { doubles: false },
      7,
    );
    expect(live.live!.rules.singles).toBe(true); // 视图落定
    expect(ui.toastMsg).toBe("规则已更新 · 下一场起按新规");
    expect(liveApi.apiLiveDeal).not.toHaveBeenCalled(); // 候场空无可补
  });
  it("setCourtsInput：『3、4 / 3,4 / 3号、4号』归一 → courtsCount 上报、片名本地挂", async () => {
    const { live, ui } = await inPlay();
    liveApi.apiLiveRules.mockResolvedValue(
      vPlay(8, { courts_count: 2, courts: [ct(1, "playing", 3, 2)] }),
    );
    for (const [i, txt] of ["3、4", "3,4", "3号、4号"].entries()) {
      expect(await live.setCourtsInput(txt)).toBe(true);
      // base 号吃最近视图：首拍 7，响应视图(total 8)落地后带 8
      expect(liveApi.apiLiveRules).toHaveBeenNthCalledWith(
        i + 1,
        900,
        { courtsCount: 2 },
        i === 0 ? 7 : 8,
      );
    }
    expect(live.live!.g.courts).toEqual(["3号", "4号"]); // 场地名本地挂
    expect(live.live!.courts[1]!.name).toBe("4号"); // 补出的空片重挂名
    expect(ui.toastMsg).toBe("场地已更新：3号、4号");
  });
  it("setCourtsInput 校验：空/垃圾拒「至少要有 1 片场地」；在打片不能收拒——均不发", async () => {
    const { live, ui } = await inPlay();
    expect(await live.setCourtsInput("")).toBe(false);
    expect(await live.setCourtsInput("abc")).toBe(false);
    expect(ui.toastMsg).toBe("至少要有 1 片场地");
    const two = await apply(
      vPlay(7, {
        courts_count: 2,
        players: [
          ...vPlay().players,
          pl(105, 6, { name: "老赵", court_no: 2, court_side: "a" }),
          pl(106, 7, { name: "老钱", court_no: 2, court_side: "b" }),
        ],
        courts: [ct(1, "playing", 3, 2), ct(2, "playing", 1, 0)],
      }),
    );
    expect(await two.live.setCourtsInput("3号")).toBe(false);
    expect(two.ui.toastMsg).toBe("在打 + 待开的场地不能收");
    expect(liveApi.apiLiveRules).not.toHaveBeenCalled();
  });
  it("autoDeal：补所有空片（多片同时要人按片号先后）+ toast「牌已发 · 按当前规则排好」", async () => {
    const { live, ui } = await apply(
      vPlay(7, {
        courts_count: 2,
        players: [
          ...vPlay().players,
          pl(105, 6, { name: "老赵", queue_pos: 0 }),
          pl(106, 7, { name: "老钱", queue_pos: 1 }),
          pl(107, 9, { name: "老孙", queue_pos: 2 }),
          pl(108, 11, { name: "老李", queue_pos: 3 }),
        ],
        queue: [105, 106, 107, 108],
      }),
    );
    liveApi.apiLiveDeal.mockResolvedValue(
      vPlay(8, {
        courts_count: 2,
        // 响应视图镜像总账：发上片的人 court_no/side 落位、队列清空
        players: [
          ...vPlay().players,
          pl(105, 6, { name: "老赵", court_no: 2, court_side: "a" }),
          pl(106, 7, { name: "老钱", court_no: 2, court_side: "a" }),
          pl(107, 9, { name: "老孙", court_no: 2, court_side: "b" }),
          pl(108, 11, { name: "老李", court_no: 2, court_side: "b" }),
        ],
        queue: [],
        courts: [ct(1, "playing", 3, 2), ct(2, "playing", 0, 0)],
      }),
    );
    await live.autoDeal();
    expect(liveApi.apiLiveDeal).toHaveBeenCalledWith(
      900,
      [{ courtNo: 2, a: [105, 106], b: [107, 108] }],
      7,
    );
    expect(live.live!.courts[1]!.A).toEqual([105, 106]); // 落定
    expect(ui.toastMsg).toBe("牌已发 · 按当前规则排好");
  });
});

describe("setAdmin / unsetAdmin（§4.6 仅组织者：留痕句由视图 feed 回来）", () => {
  it("封：apiLiveSetAdmin 载荷（靶行 id）+ toast + feed 句；已封再封静默", async () => {
    await seedGame(g900()); // 组织者是我（needOrg 读局簿）
    const { live, ui } = await inPlay();
    liveApi.apiLiveSetAdmin.mockResolvedValue(
      vPlay(8, {
        admins: [8],
        feed: [
          {
            kind: "set_admin",
            actor: "我",
            target: "北苑小钢炮",
            at: "2026-10-07T20:00:00+08:00",
          },
        ],
      }),
    );
    await live.setAdmin(103); // 北苑小钢炮（row id）
    expect(liveApi.apiLiveSetAdmin).toHaveBeenCalledWith(900, 103, 7);
    expect(ui.toastMsg).toBe("组织者封 北苑小钢炮 为管理员");
    expect(live.live!.feed[0]).toBe("组织者封 北苑小钢炮 为管理员"); // 结构化事件 → 中文句
    expect(live.live!.admins).toEqual([8]);
    const again = await inPlay(vPlay(7, { admins: [8] }));
    await again.live.setAdmin(103); // 已封再封 → 静默幂等
    expect(liveApi.apiLiveSetAdmin).toHaveBeenCalledTimes(1);
  });
  it("非组织者拒（管理员也不能封）：toast「只有组织者能做」不发", async () => {
    await seedGame(g900("locked", 1)); // 组织者是别人
    const { live, ui } = await inPlay(vPlay(7, { admins: [0] })); // 我只是管理员
    await live.setAdmin(103);
    expect(ui.toastMsg).toBe("只有组织者能做");
    expect(liveApi.apiLiveSetAdmin).not.toHaveBeenCalled();
  });
  it("撤：apiLiveUnsetAdmin 载荷 + toast 收回句", async () => {
    await seedGame(g900());
    const { live, ui } = await inPlay(vPlay(7, { admins: [8] }));
    liveApi.apiLiveUnsetAdmin.mockResolvedValue(
      vPlay(8, {
        admins: [],
        feed: [
          {
            kind: "unset_admin",
            actor: "我",
            target: "北苑小钢炮",
            at: "2026-10-07T20:00:00+08:00",
          },
        ],
      }),
    );
    await live.unsetAdmin(103);
    expect(liveApi.apiLiveUnsetAdmin).toHaveBeenCalledWith(900, 103, 7);
    expect(ui.toastMsg).toBe("组织者收回了 北苑小钢炮 的管理员身份");
    expect(live.live!.admins).toEqual([]);
  });
});

describe("startLive（批5a 后端开账路：apiLiveStart 幂等 → 视图落地 → 开场发牌）", () => {
  it("开账：视图落地 + toast「球局开始 · 现场已点亮」返 msg；开场已够人的片本地算完上报（重新开账幂等回视图的场面）", async () => {
    await seedGame(g900());
    const { live, ui } = await load();
    liveApi.apiLiveStart.mockResolvedValue(
      vPlay(7, {
        players: vPlay().players.map((p, i) => ({
          ...p,
          court_no: null,
          court_side: null,
          queue_pos: i,
        })),
        courts: [],
        queue: [101, 102, 103, 104],
      }),
    );
    liveApi.apiLiveDeal.mockResolvedValue(vPlay(8));
    const msg = await live.startLive(g900());
    expect(msg).toBe("球局开始 · 现场已点亮");
    expect(ui.toastMsg).toBe("球局开始 · 现场已点亮");
    expect(live.live!.g.id).toBe(900); // 名册展开归后端：视图直建
    expect(liveApi.apiLiveDeal).toHaveBeenCalledWith(
      900,
      [{ courtNo: 1, a: [101, 102], b: [103, 104] }],
      7,
    );
    live.stopPolling();
  });
  it("开账失败（非组织者被后端拒/断网）：返 null + toast，不建现场", async () => {
    await seedGame(g900());
    const { live, ui } = await load();
    liveApi.apiLiveStart.mockRejectedValue(new TypeError("boom"));
    expect(await live.startLive(g900())).toBeNull();
    expect(ui.toastMsg).toBe("网络不给力，请稍后再试");
    expect(live.hasLive).toBe(false);
  });
});

describe("ensureLive（守门分流：拉读 → 开账 / 终态拦 / 回看）", () => {
  it("拉读 200 → 视图落地；同局再调幂等（先对一拍）", async () => {
    const { live } = await load();
    liveApi.apiLiveView.mockResolvedValue(vMid(7));
    await live.ensureLive(900);
    expect(live.liveView!.totalSeq).toBe(7);
    expect(liveApi.apiLiveView).toHaveBeenCalledTimes(1);
    liveApi.apiLiveView.mockResolvedValue(vMid(9));
    await live.ensureLive(900); // 同局已开：对一拍（不重开账）
    expect(live.liveView!.totalSeq).toBe(9);
    live.stopPolling();
  });
  it("404 live_not_found + 局簿可开局 → 走开账后端路（apiLiveStart 被调）", async () => {
    const { ApiError } = await import("@/api/http");
    await seedGame(g900("locked"));
    const { live } = await load();
    liveApi.apiLiveView.mockRejectedValue(
      new ApiError("live_not_found", "现场不存在", 404),
    );
    liveApi.apiLiveStart.mockResolvedValue(vPlay(7));
    await live.ensureLive(900);
    expect(liveApi.apiLiveStart).toHaveBeenCalledWith(900);
    expect(live.liveView!.totalSeq).toBe(7);
    live.stopPolling();
  });
  it("404 + 终态局（done/terminated/cancelled）→ toast「球局不存在或已结束」不建现场", async () => {
    for (const status of ["done", "terminated", "cancelled"] as const) {
      vi.resetModules();
      setActivePinia(createPinia());
      Object.values(liveApi).forEach((m) => m.mockReset());
      // ApiError 与 store 同一模块图取（resetModules 后循环外取的是另一个类实例）
      const { ApiError } = await import("@/api/http");
      await seedGame(g900(status));
      const { live, ui } = await load();
      liveApi.apiLiveView.mockRejectedValue(
        new ApiError("live_not_found", "现场不存在", 404),
      );
      await live.ensureLive(900);
      expect(ui.toastMsg).toBe("球局不存在或已结束");
      expect(live.hasLive).toBe(false);
      expect(liveApi.apiLiveStart).not.toHaveBeenCalled();
    }
  });
  it("拉读断网 → toast「网络不给力，请稍后再试」不建现场", async () => {
    const { live, ui } = await load();
    liveApi.apiLiveView.mockRejectedValue(new TypeError("boom"));
    await live.ensureLive(900);
    expect(ui.toastMsg).toBe("网络不给力，请稍后再试");
    expect(live.hasLive).toBe(false);
  });
  it("散场视图（§4.10 回看态）：recap 持有定格、endedAt 落位、arriveMe 拦回 null（写入口关闭）", async () => {
    const { live } = await load();
    const ended = vMid(7);
    ended.ended = true;
    ended.ended_at = "2026-10-07T21:30:00+08:00";
    liveApi.apiLiveView.mockResolvedValue(ended);
    await live.ensureLive(900);
    expect(live.recap?.ended).toBe(true);
    expect(live.live!.endedAt).toBe("2026-10-07T21:30:00+08:00");
    expect(await live.arriveMe(900)).toBeNull(); // 旧画面残留的写动作拦下
  });
});

describe("键位修正（批4b 遗留：账号口径换视图消费）", () => {
  it("isAdmin 吃行 id（换账号对表）；访客/查无 false；myRound 按我的行 id；isFullPower 读视图旗", async () => {
    const { live } = await apply(
      mkLiveView({
        game_id: 900,
        total_seq: 7,
        admins: [8],
        courts: [ct(1, "playing")], // 在打：无空片，轮次只看队列位
        players: [
          pl(101, 0, { name: "我", queue_pos: 0 }),
          pl(103, 8, { name: "北苑小钢炮", queue_pos: 1 }),
          pl(104, null, { name: "访客", queue_pos: 2 }),
          // 1 号片在打要有人占位——视图里 playing 片没人会被重建成空片（空片计数入轮次）
          pl(102, 5, { name: "亮马河快攻", court_no: 1, court_side: "a" }),
          pl(105, 6, { name: "老赵", court_no: 1, court_side: "b" }),
        ],
        queue: [101, 103, 104],
      }),
    );
    expect(live.isAdmin(103)).toBe(true); // 行 id → 账号 8 ∈ admins
    expect(live.isAdmin(104)).toBe(false); // 访客行（账号 null）
    expect(live.isAdmin(999)).toBe(false); // 查无
    expect(live.isFullPower).toBe(false); // 视图旗：非组织者非管理员
    expect(live.myRound).toBe(1); // 队列第 0 位、无空片：ceil((4*0+0+1)/4)
    const full = await apply(mkLiveView({ game_id: 900, admins: [0] }));
    expect(full.live.isFullPower).toBe(true);
  });
});

describe("空降与带访客（1.3 批2 切真：apiLiveGuests · 命名/挂账/队尾归后端）", () => {
  it("addGuests：载荷（count/name/担保人行 id）+ 响应视图落地（roster/queue/ledger）+ toast", async () => {
    const { live, ui } = await inPlay();
    liveApi.apiLiveGuests.mockResolvedValue(
      vPlay(8, {
        players: [
          ...vPlay().players,
          pl(106, null, {
            name: "帮手·1",
            guest: true,
            guarantor_account_id: 0,
            check: "ok",
            queue_pos: 0,
          }),
          pl(107, null, {
            name: "帮手·2",
            guest: true,
            guarantor_account_id: 0,
            check: "ok",
            queue_pos: 1,
          }),
        ],
        queue: [106, 107],
      }),
    );
    await live.addGuests(2, "帮手", 101); // 101 = 担保人名册行 id（视图行，非账号 id）
    expect(liveApi.apiLiveGuests).toHaveBeenCalledWith(
      900,
      { count: 2, name: "帮手", guarantor_id: 101 },
      7,
    );
    const gs = live.live!.roster.slice(4);
    expect(gs.map((g) => g.name)).toEqual(["帮手·1", "帮手·2"]);
    expect(gs.every((g) => g.shadow && g.check === "ok")).toBe(true); // 到场即带
    expect(live.live!.queue).toEqual([106, 107]); // 队尾
    expect(live.live!.ledger.slice(4).map((r) => r.guarantor)).toEqual([
      "我",
      "我",
    ]); // 底账挂担保人（视图 guarantorAccountId → 担保人名）
    expect(ui.toastMsg).toBe("已带 2 位访客 · 进候场区");
  });
  it("G2 addGuests：空称呼不发 name（命名归后端）；needFull 前置拦截不发", async () => {
    const { live } = await inPlay();
    liveApi.apiLiveGuests.mockResolvedValue(vPlay(8));
    await live.addGuests(1, "", 101);
    expect(liveApi.apiLiveGuests).toHaveBeenCalledWith(
      900,
      { count: 1, name: undefined, guarantor_id: 101 },
      7,
    );
    const denied = await inPlay(vPlay(7, { admins: [] }));
    await denied.live.addGuests(1, "帮手", 101);
    expect(denied.ui.toastMsg).toBe("请找组织者或管理员");
    expect(liveApi.apiLiveGuests).toHaveBeenCalledTimes(1); // 被拦不发
  });
});

describe("本地遗留路（后端无对应端点——视图态上直测）", () => {
  it("subFirst：候场队首可用者顶上人数少的一队、feed 留句（本地路）", async () => {
    const { live, ui } = await apply(
      vPlay(7, {
        players: [
          ...vPlay().players.slice(0, 3), // B 只剩北苑小钢炮（打短）
          pl(105, 6, { name: "老赵", queue_pos: 0 }),
        ],
        courts: [ct(1, "playing", 3, 2)],
        queue: [105],
      }),
    );
    live.subFirst(0);
    expect(live.live!.courts[0].B).toEqual([103, 105]); // 人数少的 B 队补上老赵
    expect(live.live!.queue).toEqual([]);
    expect(live.live!.feed[0]).toBe("替补：老赵 顶上 · 比赛继续");
    expect(ui.toastMsg).toBe("替补已顶上 · 比赛继续");
    expect(liveApi.apiLiveDeal).not.toHaveBeenCalled(); // 本地路不发请求
  });
  it("removeFromRoster：名册/候场/在打全清、底账行留痕 removedAt、feed+toast", async () => {
    const { live, ui } = await inPlay();
    const L = live.live!;
    live.removeFromRoster(103);
    expect(L.roster.some((p) => p.id === 103)).toBe(false);
    expect(L.courts[0].B).toEqual([104]); // 场上同清
    const row = L.ledger.find((r) => r.id === 103)!;
    expect(row.removedAt).toBeTruthy(); // 行保留=留痕
    expect(L.feed[0]).toBe("北苑小钢炮 被移出名册");
    expect(ui.toastMsg).toBe("北苑小钢炮 被移出名册");
  });
  it("setRuleScore：本地落 g.scoring + toast（后端 rules 端点不带 scoring——遗留）", async () => {
    const { live, ui } = await inPlay();
    live.setRuleScore(21);
    expect(live.live!.g.scoring).toBe(21);
    expect(ui.toastMsg).toBe("分制已改为 21 分 · 当场生效");
  });
});

/* ─────────── 批6：散场清扫链（§4.9 切真：startSweep → 逐片 noRedeal / 一键全取消 → endGame=回看） ─────────── */

describe("散场清扫链（§4.9，批6）", () => {
  it("startSweep：先拉最新视图对一拍再进清扫态、清单=playing/pending 片；无权拒「只有组织者能收局」不拉读", async () => {
    const denied = await inPlay(vPlay(7, { admins: [] }));
    await denied.live.startSweep();
    expect(denied.ui.toastMsg).toBe("只有组织者能收局");
    expect(denied.live.sweepState).toBe(false);
    expect(liveApi.apiLiveView).not.toHaveBeenCalled();
    await seedGame(g900()); // 组织者是我：canEndLive 真
    const { live } = await inPlay();
    liveApi.apiLiveView.mockResolvedValue(
      vPlay(9, {
        courts_count: 2,
        courts: [ct(1, "pending", 11, 9), ct(2, "playing", 3, 2)],
      }),
    );
    await live.startSweep();
    expect(liveApi.apiLiveView).toHaveBeenCalledWith(900); // 残局判定吃权威数（A4 不自算）
    expect(live.sweepState).toBe(true);
    expect(live.sweepResidues.map((c) => c.status)).toEqual([
      "pending",
      "playing",
    ]);
  });
  it("管理员代收（§4.14 兜底：组织者已标早退）：canEndLive 真、照常进清扫", async () => {
    await seedGame(g900("locked", 1)); // 组织者是别人（账号 1）
    const { live } = await apply(
      vPlay(7, {
        players: [
          ...vPlay().players,
          pl(105, 1, { name: "组织者", check: "left" }),
        ],
      }),
    );
    expect(live.canEndLive).toBe(true);
    liveApi.apiLiveView.mockResolvedValue(vPlay(8));
    await live.startSweep();
    expect(live.sweepState).toBe(true);
    live.stopPolling();
  });
  it("清扫态确认（§4.9-1 不排下一场不补位）：confirmSettle noRedeal=true 透传、toast「残局已清」、不重发牌", async () => {
    const started = await inPlay(
      vPlay(7, { courts: [ct(1, "pending", 11, 9)] }),
    );
    const back = vPlay(8, {
      round: 1,
      courts: [],
      players: vPlay().players.map((p) => ({
        ...p,
        court_no: null,
        court_side: null,
        queue_pos: p.id - 101,
      })),
      queue: [101, 102, 103, 104],
    });
    liveApi.apiLiveSettleConfirm.mockResolvedValue(back);
    await started.live.confirmSettle(0, true, 11, 9, true);
    expect(liveApi.apiLiveSettleConfirm).toHaveBeenCalledWith(900, {
      courtNo: 1,
      winnerSide: "a",
      scoreA: 11,
      scoreB: 9,
      noRedeal: true,
      baseTotalSeq: 7,
      baseCourtSeq: 5,
    });
    expect(started.ui.toastMsg).toBe("积分落账 · 残局已清");
    expect(liveApi.apiLiveDeal).not.toHaveBeenCalled(); // 清扫途中没有下一场
  });
  it("清扫态取消：cancelMatch(…, true) 载荷 no_redeal=true、片腾出来不重发", async () => {
    const { live } = await inPlay();
    liveApi.apiLiveCancel.mockResolvedValue(
      vPlay(8, {
        courts: [],
        players: vPlay().players.map((p) => ({
          ...p,
          court_no: null,
          court_side: null,
          queue_pos: p.id - 101,
        })),
        queue: [101, 102, 103, 104],
      }),
    );
    await live.cancelMatch(0, true);
    expect(liveApi.apiLiveCancel).toHaveBeenCalledWith(900, 1, 7, 5);
    expect(liveApi.apiLiveDeal).not.toHaveBeenCalled();
  });
  it("sweepCancelAll 一键：载荷带总号、响应视图落地（残局清单随视图清空）+ toast", async () => {
    const { live, ui } = await inPlay();
    liveApi.apiLiveSweepCancelAll.mockResolvedValue(
      vPlay(8, {
        courts: [],
        players: vPlay().players.map((p) => ({
          ...p,
          court_no: null,
          court_side: null,
          queue_pos: p.id - 101,
        })),
        queue: [101, 102, 103, 104],
      }),
    );
    expect(live.sweepResidues).toHaveLength(1); // 出发时 1 号片在打
    await live.sweepCancelAll();
    expect(liveApi.apiLiveSweepCancelAll).toHaveBeenCalledWith(900, 7);
    expect(live.sweepResidues).toHaveLength(0); // 全清
    expect(ui.toastMsg).toBe("未完对局已全部取消");
  });
  it("endGame 残局未清：后端 live_residue 拒 → toast 后端句、清单开关不动、不封存", async () => {
    const { ApiError } = await import("@/api/http");
    await seedGame(g900()); // 组织者是我：canEndLive 真
    const { live, ui } = await inPlay();
    liveApi.apiLiveEnd.mockRejectedValue(
      new ApiError("live_residue", "还有没处理完的对局，先逐片处理再散场", 409),
    );
    live.sweepState = true; // 清单开着：被拒不关（停在那片提示重试）
    await live.endGame();
    expect(liveApi.apiLiveEnd).toHaveBeenCalledWith(900, 7);
    expect(ui.toastMsg).toBe("还有没处理完的对局，先逐片处理再散场");
    expect(live.sweepState).toBe(true);
    expect(live.recap).toBeNull();
  });
  it("endGame 成功：ended 视图落地=散场即回看（endedAt/recap 落、轮询停、清单关）", async () => {
    vi.useFakeTimers();
    try {
      await seedGame(g900());
      const { live, ui } = await inPlay();
      live.startPolling(900);
      const ended = vPlay(8, {
        ended: true,
        ended_at: "2026-10-07T21:30:00+08:00",
      });
      liveApi.apiLiveEnd.mockResolvedValue(ended);
      live.sweepState = true;
      await live.endGame();
      expect(liveApi.apiLiveEnd).toHaveBeenCalledWith(900, 7);
      expect(live.live!.endedAt).toBe("2026-10-07T21:30:00+08:00");
      expect(live.recap?.ended).toBe(true);
      expect(live.sweepState).toBe(false);
      expect(ui.toastMsg).toBe("已散场 · 战报与底账已封存");
      await vi.advanceTimersByTimeAsync(7000);
      expect(liveApi.apiLiveView).not.toHaveBeenCalled(); // 回看定格不轮询
    } finally {
      vi.useRealTimers();
    }
  });
});

/* ─────────── 批5b：确认窗联动纯函数 + 验收官补测销号（G1-G3，G4 并入 openSettle 用例） ─────────── */

describe("确认窗联动纯函数（§4.4/4.6：EndSettleModal 消费；组件测试基建缺位故下沉 store 测）", () => {
  it("followWinner：改分后胜方自动跟分高方（分低方当不了胜方）、平分清空禁确认", async () => {
    const { followWinner } = await import("@/stores/live");
    expect(followWinner(11, 9)).toBe(true);
    expect(followWinner(9, 11)).toBe(false);
    expect(followWinner(8, 11)).toBe(false); // 改小 A 侧也翻到 B（自动纠正）
    expect(followWinner(5, 5)).toBeNull(); // 平分不预选（§4.4）
    expect(followWinner(0, 0)).toBeNull();
  });
  it("canPickWinner：分低方选不中、平分双方均可点（点了才有预选）", async () => {
    const { canPickWinner } = await import("@/stores/live");
    expect(canPickWinner(11, 9, "a")).toBe(true);
    expect(canPickWinner(11, 9, "b")).toBe(false);
    expect(canPickWinner(9, 11, "b")).toBe(true);
    expect(canPickWinner(9, 11, "a")).toBe(false);
    expect(canPickWinner(5, 5, "a")).toBe(true);
    expect(canPickWinner(5, 5, "b")).toBe(true);
  });
});

describe("批5b 补测销号（验收官批5a findings G1-G3）", () => {
  it("G1 myRound 有空片放大分支：ceil((每片人数×空片数+队列位+1)/每片人数)", async () => {
    const { live } = await apply(
      mkLiveView({
        game_id: 900,
        admins: [0],
        courts_count: 2, // 1 号片在打、2 号片空（视图缺片行 → 补空片）
        courts: [ct(1, "playing")],
        players: [
          pl(101, 0, { name: "我", queue_pos: 0 }),
          pl(102, 5, { name: "亮马河快攻", court_no: 1, court_side: "a" }),
          pl(105, 6, { name: "老赵", court_no: 1, court_side: "b" }),
        ],
        queue: [101],
      }),
    );
    // 我队列位 0：ceil((4×1+0+1)/4)=2——空片项放大一轮（无空片时同队列位=1）
    expect(live.myRound).toBe(2);
  });
  it("G3 subFirst 负路：满员拒 / 候场只剩歇轮者拒 / 球友收权拒", async () => {
    const full = await inPlay();
    full.live.subFirst(0);
    expect(full.ui.toastMsg).toBe("场上没有缺位"); // 4 人满员（双打每边 2）
    expect(full.live.live!.courts[0].B).toEqual([103, 104]); // 没动
    const resting = await apply(
      vPlay(7, {
        players: [
          ...vPlay().players.slice(0, 3), // B 只剩北苑小钢炮（打短）
          pl(105, 6, { name: "老赵", queue_pos: 0, skip: 1 }), // 队首唯一人在歇
        ],
        queue: [105],
      }),
    );
    resting.live.subFirst(0);
    expect(resting.ui.toastMsg).toBe("候场没人能顶 · 先拉人吧");
    expect(resting.live.live!.courts[0].B).toEqual([103]);
    const denied = await inPlay(vPlay(7, { admins: [] }));
    denied.live.subFirst(0);
    expect(denied.ui.toastMsg).toBe("请找组织者或管理员"); // needFull gate 前置
    expect(denied.live.live!.courts[0].B).toEqual([103, 104]);
  });
});

/* ─────────── 批6 浏览器走查销号（P1 确认槽 / P2 深链 g 回填 / P3 elo 回填） ───────────
   P1 本体是页面模板层修复：确认槽内容壳 class="cf" 撞了全局 animations.scss 的撒花
   粒子类（absolute 9px 见方 + pointer-events:none）→ 面板塌成 9px 宽、按钮不可点；
   改名 cfm 后恢复。vitest 无组件渲染基建，视觉/可点性测不了（注明）——这里测确认槽
   所踩的 store 状态位：settling 窗位在视图重放（P2 回填重放首拍的场面）间不丢不闪。 */
describe("批6 走查销号（P1/P2/P3）", () => {
  it("P1 确认槽状态位：待确认窗随视图 pending 起、同视图重放不丢窗（深链回填重放首拍不闪关）、片退出 pending 窗关", async () => {
    const { toLiveView } = await import("@/api/live");
    const { live } = await load();
    const vp = vPlay(7, { courts: [ct(1, "pending", 11, 9, "manual")] });
    live.applyLiveView(toLiveView(vp));
    expect(live.settling).toEqual({ 0: { origin: "manual" } }); // pending 即有窗
    expect(live.settlingCourtId).toBe(0); // 确认槽挂在这扇窗上（live.vue confirmOpen）
    live.applyLiveView(toLiveView(vp)); // 同视图重放（回填重放首拍）：窗位原样不闪
    expect(live.settling).toEqual({ 0: { origin: "manual" } });
    live.applyLiveView(
      toLiveView(vPlay(8, { courts: [ct(1, "playing", 11, 9)] })),
    );
    expect(live.settling).toEqual({}); // 片退出 pending：窗与确认槽状态位全清
    expect(live.settlingCourtId).toBeNull();
  });

  it("P2 深链冷设备直达已开局（ensureLive 200 路）：局簿没缓存 → loadDetail 回填 g（局名/时刻/组织者）+ viewer 旗重派生；比分名册仍以视图为准", async () => {
    const { live } = await load();
    gamesApi.apiGameDetail.mockResolvedValue(d900());
    liveApi.apiLiveView.mockResolvedValue(vMid(7));
    await live.ensureLive(900);
    expect(gamesApi.apiGameDetail).toHaveBeenCalledTimes(1);
    expect(gamesApi.apiGameDetail).toHaveBeenCalledWith(900);
    const g = live.live!.g;
    expect(g.name).toBe("九百局"); // 不再是 stub 的「现场」
    expect(g.endAt).toBe("2026-10-07T21:00:00+08:00"); // 倒计时源（stub 是 "" → NaN）
    expect(g.organizer.id).toBe(0); // 组织者回到顶条 chip（stub 是 -1）
    expect(live.liveView!.isOrganizer).toBe(true); // 两旗借真组织者重派生（首拍 -1 降级 false）
    expect(live.live!.roster.map((p) => p.name)).toEqual([
      "亮马河快攻",
      "亮的球友·1",
      "我",
      "赵姐的朋友",
    ]); // 名册/比分真值未被详情覆盖
    expect(live.live!.courts[0]).toMatchObject({ sa: 3, sb: 2 });
    live.stopPolling();
  });

  it("P2 边界：详情拉不到留 stub 兜底不拦路（批5a 裁定保留）；局簿已有缓存不重复拉详情", async () => {
    const { live, ui } = await load();
    gamesApi.apiGameDetail.mockRejectedValue(new TypeError("boom"));
    liveApi.apiLiveView.mockResolvedValue(vMid(7));
    await live.ensureLive(900);
    expect(live.live!.g.name).toBe("现场"); // stub 保留
    expect(live.live!.g.organizer.id).toBe(-1);
    expect(ui.toastMsg).toBeFalsy(); // 静默降级，现场照常可看
    live.stopPolling();
  });

  it("P2 边界：局簿已有缓存（列表/详情页点进的路）→ 吃缓存起步，不重复拉详情", async () => {
    await seedGame(g900());
    const { live } = await load();
    liveApi.apiLiveView.mockResolvedValue(vMid(7));
    await live.ensureLive(900);
    expect(gamesApi.apiGameDetail).not.toHaveBeenCalled();
    expect(live.live!.g.name).toBe("九百局"); // 首建即真局（无需回填两段路）
    live.stopPolling();
  });

  it("P3 确认落账后卡面 elo 更新：roster 吃最近 matches[].eloRows 回填（正式按账号/访客按名，后一场覆盖前一场）；mock U 本体不动", async () => {
    const first = vMid().matches[0]!;
    const v = vMid(9);
    v.matches = [
      {
        ...first,
        elo_rows: [
          {
            account_id: 5,
            name: "亮马河快攻",
            guest: false,
            rating_before: 1562,
            rating_after: 1574,
            delta: 12,
          },
        ],
      },
      {
        ...first,
        seq: 2,
        ended_at: "2026-10-07T20:10:00+08:00",
        elo_rows: [
          {
            account_id: 5,
            name: "亮马河快攻",
            guest: false,
            rating_before: 1574,
            rating_after: 1586,
            delta: 12,
          },
          {
            account_id: null,
            name: "亮的球友·1",
            guest: true,
            rating_before: 1200,
            rating_after: 1190,
            delta: -10,
          },
          {
            account_id: 0,
            name: "我",
            guest: false,
            rating_before: 1518,
            rating_after: 1506,
            delta: -12,
          },
        ],
      },
    ];
    const { live } = await apply(v);
    const [li, guest, me] = live.live!.roster;
    expect(li.elo).toBe(1586); // 后一场覆盖前一场（1574 恰是 mock U.li 旧借位——必须吃到新值）
    expect(guest.elo).toBe(1190); // 访客按开账定格名回填 rating_after（展示位本就近真值）
    expect(me.elo).toBe(1506); // 负 delta 同样回填
    expect(U.li.elo).toBe(1574); // mock U 本体不被重建污染（借拷贝已改 elo 位）
    expect(U.me.elo).toBe(1518);
  });
});
