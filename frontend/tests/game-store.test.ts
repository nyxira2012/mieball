import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import type { GameViewApi } from "@/api/games";

/* 1.2 接线重写：game store 动作全是真接口调用——api 层整体 mock，用例喂 crafted
   game_view/intent_view（形状与后端 game_views.py 逐字对齐），测的是 store 侧的
   映射（toGame）、回填（upsert/refresh）与文案分支。 */
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
  apiGameDirectOpen: vi.fn(),
}));

vi.mock("@/api/games", () => api);

beforeEach(() => {
  vi.clearAllMocks();
  setActivePinia(createPinia());
});

async function loadStore() {
  const mod = await import("@/stores/game");
  return {
    store: mod.useGameStore(),
    ui: (await import("@/stores/ui")).useUiStore(),
  };
}

/* ---- game_view 造数（线上 snake 形状） ---- */
let seq = 400;
/** person_view 造数：装扮三键后端恒兜底直出（dress_fields 单一源，1.9 展示位） */
function mkPerson(id: number, nickname: string) {
  return {
    id,
    nickname,
    avatar: "a-p1",
    avatar_url: `/cosmetics/a-p${id}.webp`,
    back: id % 2 ? "b-c1" : "b-t35",
  };
}
function mkView(p: Partial<GameViewApi> = {}): GameViewApi {
  seq += 1;
  return {
    id: seq,
    name: `测试局 ${seq}`,
    organizer: mkPerson(7, "朝阳反手王"),
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
    status: "open",
    unlocked: false,
    joinable: true,
    live_opened: false,
    ended: false,
    heads: 1,
    slots_left: 7,
    per_head: null,
    forced: false,
    ...p,
  };
}

describe("directOpen（直接开场 2026-10-17）", () => {
  it("成功：载荷透传、新局插列表头、toast 开场句、source=direct 映射", async () => {
    api.apiGameDirectOpen.mockResolvedValue(
      mkView({
        id: 501,
        status: "live",
        live_opened: true,
        forced: true,
        source: "direct",
        visibility: "invite_only",
      }),
    );
    const { store, ui } = await loadStore();
    const g = await store.directOpen({
      name: "老王 · 朝阳馆",
      venue_name: "朝阳馆",
      venue_address: null,
      hours: 2,
      courts: ["3号", "5号"],
    });
    expect(api.apiGameDirectOpen).toHaveBeenCalledWith({
      name: "老王 · 朝阳馆",
      venue_name: "朝阳馆",
      venue_address: null,
      hours: 2,
      courts: ["3号", "5号"],
    });
    expect(g.id).toBe(501);
    expect(g.source).toBe("direct");
    expect(store.games[0]?.id).toBe(501); // unshift 排头
    expect(store.findGame(501)?.forced).toBe(true); // upsert 回填
    expect(ui.toastMsg).toBe("现场已开场 · 亮出二维码收人吧");
  });

  it("旧快照无 source 字段：映射兜底 plan（兼容性）", async () => {
    api.apiListGames.mockResolvedValue([mkView({ id: 601 })]);
    const { store } = await loadStore();
    await store.loadGames();
    expect(store.findGame(601)?.source).toBe("plan");
  });
});

describe("loadGames / loadMine / loadDetail（读链）", () => {
  it("列表填充 + snake→camel 映射抽查（定值直读，A4）", async () => {
    api.apiListGames.mockResolvedValue([
      mkView({
        heads: 5,
        slots_left: 3,
        per_head: 96,
        forced: true,
        my: {
          is_organizer: true,
          my_entry: { bring: 2, standing: "formal", wait_seq: null },
          invited: false,
          // 能力旗（闸旗同源）随 my 块落地——页面显隐直读（2026-10-08 债清偿）
          can_book: true,
          can_fill_fee: false,
          can_lock: false,
        },
      }),
    ]);
    const { store } = await loadStore();
    await store.loadGames();
    expect(store.games).toHaveLength(1);
    const g = store.games[0]!;
    expect(g.startAt).toBe("2026-10-08T19:00:00+08:00");
    expect(g.maxPlayers).toBe(8);
    expect(g.perHead).toBe(96);
    expect(g.slotsLeft).toBe(3);
    expect(g.forced).toBe(true);
    expect(g.my?.isOrganizer).toBe(true);
    expect(g.my?.myEntry?.bring).toBe(2);
    expect(g.ended).toBe(false);
    expect(g.my?.canBook).toBe(true);
    expect(g.my?.canFillFee).toBe(false);
    expect(g.my?.canLock).toBe(false);
    expect(g.organizer.nickname).toBe("朝阳反手王");
  });

  it("loadDetail 落 current：链接直达的局经 findGame 取到", async () => {
    api.apiGameDetail.mockResolvedValue(mkView({ id: 9 }));
    const { store } = await loadStore();
    const g = await store.loadDetail(9);
    expect(g.id).toBe(9);
    expect(store.findGame(9)?.id).toBe(9);
  });

  it("findGame 优先 current，再两个列表", async () => {
    api.apiListGames.mockResolvedValue([mkView({ id: 1 })]);
    api.apiGameDetail.mockResolvedValue(mkView({ id: 2 }));
    const { store } = await loadStore();
    await store.loadGames();
    await store.loadDetail(2);
    expect(store.findGame(2)?.id).toBe(2); // current 优先
    expect(store.findGame(1)?.id).toBe(1); // 列表兜底
    expect(store.findGame(99)).toBeNull();
  });
});

