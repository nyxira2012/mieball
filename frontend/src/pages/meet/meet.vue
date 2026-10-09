<template>
  <PageShell tab="meet">
    <!-- alpha:1069-1073 头部（.stag 入场 stagger，类在全局 base.scss） -->
    <view class="stag">
      <view class="kicker">Meet Up</view>
      <view class="brand">约<text class="bem">球</text></view>
      <view class="sub">{{ dateLine }}</view>
    </view>

    <!-- 游客注册/登录入口（1.1 先看后报的补口）：约球页是游客的主进场口——
         报名/发局/留意向的建号卡都在动作深处，这里给一扇明门；登录后整块消失 -->
    <view v-if="session.isGuest" class="guestgate">
      <view class="gg-main" @click="onSignup">
        ＋ 填张名片建号 —— 报名 · 发局 · 留意向都要用
      </view>
    </view>

    <!-- alpha:1074 跑马灯：被邀请条目 + NEXT 最近参局倒计时（×2 无缝循环由 Ticker 内部负责） -->
    <Ticker :items="tickerItems" />

    <!-- 组织者远程散场入口（2.3 §4.9）：我组织的进行中的局——点「散场收工」进现场
         自动开残局清扫（sweepOnArrive 预约位 + goLive，同一链照常二次确认） -->
    <view
      v-for="g in myLiveOrg"
      :key="g.id"
      class="sweeprow"
      @click="onRemoteSweep(g)"
    >
      <text class="sweep-txt">「{{ g.name }}」进行中 · 你是组织者</text>
      <view class="sweep-btn">散场收工 ▸</view>
    </view>

    <!-- alpha:1075-1080 球局区吸顶头（CSS sticky）· 筛选▾ / 收起 两钮 -->
    <view class="msec-head">
      <text class="mh-t">球局</text>
      <text class="mh-n">{{ flt.length }} 个 · 我参加 / 组织的置顶</text>
      <view class="sp" />
      <view class="mhbtn" @click="filtersOpen = !filtersOpen">{{
        filtersOpen ? "筛选 ▴" : "筛选 ▾"
      }}</view>
      <view class="mhbtn" @click="gamesFold = !gamesFold">{{
        gamesFold ? "展开" : "收起"
      }}</view>
    </view>

    <!-- 折叠筛选区：时间 5 chips（1.2 起只按时间筛；档位可见性归后端、地区筛随 mock 退役） -->
    <view class="fchips-wrap" :class="{ open: filtersOpen }">
      <FilterChips v-model="fTime" :options="TIME_OPTS" />
    </view>

    <!-- 收起占位行 / 列表（pinned+rest 拼接）/ 加载与空态（A2） -->
    <view v-if="gamesFold" class="foldrow" @click="gamesFold = false">
      球局列表已收起 · 点展开 {{ flt.length }} 个局 ▸
    </view>
    <template v-else>
      <EmptyBox
        v-if="game.loading && !ordered.length"
        :text="slow ? '网络有点慢 · 再等等，或稍后再来' : '正在翻局 · 马上好…'"
      />
      <template v-else>
        <GameCard
          v-for="{ g, card } in cards"
          :key="card.id"
          :card="card"
          @tap="onGameTap(g, card)"
          @enter="onGameTap(g, card)"
        />
        <EmptyBox
          v-if="!flt.length"
          text="这里还没有能翻到的局 —— 留个意向，或点右下角 ＋ 发一个"
        />
      </template>
    </template>

    <!-- 死局区三分（分派单一源 deadRowKind）：组织者 pending 待处置卡（锁必打/撤局出口，4.9）
         · 组织者 terminated 未成局卡（恢复窗内可恢复，4.8）
         · 参加者当日灰字行「该局已取消」（后端只在死亡当日返回，次日自动收走，前端只管渲染，4.8/4.10） -->
    <template v-if="orgPending.length">
      <SectionTitle title="待处置" more="恢复的局 · 等你锁必打或撤局" />
      <DeadCard
        v-for="g in orgPending"
        :key="g.id"
        pending
        :game="g"
        @lock="onLock(g)"
        @cancel="onCancel(g)"
      />
    </template>
    <template v-if="orgDead.length">
      <SectionTitle title="未成局" more="到截止人数不足自动终止" />
      <DeadCard
        v-for="g in orgDead"
        :key="g.id"
        :game="g"
        @restore="onRestore(g)"
        @cancel="onCancel(g)"
      />
    </template>
    <template v-if="grayMine.length">
      <SectionTitle title="已取消的局" more="只在今天可见" />
      <view v-for="g in grayMine" :key="g.id" class="grayrow"
        >「{{ g.name }}」 该局已取消</view
      >
    </template>

    <!-- alpha:1091-1097 意向区头：CSS 吸顶 + 贴底钉位；整头点击切换焦点，scope 两钮 stopPropagation -->
    <view class="isec-head" :style="dockStyle" @click="focusIntent">
      <text class="mh-t">意向</text>
      <text class="mh-n"
        >{{ scopeLabel }} {{ ipool.length }} 条 · 点击切换焦点 ⇅</text
      >
      <view class="sp" />
      <view
        class="mhbtn"
        :class="{ on: intentScope === 'all' }"
        @click.stop="intentScope = 'all'"
        >所有人</view
      >
      <view
        class="mhbtn"
        :class="{ on: intentScope === 'known' }"
        @click.stop="intentScope = 'known'"
        >打过</view
      >
    </view>

    <!-- alpha:1098-1102 意向区内容：我的意向条（改/删）或 留意向入口 + IntentCard 列表 + 说明行 -->
    <view class="intent-sec">
      <view v-if="game.myIntent" class="idock-my">
        <text class="my-txt"
          >我的意向 · {{ myIntentLine }} ·
          {{ freqName(game.myIntent.frequency) }}</text
        >
        <view class="my-btns">
          <view class="tbtn" @click="openIntentForm">✎ 改</view>
          <view class="tbtn on-no" @click="onDelIntent">✕</view>
        </view>
      </view>
      <view v-else class="useentry" @click="openIntentForm"
        >＋ 留我的意向 —— 什么时段想打 · 组局的人会看见你</view
      >

      <!-- 后端已排未邀在前、已邀靠后（updated_at 倒序），前端保持该序不再重排 -->
      <IntentCard
        v-for="i in ipool"
        :key="i.account.id"
        :intent="i"
        @tap="onIntentTap(i)"
      />
      <EmptyBox v-if="!ipool.length" text="这里还没有意向" />

      <view class="sub intent-note"
        >默认只看打过球的 · 点击卡片查看球友名片</view
      >
    </view>

    <view class="tailpad" />
  </PageShell>
