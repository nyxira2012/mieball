/* 现场 store（2.3 批5a 写链·全切后端；批5b 确认窗按片化收口；批6 散场清扫链+回看）：
   现场态真值=后端总账，本 store 只做 guard + 编排 + toast——写动作统一「组载荷
   （base 号取 liveView）→ api → 响应视图 applyLiveView 落地」；409 stale 携视图对表
   （toast「现场已更新」）；断网/他错走 errText（网络错文案「网络不给力，请稍后再试」）
   并把本地预变回滚成所持视图。
   发牌算法仍在前端 rotate.ts（总账把关）：到场/取消/开账后够人的空片本地算完
   apiLiveDeal 上报；「排下一场」由确认响应视图驱动（回流补位真值在后端）。
   记分本地化（2026-10-09 拍板，批2）：点比分不联网——各手机各记各的本地账
   （localScores，per court {sa,sb,last} 内存态，刷新即失）；到分 reachedLocal 命中
   自动开 settleWindow（upload 模式），打完 uploadSettle 先传先落（后端
   settle_recorded=有人先传了不同分：对表+透传服务端句+本地账清零关窗），全权
   overwriteSettle 下一场落账前改分重落。
   批3（走查缺陷：窗跨视图代次推进，洗新的 base 号把旧场账记成新一场战报）：
   upload 窗开窗锚该片 court_seq（courtSeqAnchor）——上传前闸比对现视图（越过锚
   不发请求走 settle_recorded 同款出口）+ applyLiveView 检测锚过期自动关窗；
   overwrite 窗不锚（操作的是「上一场落账行」，过期由后端片号闸兜底）。
   结算窗单一源 settleWindow（一次一扇：upload=上传结算谁都能传 / overwrite=改分
   重落全权；noRedeal 由入口传——清扫清单开窗传 true）：自动到分与手动入口
   （场卡「结束对局」/残局清单「上传比分」）共用 openSettleWindow（已有窗占位
   不重开），「暂不结算」=closeSettleWindow 保本地分接着打；遮罩不可关的旧裁决
   仍成立（关窗丢待上传的账），非上传出口只有暂不结算。旧 settling/confirmSettle
   视图 pending 窗族已随批2 会话B 消费端切换退役删除。
   积分不在前端算（settleElo 已随 2026-10-08 收归后端退役）：结算窗 ±预演吃视图
   elo_preview 双分支（预演=落账），落账响应的 elo_rows 随视图持有。
   散场走清扫链（§4.9，批6 切真）：startSweep 进清扫态（拉最新视图判定残局，
   SweepSheet 由 live.vue 编排）→ 逐片 uploadSettle(noRedeal——清单开窗即带)/
   cancelMatch(noRedeal)/sweepCancelAll → 全清 endGame（apiLiveEnd；响应 ended 视图
   即回看——recap 落地、轮询停、sealGate 收权写「球局已结束」）。清扫里的上传/取消
   照常落账但 no_redeal=true：不排下一场不补位（红线）。
   原遗留本地路三动作已收口（2026-10-08 2.6 裁决）：subFirst/removeFromRoster
   退役删除（作废重排已覆盖替补位、防幽灵统一走代办早退）、setRuleScore 切真走
   apiLiveRules（scoring 写局列）；setCheck/togglePerson/swapPlayers 对视图外行的
   支线仅防御残留（现态名册全来自总账）。空降（apiLiveDropIn）与带访客
   （apiLiveGuests）1.3 批2 已切真。
   硬约束：不触碰任何 uni.*；名册行 id 是写动作靶位（与 queue/片位同键），
   账号口径（isAdmin/myRound）按 view.players.accountId 匹配身份位 me.id（user store）；身份两旗
   （isOrganizer/isFullPower）视图身份块直读（2026-10-08 起后端下发，
   批4a 的 viewerCtx 本地拼装已退役）。 */
import { computed, reactive, ref } from "vue";
import { defineStore } from "pinia";
import { ApiError, errText } from "@/api/http";
import {
  apiLiveCancel,
  apiLiveCheck,
  apiLiveDeal,
  apiLiveDropIn,
  apiLiveEnd,
  apiLiveGuests,
  apiLiveRules,
  apiLiveSetAdmin,
  apiLiveSettleConfirm,
  apiLiveSettleOverwrite,
  apiLiveStart,
  apiLiveSweepCancelAll,
  apiLiveSwap,
  apiLiveTempo,
  apiLiveUnsetAdmin,
  apiLiveView,
  toLiveView,
} from "@/api/live";
import type {
  CheckInAction,
  CheckStatus,
  DealCourt,
  FeedEvent,
  Game,
  LiveCourt,
  LiveRulesInput,
  LiveState,
  LiveView,
  LiveViewApi,
  MatchReport,
  RotationRules,
  User,
} from "@/api/types";
import {
  activePlayers,
  courtCount,
  courtOfPerson,
  courtSize,
  fillAllCourts,
  pById,
  reachedLocal,
  usedCourts,
} from "@/utils/rotate";
import { ELO_INIT, GUEST_DUPR } from "@/utils/elo";
import { recommend } from "@/utils/recommend";
import { useGameStore } from "./game";
import { useUiStore } from "./ui";
import { useUserStore } from "./user";

