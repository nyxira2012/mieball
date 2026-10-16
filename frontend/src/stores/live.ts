/* 现场 store（2.3 批5a 写链·全切后端；批5b 确认窗按片化收口；批6 散场清扫链+回看）：
   现场态真值=后端总账，本 store 只做 guard + 编排 + toast——写动作统一「组载荷
   （base 号取 liveView）→ api → 响应视图 applyLiveView 落地」；409 stale 携视图对表
   （toast「现场已更新」）；断网/他错走 errText（网络错文案「网络不给力，请稍后再试」）
   并把本地预变回滚成所持视图。
   发牌/补片真值单一源在后端（2.8 收编，live_rotation 取队）：前端不自算牌——
   所有写动作的响应视图即排好（后端出口落账时空片顺手补满）；写触发点不再补发
   请求，唯二手动「一键排阵」直调空载荷 apiLiveDeal、清扫取消以 no_redeal 透传
   豁免补片。
   记分本地化（2026-10-09 拍板，批2）：点比分不联网——各手机各记各的本地账
   （localScores，per court {sa,sb,history} 内存态，刷新即失）；到分 reachedLocal 命中
   自动开 settleWindow（upload 模式），打完 uploadSettle 先传先落（后端
   settle_recorded=有人先传了不同分：对表+透传服务端句+本地账清零关窗），全权
   overwriteSettle 下一场落账前改分重落。
   批3（走查缺陷：窗跨视图代次推进，洗新的 base 号把旧场账记成新一场战报）：
   upload 窗开窗锚该片 court_seq（courtSeqAnchor）——上传前闸比对现视图（越过锚
   不发请求走 settle_recorded 同款出口）+ applyLiveView 检测锚过期自动关窗；
   overwrite 窗不锚（操作的是「上一场落账行」，过期由后端片号闸兜底）。
   结算窗单一源 settleWindow（一次一扇：upload=上传结算谁都能传 / overwrite=改分
   重落全权；noRedeal 由入口传——清扫清单开窗传 true）：自动到分与手动入口
   （场卡「本场完成」/残局清单「上传比分」）共用 openSettleWindow（已有窗占位
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
   apiLiveRules（scoring 写局列）；setCheck/togglePerson/swapPlayers 的视图外行
   支线已随批6 切真整段退役（现态名册全来自总账，防御分支一并删——见各动作处注）。
   空降（apiLiveDropIn）与带访客
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
  apiLiveRedeal,
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
  canPickWinner,
  courtCount,
  courtOfPerson,
  courtSize,
  followWinner,
  isArrived,
  isIdle,
  pById,
  reachedLocal,
  roundsToPlay,
  usedCourts,
} from "@/utils/rotate";
import {
  applyPoint,
  clearLocal,
  emptyLocal,
  undoPointIn,
  type LocalScoreBook,
} from "@/utils/localScore";
import { ELO_INIT, GUEST_DUPR } from "@/utils/elo";
import { recommend } from "@/utils/recommend";
import { DEAD_LINK_MSG } from "@/utils/recap";
import { useGameStore } from "./game";
import { useUiStore } from "./ui";
import { useUserStore } from "./user";

/** 「算到场」谓词单一源在 utils/rotate（isArrived），此处转出口保持既有 import 面
    （候场条状态文案与二维码浮层在场人数从 store 取）；胜方联动/点选闸同款转出口
    （EndSettleModal 与既有测试从 store 取） */
export { canPickWinner, followWinner, isArrived };

/** 片序换算单点（旧片序 0 起 ↔ 视图/载荷片号 1 起）：记分族动作、确认窗取数、
    视图落地共用——换算散写已在批5b 验收官 Nit 销号，新增一律走本函数 */
export function courtNoOf(courtId: number): number {
  return courtId + 1;
}