</template>

<script setup lang="ts">
/* 约球页（alpha.html:952-1105 · P7）。1.2 接线修订面：
   - 数据走 game store 真接口（loadGames/loadMine/loadIntents/loadMyIntent），onShow 重拉；
   - 列表只按时间筛（档位可见性后端已滤；done 局不上找局打——裁决⑧，历史归我的局/详情）；
   - 置顶/跑马灯/点卡分支全读 my 块定值（A4 画面不自算）。 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { onPageScroll, onShow } from "@dcloudio/uni-app";
import PageShell from "@/components/biz/PageShell.vue";
import GameCard from "@/components/biz/GameCard.vue";
import DeadCard from "@/components/biz/DeadCard.vue";
import IntentCard from "@/components/biz/IntentCard.vue";
import Ticker from "@/components/ui/Ticker.vue";
import type { TickerItem } from "@/components/ui/Ticker.vue";
import FilterChips from "@/components/ui/FilterChips.vue";
import SectionTitle from "@/components/ui/SectionTitle.vue";
import EmptyBox from "@/components/ui/EmptyBox.vue";
import type { Game, GameCardModel, Intent } from "@/api/types";
import { communityMeta } from "@/api/dict";
import { useGameStore } from "@/stores/game";
import { useLiveStore } from "@/stores/live";
import { useSessionStore } from "@/stores/session";
import { useUiStore } from "@/stores/ui";
import {
  deadRowKind,
  freqName,
  gameTapAction,
  newGameCard,
  slotName,
} from "@/utils/format";
import { isoDay, isoDayOff, isoHm, isoParts, untilTxt } from "@/utils/time";
import { ApiError, errText } from "@/api/http";
import { goGame, goLive } from "@/utils/nav";

const game = useGameStore();
const liveStore = useLiveStore();
const session = useSessionStore();
const ui = useUiStore();

/* ---- 游客入口（见模板注释）：建号直开名片卡（无挂起动作，名片卡内含老球友找回） ---- */
function onSignup(): void {
  ui.openSheet({ type: "signup-card" });
}

