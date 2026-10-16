import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
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
   原本地遗留路已收口（2026-10-08 2.6 裁决）：subFirst/removeFromRoster 退役删除
   （用例随删）、setRuleScore 切真走 apiLiveRules（scoring 写局列，专例见后）；
   setCheck/togglePerson/swapPlayers 的视图外行支线已随批6 切真退役；空降/带访客走
   apiLiveDropIn/apiLiveGuests 专例。散场链（startSweep/sweepCancelAll/endGame/
   noRedeal 透传/回看落地停轮询）各有专例。批2 记分本地化：记分链块改纯本地账断言、
   上传/覆盖/冲突新用例（会话A）；settling/confirmSettle/openSettle 旧窗用例随消费端
   切换退役删（会话B），窗断言改 settleWindow；apiLivePoint/Undo/Clear/SettleOpen
   四函数与视图记分五字段随会话C 删旧退役（mock 表与片行速造同步收窄，片无比分）。
   每个用例重置模块图 → 全新 mock 数据。批3（走查缺陷修复）：结算窗锚代次三用例
   （视图推进自动关窗 / 上传前闸零请求 / 代次一致照发）见「结算窗锚代次」块。 */

const liveApi = vi.hoisted(() => ({
  apiLiveView: vi.fn(),
  apiLiveStart: vi.fn(),
  apiLiveDeal: vi.fn(),
  apiLiveSettleConfirm: vi.fn(),
  apiLiveSettleOverwrite: vi.fn(),
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

/** 应用一版视图进 store（多数写用例的出发点）——身份旗按「后端会发的口径」
    注入载荷（组织者解局簿、全权看 admins；seed 过 900 的用例即得 isOrganizer）。
    2026-10-08 身份块起旗随视图走，不再经映射参数派生 */
async function apply(v: LiveViewApi) {
  const h = await load();
  const { toLiveView } = await import("@/api/live");
  const gs = (await import("@/stores/game")).useGameStore();
  const us = (await import("@/stores/user")).useUserStore();
  const org = gs.findGame(v.game_id)?.organizer.id ?? -1;
  const isOrganizer = org >= 0 && org === us.me.id;
  h.live.applyLiveView(
    toLiveView({
      ...v,
      is_organizer: isOrganizer,
      is_full_power: isOrganizer || v.admins.includes(us.me.id),
      organizer_account_id: org,
    }),
  );
  return h;
}

/* mock 世界退役后，roster「people 缓存借位 + 整拷不回写」语义沿用——
   档案缓存种子（原 mock U 表三人的对应值） */
const LI_CARD = {
  id: 5,
  name: "亮马河快攻",
  elo: 1574,
  dupr: 3.3,
  play: 52,
  win: 29,
  month: 14,
  chibi: { skin: 1, hair: 0, hc: 0, shirt: 4, face: 0, acc: 2 },
};
const ME_CARD = {
  id: 0,
  name: "我",
  elo: 1518,
  dupr: 3.2,
  play: 34,
  win: 19,
  month: 18,
  chibi: { skin: 1, hair: 5, hc: 0, shirt: 0, face: 1, acc: 2 },
};
const ZHAO_CARD = {
  id: 10,
  name: "赵姐的朋友",
  elo: 0,
  dupr: 3.0,
  play: 0,
  win: 0,
  month: 0,
  shadow: true,
  chibi: { skin: 1, hair: 4, hc: 5, shirt: 0, face: 1, acc: 0 },
};

/** 预灌档案缓存（借位语义用例的靶人） */
async function seedCards() {
  const us = (await import("@/stores/user")).useUserStore();
  us.people[5] = { ...LI_CARD, chibi: { ...LI_CARD.chibi } };
  us.people[0] = { ...ME_CARD, chibi: { ...ME_CARD.chibi } };
  us.people[10] = { ...ZHAO_CARD, chibi: { ...ZHAO_CARD.chibi } };
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
    is_organizer: false, // 身份块（2026-10-08 起）：默认游客/普通球友视角——apply() 注入真旗
    is_full_power: false,
    organizer_account_id: -1,
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

/** 片行速造（记分本地化后片无比分——进行中比分在各手机本地账；court_seq=5 与
    总号 7 可分辨；scoring 片快照默认 11=与全局一致，改分制用例靠 rules.scoring
    覆写区分全局与快照，2.6） */
const ct = (no: number, status: "idle" | "playing"): LiveCourtApi => ({
  court_no: no,
  status,
  seq: 1,
  court_seq: 5,
  scoring: 11,
});

/** 中场快照（900 局）：li(101) 与访客(102) 在 1 号片在打、我(103) 候场队首；
    已落一场战报 + 两条 feed（swap → set_admin 按发生序）；zhao(104) 未到（借属性
    覆写对称的靶行——mock U.zhao 自带 shadow） */
function vMid(seq = 7): LiveViewApi {
  return mkLiveView({
    game_id: 900,
    total_seq: seq,
    round: 2,
    admins: [5],
    is_organizer: true, // 身份块基准：900 = 我开的局（响应视图走生产 toLiveView，旗烤进载荷）
    is_full_power: true,
    organizer_account_id: 0,
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
        court_seq: 5,
        scoring: 11,
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

/** 在打基态（900 局 · 我全权 admins[0]）：1 号片 4 人对打、总号 7、片号 5 */
function vPlay(seq = 7, over: Partial<LiveViewApi> = {}): LiveViewApi {
  return mkLiveView({
    game_id: 900,
    total_seq: seq,
    admins: [0],
    is_organizer: true, // 身份块基准：900 = 我开的局（响应视图走生产 toLiveView，旗烤进载荷）
    is_full_power: true,
    organizer_account_id: 0,
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
    courts: [ct(1, "playing")],
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
  it("roster 借 people 缓存同 accountId 者的展示位（整拷不回写）、访客 shadow+默认位、覆写对称（借来的 shadow 不残留）、片/队列/战报/feed/规则/底账全回填", async () => {
    await seedCards();
    const { live } = await apply(vMid());
    const L = live.live!;
    expect(L.g.id).toBe(900); // 局簿没有 → 冷扫兜底局仍可重建
    expect(L.g.scoring).toBe(11); // 分制回填 L.g
    expect(L.g.courts).toEqual(["1号", "2号"]); // 片数吃 courts_count 真值
    const [li, guest, me, zhao] = L.roster;
    expect(li.id).toBe(101); // User.id = 名册行 id（写动作靶位，与 queue/片位同键）
    expect(li.elo).toBe(1574); // accountId 5 → 借 people[5] 展示位
    expect(li.dupr).toBe(3.42); // dupr 吃视图行真值（> people[5] 借位 3.3）
    expect(li.chibi).toEqual(LI_CARD.chibi);
    expect(li.check).toBe("ok");
    expect(li.arriveAt).toBe("2026-10-07T19:02:00+08:00");
    expect(guest.shadow).toBe(true); // 访客 shadow 标记
    expect(guest.elo).toBe(1200); // 查无者默认展示位＝后端初始等第（ELO_INIT）
    expect(guest.dupr).toBe(3.0); // 访客 dupr 后端回 GUEST_DUPR
    expect(guest.chibi).toEqual({});
    expect(me.elo).toBe(1518); // accountId 0 → 借 people[0]
    expect(me.dupr).toBe(3.28); // 视图真值覆写 people[0] 的 3.2（整拷上改）
    expect(me.dropin).toBe(true);
    expect(zhao.shadow).toBeUndefined(); // 覆写对称：people[10] 自带 shadow、行非访客 → 清掉（批5a Nit）
    expect(L.queue).toEqual([103]); // 候场队序
    expect(L.courts).toHaveLength(2); // 视图只带 1 片 → 按片数补空片（差人卡）
    expect(L.courts[0]).toMatchObject({
      id: 0, // 视图 1 起片号 → 旧 0 起片序
      name: "1号",
      A: [101],
      B: [102],
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
      down: "loser", // 总账定值
      pairing: "balance",
      champCap: 2,
    });
    expect(L.admins).toEqual([5]);
    expect(L.round).toBe(2);
    // 底账「谁带的」素材在视图行（LedgerSheet 由 guarantorAccountId 现推担保人名）
    const p102 = live.liveView!.players.find((r) => r.id === 102)!;
    expect(
      live.liveView!.players.find(
        (x) => x.accountId === p102.guarantorAccountId,
      )!.name,
    ).toBe("亮马河快攻");
    expect(live.settleWindow).toBeNull(); // 视图落地不开窗（窗只由记分/入口驱动）
    expect(live.liveView?.totalSeq).toBe(7); // 最近视图持有
    expect(live.recap).toBeNull(); // 未散场不持有回看
    const us = (await import("@/stores/user")).useUserStore();
    expect(us.people[5]!.elo).toBe(1574); // 整拷：people 缓存不被重建污染
    expect(us.people[0]!.dupr).toBe(3.2); // dupr 回填同样只改拷贝
    // 幂等：同视图重放不漂移（空片不重复补、队列不重排）
    const { toLiveView } = await import("@/api/live");
    live.applyLiveView(toLiveView(vMid()));
    expect(L.courts).toHaveLength(2);
    expect(L.queue).toEqual([103]);
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
    live.applyLiveView(toLiveView(vMid(8))); // 同局又回进行中（回放/换机重进的对账面）
    expect(live.recap).toBeNull();
  });
  it("tonight 随视图行落名册展示位（队列抽屉「今晚 N 场」数源——档案缓存 play 是生涯数，不顶用）", async () => {
    await seedCards();
    const v = vMid(8);
    v.players = v.players.map((p, i) => ({ ...p, tonight: i + 1 }));
    const { live } = await apply(v);
    expect(live.live!.roster.map((p) => p.tonight)).toEqual([1, 2, 3, 4]);
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
  it("身份两旗视图直读（2026-10-08 身份块）：载荷带的旗原样落地，store 不再本地拼——换旗即换权", async () => {
    const { live } = await load();
    liveApi.apiLiveView.mockResolvedValue(
      mkLiveView({
        game_id: 900,
        is_organizer: true,
        is_full_power: true,
        organizer_account_id: 0,
      }),
    );
    await live.pollLiveView(900);
    expect(live.liveView!.isOrganizer).toBe(true); // 组织者视角
    expect(live.isFullPower).toBe(true); // store 单一源直读视图旗
    liveApi.apiLiveView.mockResolvedValue(
      mkLiveView({ game_id: 900, total_seq: 2, admins: [5] }), // 普通球友视角载荷：两旗 false
    );
    await live.pollLiveView(900);
    expect(live.liveView!.isOrganizer).toBe(false);
    expect(live.isFullPower).toBe(false);
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

describe("point / undoPoint / clearScore（记分本地化：纯本地账，零网络零 seq）", () => {
  it("point：只写本机账零 api 调用——流水栈记账、比分即反馈无 toast、总账不动（本地账从 0:0 起记，不种子服务端旧分）", async () => {
    const { live, ui } = await inPlay();
    live.point(0, "a");
    live.point(0, "a");
    live.point(0, "b");
    // 零网络：mock 表全数零调用（apiLivePoint/Undo/Clear 已退役，整表兜住真值）
    expect(Object.values(liveApi).every((m) => m.mock.calls.length === 0)).toBe(
      true,
    );
    expect(live.localScores[0]).toEqual({
      sa: 2,
      sb: 1,
      history: ["a", "a", "b"],
    });
    expect(ui.toastMsg).toBeFalsy(); // 比分即反馈
    expect(live.liveView!.totalSeq).toBe(7); // 零 seq：总账没动
  });
  it("point 空片/无现场静默：不记账", async () => {
    const { live } = await load();
    live.point(0, "a"); // 无现场
    expect(live.localScores[0]).toBeUndefined();
    const empty = await apply(mkLiveView({ game_id: 900, admins: [0] })); // 有现场、片空
    empty.live.point(0, "b");
    expect(empty.live.localScores[0]).toBeUndefined();
  });
  it("到分自动开上传窗（reachedLocal：够线且净胜≥2，吃片分制快照）；窗占位不重开（一次一扇）", async () => {
    const { live } = await inPlay();
    live.point(0, "a"); // 1:0 不到分
    expect(live.settleWindow).toBeNull();
    for (let i = 0; i < 10; i++) live.point(0, "a"); // → 11:0 命中
    expect(live.settleWindow).toEqual({
      courtId: 0,
      noRedeal: false,
      mode: "upload",
      courtSeqAnchor: 5, // 批3：开窗即锚视图片代次（vPlay 1 号片 court_seq=5）
    });
    live.point(0, "b"); // 窗已开再加分：占位不重开
    expect(live.settleWindow).toEqual({
      courtId: 0,
      noRedeal: false,
      mode: "upload",
      courtSeqAnchor: 5,
    });
  });
  it("到分但净胜不足不开窗：10:10、11:10 继续打，净胜 2 才弹（deuce 同式）", async () => {
    const { live } = await inPlay();
    for (let i = 0; i < 10; i++) live.point(0, "a"); // 10:0
    for (let i = 0; i < 10; i++) live.point(0, "b"); // 10:10
    expect(live.settleWindow).toBeNull();
    live.point(0, "a"); // 11:10 净胜 1 仍不开
    expect(live.settleWindow).toBeNull();
    live.point(0, "a"); // 12:10 开窗
    expect(live.settleWindow?.mode).toBe("upload");
  });
  it("undoPoint 按流水栈撤回（零 api；支持连续撤回到底，0:0 静默）", async () => {
    const { live } = await inPlay();
    live.undoPoint(0); // 无账静默
    live.point(0, "a");
    live.point(0, "b");
    live.point(0, "a");
    expect(live.localScores[0]).toEqual({
      sa: 2,
      sb: 1,
      history: ["a", "b", "a"],
    });
    live.undoPoint(0); // 撤回 a
    expect(live.localScores[0]).toEqual({
      sa: 1,
      sb: 1,
      history: ["a", "b"],
    });
    live.undoPoint(0); // 撤回 b
    expect(live.localScores[0]).toEqual({
      sa: 1,
      sb: 0,
      history: ["a"],
    });
    live.undoPoint(0); // 撤回 a，归零
    expect(live.localScores[0]).toEqual({
      sa: 0,
      sb: 0,
      history: [],
    });
    live.undoPoint(0); // 已归零再撤静默
    expect(live.localScores[0]).toEqual({
      sa: 0,
      sb: 0,
      history: [],
    });
    expect(Object.values(liveApi).every((m) => m.mock.calls.length === 0)).toBe(
      true,
    ); // 零网络
  });
  it("clearScore 本地清零（收权闸随本地化卸下，球友也可点）：零 api、账面归 0:0、无 toast（比分归零即反馈）", async () => {
    const { live, ui } = await inPlay(vPlay(7, { admins: [] })); // 球友视角
    live.point(0, "a");
    await live.clearScore(0);
    expect(Object.values(liveApi).every((m) => m.mock.calls.length === 0)).toBe(
      true,
    ); // 零网络
    expect(live.localScores[0]).toEqual({
      sa: 0,
      sb: 0,
      history: [],
    });
    expect(ui.toastMsg).toBeFalsy();
  });
});

describe("上传结算与改分重落（记分本地化：先传先落 / settle_recorded 分流 / 全权覆盖）", () => {
  /** 上传窗基态：在打片 + 已开 upload 窗（清扫态 noRedeal=true 由清单入口开窗传入） */
  async function inUpload(noRedeal = false) {
    const h = await inPlay();
    h.live.openSettleWindow(0, "upload", noRedeal);
    return h;
  }
  it("uploadSettle：载荷（胜方比分全吃入参 + noRedeal + 两级号）+ 成功对表 + 本地账清零 + 窗转一步展示 + toast 分叉（排下一场/残局已清）", async () => {
    const { live, ui } = await inUpload();
    live.point(0, "a"); // 本地账 4:2：成功后清零
    // 响应视图=回流重发后的新阵容：一步展示吃的「刚发的片」（新对阵）与「候场名单」
    liveApi.apiLiveSettleConfirm.mockResolvedValue(
      vPlay(8, {
        round: 1,
        courts: [{ ...ct(1, "playing"), court_seq: 6 }],
        players: [
          pl(101, 0, { name: "我", court_no: 1, court_side: "b" }),
          pl(102, 5, { name: "亮马河快攻", court_no: 1, court_side: "b" }),
          pl(103, 8, { name: "北苑小钢炮", court_no: 1, court_side: "a" }),
          pl(104, null, {
            name: "亮的球友·1",
            guarantor_account_id: 5,
            court_no: 1,
            court_side: "a",
          }),
        ],
        queue: [],
      }),
    );
    await live.uploadSettle(0, true, 11, 9);
    expect(liveApi.apiLiveSettleConfirm).toHaveBeenCalledWith(900, {
      courtNo: 1,
      winnerSide: "a",
      scoreA: 11,
      scoreB: 9,
      noRedeal: false,
      baseTotalSeq: 7,
      baseCourtSeq: 5,
    });
    expect(live.liveView!.totalSeq).toBe(8); // 响应视图已对表
    expect(live.localScores[0]).toEqual({
      sa: 0,
      sb: 0,
      history: [],
    });
    // 窗不关、转一步展示（EndSettleModal done 态的取数路：新对阵+候场都从最新视图来）
    expect(live.settleWindow).toEqual({
      courtId: 0,
      noRedeal: false,
      mode: "upload",
      courtSeqAnchor: null, // 展示窗撤锚：不被 applyLiveView 的自动关窗当成过期窗误杀
      done: true,
    });
    expect(live.live!.courts[0]).toMatchObject({
      A: [103, 104],
      B: [101, 102],
    });
    expect(live.live!.queue).toEqual([]);
    expect(ui.toastMsg).toBe("积分落账 · 下一场已排好");
    const sweep = await inUpload(true); // 清扫态：noRedeal 透传 + 残局句 + 不转展示（没有下一场）
    liveApi.apiLiveSettleConfirm.mockResolvedValue(
      vPlay(8, { round: 1, courts: [ct(1, "playing")] }),
    );
    await sweep.live.uploadSettle(0, true, 11, 9, true);
    expect(sweep.ui.toastMsg).toBe("积分落账 · 残局已清");
    expect(sweep.live.settleWindow).toBeNull();
  });
  it("uploadSettle 400 rotation_overflow（越界降级：主动作已提交、错误体携最新视图）——对表保持最新画面 + 透传后端句；窗随锚过期自动关清账", async () => {
    const { ApiError } = await import("@/api/http");
    const { live, ui } = await inUpload();
    live.point(0, "a"); // 本机账已飞：这场其实落成了，只是发牌段降级
    liveApi.apiLiveSettleConfirm.mockRejectedValue(
      new ApiError(
        "rotation_overflow",
        "轮转数超范围，这片暂停发牌",
        400,
        vPlay(9, { courts: [] }), // 发牌段回滚：片留空
      ),
    );
    await live.uploadSettle(0, true, 11, 9);
    expect(ui.toastMsg).toBe("轮转数超范围，这片暂停发牌"); // 后端句透传（errText 链）
    expect(live.liveView!.totalSeq).toBe(9); // 错误体视图已对表（页面保持最新画面）
    expect(live.settleWindow).toBeNull(); // 片代次被推进 → 锚过期自动关窗
    expect(live.localScores[0]).toEqual({
      sa: 0,
      sb: 0,
      history: [],
    }); // 本地账对齐清零
  });
  it("一步展示窗不占一次一扇的闸：done 窗开着，下一场到分/手动入口开新窗直接顶掉（锚吃新代次）", async () => {
    const { live } = await inUpload();
    liveApi.apiLiveSettleConfirm.mockResolvedValue(
      vPlay(8, { round: 1, courts: [{ ...ct(1, "playing"), court_seq: 6 }] }),
    );
    await live.uploadSettle(0, true, 11, 9);
    expect(live.settleWindow).toMatchObject({
      done: true,
      courtSeqAnchor: null,
    });
    live.openSettleWindow(0, "upload"); // 下一场又到分
    expect(live.settleWindow).toEqual({
      courtId: 0,
      noRedeal: false,
      mode: "upload",
      courtSeqAnchor: 6,
      done: undefined,
    });
  });
  it("uploadSettle 409 settle_recorded（先传先落：有人已按别的分落账）——特判先于通用 409「现场已更新」分流：对表响应视图 + 透传服务端句 + 本地账清零 + 关窗", async () => {
    const { ApiError } = await import("@/api/http");
    const { live, ui } = await inUpload();
    live.point(0, "a"); // 本机账与先落者不同
    liveApi.apiLiveSettleConfirm.mockRejectedValue(
      new ApiError(
        "settle_recorded",
        "已按 9:11 记账 · 有异议找组织者",
        409,
        vPlay(9, {
          round: 1,
          courts: [ct(1, "playing")],
          matches: [
            {
              court_no: 1,
              seq: 1,
              winners: [
                { id: 103, name: "北苑小钢炮", guest: false },
                { id: 104, name: "亮的球友·1", guest: true },
              ],
              losers: [
                { id: 101, name: "我", guest: false },
                { id: 102, name: "亮马河快攻", guest: false },
              ],
              score_a: 9,
              score_b: 11,
              winner_side: "b",
              ended_at: "2026-10-07T20:00:00+08:00",
              elo_rows: [],
            },
          ],
        }),
      ),
    );
    await live.uploadSettle(0, true, 11, 9);
    expect(ui.toastMsg).toBe("已按 9:11 记账 · 有异议找组织者"); // 服务端句透传（句尾服务端已带全，不二次拼接）
    expect(live.liveView!.totalSeq).toBe(9); // 错误体视图已对表
    expect(live.live!.history[0]).toEqual({
      names: "北苑小钢炮 & 亮的球友·1",
      sa: 9,
      sb: 11,
    });
    expect(live.localScores[0]).toEqual({
      sa: 0,
      sb: 0,
      history: [],
    }); // 本机账对齐清零
    expect(live.settleWindow).toBeNull();
  });
  it("uploadSettle 幂等闸：窗没开不发；窗开着别的片也不发（一次一扇按 courtId 对号）", async () => {
    const { live } = await inPlay();
    await live.uploadSettle(0, true, 11, 9); // 无窗
    expect(liveApi.apiLiveSettleConfirm).not.toHaveBeenCalled();
    live.openSettleWindow(0, "upload");
    await live.uploadSettle(1, true, 11, 9); // 窗在 0 片、传的是 1 片
    expect(liveApi.apiLiveSettleConfirm).not.toHaveBeenCalled();
  });
  it("uploadSettle 幂等重放 200（断网重发/同分同位后端不重落回当前视图）：照成功路清零关窗 toast", async () => {
    const { live, ui } = await inUpload();
    liveApi.apiLiveSettleConfirm.mockResolvedValue(
      vPlay(8, {
        round: 1,
        courts: [ct(1, "playing")],
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
            elo_rows: [],
          },
        ],
      }),
    );
    await live.uploadSettle(0, true, 11, 9); // 同分同位重放：200 当前视图
    expect(ui.toastMsg).toBe("积分落账 · 下一场已排好");
    expect(live.settleWindow).toMatchObject({ done: true }); // 照成功路：转一步展示
    expect(live.localScores[0]).toEqual({
      sa: 0,
      sb: 0,
      history: [],
    });
  });
  it("overwriteSettle：needFull 前端闸（球友拒「请找组织者或管理员」不发）；全权 → 载荷（无 noRedeal）+ toast「比分已改 · 积分已重算」+ 同片窗关", async () => {
    const denied = await inPlay(vPlay(7, { admins: [] }));
    await denied.live.overwriteSettle(0, true, 11, 7);
    expect(denied.ui.toastMsg).toBe("请找组织者或管理员");
    expect(liveApi.apiLiveSettleOverwrite).not.toHaveBeenCalled();
    const { live, ui } = await inPlay();
    live.openSettleWindow(0, "overwrite"); // 「上一场 · 改分」入口开的窗（会话B/C 接）
    liveApi.apiLiveSettleOverwrite.mockResolvedValue(
      vPlay(8, {
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
            score_b: 7,
            winner_side: "a",
            ended_at: "2026-10-07T20:00:00+08:00",
            elo_rows: [],
          },
        ],
      }),
    );
    await live.overwriteSettle(0, true, 11, 7);
    expect(liveApi.apiLiveSettleOverwrite).toHaveBeenCalledWith(900, {
      courtNo: 1,
      winnerSide: "a",
      scoreA: 11,
      scoreB: 7,
      baseTotalSeq: 7,
      baseCourtSeq: 5,
    });
    expect(ui.toastMsg).toBe("比分已改 · 积分已重算");
    expect(live.settleWindow).toBeNull();
  });
});

/* ─────────── 批3 修复：结算窗锚代次（upload 窗跨视图代次推进的旧场账拦截） ───────────
   走查实弹：窗开着跨越代次推进（别人先传落账、片 court_seq 5→6），3s 轮询把 base 号
   洗新后后端两级号闸认不出旧场的账 → 误记成新一场战报。修法两处：开窗锚 courtSeqAnchor
   （upload 窗）+ 上传前闸 / applyLiveView 自动关窗；overwrite 窗不锚（操作的是上一场
   落账行，改分重落也推片代次——锚了反被误杀，过期由后端片号闸兜底）。 */

describe("结算窗锚代次（批3 修复）", () => {
  /** 代次推进后的视图：1 号片 court_seq 5→6（这场已被别人落账/该片重发），总号 9 */
  const advanced = (): LiveViewApi =>
    vPlay(9, { round: 1, courts: [{ ...ct(1, "playing"), court_seq: 6 }] });

  it("① 视图代次推进自动关窗：upload 窗开着、applyLiveView 带该片新 court_seq → 窗自动关+本地账清零+toast；总号动了片代次没动不误关", async () => {
    const { toLiveView } = await import("@/api/live");
    const { live, ui } = await inPlay();
    live.point(0, "a");
    live.openSettleWindow(0, "upload");
    live.applyLiveView(toLiveView(vPlay(8))); // 别人报到等总号推进：片代次仍 5
    expect(live.settleWindow).not.toBeNull(); // 不误伤：要传的这场还在打
    live.applyLiveView(toLiveView(advanced())); // 这场被别人落账：片代次 5→6
    expect(live.settleWindow).toBeNull(); // 窗自动关（现场已变化的诚实呈现）
    expect(live.localScores[0]).toEqual({
      sa: 0,
      sb: 0,
      history: [],
    }); // 本地账清零
    expect(ui.toastMsg).toBe("现场已更新 · 这场已有人记账");
  });

  it("①' overwrite 窗不锚：片代次推进不误关、本地账不动（它操作的是上一场落账行）", async () => {
    const { toLiveView } = await import("@/api/live");
    const { live } = await inPlay();
    live.point(0, "a");
    live.openSettleWindow(0, "overwrite");
    live.applyLiveView(toLiveView(advanced()));
    expect(live.settleWindow).not.toBeNull();
    expect(live.localScores[0]).toEqual({
      sa: 1,
      sb: 0,
      history: ["a"],
    });
  });

  it("② 上传前闸：窗锚过期（视图片代次已越过锚）零请求——有落账行拼服务端 settle_recorded 同款句、无行走通用句，均清零关窗", async () => {
    const { live, ui } = await inPlay();
    live.openSettleWindow(0, "upload"); // 开窗锚=5
    live.settleWindow!.courtSeqAnchor = 4; // 手动构造窗跨代次存活（自动关窗已兜的竞态残留）
    live.point(0, "a"); // 旧场的本地账
    await live.uploadSettle(0, true, 11, 9);
    expect(liveApi.apiLiveSettleConfirm).not.toHaveBeenCalled(); // 闸：不发请求
    expect(ui.toastMsg).toBe("现场已更新 · 这场已有人记账"); // vPlay 无战报行 → 通用句
    expect(live.localScores[0]).toEqual({
      sa: 0,
      sb: 0,
      history: [],
    });
    expect(live.settleWindow).toBeNull();
    // 有落账行：latestMatchOf 取该片最新行拼服务端同款句
    const withMatch = await inPlay(
      vPlay(7, {
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
            score_a: 9,
            score_b: 11,
            winner_side: "b",
            ended_at: "2026-10-07T20:00:00+08:00",
            elo_rows: [],
          },
        ],
      }),
    );
    withMatch.live.openSettleWindow(0, "upload");
    withMatch.live.settleWindow!.courtSeqAnchor = 4;
    await withMatch.live.uploadSettle(0, true, 11, 9);
    expect(liveApi.apiLiveSettleConfirm).not.toHaveBeenCalled();
    expect(withMatch.ui.toastMsg).toBe("已按 9:11 记账 · 有异议找组织者");
    expect(withMatch.live.settleWindow).toBeNull();
  });

  it("③ 代次一致照发（回归）：到分自动开窗即锚视图真值，uploadSettle 照发成功且不被自动关窗抢 toast", async () => {
    const { toLiveView } = await import("@/api/live");
    const { live, ui } = await inPlay();
    for (let i = 0; i < 11; i++) live.point(0, "a"); // 11:0 到分自动开窗
    expect(live.settleWindow!.courtSeqAnchor).toBe(5); // 开窗即锚视图真值
    // 响应视图片代次推进到 6：自家落账先关窗才落视图，不被自动关窗抢 toast
    liveApi.apiLiveSettleConfirm.mockResolvedValue(
      vPlay(8, { round: 1, courts: [{ ...ct(1, "playing"), court_seq: 6 }] }),
    );
    await live.uploadSettle(0, true, 11, 0);
    expect(liveApi.apiLiveSettleConfirm).toHaveBeenCalledWith(900, {
      courtNo: 1,
      winnerSide: "a",
      scoreA: 11,
      scoreB: 0,
      noRedeal: false,
      baseTotalSeq: 7,
      baseCourtSeq: 5,
    });
    expect(ui.toastMsg).toBe("积分落账 · 下一场已排好"); // 不是「这场已有人记账」
    expect(live.settleWindow).toMatchObject({ done: true }); // 成功路转一步展示
  });
});

describe("cancelMatch（§4.7 取消对局：回流队首归总账、片腾出来后端出口补）", () => {
  it("取消：载荷带 no_redeal=false + 两级号、toast 带出发时场上人数；响应视图即排好（后端出口已补片，前端不再补发）", async () => {
    const { live, ui } = await inPlay();
    const back = vPlay(8, {
      courts: [ct(1, "playing")],
      players: vPlay().players.map((p) => ({
        ...p,
        queue_pos: null,
      })),
      queue: [],
    });
    liveApi.apiLiveCancel.mockResolvedValue(back);
    await live.cancelMatch(0);
    expect(liveApi.apiLiveCancel).toHaveBeenCalledWith(900, 1, 7, 5, false);
    expect(ui.toastMsg).toBe("对局作废 · 这场不计分 · 场上 4 人回到队首");
    expect(liveApi.apiLiveDeal).not.toHaveBeenCalled(); // 补片在后端出口，前端零补发
    expect(live.live!.courts[0].A).toEqual([101, 102]); // 落定即重发完
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
      is_organizer: true, // 身份块基准：900 = 我开的局（组织者首签不授面等用例按需覆写）
      is_full_power: true,
      organizer_account_id: 0,
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
    expect(ui.toastMsg).toBe("我 已签到 · 自动加入候场队"); // 2.5 §4.7 统一句：迟到不单说
    expect(liveApi.apiLiveDeal).not.toHaveBeenCalled(); // 1 人不够一片：前端零补发
  });
  it("到场驱动补片（§4.1 够一片的人数就上片）：第 4 人报到，报到响应视图已排好——补片在后端出口", async () => {
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
    // 报到响应即总账：后端出口同拍把队首 4 人排上 1 号片，视图直接带回
    liveApi.apiLiveCheck.mockResolvedValue(
      vCheck({
        total_seq: 8,
        players: [
          pl(101, 0, {
            name: "我",
            queue_pos: null,
            court_no: 1,
            court_side: "b",
          }),
          pl(102, 5, {
            name: "亮马河快攻",
            queue_pos: null,
            court_no: 1,
            court_side: "a",
          }),
          pl(103, 8, {
            name: "北苑小钢炮",
            queue_pos: null,
            court_no: 1,
            court_side: "a",
          }),
          pl(104, null, {
            name: "亮的球友·1",
            queue_pos: null,
            court_no: 1,
            court_side: "b",
          }),
        ],
        courts: [ct(1, "playing")],
        queue: [],
      }),
    );
    await live.setCheck(101, "ok");
    expect(ui.toastMsg).toBe("我 已签到 · 自动加入候场队"); // 2.5 §4.7 统一句
    expect(liveApi.apiLiveDeal).not.toHaveBeenCalled(); // 前端不再补发
    expect(live.live!.courts[0].A).toEqual([102, 103]); // 落定即排好
    expect(live.live!.courts[0].B).toEqual([101, 104]); // 半边成员真值（半边内按名册序）
  });
  it("早退（§4.5）：toast 先走句；视图落定清队列位/片位", async () => {
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
        courts: [ct(1, "playing")],
      }),
    );
    await live.setCheck(103, "left");
    expect(liveApi.apiLiveCheck).toHaveBeenCalledWith(900, 103, "left", 7);
    expect(ui.toastMsg).toBe("北苑小钢炮 先走了 · 回见");
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
  it("签到统一句（2.5 §4.7）：ok 与 late 落定态同一句——文案只认到场，不认迟没迟到", async () => {
    const late = await apply(vCheck());
    liveApi.apiLiveCheck.mockResolvedValue(
      vCheck({
        total_seq: 8,
        players: [pl(101, 0, { name: "我", check: "late", queue_pos: 0 })],
        queue: [101],
      }),
    );
    await late.live.setCheck(101, "ok");
    const ok = await apply(vCheck());
    liveApi.apiLiveCheck.mockResolvedValue(
      vCheck({
        total_seq: 8,
        players: [pl(101, 0, { name: "我", check: "ok", queue_pos: 0 })],
        queue: [101],
      }),
    );
    await ok.live.setCheck(101, "ok");
    expect(ok.ui.toastMsg).toBe(late.ui.toastMsg); // 同句
    expect(ok.ui.toastMsg).toBe("我 已签到 · 自动加入候场队");
  });
  it("自动管理员获授（2.5 §4.2）：首签后 admins 新增含我（非组织者）→ 唯一 toast 用合同原句「组织者还没来 · 现场你先管着」，feed auto_admin 拼句", async () => {
    const { live, ui } = await apply(vCheck({ admins: [] })); // 冷账无管理员；局簿无此局 → isOrganizer false
    liveApi.apiLiveCheck.mockResolvedValue(
      vCheck({
        total_seq: 8,
        admins: [0],
        is_organizer: false, // 非组织者首签获授：后端按 viewer 发旗（组织者旗 false、全权随授管 true）
        is_full_power: true,
        players: [pl(101, 0, { name: "我", check: "ok", queue_pos: 0 })],
        queue: [101],
        feed: [
          {
            kind: "auto_admin",
            actor: "我",
            target: "我",
            at: "2026-10-07T19:00:00+08:00",
          },
        ],
      }),
    );
    await live.setCheck(101, "ok");
    expect(ui.toastMsg).toBe("组织者还没来 · 现场你先管着");
    expect(live.live!.feed[0]).toBe("现场第一位签到的 我 暂管现场"); // feedSentences auto_admin 分支
    expect(live.live!.admins).toEqual([0]);
  });
  it("自动管理员不授面：组织者首签不加尾巴（后端不授）；我已是管理员再签不重复提示", async () => {
    await seedGame(g900()); // 组织者是我
    const org = await apply(vCheck({ admins: [] }));
    liveApi.apiLiveCheck.mockResolvedValue(
      vCheck({
        total_seq: 8,
        admins: [0],
        players: [pl(101, 0, { name: "我", check: "ok", queue_pos: 0 })],
        queue: [101],
      }),
    );
    await org.live.setCheck(101, "ok");
    expect(org.ui.toastMsg).toBe("我 已签到 · 自动加入候场队");
    const already = await apply(vCheck()); // admins [0]：我已在管理员表
    liveApi.apiLiveCheck.mockResolvedValue(
      vCheck({
        total_seq: 8,
        players: [pl(101, 0, { name: "我", check: "ok", queue_pos: 0 })],
        queue: [101],
      }),
    );
    await already.live.setCheck(101, "ok");
    expect(already.ui.toastMsg).toBe("我 已签到 · 自动加入候场队");
  });
});

describe("swapPlayers（§4.9 换人：出/入方向按名册真值内定——修复批 F8，此前页面传反必被后端拒）", () => {
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
  it("候场者抽屉点场上靶：out=场上者、in=候场者（点的是候场老赵、选的是片上快攻）", async () => {
    const { live, ui } = await withQueue();
    liveApi.apiLiveSwap.mockResolvedValue(vPlay(8));
    await live.swapPlayers(105, 102);
    expect(liveApi.apiLiveSwap).toHaveBeenCalledWith(900, 102, 105, 7);
    expect(ui.toastMsg).toBe("已换人 · 对阵重排");
  });
  it("场上者抽屉点候场靶：方向同式（out 仍是场上者，与谁开抽屉无关）", async () => {
    const { live } = await withQueue();
    liveApi.apiLiveSwap.mockResolvedValue(vPlay(8));
    await live.swapPlayers(101, 105); // 点开的是场上的「我」
    expect(liveApi.apiLiveSwap).toHaveBeenCalledWith(900, 101, 105, 7);
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

describe("setRules / setCourtsInput / autoDeal（§4.7 规则与场地 · 排片真值在后端）", () => {
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
    expect(liveApi.apiLiveDeal).not.toHaveBeenCalled(); // 空片重排在后端出口，前端零补发
  });
  it("setRules 连打上限 0＝不限直传（champCap:0 是合法值不得被丢包）+ 视图 streak_max:0 回填 champCap:0", async () => {
    const { live } = await inPlay();
    liveApi.apiLiveRules.mockResolvedValue(
      vPlay(8, { rules: { ...vPlay().rules, streak_max: 0 } }),
    );
    await live.setRules({ champCap: 0 });
    expect(liveApi.apiLiveRules).toHaveBeenCalledWith(900, { streakMax: 0 }, 7);
    expect(live.live!.rules.champCap).toBe(0); // 抽屉「当前＝不限」的数源
  });
  it("setCourtsInput：『3、4 / 3,4 / 3号、4号』归一 → courtsCount 上报、片名本地挂", async () => {
    const { live, ui } = await inPlay();
    liveApi.apiLiveRules.mockResolvedValue(
      vPlay(8, { courts_count: 2, courts: [ct(1, "playing")] }),
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
        courts: [ct(1, "playing"), ct(2, "playing")],
      }),
    );
    expect(await two.live.setCourtsInput("3号")).toBe(false);
    expect(two.ui.toastMsg).toBe("在打 + 待开的场地不能收");
    expect(liveApi.apiLiveRules).not.toHaveBeenCalled();
  });
  it("autoDeal：空载荷直调让后端补所有空片 + toast「牌已发 · 按当前规则排好」（响应视图真开出片才报）", async () => {
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
        courts: [ct(1, "playing"), ct(2, "playing")],
      }),
    );
    await live.autoDeal();
    expect(liveApi.apiLiveDeal).toHaveBeenCalledWith(
      900,
      7, // 空载荷只带出发号；补哪些空片归后端
    );
    expect(live.live!.courts[1]!.A).toEqual([105, 106]); // 落定
    expect(ui.toastMsg).toBe("牌已发 · 按当前规则排好");
  });
  it("autoDeal 空手不报「牌已发」（2026-10-10 事故语义）：人没凑够一片回 200 空手视图——请求发了、toast 不出", async () => {
    const { live, ui } = await apply(
      vPlay(7, {
        courts_count: 2,
        players: [
          ...vPlay().players,
          pl(105, 6, { name: "老赵", queue_pos: 0 }),
        ],
        queue: [105],
      }),
    );
    liveApi.apiLiveDeal.mockResolvedValue(
      vPlay(8, {
        courts_count: 2,
        players: [
          ...vPlay().players,
          pl(105, 6, { name: "老赵", queue_pos: 0 }),
        ],
        queue: [105],
      }),
    );
    await live.autoDeal();
    expect(liveApi.apiLiveDeal).toHaveBeenCalledTimes(1); // 请求照发（后端裁决够不够）
    expect(ui.toastMsg).toBeFalsy(); // 空片没少：不报成功话术（差人卡常驻提示）
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

describe("startLive（批5a 后端开账路：apiLiveStart 幂等 → 视图落地）", () => {
  it("开账：视图落地 + toast「球局开始 · 现场已点亮」返 msg；开场排片在响应视图（后端出口），前端零补发", async () => {
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
    const msg = await live.startLive(g900());
    expect(msg).toBe("球局开始 · 现场已点亮");
    expect(ui.toastMsg).toBe("球局开始 · 现场已点亮");
    expect(live.live!.g.id).toBe(900); // 名册展开归后端：视图直建
    expect(live.live!.queue).toEqual([101, 102, 103, 104]); // 落定即总账
    expect(liveApi.apiLiveDeal).not.toHaveBeenCalled();
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
  it("404 + 终态局（done/terminated/cancelled）→ toast「找不到这个球局，可能已被撤销」不建现场（2.6 §4.6 链接死局句，不说「已结束」）", async () => {
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
      await expect(live.ensureLive(900)).resolves.toBe(false);
      expect(ui.toastMsg).toBe("找不到这个球局，可能已被撤销");
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

describe("pendingLiveId（2.5 弹回 bug：goLive 落位 → live.vue onShow 消费清位的跨页信号位）", () => {
  it("store 级：默认空位、可落位（消费清位在 live.vue 编排层，vitest 无页面基建不测）", async () => {
    const { live } = await load();
    expect(live.pendingLiveId).toBeNull();
    live.pendingLiveId = 900;
    expect(live.pendingLiveId).toBe(900);
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
    expect(
      live
        .liveView!.players.slice(4)
        .map(
          (p) =>
            live.liveView!.players.find(
              (x) => x.accountId === p.guarantorAccountId,
            )?.name,
        ),
    ).toEqual(["我", "我"]); // 底账挂担保人（视图 guarantorAccountId → 担保人名，LedgerSheet 现推）
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

describe("setRuleScore（2.6 切真：scoring 写局列，在打片快照照旧）", () => {
  it("成功：apiLiveRules 收 scoring 键 + toast「下一场起生效」；全局 g.scoring 随视图翻新、在打片快照照旧 11", async () => {
    const { live, ui } = await inPlay();
    liveApi.apiLiveRules.mockResolvedValue(
      vPlay(8, { rules: { ...vPlay().rules, scoring: 21 } }),
    );
    await live.setRuleScore(21);
    expect(liveApi.apiLiveRules).toHaveBeenCalledWith(900, { scoring: 21 }, 7);
    expect(live.live!.g.scoring).toBe(21); // 全局当前生效（rules 块随视图回填 g）
    expect(live.live!.courts[0]!.scoring).toBe(11); // 在打片快照不动：这局照旧 11 分打完
    expect(ui.toastMsg).toBe("分制已改为 21 分 · 下一场起生效");
  });
  it("失败：断网 toast「网络不给力，请稍后再试」、现场不动（g.scoring 与总号原样）", async () => {
    const { live, ui } = await inPlay();
    liveApi.apiLiveRules.mockRejectedValue(new TypeError("boom"));
    await live.setRuleScore(21);
    expect(ui.toastMsg).toBe("网络不给力，请稍后再试");
    expect(live.live!.g.scoring).toBe(11); // 未落地
    expect(live.liveView!.totalSeq).toBe(7);
  });
  it("收权：球友被拒「请找组织者或管理员」不发（needFull 前置保留）", async () => {
    const { live, ui } = await inPlay(vPlay(7, { admins: [] }));
    await live.setRuleScore(21);
    expect(ui.toastMsg).toBe("请找组织者或管理员");
    expect(liveApi.apiLiveRules).not.toHaveBeenCalled();
  });
});

/* ─────────── 批6：散场清扫链（§4.9 切真：startSweep → 逐片 noRedeal / 一键全取消 → endGame=回看） ─────────── */

describe("散场清扫链（§4.9，批6）", () => {
  it("startSweep：先拉最新视图对一拍再进清扫态、清单=非 idle 片（pending 已退役）；无权拒「只有组织者能收局」不拉读", async () => {
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
        courts: [ct(1, "playing"), ct(2, "playing")],
      }),
    );
    await live.startSweep();
    expect(liveApi.apiLiveView).toHaveBeenCalledWith(900, {
      totalSeq: 7,
      feeTotal: null,
    }); // 残局判定吃权威数（A4 不自算）；带指纹走条件拉取（2.8 批5）——fixture 无 fee 块折 null
    expect(live.sweepState).toBe(true);
    expect(live.sweepResidues.map((c) => c.status)).toEqual([
      "playing",
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
    liveApi.apiLiveView.mockResolvedValue(
      vPlay(8, {
        is_organizer: false, // 代收者视角的旗：非组织者、全权（组织者旗归账号 1）
        is_full_power: true,
        organizer_account_id: 1,
      }),
    );
    await live.startSweep();
    expect(live.sweepState).toBe(true);
    live.stopPolling();
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
    expect(liveApi.apiLiveCancel).toHaveBeenCalledWith(900, 1, 7, 5, true);
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

/* ─────────── 批5b：确认窗联动纯函数（EndSettleModal 消费）+ 验收官补测销号（G1；
   G3 随 2.6 subFirst 退役删；G4 空片静默随记分本地化并入 point 用例） ─────────── */

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
  it("latestMatchOf：该片最新落账行（结束序倒查）——场卡「上一场 · 改分」显示与改分窗预填同一真值；无行/无视图 undefined", async () => {
    const { latestMatchOf } = await import("@/stores/live");
    const { live } = await apply(vMid());
    const m = latestMatchOf(live.liveView, 1)!;
    expect(m.courtNo).toBe(1);
    expect(`${m.sa}:${m.sb}`).toBe("11:9"); // 链接标签「上一场 11:9 · 改分」同源
    expect(latestMatchOf(live.liveView, 2)).toBeUndefined(); // 2 号片没落过账
    expect(latestMatchOf(null, 1)).toBeUndefined();
  });
});

describe("批5b 补测销号（验收官批5a findings G1；G3 随 2.6 subFirst 退役删）", () => {
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
});

/* ─────────── 批6 浏览器走查销号（P1 elo_preview / P2 深链 g 回填 / P3 elo 回填） ───────────
   P1 本体是页面模板层修复（确认槽内容壳 class="cf" 撞全局 animations.scss 撒花粒子类
   → 面板塌成 9px 宽，改名 cfm 后恢复）：其窗位状态位（settling 随视图起落）已随批2
   记分本地化退役（结算窗改 settleWindow——store 态与视图重放无关，天然不闪关）；
   vitest 无组件渲染基建，视觉/可点性测不了。可测遗产=确认窗吃的 elo_preview 双分支
   映射（批2 起挂 playing 片，upload/overwrite 两模式共用）。 */
describe("批6 走查销号（P1/P2/P3）", () => {
  it("P1 遗产：elo_preview 双分支映射通透（playing 片随视图落地——结算窗点胜方切换消费）", async () => {
    const { toLiveView } = await import("@/api/live");
    const { live } = await load();
    const vp = vPlay(7); // playing 片（批1 起 elo_preview 挂 playing）
    vp.courts[0]!.elo_preview = {
      a: [
        {
          account_id: 0,
          name: "我",
          guest: false,
          rating_before: 1200,
          rating_after: 1212,
          delta: 12,
        },
      ],
      b: [
        {
          account_id: 5,
          name: "亮马河快攻",
          guest: false,
          rating_before: 1200,
          rating_after: 1193,
          delta: -7,
        },
      ],
    };
    live.applyLiveView(toLiveView(vp));
    expect(live.liveView!.courts[0]!.eloPreview?.a[0]).toMatchObject({
      accountId: 0,
      delta: 12,
    }); // 双分支随映射落地（窗内点胜方切换消费）
    expect(live.liveView!.courts[0]!.eloPreview?.b[0]!.delta).toBe(-7);
  });

  it("P2 深链冷设备直达已开局（ensureLive 200 路）：身份旗首拍即真（视图身份块，组织者的按钮不等局簿）；局簿没缓存 → loadDetail 回填 g（局名/时刻/组织者，纯展示让位）；比分名册仍以视图为准", async () => {
    const { live } = await load();
    gamesApi.apiGameDetail.mockResolvedValue(d900());
    liveApi.apiLiveView.mockResolvedValue({
      ...vMid(7),
      is_organizer: true, // 组织者深链：后端按 viewer 发旗，首拍就是全权（不再等回填重派生）
      is_full_power: true,
      organizer_account_id: 0,
    });
    await live.ensureLive(900);
    expect(gamesApi.apiGameDetail).toHaveBeenCalledTimes(1);
    expect(gamesApi.apiGameDetail).toHaveBeenCalledWith(900);
    const g = live.live!.g;
    expect(g.name).toBe("九百局"); // 不再是 stub 的「现场」
    expect(g.endAt).toBe("2026-10-07T21:00:00+08:00"); // 倒计时源（stub 是 "" → NaN）
    expect(g.organizer.id).toBe(0); // 组织者回到顶条 chip（stub 是 -1）
    expect(live.liveView!.isOrganizer).toBe(true); // 首拍即真：冷启动散场钮直接可用（本批修的根）
    expect(live.live!.roster.map((p) => p.name)).toEqual([
      "亮马河快攻",
      "亮的球友·1",
      "我",
      "赵姐的朋友",
    ]); // 名册真值未被详情覆盖（比分已出视图——记分本地化后挂本机 localScores）
    expect(live.localScores[0]).toBeUndefined(); // 本机账不由视图详情路触碰
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

  it("P3 确认落账后卡面 elo 更新：roster 吃最近 matches[].eloRows 回填（正式按账号/访客按名，后一场覆盖前一场）；people 缓存本体不动", async () => {
    await seedCards();
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
    const us = (await import("@/stores/user")).useUserStore();
    expect(us.people[5]!.elo).toBe(1574); // people 缓存本体不被重建污染（借拷贝已改 elo 位）
    expect(us.people[0]!.elo).toBe(1518);
  });
});
