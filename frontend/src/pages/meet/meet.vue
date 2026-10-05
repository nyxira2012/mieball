<template>
  <PageShell tab="meet">
    <!-- alpha:1069-1073 头部（.stag 入场 stagger，类在全局 base.scss） -->
    <view class="stag">
      <view class="kicker">Meet Up</view>
      <!-- alpha:1071 h1.brand 约<em>球</em>（em 用 text 承载，同 home/power 页约定） -->
      <view class="brand">约<text class="bem">球</text></view>
      <view class="sub">{{ dateLine }}</view>
    </view>

    <!-- alpha:1074 跑马灯：被邀请条目 + NEXT 最近参局倒计时（×2 无缝循环由 Ticker 内部负责） -->
    <Ticker :items="tickerItems" />

    <!-- alpha:1075-1080 球局区吸顶头（CSS sticky）· 筛选▾ / 收起 两钮 -->
    <view class="msec-head">
      <text class="mh-t">球局</text>
      <text class="mh-n">{{ flt.length }} 个 · 我参加 / 组织的置顶</text>
      <view class="sp" />
      <!-- alpha:1078 toggleFilters -->
      <view class="mhbtn" @click="filtersOpen = !filtersOpen">{{ filtersOpen ? '筛选 ▴' : '筛选 ▾' }}</view>
      <!-- alpha:1079 toggleGamesFold -->
      <view class="mhbtn" @click="gamesFold = !gamesFold">{{ gamesFold ? '展开' : '收起' }}</view>
    </view>

    <!-- alpha:1081-1086 折叠筛选区：时间 5 chips + 地区 5 chips（fchips/fchip → FilterChips） -->
    <view class="fchips-wrap" :class="{ open: filtersOpen }">
      <FilterChips v-model="fTime" :options="TIME_OPTS" />
      <FilterChips v-model="fArea" :options="AREA_OPTS" />
    </view>

    <!-- alpha:1087-1089 收起占位行 / 列表（pinned+rest 拼接）/ 空态 -->
    <view v-if="gamesFold" class="foldrow" @click="gamesFold = false">
      球局列表已收起 · 点展开 {{ flt.length }} 个局 ▸
    </view>
    <template v-else>
      <GameCard v-for="g in ordered" :key="g.id" :game="g" @tap="onGameTap(g)" />
      <EmptyBox v-if="!flt.length" text="这个时间 / 地点没有局 —— 换个筛法，或点右下角 ＋ 自己发一个" />
    </template>

    <!-- alpha:1090 未成局区（仅 dead 且组织者可见可恢复）：恢复/撤局 → store / cancel-confirm 弹层 -->
    <template v-if="deadMine.length">
      <SectionTitle title="未成局" more="到截止人数不足自动终止" />
      <DeadCard v-for="g in deadMine" :key="g.id" :game="g" @restore="onRestore(g)" @cancel="onCancel(g)" />
    </template>

    <!-- alpha:1091-1097 意向区头：CSS 吸顶 + 贴底钉位（dockY transform，alpha:1005-1011 同构）；
         整头点击切换焦点（alpha:996-1002），scope 两钮 stopPropagation -->
    <view class="isec-head" :style="dockStyle" @click="focusIntent">
      <text class="mh-t">意向</text>
      <text class="mh-n">{{ scopeLabel }} {{ ipool.length }} 条 · 点击切换焦点 ⇅</text>
      <view class="sp" />
      <view class="mhbtn" :class="{ on: intentScope === 'all' }" @click.stop="intentScope = 'all'">所有人</view>
      <view class="mhbtn" :class="{ on: intentScope === 'known' }" @click.stop="intentScope = 'known'">熟人</view>
    </view>

    <!-- alpha:1098-1102 意向区内容：我的意向条（改/删）或 留意向入口 + IntentCard 列表 + 说明行 -->
    <view class="intent-sec">
      <!-- alpha:1060-1064 idock-my 我的意向条 -->
      <view v-if="game.myIntent" class="idock-my">
        <text class="my-txt">我的意向 · {{ myIntentLine }} · {{ freqName(game.myIntent.freq) }}</text>
        <view class="my-btns">
          <view class="tbtn" @click="openIntentForm">✎ 改</view>
          <view class="tbtn on-no" @click="game.delIntent()">✕</view>
        </view>
      </view>
      <!-- alpha:1065 useentry 留意向入口（文案逐字） -->
      <view v-else class="useentry" @click="openIntentForm">＋ 留我的意向 —— 什么时段想打 · 组局的人会看见你</view>

      <!-- alpha:1100 isorted 列表（liked 优先 → 熟人优先）；点卡开球员档案（alpha:1029） -->
      <IntentCard v-for="i in isorted" :key="i.u.id" :intent="i" @tap="onIntentTap(i)" />
      <EmptyBox v-if="!isorted.length" text="这里还没有意向" />

      <!-- alpha:1101 底部说明行（内联 font-size:11px;margin:2px 2px 0） -->
      <view class="sub intent-note">默认熟人 · 喜欢的人优先 · 点击卡片查看球员档案与分值</view>
    </view>

    <!-- alpha:1103 页尾垫高 -->
    <view class="tailpad" />
  </PageShell>