/* ---- 远程散场（2.3 §4.9）：我组织的进行中的局；落预约位后 goLive——
     live 页 ensureLive 落地即自动开清扫流（同一链，逐片处理照常二次确认） ---- */
const myLiveOrg = computed(() =>
  game.myGames.filter((g) => g.status === "live" && g.my?.isOrganizer),
);
function onRemoteSweep(g: Game): void {
  liveStore.sweepOnArrive = g.id;
  goLive(g.id);
}

/* ---- 头部（alpha:1072 日期行逐字） ---- */
const dateLine = computed(() => {
  const d = new Date();
  return `${d.getMonth() + 1} 月 ${d.getDate()} 日 · 星期${"日一二三四五六"[d.getDay()]} · ${communityMeta.name}`;
});

/* ---- 状态（alpha:956） ---- */
const fTime = ref<string | number>("all");
const intentScope = ref<"known" | "all">("known");
const filtersOpen = ref(false);
const gamesFold = ref(false);

/* alpha:1082 时间筛选 chips（逐字；地区档随 mock 退役） */
const TIME_OPTS = [
  { value: "all", label: "全部时间" },
  { value: "tonight", label: "今晚" },
  { value: "tomorrow", label: "明天" },
  { value: "weekend", label: "周末" },
  { value: "week", label: "本周" },
];

/* alpha:1082-1085 桶判定：与旧 tb 推导同口径（今天/明天/周末/其余未来），从 startAt 现算
   （走查#1 收口：ISO 筛选也按北京墙钟取数，不再吃设备本地 getDay） */
function inBucket(g: Game, b: string): boolean {
  if (b === "all") return true;
  const p = isoParts(g.startAt);
  const off = isoDayOff(g.startAt);
  if (b === "tonight") return off <= 0;
  if (b === "tomorrow") return off === 1;
  if (b === "weekend") return p.wd === 0 || p.wd === 6;
  return p.wd !== 0 && p.wd !== 6;
}

/* ---- 跑马灯（alpha:983-994）：被邀条目吃 myGames 的 my.invited 定值；
     NEXT = 我的在办局里最近一场开打倒计时 ---- */
const tickerItems = computed<TickerItem[]>(() => {
  const bits: TickerItem[] = [];
  game.myGames
    .filter((g) => g.my?.invited && !g.my.myEntry)
    .forEach((g) =>
      bits.push({
        tag: "邀请",
        text: `${g.organizer.nickname} 邀你加入「${g.name}」· 点一下就加入`,
      }),
    );
  const nx = game.myGames
    .filter((g) => g.status === "open" || g.status === "locked")
    .map((g) => ({ g, t: new Date(g.startAt) }))
    .filter((x) => x.t.getTime() > Date.now())
    .sort((a, b) => a.t.getTime() - b.t.getTime())[0];
  const u = nx && untilTxt(nx.t);
  if (nx && u) {
    bits.push({
      tag: "NEXT",
      text: `距离「${nx.g.name}」${isoDay(nx.g.startAt)}${isoHm(nx.g.startAt)} 开打还有 ${u}`,
    });
  }
  if (!bits.length)
    bits.push({ tag: "NOW", text: "暂无要开的局 · 意向底坞里攒下一场" });
  return bits;
});

/* ---- 球局区（alpha:1054-1057）：done 局不上找局打（裁决⑧，历史归我的局/详情）；
     排序先 map 缓存时间值再比（比较器里反复 new Date 是 O(n log n) 次） ---- */
