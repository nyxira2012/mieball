/* 球局 store（1.2 接线重写）：真后端局簿+意向簿的前端业务态。
   - api 层线上形状（snake）→ 本 store 的 Game/Intent（camel）映射收在 toGame/toIntent 单点；
   - 写动作成功 toast 仍在 store（文案单一源），失败一律抛 ApiError 由调用方 errText；
   - quit/cancel/invite 后端只回 {ok:true}，名单/标记的回填在 store 内补拉（refresh/loadIntents）；
   - 硬约束：动作只改状态与弹出文案 —— 不做路由跳转、不直接调 uni.*（导航由页面层做）。 */
import { computed, ref } from "vue";
import { defineStore } from "pinia";
import {
  apiBookCourt,
  apiCancelGame,
  apiClearBooking,
  apiDeleteIntent,
  apiEditGame,
  apiGameDetail,
  apiGameFee,
  apiGameFeePreview,
  apiInviteUser,
  apiJoinGame,
  apiListGames,
  apiListIntents,
  apiLockGame,
  apiMyGames,
  apiMyIntent,
  apiPlaylog,
  apiPublishGame,
  apiQuitGame,
  apiRestoreGame,
  apiSaveIntent,
  type GameViewApi,
  type IntentViewApi,
} from "@/api/games";
import type {
  EditGameInput,
  Game,
  Intent,
  MyIntent,
  PublishGameInput,
} from "@/api/types";
import { ApiError } from "@/api/http";
import { deadRowKind, liveOngoing } from "@/utils/format";
import { useUiStore } from "./ui";

/** game_view（线上 snake）→ Game（store camel）：唯一映射点 */
function toGame(v: GameViewApi): Game {
  return {
    id: v.id,
    name: v.name,
    organizer: { ...v.organizer },
    startAt: v.start_at,
    endAt: v.end_at,
    deadlineAt: v.deadline_at,
    venueName: v.venue_name,
    venueAddress: v.venue_address,
    minPlayers: v.min_players,
    maxPlayers: v.max_players,
    visibility: v.visibility,
    scoring: v.scoring,
    rotation: v.rotation,
    scoreRule: v.score_rule,
    manualLock: v.manual_lock,
    courts: v.courts,
    feeTotal: v.fee_total,
    bill: v.bill
      ? {
          feeTotal: v.bill.fee_total,
          perHead: v.bill.per_head,
          heads: v.bill.heads,
          myShare: v.bill.my_share,
          myGuestCount: v.bill.my_guest_count,
        }
      : null,
    status: v.status,
    unlocked: v.unlocked,
    joinable: v.joinable,
    liveOpened: v.live_opened,
    ended: v.ended,
    heads: v.heads,
    slotsLeft: v.slots_left,
    perHead: v.per_head,
    forced: v.forced,
    entries: v.entries?.map((e) => ({
      account: { ...e.account },
      bring: e.bring,
      standing: e.standing,
      waitSeq: e.wait_seq,
    })),
    my: v.my
      ? {
          isOrganizer: v.my.is_organizer,
          myEntry: v.my.my_entry && {
            bring: v.my.my_entry.bring,
            standing: v.my.my_entry.standing,
            waitSeq: v.my.my_entry.wait_seq,
          },
          invited: v.my.invited,
          // 能力旗（闸旗同源）：窗口显隐直读，页面不再拿派生 status 拼
          canBook: v.my.can_book,
          canFillFee: v.my.can_fill_fee,
          canLock: v.my.can_lock,
        }
      : undefined,
  };
}

/** intent_view → Intent */
function toIntent(v: IntentViewApi): Intent {
  return {
    account: { ...v.account },
    slots: [...v.slots],
    frequency: v.frequency,
    note: v.note,
    updatedAt: v.updated_at,
    invited: v.invited,
    known: v.known,
  };
}