/** 「算到场」谓词单一源（候场条状态文案与二维码浮层在场人数共用）：
    ok 正常 / late 迟到已到 / join 中途加入；absent 未到、left 早退不算 */
export const isArrived = (c?: CheckStatus): boolean =>
  c === "ok" || c === "late" || c === "join";

/** 片序换算单点（旧片序 0 起 ↔ 视图/载荷片号 1 起）：记分族动作、确认窗取数、
    发牌载荷共用——换算散写已在批5b 验收官 Nit 销号，新增一律走本函数 */
export function courtNoOf(courtId: number): number {
  return courtId + 1;
}

/** 确认窗胜方联动（§4.6「改比分胜方自动跟分高方」的纯函数面，EndSettleModal 消费）：
    分高方当胜方——分低的一方当不了胜方，落不出「分低的赢了」的战报；平分清空预选
    （返回 null＝禁确认，§4.4 平分不预选）。前端联动、后端 settle-confirm 仍把关 */
export function followWinner(sa: number, sb: number): boolean | null {
  if (sa > sb) return true;
  if (sb > sa) return false;
  return null;
}

/** 确认窗胜方点选闸（§4.6 分低方选不中；平分双方均可点——点了才有预选） */
export function canPickWinner(
  sa: number,
  sb: number,
  side: "a" | "b",
): boolean {
  return side === "a" ? sa >= sb : sb >= sa;
}

/** 该片最新落账战报（视图 matches 按结束序，取同片最后一行）：改分入口的显示
    （场卡「上一场 X:Y · 改分」）与改分窗预填（EndSettleModal）共用同一真值 */
export function latestMatchOf(
  v: LiveView | null,
  courtNo: number,
): MatchReport | undefined {
  const ms = v?.matches ?? [];
  for (let i = ms.length - 1; i >= 0; i--)
    if (ms[i]!.courtNo === courtNo) return ms[i]!;
  return undefined;
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
          : e.kind === "auto_admin"
            ? `现场第一位签到的 ${e.target} 暂管现场`
            : `组织者收回了 ${e.target} 的管理员身份`,
    )
    .reverse();
}