const ftv = computed(() => String(fTime.value));
const flt = computed(() =>
  game.games
    .filter((g) => g.status !== "done" && inBucket(g, ftv.value))
    .map((g) => ({ g, t: new Date(g.startAt).getTime() }))
    .sort((a, b) => a.t - b.t)
    .map((x) => x.g),
);
/* alpha:1056/1088 pinned = 我参加/组织/被邀的置顶（my 块定值）；卡面模型同拍算好——
   模板 v-for 里直调 newGameCard 会随滚动（dockY 变值触发整页重渲）逐卡重建对象 */
const ordered = computed(() => {
  const mine = (g: Game): boolean =>
    !!g.my && (g.my.isOrganizer || !!g.my.myEntry || g.my.invited);
  return [...flt.value.filter(mine), ...flt.value.filter((g) => !mine(g))];
});
const cards = computed(() =>
  ordered.value.map((g) => ({ g, card: newGameCard(g) })),
);
/* 死局区三分（deadRowKind 单一源，4.8/4.9/4.10）：见模板注释 */
const orgPending = computed(() =>
  game.myGames.filter((g) => deadRowKind(g) === "pending"),
);
const orgDead = computed(() =>
  game.myGames.filter((g) => deadRowKind(g) === "restore"),
);
const grayMine = computed(() =>
  game.myGames.filter((g) => deadRowKind(g) === "gray"),
);

/* ---- A2 加载：等待提示，超 2 秒提示网络问题 ---- */
const slow = ref(false);
let slowTimer: ReturnType<typeof setTimeout> | null = null;
watch(
  () => game.loading,
  (on) => {
    if (slowTimer) clearTimeout(slowTimer);
    if (on) slowTimer = setTimeout(() => (slow.value = true), 2000);
    else slow.value = false;
  },
);
onUnmounted(() => {
  if (slowTimer) clearTimeout(slowTimer);
});

/* ---- 意向区（alpha:1058-1061/1093）：scope 熟人=同局打过（intent.known 后端定值，裁决②） ---- */
const ipool = computed(() =>
  game.intents.filter((i) => intentScope.value === "all" || i.known),
);
const scopeLabel = computed(() =>
  intentScope.value === "all" ? "所有人" : "打过",
);
/* alpha:1061 我的意向摘要：slots 以「 / 」相连 */
const myIntentLine = computed(() =>
  game.myIntent ? game.myIntent.slots.map(slotName).join(" / ") : "",
);

/* ---- 点击分支 ---- */
/* alpha:907 点球局卡分支（判定在 utils/format 的 gameTapAction 单一源）：
   被邀请未加入 → joinSheet；其余 → 详情页。
   2.5 批2：卡片亮「进入现场」（enter 按钮或整卡点）→ goLive 直进现场——
   组织者成员同路，开账在后端幂等（spec §4.8）。 */
function onGameTap(g: Game, card?: GameCardModel): void {
  if (card?.liveEnter) {
    goLive(g.id);
    return;
  }
  if (gameTapAction(g) === "join") {
    ui.openSheet({ type: "join", gameId: g.id });
    return;
  }
  goGame(g.id);
}
function openIntentForm(): void {
  ui.openSheet({ type: "intent-form" });
}
/* alpha:1029 点意向卡 → 球友名片弹层 */
function onIntentTap(i: Intent): void {
  ui.openSheet({ type: "profile", userId: i.account.id });
}
/* alpha:927 恢复 / 删意向：失败 toast 人话，不打断浏览 */
function onRestore(g: Game): void {
  game.restoreGame(g.id).catch((e) => ui.toast(errText(e)));
}
function onDelIntent(): void {
  game.delIntent().catch((e) => ui.toast(errText(e)));
}
/* alpha:928 撤局 → cancel-confirm 弹层（已订场局带退订提醒，ConfirmSheet 分叉） */
function onCancel(g: Game): void {
  ui.openSheet({ type: "cancel-confirm", gameId: g.id });
}
/* 待处置「锁定必打」→ 订场面板（空锁二段确认 + 登记订场同一入口，4.7/4.9） */
function onLock(g: Game): void {
  ui.openSheet({ type: "booking", gameId: g.id });
}