</template>

<script setup lang="ts">
/* 约球页（alpha.html:952-1105 renderMeet · P7）。
   同一框架两区：球局（焦点·头 CSS sticky 吸顶）/ 意向（次焦点·头贴底钉位 + 点击切换焦点）。
   §2.3：alpha:996-1016 依赖 DOM offsetTop/getComputedStyle 的钉位/焦点逻辑，
   取数换成 onPageScroll + uni.createSelectorQuery（渲染后量 .isec-head 文档自然位，
   滚动时纯数值复算 transform 拉住/释放，释放后交给 CSS sticky 吸顶 —— 与 alpha 完全同构）。 */
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { onPageScroll, onShow } from '@dcloudio/uni-app';
import PageShell from '@/components/biz/PageShell.vue';
import GameCard from '@/components/biz/GameCard.vue';
import DeadCard from '@/components/biz/DeadCard.vue';
import IntentCard from '@/components/biz/IntentCard.vue';
import Ticker from '@/components/ui/Ticker.vue';
import type { TickerItem } from '@/components/ui/Ticker.vue';
import FilterChips from '@/components/ui/FilterChips.vue';
import SectionTitle from '@/components/ui/SectionTitle.vue';
import EmptyBox from '@/components/ui/EmptyBox.vue';
import type { Game, Intent } from '@/api/types';
import { AREA_OPTS, communityMeta } from '@/api';
import { useGameStore } from '@/stores/game';
import { useUiStore } from '@/stores/ui';
import { freqName, gameTapAction, isMine, isOpen, isOrg, known, myEntry, slotName } from '@/utils/format';
import { gameTime, untilTxt } from '@/utils/time';
import { goGame } from '@/utils/nav';

const game = useGameStore();
const ui = useUiStore();

/* ---- 头部（alpha:1072 日期行逐字，无「· ALPHA」尾——与首页 936 不同） ---- */
const dateLine = computed(() => {
  const d = new Date();
  return `${d.getMonth() + 1} 月 ${d.getDate()} 日 · 星期${'日一二三四五六'[d.getDay()]} · ${communityMeta.name}`;
});

/* ---- 状态（alpha:956） ---- */
const fTime = ref<string | number>('all');
const fArea = ref<string | number>('全部');
const intentScope = ref<'known' | 'all'>('known');
const filtersOpen = ref(false);
const gamesFold = ref(false);

/* alpha:1082-1085 筛选 chips：时间 5 + 地区 5（逐字） */
const TIME_OPTS = [
  { value: 'all', label: '全部时间' },
  { value: 'tonight', label: '今晚' },
  { value: 'tomorrow', label: '明天' },
  { value: 'weekend', label: '周末' },
  { value: 'week', label: '本周' },
];