/** 冷扫兜底局（现场态与局簿都没有时的最小 Game，applyLiveView 重建用）：
    纯展示占位（顶条局名/倒计时）——身份两旗视图直读后不再担旗；组织者 -1 是
    「待真局让位」的印记（applyLiveView 消费）；ensureLive 回填后此路罕见 */
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
    liveOpened: true, // 这本账就是从现场视图重建的——账必然开着
    ended: v.ended, // 散场确认锚随现场视图直读（回看态 stub 不给现场入口）
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

  /** 最近一次总账视图——写动作 base 号（totalSeq/片 courtSeq）与轮询对表的最近真值 */
  const liveView = ref<LiveView | null>(null);

  /** 跨页信号位（仿 sweepOnArrive）：goLive 跳转前落目标局 id——switchTab 不带 query，
      live.vue 的弹回判定与 onShow 取 id 认它（参与者冷缓存时 liveGame/hasLive 全空，
      缺了它会被误弹回约球页）；ensureLive 落地后由页面消费清位，一次性非持久态 */
  const pendingLiveId = ref<number | null>(null);
  /** 散场后回看视图（ended 视图定格派生；回看 UI 批6 消费） */
  const recap = computed<LiveView | null>(() =>
    liveView.value?.ended ? liveView.value : null,
  );

  /** 我的名册行 id（键位修正：view.players 按 accountId 匹配身份位 me；查无/无视图回落
      账号 id 兼本地路——mock 时代行 id 即账号 id） */
  function myRowId(): number {
    const meId = useUserStore().me.id;
    return (
      liveView.value?.players.find((p) => p.accountId === meId)?.id ?? meId
    );
  }

  /** 管理员谓词（id 兼两键：视图行 id → 换账号对表；查无直当账号 id）：
      PersonSheet/CheckinSheet/QueueSheet 徽章共用。admins 只在视图
      （live ⟺ liveView 同生灭，无视图即无现场） */
  function isAdmin(id: number): boolean {
    const row = liveView.value?.players.find((p) => p.id === id);
    const acc = row ? row.accountId : id;
    return acc != null && (liveView.value?.admins ?? []).includes(acc);
  }

  /** 现场权限单一源（2.2 §4.7）：组织者 ∨ 被封管理员 = 全权（同一套手柄）——
      视图身份块直读（后端按 viewer 发，深链冷启动首拍即真） */
  const isFullPower = computed(() => liveView.value?.isFullPower ?? false);

  /** 封存闸（§4.10 回看态）：endedAt 有值=已散场，写动作一律拒——
      所有 needFull 检查处与 setCheck/togglePerson 的自报免检路径共用；
      后端散场后写一律拒 live_ended，这里是前置拦截（提示句对齐规格） */
  function sealGate(): boolean {
    if (live.value?.endedAt) {
      ui.toast("球局已结束");
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
  /** 组织者独占（§4.6；后端 organizer_only 兜底同句）——视图身份旗直读 */
  function needOrg(): boolean {
    if (!sealGate()) return false;
    if (liveView.value?.isOrganizer) return true;
    ui.toast("只有组织者能做");
    return false;
  }

  /** 散场权（§4.14 组织者独占 + 兜底）：组织者已标「早退」离场时管理员可代收——
      代收判定找组织者名册行吃视图 organizerAccountId（不依赖局簿缓存，
      深链冷扫 stub 期也成立） */
  const canEndLive = computed(() => {
    const v = liveView.value;
    if (!v) return false;
    return (
      v.isOrganizer ||
      (v.isFullPower &&
        v.players.find((p) => p.accountId === v.organizerAccountId)?.check ===
          "left")
    );
  });

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

  /** 写链错误共件（writeAction 与 startLive 同款两分支）：409 两码携视图 → 对表 +
      toast「现场已更新」返 true；其余 toast errText（断网「网络不给力，请稍后再试」/
      后端把关句）返 false */
  function handleWriteError(e: unknown): boolean {
    if (applyStaleView(e)) {
      ui.toast("现场已更新");
      return true;
    }
    ui.toast(errText(e));
    return false;
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
      applyLiveView(toLiveView(raw));
      onDone?.();
      return true;
    } catch (e) {
      if (!handleWriteError(e) && liveView.value) applyLiveView(liveView.value); // 回滚本地预变
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
      .map((c) => ({ courtNo: courtNoOf(c.id), a: [...c.A], b: [...c.B] }));
    if (!deals.length) return false;
    return writeAction(gid, () =>
      apiLiveDeal(gid, deals, liveView.value!.totalSeq),
    );
  }

  /* ─────── 开账与守门 ─────── */

  /** 开始打球（后端开账路）：apiLiveStart（幂等——已开账直接回视图）→ 视图落地 →
      开场发牌（已够人的片本地算完上报；新开账全员未到通常为空拍）。
      签名沿旧（吃真局对象）——g 只取 id（身份旗在视图），名册展开归后端 */
  async function startLive(g: Game): Promise<string | null> {
    const msg = "球局开始 · 现场已点亮";
    try {
      const raw = await apiLiveStart(g.id);
      applyLiveView(toLiveView(raw));
      startPolling(g.id);
    } catch (e) {
      handleWriteError(e);
      return null;
    }
    await maybeDeal(g.id);
    ui.toast(msg);
    return msg;
  }

  /** 确保现场开的是目标局（跳转/深链/扫码直达共用的守门口径，后端总账路）：
      - 拉读 200 → applyLiveView + startPolling（散场视图不再轮询——定格回看）；
        局簿没缓存这局时顺手 loadDetail 回填 g（深链冷设备顶条降级修复，批6 P2）；
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
    const first = toLiveView(raw);
    applyLiveView(first);
    if (!first.ended) startPolling(id);
    /* 深链冷设备（新 origin 无局详情缓存）直达已开局（批6 走查 P2 的残留职责）：
       身份两旗已随视图直读、不经这段；留它纯为展示——视图 200 直达不经局详情时
       g 走 stub 兜底（顶条局名「现场」/倒计时失真），局簿没这局时顺手 loadDetail
       回填缓存后重放首拍，applyLiveView 的 g 局部重建吃真局（stub 让位）。
       比分/名册/规则等真值仍全以视图为准，不被详情覆盖。
       拉不到（无权限/已删）留 stub 不拦路 */
    if (!useGameStore().findGame(id)) {
      try {
        await useGameStore().loadDetail(id);
      } catch {
        return;
      }
      // 期间视图没被轮询推进才重放首拍（推进过的那拍已带最新号，重放旧的会回拨；
      // 轮询对表 totalSeq 不变不 apply——没有这步 stub 会一直占着顶条）
      if (
        liveView.value?.gameId === id &&
        liveView.value.totalSeq === first.totalSeq
      )
        applyLiveView(toLiveView(raw));
    }
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
      const adminsBefore = liveView.value?.admins ?? []; // 对比基准：apply 前的管理员表
      const ok = await writeAction(gid, () =>
        apiLiveCheck(gid, id, act, seqs().baseTotalSeq),
      );
      const row = liveView.value?.players.find((r) => r.id === id);
      if (!ok || !row) return;
      if (row.check === "left") {
        ui.toast(`${row.name} 先走了 · 回见`);
      } else if (isArrived(row.check)) {
        // 自动管理员提示（2.5 §4.2）：授予在后端落账时办，这里只认账——
        // apply 前后 admins 新增含我且我非组织者（视图身份旗），唯一 toast 用
        // 合同原句（获授者不显统一签到句：签到已成功，spec 句信息量更高）；
        // 不获授走统一句
        const meId = useUserStore().me.id;
        const granted =
          !liveView.value?.isOrganizer &&
          !adminsBefore.includes(meId) &&
          (liveView.value?.admins ?? []).includes(meId);
        // 签到统一句（§4.7 不分迟到与否，队位真值在响应视图）
        ui.toast(
          granted
            ? "组织者还没来 · 现场你先管着"
            : `${row.name} 已签到 · 自动加入候场队`,
        );
        await maybeDeal(gid); // 到场驱动发牌（§4.1 够一片的人数就上片）
      }
      return;
    }
    /* 本地遗留路已随批6 切真整段退役（原空降行/无视图演示态支线）——live 只在
       applyLiveView 重建、名册行恒为视图行（空降/带访客也走后端建行），上面的
       isViewRow 分支即全路径；absent 只读不写（考勤底账展示口径，无写入口） */
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
    /* 本地遗留路已随批6 切真整段退役：名册行恒为视图行（见 setCheck 处注） */
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

  /** 扫码自签到（2.1·选项A）：名册没我（空降）→ apiLiveDropIn 后端建行入册
      （1.3 附录 B1 记账通道：考勤归一/队尾/摊钱人头 +1 全在后端，响应视图落地即
      完成）；有行（正式球友/已空降）→ 照旧走 setCheck 报到。
      现场没开或开的是别局 → ensureLive 先行；已结束的局被 ensureLive/sealGate 拦下 */
  async function arriveMe(gameId: number): Promise<string | null> {
    await ensureLive(gameId);
    const L = live.value;
    if (!L || L.g.id !== gameId || L.endedAt) return null; // ensureLive 已 toast 兜底
    const p = pById(L, myRowId());
    if (!p) {
      const ok = await writeAction(gameId, () =>
        apiLiveDropIn(gameId, seqs().baseTotalSeq),
      );
      if (!ok) return null;
      ui.toast("空降 · 排到队尾");
      // 空降即报到（§4.1 够一片的人数就上片）：与 setCheck 同权，别漏自动发牌
      await maybeDeal(gameId);
      return "已签到 · 进候场区";
    }
    if (isArrived(p.check)) {
      ui.toast("你已经在场了");
      return null;
    }
    await setCheck(p.id, "ok"); // 到场口径单点（归一/队尾/发排/toast）
    return "已签到 · 进候场区";
  }

  /* ─────── 记分链（记分本地化：点比分不联网，本地账 + 上传结算） ─────── */

  /** 本地账（per court {sa, sb, history, last}）：各手机各记各的比分——纯内存态，不进协议
      不进存储（刷新即失，v1 非目标）；history=得分流水栈（undo 撤回到底基准，后进先出）；last 兼容保留 */
  const localScores = reactive<
    Record<
      number,
      {
        sa: number;
        sb: number;
        history: ("a" | "b")[];
        last: "a" | "b" | null;
      }
    >
  >({});

  /** 本地账清零（上传落账/冲突对齐后归零，下一场从 0:0 起记） */
  function resetLocal(courtId: number): void {
    localScores[courtId] = { sa: 0, sb: 0, history: [], last: null };
  }

  /** 本地结算窗（一次一扇，全站唯一窗态）：mode upload=上传结算（谁都能传）/
      overwrite=改分重落（全权）；noRedeal 由入口传——清扫清单「上传比分」传 true。
      courtSeqAnchor（批3）：upload 窗开窗时锚下该片代次（视图 court_seq 真值）——
      窗开着跨视图代次推进（这场已被别人落账/该片重发）时，上传前闸与视图落地的
      自动关窗都认它，旧场的账发不成新一场；overwrite 不锚 null（它操作的是「上一场
      落账行」latestMatchOf，锚片代次反而会被改分重落误杀，过期由后端片号闸兜底）。
      旧 settling（视图 pending 驱动按片多值）窗族已随批2 会话B 退役删除，本窗独苗 */
  const settleWindow = ref<{
    courtId: number;
    noRedeal: boolean;
    mode: "upload" | "overwrite";
    courtSeqAnchor: number | null;
  } | null>(null);

  /** 窗锚过期判定（批3 单一源）：upload 窗锚的片代次已被这版视图推进＝开窗锚的
      那场已收场——旧窗的账再传就是新一场的战报（后端两级号闸认不出洗新的号）；
      anchor null（overwrite/视图已无该片行）不判过期，后端闸兜底 */
  function anchorStale(
    w: { courtId: number; courtSeqAnchor: number | null },
    v: LiveView,
  ): boolean {
    return (
      w.courtSeqAnchor != null &&
      v.courtSeqs[courtNoOf(w.courtId)] !== w.courtSeqAnchor
    );
  }

  /** 开窗（一次一扇的闸收在这里：已有窗占位一律不重开——自动开窗与手动入口共用） */
  function openSettleWindow(
    courtId: number,
    mode: "upload" | "overwrite",
    noRedeal = false,
  ): void {
    if (settleWindow.value) return;
    settleWindow.value = {
      courtId,
      noRedeal,
      mode,
      courtSeqAnchor:
        mode === "upload"
          ? (liveView.value?.courtSeqs[courtNoOf(courtId)] ?? null)
          : null,
    };
  }

  function closeSettleWindow(): void {
    settleWindow.value = null;
  }

  /** 得分（点比分不联网）：只写本机这笔账（比分即反馈，无 toast 无 seq）；到分
      （reachedLocal 与后端判分同式）→ 自动开上传窗。scoring 吃片分制快照，
      缺快照（本地补的空片行）回落全局现行分制（mkCourt 同款兜底口径） */
  function point(courtId: number, side: "a" | "b"): void {
    const L = live.value;
    const c = courtOf(courtId);
    if (!L || !c || (!c.A.length && !c.B.length)) return;
    const acc = (localScores[courtId] ??= {
      sa: 0,
      sb: 0,
      history: [],
      last: null,
    });
    acc[side === "a" ? "sa" : "sb"]++;
    acc.history.push(side);
    acc.last = side;
    if (reachedLocal(acc.sa, acc.sb, c.scoring ?? L.g.scoring))
      openSettleWindow(courtId, "upload");
  }

  /** 误记撤回：流水倒退一分（支持撤回到底） */
  function undoPoint(courtId: number): void {
    const acc = localScores[courtId];
    const side = acc?.history?.pop();
    if (side === "a") acc!.sa--;
    else if (side === "b") acc!.sb--;
    if (acc) acc.last = acc.history?.[acc.history.length - 1] ?? null;
  }

  /** 记分清零（本地）：这笔账归 0:0 重开一盘（长按撤回触发） */
  function clearScore(courtId: number): void {
    const acc = localScores[courtId];
    if (acc) {
      acc.sa = acc.sb = 0;
      acc.history = [];
      acc.last = null;
    }
  }

  /** 上传结算（先传先落）：把这片打完的本地账传后端落账（一本账原子=战报+积分+回流
      补位），任意到场者可传。不走 writeAction：settle_recorded 须先于通用 409「现场
      已更新」分流特判（writeAction 吞错只回 boolean，错误体里的已记比分句与视图够
      不着），其余错误仍走 handleWriteError 共件。幂等闸：窗没开不发；上传前闸（批3）：
      窗锚的片代次已被视图推进（轮询把 base 号洗新）不发请求——照发会把旧场的账记成
      新一场的战报，后端两级号闸拦不住，走 settle_recorded 同款出口本地拦下 */
  async function uploadSettle(
    courtId: number,
    winA: boolean,
    sa: number,
    sb: number,
    noRedeal = false,
  ): Promise<void> {
    if (settleWindow.value?.courtId !== courtId) return;
    const L = live.value;
    if (!L || !liveView.value) return;
    const w = settleWindow.value;
    // 上传前闸（批3）：现视图已新（锚过期的成因就是视图推进过）无需对表直用——
    // 吃该片最新落账行拼服务端 settle_recorded 同款句；查无行（该片被取消重开等）
    // 走通用句。不发请求、清零关窗
    if (anchorStale(w, liveView.value)) {
      const m = latestMatchOf(liveView.value, courtNoOf(courtId));
      ui.toast(
        m
          ? `已按 ${m.sa}:${m.sb} 记账 · 有异议找组织者`
          : "现场已更新 · 这场已有人记账",
      );
      resetLocal(courtId);
      closeSettleWindow();
      return;
    }
    const no = courtNoOf(courtId);
    const s = seqs(no);
    try {
      const raw = await apiLiveSettleConfirm(L.g.id, {
        courtNo: no,
        winnerSide: winA ? "a" : "b",
        scoreA: sa,
        scoreB: sb,
        noRedeal,
        baseTotalSeq: s.baseTotalSeq,
        baseCourtSeq: s.baseCourtSeq,
      });
      // 先清账关窗再落视图：响应视图的片代次必越过窗锚（自家落账也 +1），别让
      // applyLiveView 的自动关窗抢在「积分落账」前弹「这场已有人记账」
      resetLocal(courtId);
      closeSettleWindow();
      applyLiveView(toLiveView(raw));
      ui.toast(noRedeal ? "积分落账 · 残局已清" : "积分落账 · 下一场已排好");
    } catch (e) {
      if (e instanceof ApiError && e.code === "settle_recorded") {
        // 传分冲突=有人先传先落了别的分，不当现场旧处理：对表响应视图 +
        // 透传服务端句（「已按 X:Y 记账 · 有异议找组织者」句尾服务端已带全）+
        // 本机账对齐清零关窗（先清关再落视图，同上不让自动关窗抢 toast）
        resetLocal(courtId);
        closeSettleWindow();
        if (e.view) applyLiveView(toLiveView(e.view));
        ui.toast(errText(e));
        return;
      }
      if (!handleWriteError(e) && liveView.value) applyLiveView(liveView.value); // 回滚本地预变
    }
  }

  /** 改分重落（全权）：下一场落账前把该片最新一场按新分重落（战报/Elo/DUPR 重写，
      轮转物理不动）；needFull 前端闸保留，后端全权+「仍是最新一场」窗口闸兜底 */
  async function overwriteSettle(
    courtId: number,
    winA: boolean,
    sa: number,
    sb: number,
  ): Promise<void> {
    if (!needFull()) return;
    const L = live.value;
    if (!L || !liveView.value) return;
    const no = courtNoOf(courtId);
    const s = seqs(no);
    await writeAction(
      L.g.id,
      () =>
        apiLiveSettleOverwrite(L.g.id, {
          courtNo: no,
          winnerSide: winA ? "a" : "b",
          scoreA: sa,
          scoreB: sb,
          baseTotalSeq: s.baseTotalSeq,
          baseCourtSeq: s.baseCourtSeq,
        }),
      () => {
        ui.toast("比分已改 · 积分已重算");
        if (settleWindow.value?.courtId === courtId) closeSettleWindow();
      },
    );
  }

  /** 取消对局（§4.7 出口 B，收权）：整场作废不计分，场上的人原样回流队首（后端）；
      片腾出来由本地重新发牌（发牌在前端）——清扫态（noRedeal，§4.9）不重发。
      先确认在页面层（A3） */
  async function cancelMatch(courtId: number, noRedeal = false): Promise<void> {
    const L = live.value;
    const c = courtOf(courtId);
    if (!L || !c || (!c.A.length && !c.B.length) || !needFull()) return;
    const gid = L.g.id;
    const no = courtNoOf(courtId);
    const n = c.A.length + c.B.length; // 出发时场上人数（文案）
    const s = seqs(no);
    const ok = await writeAction(
      gid,
      () => apiLiveCancel(gid, no, s.baseTotalSeq, s.baseCourtSeq),
      () => ui.toast(`对局作废 · 这场不计分 · 场上 ${n} 人回到队首`),
    );
    if (ok && !noRedeal) await maybeDeal(gid); // §4.7 该片腾出来重新发牌（清扫态除外）
  }

  /** 换人（§4.9 球友开放，无 guard）：场上 outId 原位顶坑给候场 inId——
      视图行走后端（out 回队尾、feed 留名、pending 片冻结拒收全在总账）。
      出/入方向在单一源按名册真值定死（2026-10-10 修复批 F8：此前页面把
      候场者当 out 传，后端必拒「被换下的人不在场上」，换人整体不可用）——
      两参语义 = 「把 A 与 B 互换」，谁在场上谁出、候场者进。 */
  async function swapPlayers(selfId: number, targetId: number): Promise<void> {
    const L = live.value;
    if (!L) return;
    const selfOn = courtOfPerson(L, selfId) !== undefined; // 场上真值单一源
    const outId = selfOn ? selfId : targetId;
    const inId = selfOn ? targetId : selfId;
    if (isViewRow(outId)) {
      const gid = L.g.id;
      await writeAction(
        gid,
        () => apiLiveSwap(gid, outId, inId, seqs().baseTotalSeq),
        () => ui.toast("已换人 · 对阵重排"),
      );
      return;
    }
    /* 本地遗留路已随批6 切真整段退役：名册行恒为视图行（见 setCheck 处注） */
  }

  /** 带访客（1.3 附录 B1 记账通道切真）：一次请求带 count+称呼+担保人行 id——
      访客行挂担保人账号名下进总账（出账「1+名下访客人头」归担保人）、命名与
      排队尾都在后端；响应视图落地即完成。needFull 前置拦截，后端 _require_full_power
      真闸；guarantorId 是名册行 id（视图行），不是账号 id */
  async function addGuests(
    count: number,
    name: string,
    guarantorId: number,
  ): Promise<void> {
    const L = live.value;
    if (!L || count <= 0 || !needFull() || !liveView.value) return;
    const ok = await writeAction(
      L.g.id,
      () =>
        apiLiveGuests(
          L.g.id,
          { count, name: name || undefined, guarantor_id: guarantorId },
          seqs().baseTotalSeq,
        ),
      () => ui.toast(`已带 ${count} 位访客 · 进候场区`),
    );
    if (ok) await maybeDeal(L.g.id); // 访客到场即带也报到（§4.1 够人就上片）
  }

  /** 改分制（2.6 批2 切真：apiLiveRules 收 scoring 写局列——分制复用局列，裁决 Q1）：
      写的是全局当前生效分制（rules 块随视图回填 g）；在打片分制已快照进片、
      照旧打完旧制，新开片用新制（toast 口径「下一场起生效」） */
  async function setRuleScore(v: number): Promise<void> {
    const L = live.value;
    if (!L || !needFull() || !liveView.value) return;
    await writeAction(
      L.g.id,
      () => apiLiveRules(L.g.id, { scoring: v }, seqs().baseTotalSeq),
      () => ui.toast(`分制已改为 ${v} 分 · 下一场起生效`),
    );
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

  /** 自动排阵（收权）：补所有空片（多片同时要人按片号先后）——发牌算法在前端。
      只有真发出并落账才报「牌已发」：maybeDeal 返 false 是「人还没凑够一片」
      （差人卡本身常驻提示，无需再报）或「上报失败」（writeAction 已 toast
      报错）——此前无视返回值一律 toast「牌已发」，失败时假成功话术把报错
      toast 顶掉，用户看着「排好又消失」却不知败在哪（2026-10-10 事故修复） */
  async function autoDeal(): Promise<void> {
    const L = live.value;
    if (!L || !needFull() || !liveView.value) return;
    const ok = await maybeDeal(L.g.id);
    if (ok) ui.toast("牌已发 · 按当前规则排好");
  }

  /* ─────── 散场清扫链（§4.9，批6 切真） ─────── */

  /** 清扫中标记：SweepSheet 的挂载开关（live.vue 编排；开始 startSweep / 关闭页面置 false） */
  const sweepState = ref(false);
  /** 远程散场预约（meet 页「我的局」入口落）：进了目标局现场由 live.vue 自动开清扫，
      落地即清——跨页一次性的信号位，非持久态 */
  const sweepOnArrive = ref<number | null>(null);

  /** 残局清单（§4.9 强制逐片处理的对象）：非 idle 的片，按片号升序（pending 已随
      记分本地化退役，残局=在打片）。真值=最近视图（startSweep 先对一拍再判定——
      A4 画面不自算）。组装处预带 courtId（片号 1 起 ↔ 片序 0 起，沿 toLiveView
      同款单点口径）——SweepSheet 只消费不自算 */
  const sweepResidues = computed(() =>
    (liveView.value?.courts.filter((c) => c.status !== "idle") ?? []).map(
      (c) => ({ ...c, courtId: c.courtNo - 1 }),
    ),
  );

  /** 点「散场 / 结束球局」进清扫态：权限闸（canEndLive——组织者或组织者早退时的
      管理员代收）→ 先拉最新视图对一拍（残局清单判定吃权威数）→ 开 SweepSheet。
      无残局时清单为空、直接走「确认散场」二次确认（同一扇窗不分支） */
  async function startSweep(): Promise<void> {
    const L = live.value;
    if (!L || L.endedAt || !canEndLive.value) {
      ui.toast("只有组织者能收局");
      return;
    }
    await pollLiveView(L.g.id);
    sweepState.value = true;
  }

  /** 未完对局全部取消（§4.9 一键，收权）：逐片 cancel 语义一个事务在后端；
      无残局幂等 no-op。先确认在页面层（A3） */
  async function sweepCancelAll(): Promise<void> {
    const L = live.value;
    if (!L || !liveView.value || !needFull()) return;
    await writeAction(
      L.g.id,
      () => apiLiveSweepCancelAll(L.g.id, seqs().baseTotalSeq),
      () => ui.toast("未完对局已全部取消"),
    );
  }

  /** 散场收工（§4.9 二次确认后的执行件）：残局不清完后端拒 live_residue（清单留在
      那片提示重试，不放行）；成功响应=ended 视图——applyLiveView 落 recap、停轮询、
      sealed（sealGate 收权），散场即回看 */
  async function endGame(): Promise<void> {
    const L = live.value;
    if (!L || L.endedAt || !canEndLive.value) {
      ui.toast("只有组织者能收局");
      return;
    }
    const ok = await writeAction(
      L.g.id,
      () => apiLiveEnd(L.g.id, seqs().baseTotalSeq),
      () => ui.toast("已散场 · 战报与底账已封存"),
    );
    if (ok) sweepState.value = false;
  }

  /** 名册按找（视图层 byId 的共享口径） */
  function byId(id: number): User {
    const L = live.value;
    return (
      (L ? pById(L, id) : undefined) ?? {
        id: -1,
        name: "—",
        elo: 0,
        dupr: GUEST_DUPR, // 查无行展示兜底＝访客标准分（1.4 §4）
        play: 0,
        win: 0,
        month: 0,
        chibi: {},
      }
    );
  }

  /* ─────── 读链（总账视图 → 本地重建 · 轮询 · 409 对表） ─────── */

  /** 总账视图 → 本地 LiveState 重建器（幂等、纯重建：不落牌不发 toast 不自动补片——
      发牌/轮换真值已归后端）：
      - roster 整拷 mock U 同 accountId 者的展示位（chibi/elo/战绩）——不借引用：
        总账时代 elo 真值在后端，不往 mock U 回写；最近 matches[].eloRows 按人
        回填 elo 展示位（批6 P3：确认落账即显新等级，访客 rating_after 同吃）；
        访客/查无者补默认位（elo=ELO_INIT 1200、dupr 吃视图行——后端访客回 3.0）；
        fire/shadow/dropin 对称覆写（借来的旧位不残留）；
      - g 只局部重建（现场克隆不回写局簿的旧约不变）：scoring/片名回填，片数吃
        courts_count 真值（courtCount 单一源读到即对表）；stub 兜底局（组织者 -1
        印记）在局簿详情到位后让位真局（深链冷设备两段路——纯展示让位，
        身份旗不经过 g，批6 P2）；
      - history/feed 适配旧形状（view 升序 → 旧新到旧）；
      - streak/资历视图不带——旧引擎值位留 0/空。 */
  function applyLiveView(v: LiveView): void {
    const old = live.value;
    const cached = useGameStore().findGame(v.gameId);
    // 现场克隆优先（setCourtsInput 本地挂的片名只挂在克隆上，重建沿用）；唯一例外：
    // stub 兜底局（组织者 -1 印记）在局簿详情到位后让位真局——深链冷设备 ensureLive
    // 先行、loadDetail 后补的两段路（批6 走查 P2）
    const src =
      old && old.g.id === v.gameId
        ? old.g.organizer.id < 0 && cached
          ? cached
          : old.g
        : (cached ?? stubGame(v));
    const base = src ?? stubGame(v);
    const names = Array.from(
      { length: v.courtsCount },
      (_, i) => base.courts?.[i] ?? `${i + 1}号`,
    );
    const userStore = useUserStore();
    const people = userStore.people;
    /** 最近结算行按人回填 elo 展示位（批6 走查 P3：确认落账后卡面新对阵即显新等级）：
        matches 按结束序、后面的覆盖前面的——每人吃最后一场的 rating_after；正式球友按
        accountId 对表、访客（账号 null）按开账定格名对表。名册行是 {...known} 拷贝，
        回填不污染 people 缓存本体 */
    const latestElo = new Map<string, number>();
    for (const m of v.matches)
      for (const r of m.eloRows)
        latestElo.set(
          r.accountId != null ? `a${r.accountId}` : `n${r.name}`,
          r.ratingAfter,
        );
    const roster: User[] = v.players.map((p) => {
      const known = p.accountId != null ? people[p.accountId] : undefined;
      const u: User = known
        ? { ...known }
        : {
            id: p.id,
            name: p.name,
            elo: ELO_INIT,
            play: 0,
            win: 0,
            month: 0,
            chibi: {},
          };
      const elo = latestElo.get(
        p.accountId != null ? `a${p.accountId}` : `n${p.name}`,
      );
      if (elo != null) u.elo = elo; // 结算行真值优先（拷贝上改，访客同样回填）
      u.accountId = p.accountId ?? undefined; // 账号空间 id 随行带（档案卡从现场开时不撞行 id）
      u.chibi = p.chibi ?? u.chibi; // 视图行开账定格小人直出，people 缓存兜底、访客缺省
      // 缓存未命中的正式球友顺手补拉档案（战绩/形象展示位下一版视图即真；
      // ensurePerson 在途去重，轮询不会打成请求风暴）
      if (p.accountId != null && p.accountId !== useUserStore().me.id)
        void userStore.ensurePerson(p.accountId);
      u.dupr = p.dupr; // 视图行 dupr 真值直落展示位（配对 rankOf 消费；访客后端已回 3.0）
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
        sa: 0, // 真值挂 localScores 本地账（记分本地化），此位留 0 兼 mock 树必填——删旧归 1.3
        sb: 0,
        scoring: c.scoring, // 片分制快照（卡头读它——在打片照旧、新开片用新制，2.6）
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
    live.value = L;
    liveView.value = v; // recap 纯派生于 liveView，无需另行同步（结算窗 settleWindow 与视图无关）
    // 视图推进自动关窗（批3）：upload 窗锚的片代次被这版视图推进＝窗锚的那场已收场
    // （有人落账/该片重发）——旧比分窗挂着误导，关窗+本地账清零是「现场已变化」的
    // 诚实呈现（uploadSettle 自家成功路先关窗才落视图，不会走到这里抢 toast）
    const w = settleWindow.value;
    if (w && anchorStale(w, v)) {
      settleWindow.value = null;
      resetLocal(w.courtId);
      ui.toast("现场已更新 · 这场已有人记账");
    }
    if (v.ended) stopPolling(); // 散场即回看（§4.10）：定格视图派生 recap，轮询一并停（远端散场同路）
  }

  /** 拉总账读对表（§4.8）：totalSeq 没变不重建（画面零漂移），返回是否更新供上层
      决定 toast「现场已更新」。拉读失败静默 false——轮询下一拍再试，写链的 409
      对表另走 applyStaleView */
  async function pollLiveView(gameId: number): Promise<boolean> {
    try {
      const view = toLiveView(await apiLiveView(gameId));
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
    applyLiveView(toLiveView(e.view));
    return true;
  }

  return {
    live,
    hasLive,
    pendingLiveId,
    advice,
    myRound,
    myRowId,
    isFullPower,
    isAdmin,
    needFull,
    canEndLive,
    byId,
    startLive,
    ensureLive,
    setCheck,
    arriveMe,
    addGuests,
    setAdmin,
    unsetAdmin,
    point,
    undoPoint,
    clearScore,
    localScores,
    settleWindow,
    openSettleWindow,
    closeSettleWindow,
    uploadSettle,
    overwriteSettle,
    cancelMatch,
    togglePerson,
    swapPlayers,
    setRuleScore,
    setRules,
    setCourtsInput,
    autoDeal,
    sweepState,
    sweepOnArrive,
    sweepResidues,
    startSweep,
    sweepCancelAll,
    endGame,
    liveView,
    recap,
    applyLiveView,
    pollLiveView,
    startPolling,
    stopPolling,
    applyStaleView,
  };
});