/* —— 意向头贴底钉位 + 焦点切换（alpha:996-1016 同构，§2.3 取数换 uni API） —— */
const NAV_H = 64; // tokens.scss --nav-h=64px（alpha:1007 读不出时同样兜底 64）
let curScroll = 0; // onPageScroll 最近 scrollTop
let headTop = 0; // .isec-head 文档自然位（head.offsetTop 等价）
let headH = 0; // .isec-head 高
let winH = 0; // 视口高（alpha 的 box.clientHeight 等价）
const dockY = ref(0);
const dockStyle = computed(() =>
  dockY.value ? { transform: `translateY(${dockY.value}px)` } : {},
);

/** 量 .isec-head 文档自然位（渲染定型后调用） */
function measureHead(): void {
  dockY.value = 0; // 防止把钉位偏移量进自然位
  nextTick(() => {
    uni
      .createSelectorQuery()
      .select(".isec-head")
      .boundingClientRect()
      .exec((res) => {
        const r = res && res[0];
        if (!r || typeof r.top !== "number") return;
        headH = r.height ?? 0;
        headTop = r.top + curScroll; // 视口坐标 + 已滚距离 = 文档自然位（alpha:1008）
        dockHead();
      });
  });
}

/** alpha:1005-1011 dockIntentHead：自然位置沉到 nav 之下时拉到 nav 上方贴底；进入视口后释放 */
function dockHead(): void {
  if (!headH || !winH) return;
  const natural = headTop - curScroll; // alpha:1008
  const stickAt = winH - NAV_H - headH; // alpha:1009 头底紧贴底部导航条上沿
  dockY.value = natural > stickAt ? stickAt - natural : 0; // alpha:1010
}

onPageScroll((e) => {
  curScroll = e.scrollTop;
  dockHead();
});

/* alpha:996-1002 focusIntent：意向已焦点（头自然位距吸顶位 < 120px）→ 回球局；否则上升到球局头下方 */
function focusIntent(): void {
  const stickTop = 57; // alpha:998 = .isec-head 的 sticky top
  if (headTop - stickTop - curScroll < 120) {
    uni.pageScrollTo({ scrollTop: 0, duration: 300 });
  } else {
    uni.pageScrollTo({
      scrollTop: Math.max(0, headTop - stickTop),
      duration: 300,
    });
  }
}

onMounted(() => {
  winH = uni.getSystemInfoSync().windowHeight || 0;
  nextTick(() => measureHead());
});
onShow(() => {
  // 每次回页重拉：真局状态随时刻翻（懒判定发生在任何人打开的那一刻），本地不能装「最新」
  game.loadGames().catch((e) => ui.toast(errText(e)));
  game.loadMine().catch((e) => {
    // 游客没有「我的局」（401 no_identity 静默降级），别把「请先登录」糊游客一脸
    if (!(e instanceof ApiError && e.code === "no_identity"))
      ui.toast(errText(e));
  });
  game.loadIntents().catch((e) => ui.toast(errText(e)));
  game.loadMyIntent().catch(() => undefined); // 游客无意向，静默
  nextTick(() => measureHead());
});
/* 布局影响 headTop 的变化都要重测（折叠/筛选/scope/我的意向/球局与意向条数） */
watch(
  [
    filtersOpen,
    gamesFold,
    intentScope,
    () => game.myIntent,
    () => flt.value.length,
    () =>
      orgPending.value.length + orgDead.value.length + grayMine.value.length,
    () => myLiveOrg.value.length,
    () => ipool.value.length,
  ],
  () => measureHead(),
);
</script>

<style lang="scss" scoped>
/* alpha:1070 头部 brand 走全局 .brand/.bem 类（base.scss） */

/* 游客注册/登录入口（.useentry 同族的柠檬虚线主行 + dim 副行） */
.guestgate {
  margin: 0 0 14px;
}
.gg-main {
  border: 1px dashed rgba(255, 212, 0, 0.34);
  border-radius: var(--r-md);
  padding: 14px;
  text-align: center;
  color: var(--lemon);
  font-size: 13px;
  font-weight: 600;
  background: rgba(255, 212, 0, 0.04);
  cursor: pointer;
}
.gg-main:active {
  background: rgba(255, 212, 0, 0.1);
}