describe("publishGame（发局）", () => {
  it("新局插列表头（后端 id 倒序）；默认档 toast 带冷启动引导", async () => {
    api.apiListGames.mockResolvedValue([mkView({ id: 1 })]);
    const { store, ui } = await loadStore();
    await store.loadGames();
    api.apiPublishGame.mockResolvedValue(
      mkView({ id: 2, visibility: "played" }),
    );
    const g = await store.publishGame({
      name: "周六 · 测试球馆",
      start_at: "2026-10-10T14:00:00+08:00",
      end_at: "2026-10-10T16:00:00+08:00",
      deadline_at: "2026-10-10T12:00:00+08:00",
      venue_name: "测试球馆",
      venue_address: null,
      min_players: 4,
      max_players: 8,
      visibility: "played",
      scoring: 11,
      rotation: "balance",
      score_rule: "rally",
    });
    expect(store.games[0]!.id).toBe(2); // unshift 排头
    expect(g.visibility).toBe("played");
    expect(ui.toastMsg).toContain("主要通过你转的链接");
  });

  it("公开档 toast 不带引导", async () => {
    const { store, ui } = await loadStore();
    api.apiPublishGame.mockResolvedValue(mkView({ visibility: "public" }));
    await store.publishGame({
      name: "x",
      start_at: "",
      end_at: "",
      deadline_at: "",
      venue_name: "x",
      venue_address: null,
      min_players: 4,
      max_players: 8,
      visibility: "public",
      scoring: 11,
      rotation: "balance",
      score_rule: "rally",
    });
    expect(ui.toastMsg).toContain("分享到群里拉人");
    expect(ui.toastMsg).not.toContain("链接");
  });
});

describe("joinGame（报名 · toast 按返回名单分支）", () => {
  it("正式加入：带人文案 + 列表同 id 行替换（upsert）", async () => {
    api.apiListGames.mockResolvedValue([
      mkView({ id: 5, heads: 2, slots_left: 6 }),
    ]);
    const { store, ui } = await loadStore();
    await store.loadGames();
    api.apiJoinGame.mockResolvedValue(
      mkView({
        id: 5,
        heads: 5,
        slots_left: 3,
        my: {
          is_organizer: false,
          my_entry: { bring: 2, standing: "formal", wait_seq: null },
          invited: false,
        },
      }),
    );
    const g = await store.joinGame(5, 2);
    expect(g.my?.myEntry?.bring).toBe(2);
    expect(store.games[0]!.heads).toBe(5); // upsert 已替换
    expect(ui.toastMsg).toBe("已加入 · 带了 2 人（共占 3 坑）");
  });

  it("坑不够整行落候补：候补文案（4.3 提示）", async () => {
    api.apiListGames.mockResolvedValue([mkView({ id: 1 })]);
    const { store, ui } = await loadStore();
    await store.loadGames(); // JoinSheet 的局必经 findGame 取自 store，先落列表
    api.apiJoinGame.mockResolvedValue(
      mkView({
        id: 1,
        heads: 8,
        slots_left: 0,
        my: {
          is_organizer: false,
          my_entry: { bring: 0, standing: "waitlist", wait_seq: 1 },
          invited: false,
        },
      }),
    );
    await store.joinGame(1, 0);
    expect(ui.toastMsg).toBe("坑不够，已为你排候补"); // 4.3 规格原句（修复批 F1）
    expect(store.findGame(1)?.my?.myEntry?.standing).toBe("waitlist");
  });
});

