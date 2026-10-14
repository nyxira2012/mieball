/* 教学沙盒编排层（2.7 批2）：模式路由 + 步进指针 + NPC 剧本定时器 + 本地记分账 +
   结算编排的单点。真局 live store 全程不碰——教学态是 live.vue 的平级分支，
   退出即散（§4.5：卡标记之外本机不落任何东西）。动作编排套路统一为
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

export type SandboxMode = "pick" | "participate" | "organize" | "freeroam";

/** 卡标记两粒（进过即落，走没走完都算；§4.5）——storage 一 key 存一对 */
const CARDS_KEY = "mieball.sandbox.cards";
type CardKind = "participate" | "organize";

function loadCards(): Record<CardKind, boolean> {
  try {
    const raw = uni.getStorageSync(CARDS_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    if (parsed && typeof parsed === "object") {
      return {
        participate: !!parsed.participate,
        organize: !!parsed.organize,
      };
    }
  } catch {
    // 格式损坏/无环境静默走默认（venues.ts 同款兜底）
  }
  return { participate: false, organize: false };
}

export const useSandboxStore = defineStore("sandbox", () => {
  /** pick=选卡屏；participate/organize=两张教学卡；freeroam=随便逛逛 */
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
  /** 光圈锚 key（steps→组件私有协议：组件挂 :class="{ 'sb-glow': sandbox.spot===锚 }"） */
  const spot = computed(() => step.value?.spot ?? null);
  /** 当前步已解析的句子（函数步吃状态快照——第 7 条歇没歇两句）：解析单点在这，
      TutorBar 与测试都吃现成串，别各写一份 typeof 分支 */
  const stepText = computed(() => {
    const cur = step.value;
    const s = state.value;
    if (!cur || !s) return "";
    return typeof cur.text === "function" ? cur.text(s) : cur.text;
  });

  /* ---- 卡标记（storage 不在响应系内：写入后靠 rev 通知 computed 重读，
      选卡屏 ✓ 与教学横幅才能即时点亮） ---- */
  const cardsRev = ref(0);
  const doneCards = computed(() => {
    void cardsRev.value;
    return loadCards();
  });
  function markCard(kind: CardKind): void {
    const marks = loadCards();
    if (marks[kind]) return;
    marks[kind] = true;
    try {
      uni.setStorageSync(CARDS_KEY, JSON.stringify(marks));
    } catch {
      // 存储满静默跳过：卡标记只是 ✓ 装饰，丢了不影响玩法
    }
    cardsRev.value++;
  }

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
    if (cur?.autoAfterMs) {
      const at = stepIdx.value;
      autoTimer = setTimeout(() => {
        autoTimer = null;
        if (mode.value === "pick" || stepIdx.value !== at) return; // 手动先做完了不抢翻
        stepIdx.value++;
        onStepEnter();
      }, cur.autoAfterMs);
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

  /* ---- 本地记分账（同构 live store 的 per-court {sa,sb,history}，纯内存：
      比分在各手机本地记，settle 只吃确认窗定死的终局比分） ---- */
  const localScores = reactive<
    Record<number, { sa: number; sb: number; history: ("a" | "b")[] }>
  >({});
  /** 本地结算窗（一次一扇）：到分自动开，SandboxSettle（批3）直读自驱 */
  const settleWindow = ref<{ courtNo: number } | null>(null);

  function point(courtNo: number, side: "a" | "b"): void {
    const s = state.value;
    const c = s?.courts.find((c) => c.no === courtNo);
    if (!s || !c || !(c.a.length || c.b.length)) return; // 空片不记（同 live isIdle 守卫）
    const acc = (localScores[courtNo] ??= { sa: 0, sb: 0, history: [] });
    acc[side === "a" ? "sa" : "sb"]++;
    acc.history.push(side);
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
    const acc = localScores[courtNo];
    const side = acc?.history?.pop();
    if (side === "a") acc!.sa--;
    else if (side === "b") acc!.sb--;
  }

  function clearScore(courtNo: number): void {
    const acc = localScores[courtNo];
    if (acc) {
      acc.sa = acc.sb = 0;
      acc.history = [];
    }
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
    localScores[courtNo] = { sa: 0, sb: 0, history: [] };
    advanceIf();
  }

  /** 「暂不结算」：只关窗不清账，接着打（真局同语义） */
  function closeSettleWindow(): void {
    settleWindow.value = null;
  }

  /* ---- 进出与重放 ---- */

  /** 自由玩态种子（§4.5/A2 快照）：走到「第一场收完」——你在 1 号场打第二场
      （7:5），阿豪、老周候场。组合 engine 动作搭出来，不另开剧本 */
  function seedFreeroam(): SandState {
    const s = engine.initParticipate();
    const id = (name: string) => s.players.find((p) => p.name === name)!.id;
    engine.checkIn(s, id("你"));
    engine.checkIn(s, id("球球")); // 第 4 人→自动开赛 阿豪·老周 vs 你·球球
    engine.checkIn(s, id("老金"));
    engine.checkIn(s, id("小鹿"));
    engine.settle(s, 1, "a", 11, 9); // 老金小鹿顶坑，候场 [阿豪, 老周]
    const history: ("a" | "b")[] = [];
    for (let i = 0; i < 12; i++) history.push(i < 7 ? "a" : "b");
    localScores[1] = { sa: 7, sb: 5, history };
    return s;
  }

  function enter(kind: Exclude<SandboxMode, "pick">): void {
    clearTimers();
    fired.clear();
    mode.value = kind;
    // 重放/换卡前清残账：局面不落盘（§4.5），上一局的本地记分不得带进新开局
    for (const k of Object.keys(localScores)) delete localScores[Number(k)];
    state.value =
      kind === "organize"
        ? engine.initOrganize()
        : kind === "freeroam"
          ? seedFreeroam()
          : engine.initParticipate();
    if (kind !== "freeroam") markCard(kind); // 随便逛逛不落卡标记（本机只落两粒）
    stepIdx.value = 0;
    settleWindow.value = null;
    onStepEnter();
    armCues("enter");
  }

  /** 重放=同卡重进（§4.5：再进=带引导完整重放；局面不落盘、重放即全新开局） */
  function restart(): void {
    if (mode.value !== "pick") enter(mode.value);
  }

  /** 退出：局面散、定时器清、回选卡屏 */
  function exit(): void {
    clearTimers();
    fired.clear();
    mode.value = "pick";
    state.value = null;
    stepIdx.value = 0;
    settleWindow.value = null;
    for (const k of Object.keys(localScores)) delete localScores[Number(k)];
  }

  return {
    mode,
    state,
    stepIdx,
    step,
    stepText,
    spot,
    doneCards,
    localScores,
    settleWindow,
    enter,
    exit,
    restart,
    checkInMe,
    point,
    undoPoint,
    clearScore,
    confirmSettle,
    closeSettleWindow,
  };
});