/* alpha:370-372 分区头：球局 · 悬浮置顶（CSS sticky） */
.msec-head {
  position: sticky;
  top: calc(env(safe-area-inset-top, 0px) + 6px);
  z-index: 6;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 12px;
  margin: 16px -8px 10px;
  background: rgba(20, 20, 26, 0.94);
  backdrop-filter: blur(6px);
}
/* alpha:373-374 */
.mh-t {
  font-family: var(--disp);
  font-size: 18px;
  letter-spacing: 0.02em;
}
.mh-n {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
}
/* alpha:375-378 mhbtn（+on 态） */
.mhbtn {
  padding: 6px 10px;
  border-radius: 9px;
  border: 1px solid rgba(245, 241, 232, 0.16);
  background: none;
  color: var(--dim);
  font-size: 11px;
  font-weight: 700;
  font-family: var(--sans);
  transition: 0.15s;
}
.mhbtn:active {
  color: var(--lemon);
  border-color: var(--lemon);
}
.mhbtn.on {
  color: var(--lemon);
  border-color: var(--lemon);
}
/* alpha:380-381 折叠筛选项（fadeUp 在全局 animations.scss） */
.fchips-wrap {
  display: none;
}
.fchips-wrap.open {
  display: block;
  animation: fadeUp 0.25s ease;
}
/* alpha:383-385 折叠列表的占位行 */
.foldrow {
  border: 1px dashed rgba(245, 241, 232, 0.16);
  border-radius: 12px;
  padding: 12px;
  text-align: center;
  color: var(--dim);
  font-size: 12px;
}
.foldrow:active {
  color: var(--lemon);
}
/* 参加者的当日灰字行（4.8/4.10「该局已取消」）：一行 dim 字，次日随 mine 不再返回而消失 */
.grayrow {
  border: 1px dashed rgba(245, 241, 232, 0.14);
  border-radius: 12px;
  padding: 10px 12px;
  margin-bottom: 8px;
  color: var(--dim);
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
/* 组织者远程散场入口行（2.3 §4.9）：珊瑚示警同散场钮语言 */
.sweeprow {
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid rgba(255, 90, 54, 0.4);
  border-radius: 12px;
  padding: 10px 12px;
  margin-bottom: 10px;
  background: rgba(255, 90, 54, 0.06);
  cursor: pointer;
}
.sweep-txt {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  color: var(--cream);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sweep-btn {
  flex: none;
  font-family: var(--mono);
  font-size: 11px;
  color: var(--coral);
  border: 1px solid rgba(255, 90, 54, 0.4);
  border-radius: 9px;
  padding: 5px 9px;
}

/* alpha:387-389 意向区头：CSS 吸顶 + JS 贴底钉位双通道 */
.isec-head {
  position: sticky;
  top: calc(env(safe-area-inset-top, 0px) + 57px);
  z-index: 6;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 12px;
  margin: 10px -8px 10px;
  background: rgba(20, 20, 26, 0.94);
  backdrop-filter: blur(6px);
  cursor: pointer;
  user-select: none;
}
/* alpha:356-358 留我的意向入口 */
.useentry {
  border: 1px dashed rgba(255, 212, 0, 0.34);
  border-radius: var(--r-md);
  padding: 15px;
  text-align: center;
  color: var(--lemon);
  font-size: 13px;
  font-weight: 600;
  background: rgba(255, 212, 0, 0.04);
  margin-bottom: 12px;
}
.useentry:active {
  background: rgba(255, 212, 0, 0.1);
}
/* alpha:390-391 我的意向条（idock-my） */
.idock-my {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px dashed rgba(111, 231, 255, 0.3);
  border-radius: 12px;
  padding: 10px 12px;
  background: rgba(111, 231, 255, 0.05);
}
.my-txt {
  font-size: 11px;
  color: var(--cream);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.my-btns {
  margin-left: auto;
  display: flex;
  gap: 6px;
  flex: none;
}
/* 小操作按钮走全局 .tbtn/.tbtn.on-no（base.scss 收源） */
.intent-note {
  font-size: 11px;
  margin: 2px 2px 0;
}
.tailpad {
  height: 24px;
}
.sp {
  flex: 1;
}
</style>
