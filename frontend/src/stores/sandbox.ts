/* 教学沙盒编排层（2.7 批2）：模式路由 + 步进指针 + NPC 剧本定时器 + 本地记分账 +
   结算编排的单点。真局 live store 全程不碰——教学态是 live.vue 的平级分支，
   退出即散（§4.5：本机不落任何东西）。动作编排套路统一为
   「调 engine → 查 NPC 调度表 → advanceIf 跑当前步判据」，批3/批4 的组件动作
   （tempo/swap/加片等）进来时照同一套路挂。 */
import { computed, reactive, ref } from "vue";
import { defineStore } from "pinia";
import * as engine from "@/sandbox/engine";
import type { SandState } from "@/sandbox/engine";
import { ORGANIZE_CUES, PARTICIPATE_CUES, type NpcCue } from "@/sandbox/data";
import {
  ORGANIZE_STEPS,
  PARTICIPATE_STEPS,
  type TutorEv,
  type TutorStep,
} from "@/sandbox/steps";
import { reachedLocal } from "@/utils/rotate";
import {
  applyPoint,
  clearLocal,
  emptyLocal,
  undoPointIn,
  type LocalScoreBook,
} from "@/utils/localScore";
import { useUiStore } from "@/stores/ui";

export type SandboxMode = "pick" | "participate" | "organize";

