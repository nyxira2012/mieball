/* 现场 store（2.3 批5a 写链·全切后端）：现场态真值=后端总账，本 store 只做
   guard + 编排 + toast——写动作统一「组载荷（base 号取 liveView）→ api → 响应视图
   applyLiveView 落地」；409 stale 携视图对表（toast「现场已更新」）；断网/他错走
   errText（网络错文案「网络不给力，请稍后再试」）并把本地预变回滚成所持视图。
   发牌算法仍在前端 rotate.ts（总账把关）：到场/取消/开账后够人的空片本地算完
   apiLiveDeal 上报；「排下一场」由确认响应视图驱动（回流补位真值在后端）。
   积分不再本地落账（settleElo 退役到组件预览）；确认响应的 elo_rows 随视图持有。
   待确认窗按片多值：settling Record（courtId→来源）由视图 pending 驱动，
   closeSettle 纯前端关窗（记 hide 位，片退出 pending 自动解除）。
   遗留本地路（后端无对应端点，批6/后续切真）：addGuests/subFirst/removeFromRoster/
   setRuleScore/endLive（散场清扫流批6 重造）与空降入册（arriveMe 的 dropin 支）。
   硬约束：不触碰任何 uni.*；名册行 id 是写动作靶位（与 queue/片位同键），
   账号口径（isAdmin/myRound）按 view.players.accountId 匹配 U.me。 */
import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { U } from "@/api";
import { ApiError, errText } from "@/api/http";
import {
  apiLiveCancel,
  apiLiveCheck,
  apiLiveClear,
  apiLiveDeal,
  apiLivePoint,
  apiLiveRules,
  apiLiveSetAdmin,
  apiLiveSettleConfirm,
  apiLiveSettleOpen,
  apiLiveStart,
  apiLiveSwap,
  apiLiveTempo,
  apiLiveUndo,
  apiLiveUnsetAdmin,
  apiLiveView,
  toLiveView,
  type LiveViewer,
} from "@/api/live";
import type {
  CheckInAction,
  CheckStatus,
  DealCourt,
  FeedEvent,
  Game,
  LedgerRow,
  LiveCourt,
  LiveRulesInput,
  LiveState,
  LiveView,
  LiveViewApi,
  PendingOrigin,
  Person,
  RotationRules,
  User,
} from "@/api/types";
import { DRESS_RANGES } from "@/utils/chibi";
import {
  RANK_INIT,
  activePlayers,
  courtCount,
  courtSize,
  fillAllCourts,
  pById,
  usedCourts,
} from "@/utils/rotate";
import { recommend } from "@/utils/recommend";
import { isOrg } from "@/utils/format";
import { toIso } from "@/utils/time";
import { useGameStore } from "./game";
import { useUiStore } from "./ui";
import { useUserStore } from "./user";

/** 访客 id 单调发号（批1 刺客：Math.random 撞号会让两位访客在 roster/swap 里互相串线） */
let guestSeq = 0;

/** 「算到场」谓词单一源（候场条状态文案与二维码浮层在场人数共用）：
    ok 正常 / late 迟到已到 / join 中途加入；absent 未到、left 早退不算 */
export const isArrived = (c?: CheckStatus): boolean =>
  c === "ok" || c === "late" || c === "join";

/** 每边满员口径单一源（双打 2 / 单打 1）：subFirst 缺位判定与 CourtMatchCard 找替补入口共用 */
export const perSide = (singles: boolean): number => courtSize(singles) / 2;

/** 清场单点（早退/移出本地路共用）：把人从候场队和各片 A/B 同时清掉；在场资历一并注销 */
function clearFromPlay(L: LiveState, id: number): void {
  L.queue = L.queue.filter((x) => x !== id);
  L.courts.forEach((c) => {
    c.A = c.A.filter((x) => x !== id);
    c.B = c.B.filter((x) => x !== id);
  });
  const p = pById(L, id);
  if (p) {
    p.tenure = 0;
    p.courtSeq = undefined;
  }
}

/** 总账结构化事件句 → 中文句（契约§2 后端不产文案；句式与 2.2 动作处留痕同款）：
    view 按发生序追加、旧 feed 新到旧——reverse 适配 */
function feedSentences(events: FeedEvent[]): string[] {
  return events
    .map((e) =>
      e.kind === "swap"
        ? `${e.actor} 把 ${e.out} 换下 · ${e.in} 上`
        : e.kind === "set_admin"
          ? `组织者封 ${e.target} 为管理员`
          : `组织者收回了 ${e.target} 的管理员身份`,
    )
    .reverse();
}

/** 冷扫兜底局（现场态与局簿都没有时的最小 Game，applyLiveView 重建用）：
    组织者未知给 -1——viewer 两旗降级 false；ensureLive 先行后此路罕见 */
function stubGame(v: LiveView): Game {
  return {
    id: v.gameId,
    name: "现场",
    organizer: { id: -1, nickname: "—", chibi: {} },
    startAt: v.startedAt,
    endAt: "",
    deadlineAt: "",
    venueName: "",
    venueAddress: null,
    minPlayers: 0,
    maxPlayers: 0,
    visibility: "public",
    scoring: v.rules.scoring,
    rotation: "winner",
    scoreRule: "",
    manualLock: false,
    courts: null,
    feeTotal: null,
    status: "live",
    unlocked: false,
    joinable: false,
    heads: v.players.length,
    slotsLeft: 0,
    perHead: null,
    forced: false,
  };
}