describe("quitGame / cancelGame（只回 ok 的动作：回填在 store）", () => {
  it("退局：refresh 重拉单局回填（候补递补可见）", async () => {
    api.apiListGames.mockResolvedValue([
      mkView({ id: 5, heads: 4, slots_left: 4 }),
    ]);
    const { store, ui } = await loadStore();
    await store.loadGames();
    api.apiQuitGame.mockResolvedValue({ ok: true });
    api.apiGameDetail.mockResolvedValue(
      mkView({ id: 5, heads: 2, slots_left: 6 }),
    );
    await store.quitGame(5);
    expect(ui.toastMsg).toBe("已退出 · 名单里少了你");
    expect(store.games[0]!.heads).toBe(2);
  });

  it("撤局：从列表移除、current 清空、组织者不留痕", async () => {
    api.apiMyGames.mockResolvedValue([mkView({ id: 5 })]);
    const { store, ui } = await loadStore();
    await store.loadMine();
    await store.loadDetail(5);
    api.apiCancelGame.mockResolvedValue({ ok: true });
    await store.cancelGame(5);
    expect(store.myGames).toHaveLength(0);
    expect(store.findGame(5)).toBeNull();
    expect(ui.toastMsg).toContain("同步消失");
  });
});

describe("editGame（改局 · 上限放宽反馈）", () => {
  it("候补全部转正：toast「已全部转正」", async () => {
    api.apiGameDetail.mockResolvedValue(
      mkView({
        id: 5,
        entries: [
          {
            account: { id: 1, nickname: "甲" },
            bring: 0,
            standing: "formal",
            wait_seq: null,
          },
        ],
      }),
    );
    const { store, ui } = await loadStore();
    await store.loadDetail(5);
    api.apiEditGame.mockResolvedValue(
      mkView({
        id: 5,
        max_players: 8,
        entries: [
          {
            account: mkPerson(1, "甲"),
            bring: 0,
            standing: "formal",
            wait_seq: null,
          },
          {
            account: mkPerson(2, "乙"),
            bring: 0,
            standing: "formal",
            wait_seq: null,
          },
          {
            account: mkPerson(3, "丙"),
            bring: 0,
            standing: "formal",
            wait_seq: null,
          },
          {
            account: mkPerson(4, "丁"),
            bring: 1,
            standing: "formal",
            wait_seq: null,
          },
        ],
      }),
    );
    await store.editGame(5, { max_players: 8 });
    expect(ui.toastMsg).toBe("局已改好 · 上限放宽，候补已全部转正");
  });

  it("普通改局（没放宽）：toast「名单里的人看到的就是新信息」", async () => {
    api.apiGameDetail.mockResolvedValue(mkView({ id: 5 }));
    const { store, ui } = await loadStore();
    await store.loadDetail(5);
    api.apiEditGame.mockResolvedValue(mkView({ id: 5, name: "新名" }));
    await store.editGame(5, { name: "新名" });
    expect(ui.toastMsg).toBe("局已改好 · 名单里的人看到的就是新信息");
    expect(store.findGame(5)?.name).toBe("新名");
  });
});

describe("lockGame / bookCourt / clearBooking（必打三态）", () => {
  it("空锁与订场的 toast 逐字", async () => {
    const { store, ui } = await loadStore();
    api.apiLockGame.mockResolvedValue(
      mkView({ id: 5, manual_lock: true, forced: true }),
    );
    await store.lockGame(5);
    expect(ui.toastMsg).toContain("已锁定必打");
    api.apiBookCourt.mockResolvedValue(
      mkView({
        id: 5,
        manual_lock: true,
        courts: ["3号", "5号"],
        fee_total: 480,
        per_head: 60,
        forced: true,
      }),
    );
    await store.bookCourt(5, ["3号", "5号"], 480);
    expect(ui.toastMsg).toBe("已订场 · 3号、5号（2 片）· 这局必开，费用已落定");
    api.apiClearBooking.mockResolvedValue(
      mkView({
        id: 5,
        manual_lock: true,
        courts: null,
        fee_total: null,
        per_head: null,
        forced: true,
      }),
    );
    await store.clearBooking(5);
    expect(ui.toastMsg).toBe("订场登记已清空 · 手动锁定保留，这局仍必打");
  });

  it("清空登记（无手动锁）→ 局回未订场原样文案", async () => {
    const { store, ui } = await loadStore();
    api.apiClearBooking.mockResolvedValue(
      mkView({
        id: 5,
        manual_lock: false,
        courts: null,
        fee_total: null,
        forced: false,
      }),
    );
    await store.clearBooking(5);
    expect(ui.toastMsg).toBe(
      "订场登记已清空 · 局回到未订场，费用未定，截止照常判人数",
    );
  });
});