export const useSandboxStore = defineStore("sandbox", () => {
  /** pick=未进教学（渲染落回 live.vue 真局/空态）；participate/organize=两张教学卡 */
  const mode = ref<SandboxMode>("pick");
  /** 教学态现场数据（engine 初始化的剧本局）；pick 态恒 null */
  const state = ref<SandState | null>(null);
  const stepIdx = ref(0);

  /* ---- 步进表 ---- */
  const curSteps = computed(() =>
    mode.value === "participate"
      ? PARTICIPATE_STEPS
      : mode.value === "organize"
        ? ORGANIZE_STEPS
        : null,
  );
  const step = computed<TutorStep | null>(
    () => curSteps.value?.[stepIdx.value] ?? null,
  );
  /** 光圈锚 key（steps→组件私有协议：组件挂 :class="{ 'sb-glow': sandbox.spot===锚 }"；
      函数形随状态解析——组织卡末条 ended 后熄） */
  const spot = computed(() => {
    const cur = step.value;
    const s = state.value;
    if (!cur || !s) return null;
    return typeof cur.spot === "function" ? cur.spot(s) : (cur.spot ?? null);
  });
  /** 当前步已解析的句子（函数步吃状态快照——第 7 条歇没歇两句）：解析单点在这，
      TutorBar 与测试都吃现成串，别各写一份 typeof 分支 */
  const stepText = computed(() => {
    const cur = step.value;
    const s = state.value;
    if (!cur || !s) return "";
    return typeof cur.text === "function" ? cur.text(s) : cur.text;
  });

  /* ---- NPC 剧本定时器（调度表在 data.ts；fired 去重防条件重复武装） ---- */
  let timers: ReturnType<typeof setTimeout>[] = [];
  let autoTimer: ReturnType<typeof setTimeout> | null = null;
  const fired = new Set<NpcCue>();

  function clearTimers(): void {
    timers.forEach(clearTimeout);
    timers = [];
    if (autoTimer != null) {
      clearTimeout(autoTimer);
      autoTimer = null;
    }
  }
  function schedule(fn: () => void, ms: number): void {
    const t = setTimeout(() => {
      timers = timers.filter((x) => x !== t);
      fn();
    }, ms);
    timers.push(t);
  }

  /** 武装一类触发条件成立的线索：到点调 engine（到场/跑马灯句）再走动作出口 */
  function armCues(
    when: NpcCue["when"],
    ctx?: { who?: string; step?: number },
  ): void {
    const cues =
      mode.value === "participate"
        ? PARTICIPATE_CUES
        : mode.value === "organize"
          ? ORGANIZE_CUES
          : [];
    for (const cue of cues) {
      if (cue.when !== when || fired.has(cue)) continue;
      if (cue.who !== undefined && cue.who !== ctx?.who) continue;
      if (cue.step !== undefined && cue.step !== ctx?.step) continue;
      fired.add(cue);
      schedule(() => {
        const s = state.value;
        if (!s || mode.value === "pick") return; // 已退出/散场：旧定时器哑火
        if (cue.arrive) {
          const p = s.players.find((p) => p.name === cue.arrive);
          if (p && !engine.arrived(p)) checkInById(p.id);
        }
        if (cue.feed) engine.pushFeed(s, cue.feed);
        advanceIf();
      }, cue.delayMs);
    }
  }

  /* ---- 动作编排（调 engine → 查表 → 推进步进） ---- */

  /** 步进翻一面 + 落新步的附带事（step 线索武装、自动步计时）。事件参只对
      当前步有效（翻面后继续级联判据时事件已消费） */
  function advanceIf(ev?: TutorEv): void {
    const steps = curSteps.value;
    const s = state.value;
    if (!steps || !s) return;
    for (;;) {
      const cur = steps[stepIdx.value];
      // final 行不翻（收尾行整行可点跳约球页——final 行 autoAfterMs 由 store autoTimer 推过末条成尾巴态）
      if (!cur || cur.final || !cur.done?.(s, ev)) return;
      stepIdx.value++;
      ev = undefined;
      onStepEnter();
    }
  }

  function onStepEnter(): void {
    if (autoTimer != null) {
      clearTimeout(autoTimer);
      autoTimer = null;
    }
    armCues("step", { step: stepIdx.value + 1 });
    const cur = step.value;
    const s = state.value;
    // autoAfterMs 函数形=条件自动步（组织卡末条：ended 才计时收尾巴；进条时未到条件不武装）
    const raw = cur?.autoAfterMs;
    const ms =
      raw == null || s == null
        ? null
        : typeof raw === "function"
          ? raw(s)
          : raw;
    if (cur && ms) {
      const at = stepIdx.value;
      autoTimer = setTimeout(() => {
        autoTimer = null;
        if (mode.value === "pick" || stepIdx.value !== at) return; // 手动先做完了不抢翻
        stepIdx.value++;
        onStepEnter();
        advanceIf(); // 定时步等待期用户可能已办完新步的事（组织卡第 2 步停一拍期间
        // 代办了凯文）——翻面后补跑级联，否则要等下一个动作才翻、卡一步
      }, ms);
    }
  }

  /** 到场单点（NPC 定时器与将来的代办/带访客出口同路）：到达才武装 arrive 线索 */
  function checkInById(id: number): void {
    const s = state.value;
    if (!s) return;
    engine.checkIn(s, id);
    const p = engine.pOf(s, id);
    if (engine.arrived(p)) armCues("arrive", { who: p.name });
    advanceIf();
  }

  /** 「我到了」（参与卡幕一；组织卡开场已签到，engine 幂等兜底） */
  function checkInMe(): void {
    const s = state.value;
    const you = s?.players.find((p) => p.you);
    if (!s || !you) return;
    armCues("me-checked-in");
    checkInById(you.id);
  }

  /** 二维码示意浮层点开（参与卡「亮码收人」步）：开关本位在 Stage 本地，
      这里只收「点开过」事件喂判据——看到了就算学过，关不关不问 */
  function qrShown(): void {
    advanceIf({ kind: "qr" });
  }

  /* ---- 本地记分账（同构 live store 的 per-court 账，纯内存：比分在各手机本地记，
      settle 只吃确认窗定死的终局比分；形状与代数单一源在 utils/localScore） ---- */
  const localScores = reactive<LocalScoreBook>({});
  /** 本地结算窗（一次一扇）：到分自动开，SandboxSettle（批3）直读自驱 */
  const settleWindow = ref<{ courtNo: number } | null>(null);

  function point(courtNo: number, side: "a" | "b"): void {
    const s = state.value;
    const c = s?.courts.find((c) => c.no === courtNo);
    if (!s || !c || !(c.a.length || c.b.length)) return; // 空片不记（同 live isIdle 守卫）
    const acc = (localScores[courtNo] ??= emptyLocal());
    applyPoint(acc, side);
    const you = s.players.find((p) => p.you);
    const mine = you != null && (c.a.includes(you.id) || c.b.includes(you.id));
    if (mine) armCues("me-scored"); // 幕三：你打着分，老金小鹿前后脚到
    advanceIf({ kind: "score", mine });
    // 到分自动开窗：reachedLocal 与后端/真局判分同式，吃片分制快照（改分在打片照旧）
    if (reachedLocal(acc.sa, acc.sb, c.scoring)) {
      if (!settleWindow.value) settleWindow.value = { courtNo };
    }
  }

  function undoPoint(courtNo: number): void {
    undoPointIn(localScores[courtNo]);
  }

  function clearScore(courtNo: number): void {
    clearLocal(localScores[courtNo]);
  }

  /** 窗内直录纠偏写回（SandboxSettle 消费）：懒建在账代数内，组件不经账面结构直改 */
  function setLocalScore(courtNo: number, sa: number, sb: number): void {
    const acc = (localScores[courtNo] ??= emptyLocal());
    acc.sa = sa;
    acc.sb = sb;
  }

  /** 结算确认编排：engine.settle（战报+先上的先下回流）→ 关窗清账（下一场
      0:0 起记）→ 步进推进。窗没开着不落（幂等闸同 live store 上传链） */
  function confirmSettle(
    courtNo: number,
    winner: "a" | "b",
    sa: number,
    sb: number,
  ): void {
    const s = state.value;
    if (!s || settleWindow.value?.courtNo !== courtNo) return;
    engine.settle(s, courtNo, winner, sa, sb);
    settleWindow.value = null;
    localScores[courtNo] = emptyLocal();
    advanceIf();
  }

  /** 「暂不结算」：只关窗不清账，接着打（真局同语义） */
  function closeSettleWindow(): void {
    settleWindow.value = null;
  }

  /* ---- 权限闸单点（§4.4 权限随卡走）：组织卡=组织者全开；参与卡=普通
      球员——只有自己歇/退场与记分/结算，其余动作如实拦下（真局 needFull 同句）。 ---- */
  const ui = useUiStore();
  const isFull = computed(() => mode.value === "organize");
  function needFull(): boolean {
    if (isFull.value) return true;
    ui.toast("请找组织者或管理员");
    return false;
  }
  /** 手柄钮闸（歇/连/退/换）：自己随时可、给别人需全权（真局 canOperate 同式）——
      拦下即提示，钮不隐藏（教学要的就是「点了看见真实待遇」） */
  function canOperatePerson(id: number): boolean {
    const s = state.value;
    if (!s) return false;
    if (isFull.value || s.players.find((p) => p.you)?.id === id) return true;
    // 拦下分支 isFull 必假（上方放过），与 needFull 的拦下路同句同果——直写免借道
    ui.toast("请找组织者或管理员");
    return false;
  }

  /* ---- 抽屉族（2.7 批4）：点人/签到代办/规则/散场四扇——开关单槽与点中人都在这
      （真局 liveSheet 单槽替换同语义），SandboxSheets 直读自驱。 ---- */
  type SheetKind = "person" | "checkin" | "rules" | "sweep";
  const sheetKind = ref<SheetKind | null>(null);
  const personId = ref(0);
  const personSwap = ref(false); // 换人二段态（点人抽屉内）

  function closeSheet(): void {
    sheetKind.value = null;
    personSwap.value = false;
  }
  function openPerson(id: number): void {
    personId.value = id;
    personSwap.value = false;
    sheetKind.value = "person";
  }
  /** ＋到场：代办工具入口（§4.4 唯一入口级拦截——参与卡如实拦下） */
  function tapCheckin(): void {
    if (!needFull()) return;
    sheetKind.value = "checkin";
  }
  /** 规则抽屉两卡都可开（参与卡只读三保险之一：抽屉内罩层） */
  function openRules(): void {
    sheetKind.value = "rules";
  }
  function openSweep(): void {
    if (!isFull.value) return; // 散场钮只组织卡渲染，闸在 store 兜底
    sheetKind.value = "sweep";
  }

  /* ---- 组织卡编排动作（调 engine → 查表 → 推进步进，同 checkInMe 套路） ---- */

  /** 带访客：称呼用你填的（签到前直接改行上的 name——data.ts 契约），已到场不重带 */
  function bringGuest(name: string): void {
    const s = state.value;
    if (!s || !isFull.value) return;
    const g = s.players.find((p) => p.guest);
    if (!g || engine.arrived(g)) return;
    g.name = name.trim() || g.name;
    checkInById(g.id);
  }

  /** 歇/连/取消歇（点人抽屉手柄钮）：办完抽屉即关——提示行是教学的引导本体，
      不能压在抽屉底下（规格幕五验收「设歇后抽屉关上」，歇的凭据靠复开抽屉看
      「再歇一轮 · 将跳 N 轮」；真局抽屉不关是另一套口径，教学按自己的规格走） */
  function tempo(id: number, action: "skip" | "unskip" | "fire"): void {
    const s = state.value;
    if (!s || !canOperatePerson(id)) return;
    engine.tempo(s, id, action);
    closeSheet();
    advanceIf();
  }

  /** 退场：清队列清场上、关抽屉（真局 onLeave 同编排） */
  function leavePerson(id: number): void {
    const s = state.value;
    if (!s || !canOperatePerson(id)) return;
    engine.checkIn(s, id, "left");
    closeSheet();
    advanceIf();
  }

  /** 换人二段态开关：进二段要手柄权，返回随时 */
  function setSwapMode(on: boolean): void {
    if (on && !canOperatePerson(personId.value)) return;
    personSwap.value = on;
  }

  /** 换人落子：换上落位盖章（状态无痕，判据吃事件）——落子即关抽屉（真局同） */
  function swapWith(inId: number): void {
    const s = state.value;
    if (!s || !canOperatePerson(personId.value)) return;
    engine.swap(s, personId.value, inId);
    closeSheet();
    advanceIf({ kind: "swap" });
  }

  /** 封管理员：只封候场正式球友（访客不行——真局口径；抽屉渲染同闸，store 兜底）。
      封完关抽屉（tempo 同族：下一步入口在顶条场地格，抽屉压着够不着）+ 武装
      admin-set 线索（NPC 调度表：小鹿随后到，第八步的因） */
  function setAdmin(id: number): void {
    const s = state.value;
    if (!s || !isFull.value) return;
    const p = engine.pOf(s, id);
    if (p.guest || p.admin || !s.queue.includes(id)) return;
    engine.setAdmin(s, id);
    closeSheet();
    armCues("admin-set");
    advanceIf();
  }

  /** 改分制（规则抽屉，全权）：真局 setRuleScore 同句提示「下一场起生效」 */
  function setScoring(v: number): void {
    const s = state.value;
    if (!s || !isFull.value) return;
    engine.setScoring(s, v);
    ui.toast(`分制已改为 ${v} 分 · 下一场起生效`);
    advanceIf();
  }

  /** ⚡ 兜底钮（差人卡）：自动补片没成时手动补发——engine.autoDeal 幂等 */
  function autoDeal(): void {
    const s = state.value;
    if (!s || !isFull.value) return;
    engine.autoDeal(s);
    advanceIf();
  }

  /** 顶条场地格直填（组织卡第八步「填 2」）：本地解析 1~9，只增不减（减片教学不教
      ——真局减片也是散场/取消的事）；成败回传给输入框回退展示值（真局 setCourtsInput 同式） */
  function courtsInput(raw: string): boolean {
    const s = state.value;
    if (!s || !isFull.value) return false;
    const n = Number(raw.match(/\d+/)?.[0]);
    if (!Number.isFinite(n) || n < 1 || n > 9 || n < s.courtsCount)
      return false;
    while (s.courtsCount < n) engine.addCourt(s); // 加片出口自动补片（engine.addCourt 内含）
    advanceIf();
    return true;
  }

  /** 「本场完成」（全权专属，参与卡不教不渲染）：手动开本片结算窗直录——与到分自动
      开的是同一扇（一次一扇的闸在 settleWindow） */
  function openSettle(courtNo: number): void {
    const s = state.value;
    if (!s || !isFull.value || settleWindow.value) return;
    const c = s.courts.find((c) => c.no === courtNo);
    if (!c || (!c.a.length && !c.b.length)) return;
    settleWindow.value = { courtNo };
  }

  /** 残局清单行内【取消】（散场清扫）：单片作废回流队首 */
  function sweepCancelCourt(courtNo: number): void {
    const s = state.value;
    if (!s || !isFull.value) return;
    engine.cancelCourt(s, courtNo);
  }
  /** 「未完对局全部取消」一键（真码 sweep_cancel_all 镜像） */
  function sweepCancelAll(): void {
    const s = state.value;
    if (!s || !isFull.value) return;
    engine.sweepCancelAll(s);
  }
  /** 确认散场（抽屉内二次确认后调）：放行落 ended → 抽屉转账单态、提示条换收尾句；
      重进 onStepEnter 让末条的条件自动步（收尾巴）此刻才计时。提前散场（如第九步
      直录没做完场就没了）时后面各步判据从此不可满足——散场收工=组织者的事教完了，
      直接跳末条收尾，别把提示行死锁在中间步（用户实测踩中） */
  function endGame(): boolean {
    const s = state.value;
    if (!s || !isFull.value) return false;
    const ok = engine.endGame(s);
    if (ok) {
      const steps = curSteps.value;
      if (steps && !steps[stepIdx.value]?.final)
        stepIdx.value = steps.length - 1;
      onStepEnter();
    }
    return ok;
  }

  /* ---- 进出与重放 ---- */

  /** 会话态归零（enter/exit 的公共序列收此一处：加第九个会话态只改这里，
      漏一处即成重放残留） */
  function resetSession(): void {
    clearTimers();
    fired.clear();
    stepIdx.value = 0;
    settleWindow.value = null;
    sheetKind.value = null;
    personId.value = 0;
    personSwap.value = false;
    // 残账清零：局面不落盘（§4.5），上一局的本地记分不得带进新开局
    for (const k of Object.keys(localScores)) delete localScores[Number(k)];
  }

  function enter(kind: Exclude<SandboxMode, "pick">): void {
    resetSession();
    mode.value = kind;
    state.value =
      kind === "organize" ? engine.initOrganize() : engine.initParticipate();
    onStepEnter();
    armCues("enter");
  }

  /** 重放=同卡重进（§4.5：再进=带引导完整重放；局面不落盘、重放即全新开局） */
  function restart(): void {
    if (mode.value !== "pick") enter(mode.value);
  }

  /** 退出：局面散、定时器清、回未进教学态（渲染落回 live.vue 真局/空态） */
  function exit(): void {
    resetSession();
    mode.value = "pick";
    state.value = null;
  }

  return {
    mode,
    state,
    stepIdx,
    step,
    stepText,
    spot,
    localScores,
    settleWindow,
    enter,
    exit,
    restart,
    checkInMe,
    qrShown,
    point,
    undoPoint,
    clearScore,
    setLocalScore,
    confirmSettle,
    closeSettleWindow,
    /* 批4：权限闸 + 抽屉族 + 组织卡编排 */
    isFull,
    sheetKind,
    personId,
    personSwap,
    closeSheet,
    openPerson,
    tapCheckin,
    openRules,
    openSweep,
    checkInRow: checkInById, // 抽屉【到场】消费的语义名（到场单点即 checkInById）
    bringGuest,
    tempo,
    leavePerson,
    setSwapMode,
    swapWith,
    setAdmin,
    setScoring,
    autoDeal,
    courtsInput,
    openSettle,
    sweepCancelCourt,
    sweepCancelAll,
    endGame,
  };
});