/** 逆向换算（视图片号 → 本地片 id），与 courtNoOf 同一把双键契约 */
export function courtIdOf(courtNo: number): number {
  return courtNo - 1;
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

  /** 收摊（2.6 完成）：只清本机画面——定格回看视图/现场态/跨页信号位全清，
      账一点不动；有别的在办局由页面层接（ensureLive），store 只管原子清位 */
  function dismissRecap(): void {
    stopPolling();
    live.value = null;
    liveView.value = null;
    pendingLiveId.value = null;
  }

  /** 我的名册行 id（view.players 按 accountId 匹配身份位 me；查无返回 null——
      我不在名册：没签到没空降的新号/游客。绝不回落裸账号 id：行 id 与账号 id 是
      同库两套独立自增，数值撞车会把别人的行认成我（2026-10-11 扫码注册「提示
      已签到却不进队」事故——新账号 id 恰等于本局某名册行 id，arriveMe 吃到别人
      的已到场行，空降道被「你已经在场了」堵死）。mock 本地路已退役，回落无消费方） */
  function myRowId(): number | null {
    const meId = useUserStore().me.id;
    return (
      liveView.value?.players.find((p) => p.accountId === meId)?.id ?? null
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
      roundsToPlay 单一源（utils/rotate，沙盒候场条同吃）。不在名册 → null（未签到） */
  const myRound = computed<number | null>(() => {
    const L = live.value;
    if (!L) return null;
    const me = myRowId();
    const idx = me == null ? -1 : L.queue.indexOf(me);
    if (idx < 0) return null;
    return roundsToPlay(
      courtSize(L.rules.singles),
      L.courts.filter(isIdle).length,
      idx,
    );
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
    };
  }

  /* ─────── 写链公共件：base 号 / 统一发送 ─────── */

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
      toast「现场已更新」返 true；越界（rotation_overflow）错误体也携视图——主动作
      已提交不算失败，先对表保持最新画面（发牌降级片留空，差人卡照常兜底）再透传
      后端句「轮转数超范围，这片暂停发牌」返 false；其余 toast errText（断网
      「网络不给力，请稍后再试」/后端把关句）返 false */
  function handleWriteError(e: unknown): boolean {
    if (applyStaleView(e)) {
      ui.toast("现场已更新");
      return true;
    }
    if (e instanceof ApiError && e.code === "rotation_overflow" && e.view)
      applyLiveView(toLiveView(e.view));
    ui.toast(errText(e));
    return false;
  }

  /** 统一发送（写动作唯一通道）：api → 响应即最新视图 → applyLiveView 落地；
      - 409 两码（live_stale_total/court）携视图 → applyStaleView 对表 + toast「现场已更新」；
      - 其余错误走 errText（断网「网络不给力，请稍后再试」/后端把关句），
        并重放所持视图回滚本地预变——下一拍轮询兜底。
      - onError 特判钩子（返回 true=调用方已消费该错误，跳过通用处理）：给要读
        错误体的动作留分流口（如 settle_recorded 透传服务端句），别再自抄 try/catch
        骨架——回滚/对表规矩改这里一处全链生效。
      返回是否成功（调用方据此决定后续编排与 toast） */
  async function writeAction(
    gameId: number,
    run: () => Promise<LiveViewApi>,
    onDone?: () => void,
    onError?: (e: unknown) => boolean,
  ): Promise<boolean> {
    try {
      const raw = await run();
      applyLiveView(toLiveView(raw));
      onDone?.();
      return true;
    } catch (e) {
      if (onError?.(e)) return false;
      if (!handleWriteError(e) && liveView.value) applyLiveView(liveView.value); // 回滚本地预变
      return false;
    }
  }

  /* ─────── 开账与守门 ─────── */

  /** 开始打球（后端开账路）：apiLiveStart（幂等——已开账直接回视图）→ 视图落地。
      开场排片真值在响应视图（后端出口；新开账全员未到无队可取，通常无片开）。
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
    ui.toast(msg);
    return msg;
  }

  /** 确保现场开的是目标局（跳转/深链/扫码直达共用的守门口径，后端总账路）：
      - 拉读 200 → applyLiveView + startPolling（散场视图不再轮询——定格回看）；
        局簿没缓存这局时顺手 loadDetail 回填 g（深链冷设备顶条降级修复，批6 P2）；
      - 404 live_not_found → 终态局（done/terminated/cancelled）拦「找不到这个球局，
        可能已被撤销」（2.6 §4.6 链接死局句：不说「已结束」——散场恰恰是翻得回战报
        的状态；apiLiveView 对散场局照回 200 回看视图，404 只发生在真没有/已撤销），
        否则走开账后端路（组织者；幂等）；
      - 同局已开 → 续轮询 + 先对一拍（不靠计时器等 3s）；已散场同局 → 拉定格回看，
        写入口由 sealGate 与后端 live_ended 拦（§4.2/§4.10）。
      返回是否接上了（页面据此切死链态：失败只 toast 不留画面，2.6 前页面停骨架）。 */
  async function ensureLive(id: number): Promise<boolean> {
    const cur = live.value;
    if (cur && cur.g.id === id) {
      if (!cur.endedAt) startPolling(id);
      void pollLiveView(id);
      return true;
    }
    let raw: LiveViewApi;
    try {
      raw = await apiLiveView(id);
    } catch (e) {
      if (!(e instanceof ApiError) || e.code !== "live_not_found") {
        ui.toast(errText(e));
        return false;
      }
      // 404 探局存在性（probeExistence 单一源，战报子页同吃）：局在但从没开过账
      // 不说「已被撤销」——终态局拦死链句（散场恰恰是翻得回战报的状态，
      // apiLiveView 对散场局照回 200 回看视图，404 只发生在真没有/已撤销），
      // 在局走开账后端路（组织者；幂等）
      const g = await useGameStore().probeExistence(id);
      if (!g) {
        ui.toast(DEAD_LINK_MSG);
        return false;
      }
      if (["done", "terminated", "cancelled"].includes(g.status)) {
        ui.toast(DEAD_LINK_MSG);
        return false;
      }
      return !!(await startLive(g));
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
        return true; // 拉不到（无权限/已删）留 stub 不拦路——视图本身已接上
      }
      // 期间视图没被轮询推进才重放首拍（推进过的那拍已带最新号，重放旧的会回拨；
      // 轮询对表 totalSeq 不变不 apply——没有这步 stub 会一直占着顶条）
      if (
        liveView.value?.gameId === id &&
        liveView.value.totalSeq === first.totalSeq
      )
        applyLiveView(toLiveView(raw));
    }
    return true;
  }

  /** 到场操作（后端总账路）：apiLiveCheck（ok/late 归一、队尾口径全在后端镜像）→
      响应视图落地即排好（到场补片在后端出口，前端不再补发）→ 按落定态 toast。
      权限（§4.3）：代办他人收权；自己报到/早退随时可。
      （本地遗留路已随批6 切真整段退役——live 只在 applyLiveView 重建、名册行恒为
      视图行（空降/带访客也走后端建行），原 isViewRow 分支即全路径；absent 只读不写
      （考勤底账展示口径，无写入口）。 */
  async function setCheck(id: number, st: CheckStatus): Promise<void> {
    const L = live.value;
    const p = L ? pById(L, id) : undefined;
    if (!L || !p) return;
    if (!sealGate()) return;
    if (id !== myRowId() && !needFull()) return;
    if (st === "absent") return; // absent 只读不写（考勤底账展示口径，无写入口）
    const act: CheckInAction = st; // 窄化进闭包
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
    }
  }

  /** 休息/连战/取消休息（§4.10）：互斥与叠帐全在后端；toast 按响应视图落定态拼
      （共跳几轮/连战同条件排最前）。名册行恒为视图行（见 setCheck 处注） */
  async function togglePerson(
    id: number,
    k: "skip" | "fire" | "unskip",
  ): Promise<void> {
    const L = live.value;
    const p = L ? pById(L, id) : undefined;
    if (!L || !p) return;
    if (!sealGate()) return;
    if (id !== myRowId() && !needFull()) return;
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
    else ui.toast(row.fire ? "连战 · 同条件排最前" : "取消连战");
  }

  /** 封/撤管理员（§4.6 仅组织者；靶行须正式球友）：守卫链/取账号/极性幂等同构，
      双胞胎合体只留 api 与句两处分叉；留痕句由视图 feed 回来，toast 本地拼 */
  async function toggleAdmin(id: number, grant: boolean): Promise<void> {
    if (!needOrg()) return;
    const L = live.value;
    const p = L ? pById(L, id) : undefined;
    if (!L || !p || !liveView.value) return;
    const acc = liveView.value.players.find((r) => r.id === id)?.accountId;
    // 访客当不了（acc null）；极性不符静默幂等（已封再封/不是管理员再撤）
    if (acc == null || liveView.value.admins.includes(acc) === grant) return;
    const gid = L.g.id;
    await writeAction(
      gid,
      () =>
        grant
          ? apiLiveSetAdmin(gid, id, seqs().baseTotalSeq)
          : apiLiveUnsetAdmin(gid, id, seqs().baseTotalSeq),
      () =>
        ui.toast(
          grant
            ? `组织者封 ${p.name} 为管理员`
            : `组织者收回了 ${p.name} 的管理员身份`,
        ),
    );
  }

  /** 封管理员（§4.6 仅组织者） */
  const setAdmin = (id: number): Promise<void> => toggleAdmin(id, true);
  /** 撤管理员（§4.6 仅组织者） */
  const unsetAdmin = (id: number): Promise<void> => toggleAdmin(id, false);

  /** 扫码自签到（2.1·选项A）：名册没我（空降）→ apiLiveDropIn 后端建行入册
      （1.3 附录 B1 记账通道：考勤归一/队尾/摊钱人头 +1 全在后端，响应视图落地即
      完成）；有行（正式球友/已空降）→ 照旧走 setCheck 报到。
      现场没开或开的是别局 → ensureLive 先行；已结束的局被 ensureLive/sealGate 拦下 */
  async function arriveMe(gameId: number): Promise<string | null> {
    await ensureLive(gameId);
    const L = live.value;
    if (!L || L.g.id !== gameId || L.endedAt) return null; // ensureLive 已 toast 兜底
    const meRow = myRowId(); // null=我无行（新号/游客）→ 空降建行，不认别人的行
    const p = meRow == null ? undefined : pById(L, meRow);
    if (!p) {
      const ok = await writeAction(gameId, () =>
        apiLiveDropIn(gameId, seqs().baseTotalSeq),
      );
      if (!ok) return null;
      ui.toast("空降 · 排到队尾");
      // 空降即报到（§4.1）：够人开片同拍在后端出口办——响应视图落地即排好
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

  /** 本地账（per court）：各手机各记各的比分——纯内存态，不进协议不进存储
      （刷新即失，v1 非目标）；形状与代数单一源在 utils/localScore */
  const localScores = reactive<LocalScoreBook>({});

  /** 本地账清零（上传落账/冲突对齐后归零，下一场从 0:0 起记） */
  function resetLocal(courtId: number): void {
    localScores[courtId] = emptyLocal();
  }

  /** 本地结算窗（一次一扇，全站唯一窗态）：mode upload=上传结算（谁都能传）/
      overwrite=改分重落（全权）；noRedeal 由入口传——清扫清单「上传比分」传 true。
      courtSeqAnchor（批3）：upload 窗开窗时锚下该片代次（视图 court_seq 真值）——
      窗开着跨视图代次推进（这场已被别人落账/该片重发）时，上传前闸与视图落地的
      自动关窗都认它，旧场的账发不成新一场；overwrite 不锚 null（它操作的是「上一场
      落账行」latestMatchOf，锚片代次反而会被改分重落误杀，过期由后端片号闸兜底）。
      done（结算一步展示）：上传成功后窗不关、内容切「下一场对阵+候场名单」只读展示，
      等「好的」关闭——锚一并撤（不撤会被 applyLiveView 的自动关窗当成过期窗误杀）。
      旧 settling（视图 pending 驱动按片多值）窗族已随批2 会话B 退役删除，本窗独苗 */
  const settleWindow = ref<{
    courtId: number;
    noRedeal: boolean;
    mode: "upload" | "overwrite";
    courtSeqAnchor: number | null;
    done?: boolean;
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

  /** 开窗（闸收在这里）：表单窗占位一律不重开——自动开窗与手动入口共用（一次一扇）；
      一步展示窗是只读尾巴不占闸，下一场到分/手动入口开新窗直接顶掉它 */
  function openSettleWindow(
    courtId: number,
    mode: "upload" | "overwrite",
    noRedeal = false,
  ): void {
    if (settleWindow.value && !settleWindow.value.done) return;
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

  /** 上传链收尾配对（先清账关窗再落视图，下一场从 0:0 起记）：applyLiveView 的
      自动关窗、uploadSettle 三条出口（锚过期/成功/传分冲突）四处同吃——
      「别让自动关窗抢在落账 toast 前」的顺序契约收此一处 */
  function clearSettle(courtId: number): void {
    settleWindow.value = null;
    resetLocal(courtId);
  }

  /** 上传成功收尾（非清扫）：本地账清零 + 窗转一步展示（结算一步到位）——窗不关，
      内容切「下一场对阵+候场名单」；锚一并撤（不撤会被 applyLiveView 的自动关窗
      当成过期窗误杀），展示等「好的」或被下一场的新窗顶掉 */
  function settleDone(courtId: number): void {
    resetLocal(courtId);
    const w = settleWindow.value;
    if (w && w.courtId === courtId)
      settleWindow.value = { ...w, courtSeqAnchor: null, done: true };
  }

  /** 得分（点比分不联网）：只写本机这笔账（比分即反馈，无 toast 无 seq）；到分
      （reachedLocal 与后端判分同式）→ 自动开上传窗。scoring 吃片分制快照，
      缺快照（本地补的空片行）回落全局现行分制（mkCourt 同款兜底口径） */
  function point(courtId: number, side: "a" | "b"): void {
    const L = live.value;
    const c = courtOf(courtId);
    if (!L || !c || isIdle(c)) return;
    const acc = (localScores[courtId] ??= emptyLocal());
    applyPoint(acc, side);
    if (reachedLocal(acc.sa, acc.sb, c.scoring ?? L.g.scoring))
      openSettleWindow(courtId, "upload");
  }

  /** 误记撤回：流水倒退一分（支持撤回到底） */
  function undoPoint(courtId: number): void {
    undoPointIn(localScores[courtId]);
  }

  /** 记分清零（本地）：这笔账归 0:0 重开一盘（长按撤回触发） */
  function clearScore(courtId: number): void {
    clearLocal(localScores[courtId]);
  }

  /** 窗内直录纠偏写回（EndSettleModal upload 模式消费）：懒建在账代数内，
      组件不经账面结构直改 */
  function setLocalScore(courtId: number, sa: number, sb: number): void {
    const acc = (localScores[courtId] ??= emptyLocal());
    acc.sa = sa;
    acc.sb = sb;
  }

  /** 上传结算（先传先落）：把这片打完的本地账传后端落账（一本账原子=战报+积分+回流
      补位），任意到场者可传。走 writeAction 通道、settle_recorded 特判经 onError 钩子：
      通用 409「现场已更新」吞掉就够不着错误体里的已记比分句与视图。幂等闸：窗没开
      不发；上传前闸（批3）：窗锚的片代次已被视图推进（轮询把 base 号洗新）不发请求
      ——照发会把旧场的账记成新一场的战报，后端两级号闸拦不住，走 settle_recorded
      同款出口本地拦下 */
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
    // 上传前闸（批3）：现视图已新（锚过期的成因就是视图推进过）无需对表直用——
    // 吃该片最新落账行拼服务端 settle_recorded 同款句；查无行（该片被取消重开等）
    // 走通用句。不发请求、清零关窗
    if (anchorStale(settleWindow.value, liveView.value)) {
      const m = latestMatchOf(liveView.value, courtNoOf(courtId));
      ui.toast(
        m
          ? `已按 ${m.sa}:${m.sb} 记账 · 有异议找组织者`
          : "现场已更新 · 这场已有人记账",
      );
      clearSettle(courtId);
      return;
    }
    const no = courtNoOf(courtId);
    const s = seqs(no);
    await writeAction(
      L.g.id,
      async () => {
        const raw = await apiLiveSettleConfirm(L.g.id, {
          courtNo: no,
          winnerSide: winA ? "a" : "b",
          scoreA: sa,
          scoreB: sb,
          noRedeal,
          baseTotalSeq: s.baseTotalSeq,
          baseCourtSeq: s.baseCourtSeq,
        });
        // 收尾先于落视图（clearSettle 的顺序契约）：非清扫窗转一步展示（响应视图
        // 随后落地，展示数据即最新真值）、清扫态照旧关窗清账
        if (noRedeal) clearSettle(courtId);
        else settleDone(courtId);
        return raw;
      },
      () =>
        ui.toast(noRedeal ? "积分落账 · 残局已清" : "积分落账 · 下一场已排好"),
      (e) => {
        if (!(e instanceof ApiError) || e.code !== "settle_recorded")
          return false;
        // 传分冲突=有人先传先落了别的分，不当现场旧处理：对表响应视图 +
        // 透传服务端句（「已按 X:Y 记账 · 有异议找组织者」句尾服务端已带全）+
        // 本机账对齐清零关窗（clearSettle 契约，同上不让自动关窗抢 toast）
        clearSettle(courtId);
        if (e.view) applyLiveView(toLiveView(e.view));
        ui.toast(errText(e));
        return true;
      },
    );
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

  /** 取消对局（§4.7 出口 B，收权）：整场作废不计分，场上的人原样回流队首（后端）。
      noRedeal 随体透传（清扫态 true，§4.9）：非清扫后端出口已把腾出的片补满
      （响应视图即排好，前端不再补发）；清扫态后端豁免补片——只清不补好散场（红线）。
      先确认在页面层（A3） */
  async function cancelMatch(courtId: number, noRedeal = false): Promise<void> {
    const L = live.value;
    const c = courtOf(courtId);
    if (!L || !c || isIdle(c) || !needFull()) return;
    const gid = L.g.id;
    const no = courtNoOf(courtId);
    const n = c.A.length + c.B.length; // 出发时场上人数（文案）
    const s = seqs(no);
    await writeAction(
      gid,
      () => apiLiveCancel(gid, no, s.baseTotalSeq, s.baseCourtSeq, noRedeal),
      () => ui.toast(`对局作废 · 这场不计分 · 场上 ${n} 人回到队首`),
    );
  }

  /** 重排这片（全权，2.8 §4.4）：取消+立刻重发二合一在后端一个事务——刚设的
      歇/连战立刻兑现（响应视图即重排结果）。清扫态不可用（sweepState 前闸：
      清扫要清出空片好散场，重发会把残局变回在打）；二次确认在页面层（A3，
      合同确认句「重排会推翻当前这场」），needFull 只是提示性前闸、真闸在后端 */
  async function redealCourt(courtId: number): Promise<void> {
    const L = live.value;
    const c = courtOf(courtId);
    if (!L || !c || sweepState.value || !needFull()) return;
    const gid = L.g.id;
    const no = courtNoOf(courtId);
    const s = seqs(no);
    await writeAction(
      gid,
      () => apiLiveRedeal(gid, no, s.baseTotalSeq, s.baseCourtSeq),
      () => ui.toast("这片已重排 · 按最新状态排好"),
    );
  }

  /** 换人（§4.9 球友开放，无 guard）：场上 outId 原位顶坑给候场 inId——
      out 回队尾、feed 留名、pending 片冻结拒收全在总账；名册行恒为视图行
      （见 setCheck 处注）。
      出/入方向在单一源按名册真值定死（2026-10-10 修复批 F8：此前页面把
      候场者当 out 传，后端必拒「被换下的人不在场上」，换人整体不可用）——
      两参语义 = 「把 A 与 B 互换」，谁在场上谁出、候场者进。 */
  async function swapPlayers(selfId: number, targetId: number): Promise<void> {
    const L = live.value;
    if (!L) return;
    const selfOn = courtOfPerson(L, selfId) !== undefined; // 场上真值单一源
    const outId = selfOn ? selfId : targetId;
    const inId = selfOn ? targetId : selfId;
    await writeAction(
      L.g.id,
      () => apiLiveSwap(L.g.id, outId, inId, seqs().baseTotalSeq),
      () => ui.toast("已换人 · 对阵重排"),
    );
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
    await writeAction(
      L.g.id,
      () =>
        apiLiveGuests(
          L.g.id,
          { count, name: name || undefined, guarantor_id: guarantorId },
          seqs().baseTotalSeq,
        ),
      () => ui.toast(`已带 ${count} 位访客 · 进候场区`),
    );
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
      组合回落/连打上限口径归总账（默认随谁下自适应、手动优先）；换单双打后空片由后端
      出口按新制补（响应视图即排好，§5 边界：2 人即开赛） */
  async function setRules(patch: Partial<RotationRules>): Promise<void> {
    const L = live.value;
    if (!L || !needFull() || !liveView.value) return;
    const input: LiveRulesInput = {};
    if (patch.singles !== undefined) input.doubles = !patch.singles;
    if (patch.down !== undefined) input.down = patch.down;
    if (patch.pairing !== undefined) input.pairing = patch.pairing;
    if (patch.champCap !== undefined) input.streakMax = patch.champCap;
    await writeAction(
      L.g.id,
      () => apiLiveRules(L.g.id, input, seqs().baseTotalSeq),
      () => ui.toast("规则已更新 · 下一场起按新规"),
    );
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

  /** 一键排阵（全权，2.8 §4.5）：空载荷直调——按下=让后端补满所有空片（多片同时
      要人按片号先后），取队真值在 live_rotation 单一源；needFull 前端闸保留，
      后端全权闸兜底。只有响应视图真开出片才报「牌已发」（对比请求前后空片数）：
      人没凑够一片回 200 空手视图、不报成功话术（差人卡常驻提示，无需再报）；
      请求失败 writeAction 已 toast 报错——此前无视返回值一律 toast「牌已发」，
      失败时假成功话术把报错 toast 顶掉（2026-10-10 事故修复，语义沿旧） */
  async function autoDeal(): Promise<void> {
    const L = live.value;
    if (!L || !needFull() || !liveView.value) return;
    const idleBefore = L.courts.filter(isIdle).length;
    const ok = await writeAction(L.g.id, () =>
      apiLiveDeal(L.g.id, seqs().baseTotalSeq),
    );
    if (ok && (live.value?.courts.filter(isIdle).length ?? 0) < idleBefore)
      ui.toast("牌已发 · 按当前规则排好");
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
      (c) => ({ ...c, courtId: courtIdOf(c.courtNo) }),
    ),
  );

  /** 散场权共闸（startSweep/endGame 同一守卫）：在办且我有散场权才放行 */
  function sweeperReady(): LiveState | null {
    const L = live.value;
    if (!L || L.endedAt || !canEndLive.value) {
      ui.toast("只有组织者能收局");
      return null;
    }
    return L;
  }

  /** 点「散场 / 结束球局」进清扫态：权限闸（canEndLive——组织者或组织者早退时的
      管理员代收）→ 先拉最新视图对一拍（残局清单判定吃权威数）→ 开 SweepSheet。
      无残局时清单为空、直接走「确认散场」二次确认（同一扇窗不分支） */
  async function startSweep(): Promise<void> {
    const L = sweeperReady();
    if (!L) return;
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
      sealed（sealGate 收权），散场即回看。
      例外（2026-10-17 用户裁决①）：直接开场局一场对局都没落账时后端走撤局语义
      （响应换形 {ok,vacated}）——无战报可回看，dismissRecap 清本机画面回空态 */
  async function endGame(): Promise<void> {
    const L = sweeperReady();
    if (!L) return;
    let raw: LiveViewApi & { vacated?: boolean };
    try {
      raw = await apiLiveEnd(L.g.id, seqs().baseTotalSeq);
    } catch (e) {
      if (!handleWriteError(e) && liveView.value) applyLiveView(liveView.value);
      return;
    }
    sweepState.value = false;
    if (raw.vacated) {
      dismissRecap();
      ui.toast("已散场 · 没打过球，这局不留记录");
      return;
    }
    applyLiveView(toLiveView(raw));
    ui.toast("已散场 · 战报与底账已封存");
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
      - streak 视图不带——旧引擎值位留 0（资历记账已随回流补位归后端，前端无此位）。 */
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
        : (cached ?? stubGame(v)); // 两支都非空，无需再兜底
    const names = Array.from(
      { length: v.courtsCount },
      (_, i) => src.courts?.[i] ?? `${i + 1}号`,
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
      // 缓存未命中的正式球友顺手补拉档案（战绩/形象展示位下一版视图即真）：
      // ensurePerson 在途去重 + 失败冷却，轮询不会打成请求风暴（known 命中
      // 免调——重建每拍都跑，省掉逐人进函数再查一遍缓存）
      if (p.accountId != null && p.accountId !== userStore.me.id && !known)
        void userStore.ensurePerson(p.accountId);
      u.dupr = p.dupr; // 视图行 dupr 真值直落展示位（访客后端回 GUEST_DUPR=2.5；均衡配对已收编后端）
      u.id = p.id; // 名册行 id（写动作靶位），与 queue/片位同键
      u.name = p.name; // 开账定格名（注销者占位名/访客编号名照显）
      u.shadow = p.guest || undefined;
      u.dropin = p.dropin || undefined;
      u.fire = p.fire || undefined;
      u.check = p.check;
      u.skip = p.skip;
      u.tonight = p.tonight; // 今晚已打场数（队列抽屉「今晚 N 场」数源；生涯数在档案缓存 play，两数不同源）
      u.arriveAt = p.arriveAt ?? undefined;
      u.leftAt = p.leftAt ?? undefined;
      return u;
    });
    const onSide = (no: number, side: "a" | "b"): number[] =>
      v.players
        .filter((p) => p.courtNo === no && p.courtSide === side)
        .map((p) => p.id);
    const L: LiveState = {
      g: { ...src, courts: names, scoring: v.rules.scoring },
      roster,
      queue: [...v.queue],
      courts: v.courts.map((c) => ({
        id: courtIdOf(c.courtNo), // 视片段号 1 起 ↔ 旧片序 0 起（记分族动作按旧键定位）
        name: names[courtIdOf(c.courtNo)] ?? `${c.courtNo}号`,
        singles: !v.rules.doubles,
        A: onSide(c.courtNo, "a"),
        B: onSide(c.courtNo, "b"),
        scoring: c.scoring, // 片分制快照（卡头读它——在打片照旧、新开片用新制，2.6）
      })),
      history: v.matches
        .map((m) => ({
          // 轮播句「X & Y N:M 拿下」：名单与比分都按胜方摆（胜方在前）——边序
          // sideA/sideB 只管战报行左右摆位，这里语义是「谁赢了」
          names: (m.winA ? m.sideA : m.sideB).map((w) => w.name).join(" & "),
          sa: m.winA ? m.sa : m.sb,
          sb: m.winA ? m.sb : m.sa,
        }))
        .reverse(),
      round: v.round,
      admins: [...v.admins],
      feed: feedSentences(v.feed),
      startedAt: v.startedAt,
      endedAt: v.endedAt ?? undefined,
      rules: {
        singles: !v.rules.doubles,
        down: v.rules.down, // 总账定值：推荐替改已归后端
        pairing: v.rules.pairing,
        champCap: v.rules.streakMax,
      },
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
      clearSettle(w.courtId); // 上传链收尾配对（关窗+清账）单一源
      ui.toast("现场已更新 · 这场已有人记账");
    }
    if (v.ended) stopPolling(); // 散场即回看（§4.10）：定格视图派生 recap，轮询一并停（远端散场同路）
  }

  /** 拉总账读对表（§4.8）：手里有本局视图就带指纹走条件拉取快路（2.8 §4.6）
      ——后端稳态回 204 空体（null），空拍直接 false、零重建不进映射；变了回全量，
      落地前的 totalSeq 比对留作兜底（指纹口径外的漂移不重建）。首拍无指纹恒全量。
      拉读失败静默 false——轮询下一拍再试，写链的 409 对表另走 applyStaleView */
  async function pollLiveView(gameId: number): Promise<boolean> {
    try {
      const since =
        liveView.value?.gameId === gameId
          ? {
              totalSeq: liveView.value.totalSeq,
              feeTotal: liveView.value.fee?.total ?? null,
            }
          : undefined;
      const raw = await apiLiveView(gameId, since);
      if (raw === null) return false; // 204 空拍：稳态，画面零漂移
      if (
        liveView.value?.gameId === raw.game_id &&
        raw.total_seq === liveView.value.totalSeq
      )
        return false;
      applyLiveView(toLiveView(raw));
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
    setLocalScore,
    localScores,
    settleWindow,
    openSettleWindow,
    closeSettleWindow,
    uploadSettle,
    overwriteSettle,
    cancelMatch,
    redealCourt,
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
    dismissRecap,
    applyLiveView,
    pollLiveView,
    startPolling,
    stopPolling,
    applyStaleView,
  };
});