/* ---- 跑马灯（alpha:983-994 meetTicker 逐字逻辑；s+s ×2 循环由 Ticker 负责） ---- */
const tickerItems = computed<TickerItem[]>(() => {
  const bits: TickerItem[] = [];
  // alpha:985-986 被邀请条目（未加入才提示）；isOpen 为列表过滤口径单一源（5.1 起排除 done 局）
  game.games
    .filter((g) => isOpen(g) && g.invitedMe && !myEntry(g))
    .forEach((g) =>
      bits.push({ tag: '邀请', text: `${g.organizer.name} 邀你加入「${g.name}」· 点一下就加入` }),
    );
  // alpha:987-990 NEXT：我参加/组织的局里最近一场的开打倒计时。
  // 消费 game store 的登记口径单一源 mySignups（含 !dead，登记页/我的页同源），
  // 再排掉 done 局——gameTime 会把已过的「周X」顺延下周、日期串兜底成今天，未来时间过滤排不掉终局
  const nx = game.mySignups
    .filter((g) => g.status !== 'done')
    .map((g) => ({ g, t: gameTime(g.t) }))
    .filter((x) => x.t.getTime() > Date.now())
    .sort((a, b) => a.t.getTime() - b.t.getTime())[0];
  const u = nx && untilTxt(nx.t);
  if (nx && u) bits.push({ tag: 'NEXT', text: `距离「${nx.g.name}」${nx.g.t.replace(' ', '')} 开打还有 ${u}` });
  // alpha:991 兜底条目
  if (!bits.length) bits.push({ tag: 'NOW', text: '暂无要开的局 · 意向底坞里攒下一场' });
  return bits;
});

/* ---- 球局区（alpha:1054-1057） ---- */
/* alpha:1054-1055 flt = games.filter(isOpen && (fTime all || tb) && (fArea 全部 || area))，gameTime 升序；
   5.1 起排除 done 局（本区只面向未开场的局，已结束局归登记/记录页）。
   排序先 map 出缓存的时间值再比（比较器里反复 gameTime 解析是 O(n log n) 次），tickerItems 同法 */
const ftv = computed(() => String(fTime.value));
const fav = computed(() => String(fArea.value));
const flt = computed(() =>
  game.games
    .filter(
      (g) =>
        isOpen(g) &&
        (ftv.value === 'all' || g.tb === ftv.value) &&
        (fav.value === '全部' || g.area === fav.value),
    )
    .map((g) => ({ g, t: gameTime(g.t).getTime() }))
    .sort((a, b) => a.t - b.t)
    .map((x) => x.g),
);
/* alpha:1056/1088 pinned = 我参加/组织的置顶，列表 = [...pinned, ...rest] */
const ordered = computed(() => {
  const pinned = flt.value.filter(isMine);
  const rest = flt.value.filter((g) => !isMine(g));
  return [...pinned, ...rest];
});
/* alpha:1057 未成局记录 · 仅组织者可见可恢复 */
const deadMine = computed(() => game.games.filter((g) => !!g.dead && isOrg(g)));

/* ---- 意向区（alpha:1058-1061/1093） ---- */
/* alpha:1058 ipool：scope==='all' 或 熟人（喜欢过/同局打过） */
const ipool = computed(() => game.intents.filter((i) => intentScope.value === 'all' || known(i.u)));
/* alpha:1059 isorted：liked 优先 → 熟人优先 */
const isorted = computed(() =>
  [...ipool.value].sort(
    (a, b) => (b.u.liked ? 1 : 0) - (a.u.liked ? 1 : 0) || (known(b.u) ? 1 : 0) - (known(a.u) ? 1 : 0),
  ),
);
/* alpha:1093 scope 标签两态 */
const scopeLabel = computed(() => (intentScope.value === 'all' ? '所有人' : '熟人'));
/* alpha:1061 我的意向摘要：slots 以「 / 」相连 */
const myIntentLine = computed(() => (game.myIntent ? game.myIntent.slots.map(slotName).join(' / ') : ''));

/* ---- 点击分支 ---- */
/* alpha:907 点球局卡分支同首页（判定在 utils/format 的 gameTapAction 单一源）：
   被邀请未加入 → joinSheet；其余 → 详情页 */
function onGameTap(g: Game): void {
  if (gameTapAction(g) === 'join') {
    ui.openSheet({ type: 'join', gameId: g.id });
    return;
  }
  goGame(g.id);
}
/* alpha:1063/1065 intentForm() → intent-form 弹层 */
function openIntentForm(): void {
  ui.openSheet({ type: 'intent-form' });
}
/* alpha:1029 openProfileById → profile 弹层 */
function onIntentTap(i: Intent): void {
  ui.openSheet({ type: 'profile', userId: i.u.id });
}
/* alpha:927 恢复（store 内 toast） */
function onRestore(g: Game): void {
  game.restoreGame(g.id);
}
/* alpha:928 撤局 → cancel-confirm 弹层 */
function onCancel(g: Game): void {
  ui.openSheet({ type: 'cancel-confirm', gameId: g.id });
}