describe("restoreGame / inviteUser", () => {
  it("恢复 → 待处置文案；邀请 → 带名 toast + 意向列表重拉", async () => {
    api.apiListIntents.mockResolvedValue([
      {
        account: mkPerson(12, "小张"),
        slots: ["wd"],
        frequency: 1,
        note: null,
        updated_at: "2026-10-06T10:00:00+08:00",
        invited: false,
        known: false,
      },
    ]);
    const { store, ui } = await loadStore();
    await store.loadIntents();
    api.apiMyGames.mockResolvedValue([mkView({ id: 5, status: "terminated" })]);
    await store.loadMine(); // 未成局区从 myGames 点恢复——局先在列表里，upsert 才有落点
    api.apiRestoreGame.mockResolvedValue(mkView({ id: 5, status: "pending" }));
    await store.restoreGame(5);
    expect(ui.toastMsg).toContain("待处置");
    expect(store.findGame(5)?.status).toBe("pending");
    api.apiInviteUser.mockResolvedValue({ ok: true });
    await store.inviteUser(5, 12);
    expect(api.apiInviteUser).toHaveBeenCalledWith(5, 12);
    expect(ui.toastMsg).toBe("已邀请 小张 · 局已出现在 ta 的「我的局」");
    expect(api.apiListIntents).toHaveBeenCalledTimes(2); // 已邀标记重拉
  });
});

describe("saveIntent / delIntent（意向簿）", () => {
  it("空时段：本地拦截（toast + 抛错，不发请求）", async () => {
    const { store, ui } = await loadStore();
    await expect(store.saveIntent([], 2, "")).rejects.toThrow();
    expect(ui.toastMsg).toBe("至少选一个时段");
    expect(api.apiSaveIntent).not.toHaveBeenCalled();
  });

  it("留/改：写 myIntent，两态文案", async () => {
    const { store, ui } = await loadStore();
    api.apiSaveIntent.mockResolvedValue({
      account: mkPerson(0, "我"),
      slots: ["we-n"],
      frequency: 2,
      note: "夜战优先",
      updated_at: "",
      invited: false,
      known: false,
    });
    await store.saveIntent(["we-n"], 2, "夜战优先");
    expect(ui.toastMsg).toBe("意向已留下 · 组局的人凑人时会看见你");
    expect(store.myIntent).toEqual({
      slots: ["we-n"],
      frequency: 2,
      note: "夜战优先",
    });
    api.apiSaveIntent.mockResolvedValue({
      account: mkPerson(0, "我"),
      slots: ["wd"],
      frequency: 1,
      note: "",
      updated_at: "",
      invited: false,
      known: false,
    });
    await store.saveIntent(["wd"], 1, "");
    expect(ui.toastMsg).toBe("意向已更新 · 想改随时改");
    expect(store.myIntent?.slots).toEqual(["wd"]);
  });

  it("删意向：myIntent 清空", async () => {
    const { store, ui } = await loadStore();
    api.apiMyIntent.mockResolvedValue(null);
    await store.loadMyIntent();
    api.apiDeleteIntent.mockResolvedValue({ ok: true });
    await store.delIntent();
    expect(store.myIntent).toBeNull();
    expect(ui.toastMsg).toBe("意向已删 · 随时可以再留");
  });
});

describe("feePreview / setFee（补填链，1.3 §4.5）", () => {
  it("feePreview 纯现算直通：回定值、不落 store、不 toast（组件确认步定值源头）", async () => {
    const { store, ui } = await loadStore();
    api.apiGameFeePreview.mockResolvedValue({
      heads: 12,
      per_head: 58,
      organizer_share: 62,
    });
    // store 收 camel 映射（组件不吃线上 snake 形状，映射规约同 toGame）
    await expect(store.feePreview(5, 700)).resolves.toEqual({
      heads: 12,
      perHead: 58,
      organizerShare: 62,
    });
    expect(api.apiGameFeePreview).toHaveBeenCalledWith(5, 700);
    expect(ui.toastMsg).toBe(""); // 不 toast
    expect(store.games).toHaveLength(0); // 不落 store（纯现算，不回填）
  });

  it("setFee >0：出账回填 bill 块，toast 带实摊份数；=0 只定值不出账文案", async () => {
    const { store, ui } = await loadStore();
    api.apiListGames.mockResolvedValue([mkView({ id: 5 })]);
    await store.loadGames(); // upsert 要有落点
    api.apiGameFee.mockResolvedValue(
      mkView({
        id: 5,
        fee_total: 700,
        bill: {
          fee_total: 700,
          per_head: 58,
          heads: 12,
          my_share: 62,
          my_guest_count: 0,
        },
      }),
    );
    await store.setFee(5, 700);
    expect(api.apiGameFee).toHaveBeenCalledWith(5, 700);
    expect(store.findGame(5)?.bill?.heads).toBe(12);
    expect(ui.toastMsg).toBe("总价已定 · 账已出，按 12 份摊，账单里见");
    api.apiGameFee.mockResolvedValue(
      mkView({ id: 5, fee_total: 0, bill: null }),
    );
    await store.setFee(5, 0);
    expect(ui.toastMsg).toBe("费用已定为 ¥0 · 免费场，不出账");
  });
});