export const useLiveStore = defineStore("live", () => {
  const ui = useUiStore();
  /** 进行中的现场态（视图重建产物；TabBar 的 LIVE 红点） */
  const live = ref<LiveState | null>(null);
  const hasLive = computed(() => !!live.value);

  /** 待确认窗按片多值（§4.3 多片同待确认是正常情况）：courtId（0 起）→ 窗来源；
      视图 courts[].status==='pending' 驱动、applyLiveView 同步维护。
      hide 位=纯前端关窗（closeSettle）：片仍 pending 但用户关了窗不重开，
      片退出 pending（确认/清零/撤分关窗）时自动解除 */
  const settling = ref<Record<number, { origin: PendingOrigin } | null>>({});
  const settleHidden = new Set<number>();

  /** 最近一次总账视图——写动作 base 号（totalSeq/片 courtSeq）与轮询对表的最近真值 */
  const liveView = ref<LiveView | null>(null);
  /** 散场后回看视图持有（ended 视图定格；回看 UI 批6 消费） */
  const recap = ref<LiveView | null>(null);

  /** settling 多值的降级单值读法（批5a 消费面：live.vue/EndSettleModal 单窗呈现）：
      片号最小的一片 + 该片当前比分快照；批5b UI 按片化后可退役 */
  const settlingOne = computed<{
    courtId: number;
    sa: number;
    sb: number;
    origin: PendingOrigin;
  } | null>(() => {
    const L = live.value;
    const hit = Object.entries(settling.value)
      .filter(([, v]) => v)
      .map(([k]) => Number(k))
      .sort((a, b) => a - b)[0];
    if (hit == null || !L) return null;
    const c = L.courts.find((x) => x.id === hit);
    return {
      courtId: hit,
      sa: c?.sa ?? 0,
      sb: c?.sb ?? 0,
      origin: settling.value[hit]!.origin,
    };
  });

  /** 我的名册行 id（键位修正：view.players 按 accountId 匹配 U.me；查无/无视图回落
      账号 id 兼本地路——mock 时代行 id 即账号 id） */
  function myRowId(): number {
    return (
      liveView.value?.players.find((p) => p.accountId === U.me.id)?.id ??
      U.me.id
    );
  }

  /** 管理员谓词（id 兼两键：视图行 id → 换账号对表；本地路直当账号 id）：
      PersonSheet/CheckinSheet/QueueSheet 徽章与全权判定共用 */
  function isAdmin(id: number): boolean {
    const row = liveView.value?.players.find((p) => p.id === id);
    const acc = row ? row.accountId : id;
    const admins = liveView.value?.admins ?? live.value?.admins ?? [];
    return acc != null && admins.includes(acc);
  }

  /** 现场权限单一源（2.2 §4.7）：组织者 ∨ 被封管理员 = 全权（同一套手柄）；
      视图时代读映射派生旗（toLiveView 按 viewer 算好），无视图回落本地判 */
  const isFullPower = computed(() => {
    if (liveView.value) return liveView.value.isFullPower;
    const L = live.value;
    return !!L && (isOrg(L.g) || isAdmin(U.me.id));
  });

  /** 封存闸（§4.14 现场封存）：endedAt 有值=已散场，收权动作一律拒——
      所有 needFull 检查处与 setCheck/togglePerson 的自报免检路径共用；
      后端散场后写一律拒 live_ended，这里是前置拦截 */
  function sealGate(): boolean {
    if (live.value?.endedAt) {
      ui.toast("现场已散 · 不能再操作");
      return false;
    }
    return true;
  }

  /** 越权拦截（规格 B1 总账把关；后端 live_forbidden 兜底同一句） */
  function needFull(): boolean {
    if (!sealGate()) return false;
    if (isFullPower.value) return true;
    ui.toast("请找组织者或管理员");
    return false;
  }
  /** 组织者独占（§4.6；后端 organizer_only 兜底同句） */
  function needOrg(): boolean {
    if (!sealGate()) return false;
    const L = live.value;
    if (L && isOrg(L.g)) return true;
    ui.toast("只有组织者能做");
    return false;
  }

  /** 散场权（§4.14 组织者独占 + 兜底）：组织者已标「早退」离场时管理员可代收；
      视图时代组织者名册行按 accountId 找 */
  const canEndLive = computed(() => {
    const L = live.value;
    const v = liveView.value;
    if (!L) return false;
    if (v)
      return (
        v.isOrganizer ||
        (v.isFullPower &&
          v.players.find((p) => p.accountId === L.g.organizer.id)?.check ===
            "left")
      );
    return (
      isOrg(L.g) ||
      (isAdmin(U.me.id) && pById(L, L.g.organizer.id)?.check === "left")
    );
  });

  /** 战报 feed（unshift 新到旧）：句子由视图结构化事件拼好（feedSentences 单点） */
  function feedPush(sentence: string): void {
    live.value?.feed.unshift(sentence);
  }

  /** 推荐快照（2.4 §4.2：总账算好随时可取；RulesSheet 消费） */
  const advice = computed(() => {
    const L = live.value;
    return L
      ? recommend(L.rules.singles, activePlayers(L), courtCount(L))
      : null;
  });

  /** 我还有几轮上场（2.1 §3 · 键位修正：队列存行 id，先换回我的行）：
      ceil((每片人数 × 空片数 + 我的队列位 + 1) / 每片人数) */
  const myRound = computed<number | null>(() => {
    const L = live.value;
    if (!L) return null;
    const idx = L.queue.indexOf(myRowId());
    if (idx < 0) return null;
    const size = courtSize(L.rules.singles);
    const empty = L.courts.filter((c) => !c.A.length && !c.B.length).length;
    return Math.ceil((size * empty + idx + 1) / size);
  });

  /** 按片找（记分族动作的定位口径；片序 0 起） */
  function courtOf(courtId: number): LiveCourt | undefined {
    return live.value?.courts.find((c) => c.id === courtId);
  }

  /** 建一片空片（差人卡呈现；格式跟当前规则） */
  function mkCourt(L: LiveState, idx: number): LiveCourt {
    return {
      id: idx,
      name: L.g.courts?.[idx] ?? `${idx + 1}号`,
      singles: L.rules.singles,
      A: [],
      B: [],
      sa: 0,
      sb: 0,
      streakA: 0,
      streakB: 0,
    };
  }

  /* ─────── 写链公共件：base 号 / 统一发送 / 发牌上报 ─────── */

  /** 片级写的 base 号对（动全场只带总号） */
  function seqs(courtNo?: number): {
    baseTotalSeq: number;
    baseCourtSeq: number;
  } {
    const v = liveView.value;
    return {
      baseTotalSeq: v?.totalSeq ?? 0,
      baseCourtSeq: courtNo != null ? (v?.courtSeqs[courtNo] ?? 0) : 0,
    };
  }

  /** 统一发送（写动作唯一通道）：api → 响应即最新视图 → applyLiveView 落地；
      - 409 两码（live_stale_total/court）携视图 → applyStaleView 对表 + toast「现场已更新」；
      - 其余错误走 errText（断网「网络不给力，请稍后再试」/后端把关句），
        并重放所持视图把本地预变（发牌预填等）回滚——下一拍轮询兜底。
      返回是否成功（调用方据此决定后续编排与 toast） */
  async function writeAction(
    gameId: number,
    run: () => Promise<LiveViewApi>,
    onDone?: () => void,
  ): Promise<boolean> {
    try {
      const raw = await run();
      applyLiveView(toLiveView(raw, viewerCtx(gameId)));
      onDone?.();
      return true;
    } catch (e) {
      if (applyStaleView(e)) {
        ui.toast("现场已更新");
        return false;
      }
      ui.toast(errText(e));
      if (liveView.value) applyLiveView(liveView.value); // 回滚本地预变
      return false;
    }
  }

  /** 发牌上报（发牌算法在前端，总账把关）：本地把空片补满 → 新填的片组载荷上报；
      无片可填返 false 不发请求。到场/取消/开账/改单双打后的自动补牌都走这里 */
  async function maybeDeal(gid: number): Promise<boolean> {
    const L = live.value;
    if (!L || !liveView.value) return false;
    const emptyBefore = new Set(
      L.courts.filter((c) => !c.A.length && !c.B.length).map((c) => c.id),
    );
    fillAllCourts(L);
    const deals: DealCourt[] = L.courts
      .filter((c) => emptyBefore.has(c.id) && (c.A.length || c.B.length))
      .map((c) => ({ courtNo: c.id + 1, a: [...c.A], b: [...c.B] }));
    if (!deals.length) return false;
    return writeAction(gid, () =>
      apiLiveDeal(gid, deals, liveView.value!.totalSeq),
    );
  }

  /* ─────── 开账与守门 ─────── */

  /** 开始打球（后端开账路）：apiLiveStart（幂等——已开账直接回视图）→ 视图落地 →
      开场发牌（已够人的片本地算完上报；新开账全员未到通常为空拍）。
      签名沿旧（吃真局对象）——g 只取 id 与组织者（viewer 旗派生），名册展开归后端 */
  async function startLive(g: Game): Promise<string | null> {
    const msg = "球局开始 · 现场已点亮";
    try {
      const raw = await apiLiveStart(g.id);
      applyLiveView(
        toLiveView(raw, { myId: U.me.id, organizerId: g.organizer.id }),
      );
      startPolling(g.id);
    } catch (e) {
      if (applyStaleView(e)) {
        ui.toast("现场已更新");
        return null;
      }
      ui.toast(errText(e));
      return null;
    }
    await maybeDeal(g.id);
    ui.toast(msg);
    return msg;
  }

  /** 成员卡 → 名册 User（空降入册本地路用）：mock U 同 id 者直接借对象，否则造伪 User */
  function mkPlayer(p: Person): User {
    const known = Object.values(useUserStore().users).find(
      (x) => x.id === p.id,
    );
    if (known) return known;
    return {
      id: p.id,
      name: p.nickname,
      elo: RANK_INIT,
      play: 0,
      win: 0,
      month: 0,
      chibi: { ...p.chibi },
    };
  }

  /** 确保现场开的是目标局（跳转/深链/扫码直达共用的守门口径，后端总账路）：
      - 拉读 200 → applyLiveView + startPolling（散场视图不再轮询——定格回看）；
      - 404 live_not_found → 终态局（done/terminated/cancelled）拦「球局不存在或已结束」，
        否则走开账后端路（组织者；幂等）；
      - 同局已开 → 续轮询 + 先对一拍（不靠计时器等 3s）；已散场同局 → 拉定格回看，
        写入口由 sealGate 与后端 live_ended 拦（§4.2/§4.10）。 */
  async function ensureLive(id: number): Promise<void> {
    const cur = live.value;
    if (cur && cur.g.id === id) {
      if (!cur.endedAt) startPolling(id);
      void pollLiveView(id);
      return;
    }
    let raw: LiveViewApi;
    try {
      raw = await apiLiveView(id);
    } catch (e) {
      if (!(e instanceof ApiError) || e.code !== "live_not_found") {
        ui.toast(errText(e));
        return;
      }
      const gs = useGameStore();
      let g = gs.findGame(id);
      if (!g || !g.entries?.length) {
        try {
          g = await gs.loadDetail(id);
        } catch {
          ui.toast("球局不存在或已结束");
          return;
        }
      }
      if (["done", "terminated", "cancelled"].includes(g.status)) {
        ui.toast("球局不存在或已结束");
        return;
      }
      await startLive(g);
      return;
    }
    const view = toLiveView(raw, viewerCtx(id));
    applyLiveView(view);
    if (!view.ended) startPolling(id);
  }

  /** 造一位随行访客（addGuests 本地路；随机 chibi 引用 chibi.ts 单一源 DRESS_RANGES） */
  function mkGuest(name: string): User {
    return {
      id: 9000 + ++guestSeq,
      name,
      elo: RANK_INIT,
      play: 0,
      win: 0,
      month: 0,
      shadow: true,
      chibi: {
        skin: Math.floor(Math.random() * DRESS_RANGES.skin),
        hair: Math.floor(Math.random() * DRESS_RANGES.hair),
        hc: Math.floor(Math.random() * DRESS_RANGES.hc),
        shirt: Math.floor(Math.random() * DRESS_RANGES.shirt),
        face: Math.floor(Math.random() * DRESS_RANGES.face),
        acc: Math.floor(Math.random() * DRESS_RANGES.acc),
      },
    };
  }

  /** 出勤底账单点补笔（本地路）：只按 id 合并 patch */
  function touchLedger(id: number, patch: Partial<LedgerRow>): void {
    const row = live.value?.ledger.find((r) => r.id === id);
    if (row) Object.assign(row, patch);
  }

  /** 行是否在后端总账（视图行走后端写；空降/本地造的行走本地旧路） */
  function isViewRow(id: number): boolean {
    return !!liveView.value?.players.some((r) => r.id === id);
  }

  /** 到场四操作（后端路 + 本地遗留路）：
    - 视图行：apiLiveCheck（ok/late 归一、队尾口径全在后端镜像）→ 响应视图落地 →
      按落定态 toast → 到场支线 maybeDeal（够一片的人数本地算完上报）；
    - 本地行（空降/无视图）：沿 2.2 批2 本地口径（队尾/清场/底账/自动补片）。
    权限（§4.3）：代办他人收权；自己报到/早退随时可 */
  async function setCheck(id: number, st: CheckStatus): Promise<void> {
    const L = live.value;
    const p = L ? pById(L, id) : undefined;
    if (!L || !p) return;
    if (!sealGate()) return;
    if (id !== myRowId() && !needFull()) return;
    if (st !== "absent" && isViewRow(id)) {
      const act: CheckInAction = st; // 窄化进闭包（absent 只出不进——上面已挡）
      const gid = L.g.id;
      const ok = await writeAction(gid, () =>
        apiLiveCheck(gid, id, act, seqs().baseTotalSeq),
      );
      const row = liveView.value?.players.find((r) => r.id === id);
      if (!ok || !row) return;
      if (row.check === "left") {
        ui.toast(`${row.name} 早退 · 已记离场时刻`);
      } else if (isArrived(row.check)) {
        ui.toast(
          row.check === "late"
            ? `${row.name} 迟到 · 自动排到队尾等一轮`
            : row.check === "join"
              ? `${row.name} 中途加入 · 排到队尾`
              : `${row.name} 已到场 · 排进候场队`,
        );
        await maybeDeal(gid); // 到场驱动发牌（§4.1 够一片的人数就上片）
      }
      return;
    }
    /* ── 本地遗留路（空降行/无视图演示态；批6 切真时整段退役） ── */
    const was = p.check;
    if (st === "ok" || st === "late") {
      if (p.check === "left") st = "join";
      else if (
        st === "ok" &&
        p.check === "absent" &&
        Date.now() > new Date(L.g.startAt).getTime()
      )
        st = "late"; // 迟到口径：未到首报且已过开球时刻
    }
    if (st === "late") {
      p.check = "late";
      const i = L.queue.indexOf(id);
      if (i >= 0) L.queue.splice(i, 1);
      L.queue.push(id);
      ui.toast(`${p.name} 迟到 · 自动排到队尾等一轮`);
    } else if (st === "left") {
      p.check = "left";
      clearFromPlay(L, id);
      ui.toast(`${p.name} 早退 · 已记离场时刻`);
    } else if (st === "join") {
      p.check = "join";
      if (!L.queue.includes(id)) L.queue.push(id);
      ui.toast(`${p.name} 中途加入 · 排到队尾`);
    } else {
      const first = !isArrived(p.check);
      p.check = st;
      if (st === "ok") {
        if (first && !L.queue.includes(id)) L.queue.push(id);
        ui.toast(`${p.name} 已到场 · 排进候场队`);
      }
    }
    if (st === "left") {
      if (!p.leftAt) p.leftAt = toIso(new Date());
      touchLedger(id, { leftAt: p.leftAt });
      feedPush(`${p.name} 早退 · 已记离场时刻`);
    } else if (st !== "absent" && !p.arriveAt) {
      p.arriveAt = toIso(new Date());
      touchLedger(id, { arriveAt: p.arriveAt });
    }
    if ((st === "ok" || st === "late" || st === "join") && !isArrived(was)) {
      fillAllCourts(L);
    }
  }

  /** 移出名册（本地遗留路：后端无对应端点）——人从名册消失（对付远程扫码幽灵）：
      候场/各片全清，底账行保留只落 removedAt（留痕）；与早退的区别：早退还留在名册 */
  function removeFromRoster(id: number): void {
    if (!needFull()) return;
    const L = live.value;
    const p = L ? pById(L, id) : undefined;
    if (!L || !p) return;
    L.roster = L.roster.filter((x) => x.id !== id);
    clearFromPlay(L, id);
    touchLedger(id, { removedAt: toIso(new Date()) });
    feedPush(`${p.name} 被移出名册`);
    ui.toast(`${p.name} 被移出名册`);
  }

  /** 休息/连战/取消休息（§4.10；视图行走 apiLiveTempo，本地行沿旧路）：
      互斥与叠帐全在后端；toast 按响应视图落定态拼（共跳几轮/连战队首） */
  async function togglePerson(
    id: number,
    k: "skip" | "fire" | "unskip",
  ): Promise<void> {
    const L = live.value;
    const p = L ? pById(L, id) : undefined;
    if (!L || !p) return;
    if (!sealGate()) return;
    if (id !== myRowId() && !needFull()) return;
    if (isViewRow(id)) {
      const gid = L.g.id;
      const ok = await writeAction(gid, () =>
        apiLiveTempo(gid, id, k, seqs().baseTotalSeq),
      );
      if (!ok) return;
      const row = liveView.value!.players.find((r) => r.id === id)!;
      if (k === "unskip") ui.toast("取消休息 · 下轮照常");
      else if (k === "skip")
        ui.toast(
          row.skip > 1
            ? `已再跳一轮 · 共跳 ${row.skip} 轮`
            : "已设休息 · 轮到你时自动跳一轮",
        );
      else ui.toast(row.fire ? "连战 · 排到队首" : "取消连战");
      return;
    }
    /* ── 本地遗留路 ── */
    if (k === "unskip") {
      p.skip = 0;
      ui.toast("取消休息 · 下轮照常");
      return;
    }
    if (k === "skip") {
      if (p.fire) p.fire = false;
      p.skip = (p.skip ?? 0) + 1;
      ui.toast(
        p.skip > 1
          ? `已再跳一轮 · 共跳 ${p.skip} 轮`
          : "已设休息 · 轮到你时自动跳一轮",
      );
      return;
    }
    p.fire = !p.fire;
    if (p.fire) p.skip = 0;
    if (p.fire) {
      const i = L.queue.indexOf(id);
      if (i >= 0) {
        L.queue.splice(i, 1);
        L.queue.unshift(id);
      }
    }
    ui.toast(p.fire ? "连战 · 排到队首" : "取消连战");
  }

  /** 封管理员（§4.6 仅组织者；靶行须正式球友）：留痕句由视图 feed 回来，toast 本地拼 */
  async function setAdmin(id: number): Promise<void> {
    if (!needOrg()) return;
    const L = live.value;
    const p = L ? pById(L, id) : undefined;
    if (!L || !p || !liveView.value) return;
    const acc = liveView.value.players.find((r) => r.id === id)?.accountId;
    if (acc == null || liveView.value.admins.includes(acc)) return; // 访客当不了/已封静默幂等
    const gid = L.g.id;
    await writeAction(
      gid,
      () => apiLiveSetAdmin(gid, id, seqs().baseTotalSeq),
      () => ui.toast(`组织者封 ${p.name} 为管理员`),
    );
  }

  /** 撤管理员（§4.6 仅组织者）：留痕句由视图 feed 回来 */
  async function unsetAdmin(id: number): Promise<void> {
    if (!needOrg()) return;
    const L = live.value;
    const p = L ? pById(L, id) : undefined;
    if (!L || !p || !liveView.value) return;
    const acc = liveView.value.players.find((r) => r.id === id)?.accountId;
    if (acc == null || !liveView.value.admins.includes(acc)) return; // 不是管理员静默
    const gid = L.g.id;
    await writeAction(
      gid,
      () => apiLiveUnsetAdmin(gid, id, seqs().baseTotalSeq),
      () => ui.toast(`组织者收回了 ${p.name} 的管理员身份`),
    );
  }

  /** 扫码自签到（2.1·选项A）：名册没我（空降）→ 本地入册带「空降」标（后端无空降端点，
      遗留本地路；批6/后续切真）→ 统一走 setCheck 到场支线（视图行走后端）。
      现场没开或开的是别局 → ensureLive 先行；已结束的局被 ensureLive/sealGate 拦下 */
  async function arriveMe(gameId: number): Promise<string | null> {
    await ensureLive(gameId);
    const L = live.value;
    if (!L || L.g.id !== gameId || L.endedAt) return null; // ensureLive 已 toast 兜底
    let p = pById(L, myRowId());
    if (!p) {
      p = mkPlayer({ id: U.me.id, nickname: U.me.name, chibi: U.me.chibi });
      p.check = undefined; // 借回共享对象残留的 check 先重置，防幂等闸误拦
      p.dropin = true; // 空降标记全场看得到（§4.4）
      L.roster.push(p);
      if (!L.ledger.some((r) => r.id === U.me.id))
        L.ledger.push({ id: U.me.id, name: p.name, dropin: true }); // 同一人一行不累积
      feedPush(`${p.name} 空降 · 排到队尾`);
    }
    if (isArrived(p.check)) {
      ui.toast("你已经在场了");
      return null;
    }
    await setCheck(p.id, p.dropin ? "join" : "ok"); // 到场口径单点（归一/队尾/发排/toast）
    return "已到场 · 进候场区";
  }

  /* ─────── 记分链（片级写，base 号带双号） ─────── */

  /** 得分（§4.1）：后端落账时当即判到分——够线该片转待确认(origin='auto')，
      响应视图驱动 settling；待确认片冻结（§4.3，后端 court_frozen 兜底） */
  async function point(courtId: number, side: "a" | "b"): Promise<void> {
    if (settling.value[courtId]) return;
    const L = live.value;
    const c = courtOf(courtId);
    if (!L || !c || (!c.A.length && !c.B.length) || !liveView.value) return;
    const no = courtId + 1;
    const s = seqs(no);
    await writeAction(L.g.id, () =>
      apiLivePoint(L.g.id, no, side, s.baseTotalSeq, s.baseCourtSeq),
    );
  }

  /** 误记撤回一分（§4.5）：只撤该片最后得分方那 1 分——auto 窗撤到分线下自动关窗
      回在打、manual 窗只改比分不关窗（两路都由响应视图落定）；卡上入口对 pending 片
      由 UI 冻结（§4.3），窗内撤分（批5b UI）与在打撤走同一动作 */
  async function undoPoint(courtId: number): Promise<void> {
    const L = live.value;
    const c = courtOf(courtId);
    if (!L || !c || !liveView.value) return;
    const no = courtId + 1;
    const s = seqs(no);
    await writeAction(L.g.id, () =>
      apiLiveUndo(L.g.id, no, s.baseTotalSeq, s.baseCourtSeq),
    );
  }

  /** 记分已清零 · 重开一盘（§4.2 收权）：比分归 0:0、pending 作废回在打、人不下场 */
  async function clearScore(courtId: number): Promise<void> {
    const L = live.value;
    if (!L || !courtOf(courtId) || !needFull() || !liveView.value) return;
    const no = courtId + 1;
    const s = seqs(no);
    await writeAction(
      L.g.id,
      () => apiLiveClear(L.g.id, no, s.baseTotalSeq, s.baseCourtSeq),
      () => ui.toast("记分已清零 · 重开一盘"),
    );
  }

  /** 提前结算开窗（§4.4 收权）：转 pending(origin='manual')——窗开在视图，无成功
      toast（窗即反馈）；预选看视图 preselect */
  async function openSettle(courtId: number): Promise<void> {
    const L = live.value;
    const c = courtOf(courtId);
    if (!L || !c || (!c.A.length && !c.B.length) || !needFull()) return;
    const no = courtId + 1;
    const s = seqs(no);
    await writeAction(L.g.id, () =>
      apiLiveSettleOpen(L.g.id, no, s.baseTotalSeq, s.baseCourtSeq),
    );
  }

  /** 关结算窗不落账（纯前端关窗 §4.5 遮罩可关）：片仍 pending 但窗不再弹，
      片退出 pending 后 hide 位自动解除（applyLiveView 维护） */
  function closeSettle(courtId?: number): void {
    const ids =
      courtId != null ? [courtId] : Object.keys(settling.value).map(Number); // 无参=全关（降级单窗消费面等效）
    for (const id of ids) {
      if (settling.value[id]) {
        settleHidden.add(id);
        settling.value[id] = null;
      }
    }
  }

  /** 确认终局 · 排下一场（§4.6 出口 A，收权）：一本账原子在后端（战报+积分+回流补位），
      响应视图落地即「排好」——确认响应的 elo_rows 随视图持有（预览修正消费面批5b）。
      幂等闸：窗没开不落账（前端版；真值在后端——重放幂等回 200） */
  async function confirmSettle(
    courtId: number,
    winA: boolean,
    sa: number,
    sb: number,
  ): Promise<void> {
    if (!settling.value[courtId]) return;
    if (!needFull()) return;
    const L = live.value;
    if (!L || !liveView.value) return;
    const no = courtId + 1;
    const s = seqs(no);
    await writeAction(
      L.g.id,
      () =>
        apiLiveSettleConfirm(L.g.id, {
          courtNo: no,
          winnerSide: winA ? "a" : "b",
          scoreA: sa,
          scoreB: sb,
          baseTotalSeq: s.baseTotalSeq,
          baseCourtSeq: s.baseCourtSeq,
        }),
      () => ui.toast("积分落账 · 下一场已排好"),
    );
  }

  /** 取消对局（§4.7 出口 B，收权）：整场作废不计分，场上的人原样回流队首（后端）；
      片腾出来由本地重新发牌（发牌在前端）。先确认在页面层（A3） */
  async function cancelMatch(courtId: number): Promise<void> {
    const L = live.value;
    const c = courtOf(courtId);
    if (!L || !c || (!c.A.length && !c.B.length) || !needFull()) return;
    const gid = L.g.id;
    const no = courtId + 1;
    const n = c.A.length + c.B.length; // 出发时场上人数（文案）
    const s = seqs(no);
    const ok = await writeAction(
      gid,
      () => apiLiveCancel(gid, no, false, s.baseTotalSeq, s.baseCourtSeq),
      () => ui.toast(`对局作废 · 这场不计分 · 场上 ${n} 人回到队首`),
    );
    if (ok) await maybeDeal(gid); // §4.7 该片腾出来重新发牌
  }

  /** 紧急替补（本地遗留路：后端无独立端点——换人 apiLiveSwap 可覆盖同型操作）：
      候场队首可用者顶上该片人数少的一队，这局接着打完 */
  function subFirst(courtId: number): void {
    const L = live.value;
    const c = courtOf(courtId);
    if (!L || !c || !needFull()) return;
    const per = perSide(c.singles);
    if (c.A.length >= per && c.B.length >= per) {
      ui.toast("场上没有缺位");
      return;
    }
    const id = L.queue.find((qid) => {
      const p = pById(L, qid);
      return p && isArrived(p.check) && !p.skip;
    });
    if (id === undefined) {
      ui.toast("候场没人能顶 · 先拉人吧");
      return;
    }
    const short = c.A.length <= c.B.length ? c.A : c.B;
    L.queue.splice(L.queue.indexOf(id), 1);
    short.push(id);
    const p = pById(L, id)!;
    L.courtSeqNext += 1;
    p.courtSeq = L.courtSeqNext;
    p.tenure = 0;
    feedPush(`替补：${p.name} 顶上 · 比赛继续`);
    ui.toast("替补已顶上 · 比赛继续");
  }

  /** 换人（§4.9 球友开放，无 guard）：场上 outId 原位顶坑给候场 inId——
      视图行走后端（out 回队尾、feed 留名、pending 片冻结拒收全在总账）；
      本地行沿旧路（原位顶坑/资历注销） */
  async function swapPlayers(outId: number, inId: number): Promise<void> {
    const L = live.value;
    if (!L) return;
    if (isViewRow(outId)) {
      const gid = L.g.id;
      await writeAction(
        gid,
        () => apiLiveSwap(gid, outId, inId, seqs().baseTotalSeq),
        () => ui.toast("已换人 · 对阵重排"),
      );
      return;
    }
    /* ── 本地遗留路 ── */
    const court = L.courts.find(
      (c) => c.A.includes(outId) || c.B.includes(outId),
    );
    if (!court) return; // out 不在场上：无坑可换
    const side = court.A.includes(outId) ? "A" : "B";
    court[side][court[side].indexOf(outId)] = inId; // 原位顶坑
    const j = L.queue.indexOf(inId);
    if (j >= 0) L.queue.splice(j, 1);
    L.queue.push(outId); // 换下排队尾（§0.2 裁定）
    const outP = pById(L, outId);
    if (outP) {
      outP.tenure = 0;
      outP.courtSeq = undefined;
    }
    const inP = pById(L, inId);
    if (inP) {
      L.courtSeqNext += 1;
      inP.courtSeq = L.courtSeqNext;
      inP.tenure = 0;
    }
    feedPush(
      `${U.me.name} 把 ${outP?.name ?? "?"} 换下 · ${inP?.name ?? "?"} 上`,
    );
    ui.toast("已换人 · 对阵重排");
  }

  /** 带访客（本地遗留路：后端无对应端点）——底账加行挂担保人（§4.14 访客谁带的） */
  function addGuests(count: number, name: string, introducer: User): void {
    const L = live.value;
    if (!L || count <= 0 || !needFull()) return;
    for (let i = 0; i < count; i++) {
      const g = mkGuest(
        !name
          ? `${introducer.name.slice(0, 2)}的球友`
          : count > 1
            ? `${name}·${i + 1}`
            : name,
      );
      g.check = "join";
      L.roster.push(g);
      L.queue.push(g.id); // 队尾
      L.ledger.push({
        id: g.id,
        name: g.name,
        shadow: true,
        guarantor: introducer.name,
      });
    }
    ui.toast(`已带 ${count} 位访客 · 进候场区`);
  }

  /** 改分制（本地遗留路：后端 rules 端点不带 scoring——分制复用局列，裁决 Q1；
      改局归 3.2 改局链，本动作待后端定夺后切真） */
  function setRuleScore(v: number): void {
    const L = live.value;
    if (!L || !needFull()) return;
    L.g.scoring = v;
    ui.toast(`分制已改为 ${v} 分 · 当场生效`);
  }

  /** 改轮换四件套（§4.7 收权，视图路）：点选即生效、在打对局照旧打完；
      组合回落/连庄口径归总账；换单双打后空片重算发牌（§5 边界：2 人即开赛） */
  async function setRules(patch: Partial<RotationRules>): Promise<void> {
    const L = live.value;
    if (!L || !needFull() || !liveView.value) return;
    const input: LiveRulesInput = {};
    if (patch.singles !== undefined) input.doubles = !patch.singles;
    if (patch.down !== undefined) input.down = patch.down;
    if (patch.pairing !== undefined) input.pairing = patch.pairing;
    if (patch.champCap !== undefined) input.streakMax = patch.champCap;
    const gid = L.g.id;
    const ok = await writeAction(
      gid,
      () => apiLiveRules(gid, input, seqs().baseTotalSeq),
      () => ui.toast("规则已更新 · 下一场起按新规"),
    );
    if (ok && patch.singles !== undefined) await maybeDeal(gid);
  }

  /** 场地输入（2.1 顶条）：本地解析校验（至少 1 片且 ≥ 非空片数）→ 片数上报
      （apiLiveRules courtsCount；缩片先撤空闲片归总账）；场地名本地挂供重建沿用 */
  async function setCourtsInput(text: string): Promise<boolean> {
    const L = live.value;
    if (!L || !needFull() || !liveView.value) return false;
    const parts = text
      .split(/[、,，\s]+/)
      .map((s) => s.trim())
      .filter((s) => /^\d+号?$/.test(s))
      .map((s) => (s.endsWith("号") ? s : `${s}号`));
    const need = usedCourts(L);
    if (parts.length < 1) {
      ui.toast("至少要有 1 片场地");
      return false;
    }
    if (parts.length < need) {
      ui.toast("在打 + 待开的场地不能收");
      return false;
    }
    const gid = L.g.id;
    const ok = await writeAction(gid, () =>
      apiLiveRules(gid, { courtsCount: parts.length }, seqs().baseTotalSeq),
    );
    if (!ok) return false;
    const cur = live.value; // writeAction 已整树重建现场态：挂名必须落最新对象
    if (!cur) return false;
    cur.g.courts = parts; // 场地名本地挂（视图重建沿用本地 g，片名即用户输入）
    cur.courts.forEach((c, i) => {
      c.name = parts[i] ?? `${i + 1}号`;
    });
    ui.toast(`场地已更新：${parts.join("、")}`);
    return true;
  }

  /** 自动排阵（收权）：补所有空片（多片同时要人按片号先后）——发牌算法在前端 */
  async function autoDeal(): Promise<void> {
    const L = live.value;
    if (!L || !needFull() || !liveView.value) return;
    await maybeDeal(L.g.id);
    ui.toast("牌已发 · 按当前规则排好");
  }

  /** 散场两道闸（§4.14 旧路保留；清扫流批6 重造）：①权限（canEndLive）②在打防线 */
  function endGate(): boolean {
    const L = live.value;
    if (!L || !canEndLive.value) {
      ui.toast("只有组织者能收局");
      return false;
    }
    if (L.courts.some((c) => c.A.length || c.B.length)) {
      ui.toast("还有片在打 · 先收局或作废");
      return false;
    }
    return true;
  }

  /** 散场收局（本地遗留路；批6 重造为清扫链+apiLiveEnd）：endedAt 落 → 底账定格
      → live 态保留（回看消费面批6）。已封存直调不重放 */
  function endLive(): void {
    const L = live.value;
    if (!L || L.endedAt || !endGate()) return;
    const at = toIso(new Date());
    L.endedAt = at;
    for (const p of L.roster)
      if (isArrived(p.check) && !p.leftAt) {
        p.leftAt = at;
        touchLedger(p.id, { leftAt: at });
      }
    feedPush("现场已散 · 二维码失效");
    ui.toast("已散场 · 底账定格");
  }

  /** 名册按找（视图层 byId 的共享口径） */
  function byId(id: number): User {
    const L = live.value;
    return (
      (L ? pById(L, id) : undefined) ?? {
        id: -1,
        name: "—",
        elo: 0,
        play: 0,
        win: 0,
        month: 0,
        chibi: {},
      }
    );
  }

  /* ─────── 读链（总账视图 → 本地重建 · 轮询 · 409 对表） ─────── */

  /** viewer 上下文（批4a 裁定：view 不带身份块，toLiveView 映射时派生两旗）：
      本人在 session（过渡期写到 U.me 位）、组织者在局簿——现场态或局缓存先找，
      都没有给 -1（游客/冷扫降级：两旗 false） */
  function viewerCtx(gameId: number): LiveViewer {
    const L = live.value;
    const org =
      L && L.g.id === gameId
        ? L.g.organizer.id
        : (useGameStore().findGame(gameId)?.organizer.id ?? -1);
    return { myId: U.me.id, organizerId: org };
  }

  /** 总账视图 → 本地 LiveState 重建器（幂等、纯重建：不落牌不发 toast 不自动补片——
      发牌/轮换真值已归后端）：
      - roster 整拷 mock U 同 accountId 者的展示位（chibi/elo/战绩）——不借引用：
        总账时代 elo 真值在后端，不往 mock U 回写；访客/查无者补默认位（elo=RANK_INIT）；
        fire/shadow/dropin 对称覆写（借来的旧位不残留）；
      - g 只局部重建（现场克隆不回写局簿的旧约不变）：scoring/片名回填，片数吃
        courts_count 真值（courtCount 单一源读到即对表）；
      - history/feed 适配旧形状（view 升序 → 旧新到旧）；
      - settling 按片多值：pending 片进 Record（hide 位不重开）；streak/资历视图不带——
        旧引擎值位留 0/空。 */
  function applyLiveView(v: LiveView): void {
    const old = live.value;
    if (!old || old.g.id !== v.gameId) settleHidden.clear(); // 换局：关窗位不跨局残留
    const src =
      old && old.g.id === v.gameId ? old.g : useGameStore().findGame(v.gameId);
    const base = src ?? stubGame(v);
    const names = Array.from(
      { length: v.courtsCount },
      (_, i) => base.courts?.[i] ?? `${i + 1}号`,
    );
    const users = Object.values(useUserStore().users);
    const roster: User[] = v.players.map((p) => {
      const known =
        p.accountId != null
          ? users.find((u) => u.id === p.accountId)
          : undefined;
      const u: User = known
        ? { ...known }
        : {
            id: p.id,
            name: p.name,
            elo: RANK_INIT,
            play: 0,
            win: 0,
            month: 0,
            chibi: {},
          };
      u.id = p.id; // 名册行 id（写动作靶位），与 queue/片位同键
      u.name = p.name; // 开账定格名（注销者占位名/访客编号名照显）
      u.shadow = p.guest || undefined;
      u.dropin = p.dropin || undefined;
      u.fire = p.fire || undefined;
      u.check = p.check;
      u.skip = p.skip;
      u.arriveAt = p.arriveAt ?? undefined;
      u.leftAt = p.leftAt ?? undefined;
      u.courtSeq = undefined;
      u.tenure = 0;
      return u;
    });
    const onSide = (no: number, side: "a" | "b"): number[] =>
      v.players
        .filter((p) => p.courtNo === no && p.courtSide === side)
        .map((p) => p.id);
    const L: LiveState = {
      g: { ...base, courts: names, scoring: v.rules.scoring },
      roster,
      queue: [...v.queue],
      courts: v.courts.map((c) => ({
        id: c.courtNo - 1, // 视片段号 1 起 ↔ 旧片序 0 起（记分族动作按旧键定位）
        name: names[c.courtNo - 1] ?? `${c.courtNo}号`,
        singles: !v.rules.doubles,
        A: onSide(c.courtNo, "a"),
        B: onSide(c.courtNo, "b"),
        sa: c.scoreA,
        sb: c.scoreB,
        last: c.lastWinnerSide ?? undefined,
        streakA: 0,
        streakB: 0,
      })),
      history: v.matches
        .map((m) => ({
          names: m.winners.map((w) => w.name).join(" & "),
          sa: m.sa,
          sb: m.sb,
        }))
        .reverse(),
      round: v.round,
      admins: [...v.admins],
      feed: feedSentences(v.feed),
      startedAt: v.startedAt,
      endedAt: v.endedAt ?? undefined,
      ledger: v.players.map((p) => ({
        id: p.id,
        name: p.name,
        ...(p.guest ? { shadow: true } : {}),
        ...(p.dropin ? { dropin: true } : {}),
        ...(p.guarantorAccountId != null
          ? {
              guarantor: v.players.find(
                (x) => x.accountId === p.guarantorAccountId,
              )?.name,
            }
          : {}),
        ...(p.arriveAt ? { arriveAt: p.arriveAt } : {}),
        ...(p.leftAt ? { leftAt: p.leftAt } : {}),
      })),
      rules: {
        singles: !v.rules.doubles,
        down: v.rules.down,
        downChosen: true, // 冻结本地推荐跟随：down 是总账定值
        pairing: v.rules.pairing,
        champCap: v.rules.streakMax,
      },
      courtSeqNext: 0,
    };
    while (L.courts.length < v.courtsCount)
      L.courts.push(mkCourt(L, L.courts.length)); // 视图片行缺额补空片（差人卡口径）
    const next: Record<number, { origin: PendingOrigin } | null> = {};
    for (const c of v.courts) {
      const id = c.courtNo - 1;
      if (c.status !== "pending") {
        settleHidden.delete(id); // 片退出 pending：hide 位解除（下次再 pending 会重开窗）
        continue;
      }
      next[id] = settleHidden.has(id)
        ? null
        : { origin: c.pendingOrigin ?? "manual" };
    }
    settling.value = next;
    live.value = L;
    liveView.value = v;
    if (v.ended) recap.value = v;
  }

  /** 拉总账读对表（§4.8）：totalSeq 没变不重建（画面零漂移），返回是否更新供上层
      决定 toast「现场已更新」。拉读失败静默 false——轮询下一拍再试，写链的 409
      对表另走 applyStaleView */
  async function pollLiveView(gameId: number): Promise<boolean> {
    try {
      const view = toLiveView(await apiLiveView(gameId), viewerCtx(gameId));
      if (
        liveView.value?.gameId === view.gameId &&
        view.totalSeq === liveView.value.totalSeq
      )
        return false;
      applyLiveView(view);
      return true;
    } catch {
      return false;
    }
  }

  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let pollGameId: number | null = null;

  /** 轮询器（3s 一拍）：幂等启动、换局重起；进页首拍直调 pollLiveView（不靠计时器等） */
  function startPolling(gameId: number): void {
    if (pollTimer && pollGameId === gameId) return;
    if (pollTimer) clearInterval(pollTimer);
    pollGameId = gameId;
    pollTimer = setInterval(() => {
      void pollLiveView(gameId);
    }, 3000);
  }

  function stopPolling(): void {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
    pollGameId = null;
  }

  /** 409 两码对表件（附录 B1）：错误体自带最新视图——映射+重建一步到位、返回 true
      供上层 toast「现场已更新」；其余错误（非 ApiError / 他码 / 不带视图）不动现场返 false */
  function applyStaleView(e: unknown): boolean {
    if (!(e instanceof ApiError) || !e.view) return false;
    if (e.code !== "live_stale_total" && e.code !== "live_stale_court")
      return false;
    applyLiveView(toLiveView(e.view, viewerCtx(e.view.game_id)));
    return true;
  }

  return {
    live,
    hasLive,
    settling,
    settlingOne,
    advice,
    myRound,
    isFullPower,
    isAdmin,
    needFull,
    canEndLive,
    endGate,
    byId,
    startLive,
    ensureLive,
    setCheck,
    arriveMe,
    addGuests,
    removeFromRoster,
    setAdmin,
    unsetAdmin,
    point,
    undoPoint,
    clearScore,
    openSettle,
    closeSettle,
    confirmSettle,
    cancelMatch,
    subFirst,
    togglePerson,
    swapPlayers,
    setRuleScore,
    setRules,
    setCourtsInput,
    autoDeal,
    endLive,
    liveView,
    recap,
    applyLiveView,
    pollLiveView,
    startPolling,
    stopPolling,
    applyStaleView,
  };
});