/* —— 意向头贴底钉位 + 焦点切换（alpha:996-1016 同构，§2.3 取数换 uni API） ——
   alpha 每次 scroll 读 head.offsetTop（布局位，不含 transform）；这里在布局可能变化处
   （onMounted/onShow/折叠/筛选/scope/我的意向/列表条数）量一次 .isec-head 的文档自然位缓存，
   onPageScroll 里纯数值复算。量位前先清钉位 transform（boundingClientRect 含 transform，
   offsetTop 不含 —— 清零等价规避）。 */
const NAV_H = 64; // tokens.scss --nav-h=64px（alpha:1007 读不出时同样兜底 64）
let curScroll = 0; // onPageScroll 最近 scrollTop
let headTop = 0; // .isec-head 文档自然位（head.offsetTop 等价）
let headH = 0; // .isec-head 高
let winH = 0; // 视口高（alpha 的 box.clientHeight 等价）
const dockY = ref(0);
/* alpha:1010 head.style.transform —— 0 时不挂内联样式，交给 CSS sticky */
const dockStyle = computed(() => (dockY.value ? { transform: `translateY(${dockY.value}px)` } : {}));

/** 量 .isec-head 文档自然位（渲染定型后调用） */
function measureHead(): void {
  dockY.value = 0; // 防止把钉位偏移量进自然位
  nextTick(() => {
    uni
      .createSelectorQuery()
      .select('.isec-head')
      .boundingClientRect()
      .exec((res) => {
        const r = res && res[0];
        if (!r || typeof r.top !== 'number') return;
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

/* alpha:1014 scroll → rAF(dockIntentHead)：计算为纯数值，直接重算 */
onPageScroll((e) => {
  curScroll = e.scrollTop;
  dockHead();
});

/* alpha:996-1002 focusIntent：意向已焦点（头自然位距吸顶位 < 120px）→ 回球局；否则上升到球局头下方 */
function focusIntent(): void {
  const stickTop = 57; // alpha:998 = .isec-head 的 sticky top（env(safe-area-inset-top)+57px，H5 安全区为 0）
  if (headTop - stickTop - curScroll < 120) {
    uni.pageScrollTo({ scrollTop: 0, duration: 300 }); // 意向已是焦点 → 回到球局
  } else {
    uni.pageScrollTo({ scrollTop: Math.max(0, headTop - stickTop), duration: 300 }); // 上升到球局头下方
  }
}

onMounted(() => {
  winH = uni.getSystemInfoSync().windowHeight || 0;
  nextTick(() => measureHead());
});
onShow(() => {
  // tab 回切滚动位置保留（P3 约定），只重测钉位
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
    () => deadMine.value.length,
    () => ipool.value.length,
  ],
  () => measureHead(),
);
</script>

<style lang="scss" scoped>
/* alpha:1070 头部 brand 走全局 .brand/.bem 类（base.scss） */

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
/* alpha:387-389 意向区头：CSS 吸顶 + JS 贴底钉位（transform 由 dockStyle 挂）双通道 */
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
/* alpha:354 .msub2 + alpha:1061 内联覆写 margin:0;color:var(--cream) */
.my-txt {
  font-size: 11px;
  color: var(--cream);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* alpha:1062 内联 margin-left:auto;display:flex;gap:6px;flex:none */
.my-btns {
  margin-left: auto;
  display: flex;
  gap: 6px;
  flex: none;
}
/* 小操作按钮走全局 .tbtn/.tbtn.on-no（base.scss 收源） */
/* alpha:1101 说明行内联 font-size:11px;margin:2px 2px 0 */
.intent-note {
  font-size: 11px;
  margin: 2px 2px 0;
}
/* alpha:1103 页尾垫高 */
.tailpad {
  height: 24px;
}
.sp {
  flex: 1;
}
</style>