describe("装扮三键透传（1.9 展示位：局卡铺组织者/意向卡铺意向者/名单墙铺格主）", () => {
  it("toGame：organizer/entries/dropins 的 avatar_url→avatarUrl、back 原样（snake→camel 单点）", async () => {
    api.apiGameDetail.mockResolvedValue(
      mkView({
        id: 31,
        organizer: mkPerson(7, "朝阳反手王"),
        entries: [
          {
            account: mkPerson(2, "乙"),
            bring: 0,
            standing: "formal",
            wait_seq: null,
          },
        ],
        dropins: [{ account: mkPerson(4, "丁") }],
      }),
    );
    const { store } = await loadStore();
    const g = await store.loadDetail(31);
    expect(g.organizer.avatarUrl).toBe("/cosmetics/a-p7.webp");
    expect(g.organizer.back).toBe("b-c1");
    // mkPerson 偶数 id 造另一档卡背，锁同格不同款也各自透传
    expect(g.entries?.[0]?.account.avatarUrl).toBe("/cosmetics/a-p2.webp");
    expect(g.entries?.[0]?.account.back).toBe("b-t35");
    expect(g.dropins?.[0]?.account.back).toBe("b-t35");
  });

  it("toIntent：意向者 avatarUrl/back 随列表透传（意向卡铺意向者卡背的原料）", async () => {
    api.apiListIntents.mockResolvedValue([
      {
        account: mkPerson(12, "小张"),
        slots: ["wd"],
        frequency: 1,
        note: null,
        updated_at: "2026-10-06T10:00:00+08:00",
        invited: false,
        known: false,
      },
    ]);
    const { store } = await loadStore();
    await store.loadIntents();
    expect(store.intents[0]?.account.avatarUrl).toBe("/cosmetics/a-p12.webp");
    expect(store.intents[0]?.account.back).toBe("b-t35"); // 偶数 id 造的荣誉款卡背
  });
});

describe("liveGame（live 入口页冷启动分发）", () => {
  it("账开（live_opened）而簿 state 仍 open 的 manual_lock 局也算进行中：reload 不弹回约球页", async () => {
    api.apiListGames.mockResolvedValue([
      mkView({ id: 1, status: "open", manual_lock: true, live_opened: true }),
    ]);
    const { store } = await loadStore();
    await store.loadGames();
    expect(store.liveGame?.id).toBe(1);
  });

  it("games 无命中时回落 myGames；status=live 照常命中", async () => {
    api.apiListGames.mockResolvedValue([]);
    api.apiMyGames.mockResolvedValue([mkView({ id: 2, status: "live" })]);
    const { store } = await loadStore();
    await store.loadGames();
    await store.loadMine();
    expect(store.liveGame?.id).toBe(2);
  });

  it("普通 open 局（未锁未订未开账）：不命中", async () => {
    api.apiMyGames.mockResolvedValue([
      mkView({ id: 3, status: "open", live_opened: false }),
    ]);
    const { store } = await loadStore();
    await store.loadMine();
    expect(store.liveGame).toBeNull();
  });

  it("已散场局（done + live_opened + ended）：不命中——LiveState 行存续 live_opened 恒真，收摊后不被 liveGame 原路接回（2.6 §4.1-3/§5-2）", async () => {
    api.apiListGames.mockResolvedValue([
      mkView({ id: 4, status: "done", live_opened: true, ended: true }),
    ]);
    const { store } = await loadStore();
    await store.loadGames();
    expect(store.liveGame).toBeNull();
  });
});