export const useGameStore = defineStore("game", () => {
  const ui = useUiStore();
  /* 数据：找局打 / 我的局 / 详情页当前局（链接直达的局可能不在列表里，弹层经 findGame 统一取） */
  const games = ref<Game[]>([]);
  const myGames = ref<Game[]>([]);
  const current = ref<Game | null>(null);
  const intents = ref<Intent[]>([]);
  const myIntent = ref<MyIntent | null>(null);
  /** 打球记录（2.6）：后端已按散场倒序，整袋落位不重排；logs 页消费 */
  const playlog = ref<{ games: Game[]; matchesCount: number } | null>(null);
  /** 读/写请求在途标记（A2 加载态；页面据此显示等待提示） */
  const loading = ref(false);

  async function track<T>(fn: () => Promise<T>): Promise<T> {
    loading.value = true;
    try {
      return await fn();
    } finally {
      loading.value = false;
    }
  }

  /** 局回填：两个列表里同 id 的行整体替换；详情页当前局同步换新（写动作后视图刷新的单一入口） */
  function upsert(g: Game): void {
    const put = (list: Game[]): void => {
      const i = list.findIndex((x) => x.id === g.id);
      if (i >= 0) list[i] = g;
    };
    put(games.value);
    put(myGames.value);
    if (current.value?.id === g.id) current.value = g;
  }

  /** 弹层/详情统一取局：current 优先（链接直达），再两个列表 */
  function findGame(id: number): Game | null {
    if (current.value?.id === id) return current.value;
    return (
      games.value.find((x) => x.id === id) ??
      myGames.value.find((x) => x.id === id) ??
      null
    );
  }

  /* ---- 读 ---- */

  /** 游客静默闸（「我的」数据族单一出口）：游客没有「我的局/我的意向/打球记录」，
      401 no_identity 归静默空，其余错误照抛由页面 errText toast——各页面不再
      各写一遍特判（页面只管 toast）。bills store 的 isDemo 前置空视图是同族先例 */
  function guestQuiet(fn: () => Promise<void>): Promise<void> {
    return fn().catch((e) => {
      if (!(e instanceof ApiError && e.code === "no_identity")) throw e;
    });
  }

  async function loadGames(): Promise<void> {
    games.value = (await track(apiListGames)).map(toGame);
  }

  async function loadMine(): Promise<void> {
    await guestQuiet(async () => {
      myGames.value = (await track(apiMyGames)).map(toGame);
    });
  }

  /** 详情（终态照常 200；不存在抛 game_not_found 由页面转说明页） */
  async function loadDetail(id: number): Promise<Game> {
    const g = toGame(await track(() => apiGameDetail(id)));
    current.value = g;
    return g;
  }

  /** 操作后单局重拉（quit/invite 这类只回 ok 的动作靠它回填名单） */
  async function refresh(id: number): Promise<Game> {
    const g = toGame(await track(() => apiGameDetail(id)));
    upsert(g);
    return g;
  }

  async function loadIntents(): Promise<void> {
    intents.value = (await track(apiListIntents)).map(toIntent);
  }

  async function loadMyIntent(): Promise<void> {
    await guestQuiet(async () => {
      const v = await track(apiMyIntent);
      myIntent.value = v
        ? { slots: [...v.slots], frequency: v.frequency, note: v.note }
        : null;
    });
  }

  /** 打球记录（2.6）：整袋落位（toGame 映射单点），排序真值在后端 */
  async function loadPlaylog(): Promise<void> {
    await guestQuiet(async () => {
      const v = await track(apiPlaylog);
      playlog.value = {
        games: v.games.map(toGame),
        matchesCount: v.matches_count,
      };
    });
  }

  /* ---- 局簿写动作 ---- */

  async function publishGame(input: PublishGameInput): Promise<Game> {
    const g = toGame(await track(() => apiPublishGame(input)));
    games.value.unshift(g); // 后端列表 id 倒序，新局排头
    upsert(g);
    // 4.1：默认「跟我打过的人」档冷启动靠链接，发布提示带一句引导
    ui.toast(
      input.visibility === "played"
        ? "局已发布 · 名单头一个就是你 · 这个档位下，球友主要通过你转的链接看到这个局"
        : "局已发布 · 名单头一个就是你，点局上的 ⤴ 分享到群里拉人",
    );
    return g;
  }

  async function editGame(id: number, input: EditGameInput): Promise<Game> {
    const before = findGame(id);
    const g = toGame(await track(() => apiEditGame(id, input)));
    upsert(g);
    // A3 上限放宽反馈：转正人数 = 前后正式名单差，剩余候补照实说（上限没放宽就是普通改局）
    const formal = (x: Game | null): number =>
      x?.entries?.filter((e) => e.standing === "formal").length ?? 0;
    const waitN =
      g.entries?.filter((e) => e.standing === "waitlist").length ?? 0;
    const moved = Math.max(0, formal(g) - formal(before));
    ui.toast(
      moved
        ? waitN
          ? `局已改好 · 上限放宽，候补转正，仍剩 ${waitN} 人满员（建议下次再参加）`
          : "局已改好 · 上限放宽，候补已全部转正"
        : "局已改好 · 名单里的人看到的就是新信息",
    );
    return g;
  }

  async function joinGame(id: number, bring: number): Promise<Game> {
    const g = toGame(await track(() => apiJoinGame(id, bring)));
    upsert(g);
    // 整行装不下时后端落候补也 200——文案按返回名单分支（4.3 候补提示，规格原句）
    ui.toast(
      g.my?.myEntry?.standing === "waitlist"
        ? "坑不够，已为你排候补"
        : bring
          ? `已加入 · 带了 ${bring} 人（共占 ${1 + bring} 坑）`
          : "已加入 · 这局进了「我的局」",
    );
    return g;
  }

  async function quitGame(id: number): Promise<void> {
    await track(() => apiQuitGame(id));
    ui.toast("已退出 · 名单里少了你");
    await refresh(id); // 名额释放/候补递补回填
  }

  async function cancelGame(id: number): Promise<void> {
    await track(() => apiCancelGame(id));
    const drop = (list: Game[]): void => {
      const i = list.findIndex((x) => x.id === id);
      if (i >= 0) list.splice(i, 1);
    };
    drop(games.value);
    drop(myGames.value);
    if (current.value?.id === id) current.value = null;
    ui.toast("局已撤下 · 报名的球友「我的局」里同步消失"); // 订场退订提醒由 ConfirmSheet 的提示行负责
  }

  async function lockGame(id: number): Promise<Game> {
    const g = toGame(await track(() => apiLockGame(id)));
    upsert(g);
    ui.toast("已锁定必打 · 到截止不再因人数不足终止，最少人数要求作废");
    return g;
  }

  async function bookCourt(
    id: number,
    courts: string[],
    feeTotal: number,
  ): Promise<Game> {
    const g = toGame(await track(() => apiBookCourt(id, courts, feeTotal)));
    upsert(g);
    ui.toast(
      `已订场 · ${courts.join("、")}（${courts.length} 片）· 这局必开，费用已落定`,
    );
    return g;
  }

  async function clearBooking(id: number): Promise<Game> {
    const g = toGame(await track(() => apiClearBooking(id)));
    upsert(g);
    ui.toast(
      g.manualLock
        ? "订场登记已清空 · 手动锁定保留，这局仍必打"
        : "订场登记已清空 · 局回到未订场，费用未定，截止照常判人数",
    );
    return g;
  }

  /** 补填确认步定值（1.3 §4.5「将按人均 X 元向 N 人出账」）：纯现算，不落库不 toast。
      snake→camel 在此收口（映射规约同 toGame），组件不吃线上形状 */
  async function feePreview(
    id: number,
    amount: number,
  ): Promise<{ heads: number; perHead: number; organizerShare: number }> {
    const v = await track(() => apiGameFeePreview(id, amount));
    return {
      heads: v.heads,
      perHead: v.per_head,
      organizerShare: v.organizer_share,
    };
  }

  /** 补填总价（散场后从未填价的局）：>0 当场出账、=0 只定值；价格就此定死 */
  async function setFee(id: number, feeTotal: number): Promise<Game> {
    const g = toGame(await track(() => apiGameFee(id, feeTotal)));
    upsert(g);
    ui.toast(
      feeTotal > 0
        ? `总价已定 · 账已出，按 ${g.bill?.heads ?? g.heads} 份摊，账单里见`
        : "费用已定为 ¥0 · 免费场，不出账",
    );
    return g;
  }

  async function restoreGame(id: number): Promise<Game> {
    const g = toGame(await track(() => apiRestoreGame(id)));
    upsert(g);
    ui.toast("局已恢复 · 待处置：决定必定开局还是撤局后回到正常列表");
    return g;
  }

  async function inviteUser(gameId: number, accountId: number): Promise<void> {
    const name = intents.value.find((i) => i.account.id === accountId)?.account
      .nickname;
    await track(() => apiInviteUser(gameId, accountId));
    ui.toast(
      name
        ? `已邀请 ${name} · 局已出现在 ta 的「我的局」`
        : "已邀请 · 局已出现在 ta 的「我的局」",
    );
    await loadIntents(); // 已邀标记与排序刷新（排序单一源=后端：未邀在前、已邀靠后，前端保持该序）
  }

  /* ---- 意向簿 ---- */

  async function saveIntent(
    slots: string[],
    frequency: number,
    note: string,
  ): Promise<Intent> {
    if (!slots.length) {
      ui.toast("至少选一个时段");
      throw new Error("intent_slots_empty"); // 调用方（表单）应先拦，此处兜底
    }
    const had = !!myIntent.value;
    const v = await track(() => apiSaveIntent(slots, frequency, note));
    const it = toIntent(v);
    myIntent.value = {
      slots: it.slots,
      frequency: it.frequency,
      note: it.note,
    };
    ui.toast(
      had ? "意向已更新 · 想改随时改" : "意向已留下 · 组局的人凑人时会看见你",
    );
    return it;
  }

  async function delIntent(): Promise<void> {
    await track(() => apiDeleteIntent());
    myIntent.value = null;
    ui.toast("意向已删 · 随时可以再留");
  }

  /** 进行中的局（live 入口页冷启动分发在用；真局来自后端派生态）。manual_lock 局截止前
      簿 state 仍 open——账开即现场（2.5 §4.4），liveOpened 定值一并算数，现场页 reload
      才不会被 onLoad 弹回约球页。同时在办多个挑最近开打的（4.1-3）：开账时刻局簿
      没有，startAt 是可用近似。已散场局（ended）不算在办（2.6 §4.1-3/§5-2）：LiveState
      行存续使 live_opened 恒 true、拦不住 done——不排除则收摊后被 liveGame 原路接回，
      完成钮失效；回看入口由 打球记录→局详情→战报子页 承接。 */
  const liveGame = computed((): Game | null => {
    const pick = (list: Game[]): Game | null => {
      const on = list.filter(liveOngoing);
      return on.length
        ? on.reduce((a, b) => (b.startAt > a.startAt ? b : a))
        : null;
    };
    return pick(games.value) ?? pick(myGames.value);
  });

  /** 登记口径（5.1 单一源，我的页与登记页同消费）：myGames 去死局行；打完 = done */
  const mySignups = computed(() =>
    myGames.value.filter((g) => deadRowKind(g) === null),
  );
  const myDone = computed(() =>
    mySignups.value.filter((g) => g.status === "done"),
  );

  return {
    games,
    myGames,
    current,
    intents,
    myIntent,
    loading,
    liveGame,
    mySignups,
    myDone,
    playlog,
    findGame,
    loadGames,
    loadMine,
    loadDetail,
    refresh,
    loadIntents,
    loadMyIntent,
    loadPlaylog,
    publishGame,
    editGame,
    joinGame,
    quitGame,
    cancelGame,
    lockGame,
    bookCourt,
    clearBooking,
    feePreview,
    setFee,
    restoreGame,
    inviteUser,
    saveIntent,
    delIntent,
  };
});
