<template>
  <PageShell tab="power">
    <view>
      <!-- 标题区 + 分制切换胶囊（alpha.html:1831-1843） -->
      <view class="stag">
        <view class="head">
          <view>
            <view class="kicker">Power Rating</view>
            <!-- alpha:1835 <h1 class="brand" style="margin-bottom:0">战<em>力</em>榜（em 用 text 承载，避堵小程序） -->
            <view class="brand">战<text class="em">力</text>榜</view>
          </view>
          <!-- alpha:1837-1840 sw-capsule：Elo/NTRP 切换（全局类 .sw-capsule 在 base.scss；行为 ui.setScoreMode，全页联动） -->
          <view class="sw-capsule">
            <text class="sw-opt" :class="{ on: ui.scoreMode === 'elo' }" @click="ui.setScoreMode('elo')">Elo</text>
            <text class="sw-opt" :class="{ on: ui.scoreMode === 'ntrp' }" @click="ui.setScoreMode('ntrp')">NTRP</text>
          </view>
        </view>
        <!-- alpha:1842 副标题两态 -->
        <view class="sub sub-mt">
          {{ ui.scoreMode === 'elo' ? 'Elo 默认 1500 起 · 内部引擎原始分' : 'NTRP 国际分级 (2.0-5.0) · 排阵对位参考' }}
        </view>
      </view>

      <!-- 我的战力卡（alpha:1844-1861）：点卡开我的档案，卡内头像去「我的」页 -->
      <MyPowerCard :rank="myRank" @profile="openProfile(userStore.me.id)" />

      <!-- 前三打架图（alpha:1862-1870）：点人开档案 -->
      <SectionTitle title="前三 · 对峙中" more="点人看档案" />
      <BrawlStage :top3="t3" @profile="openProfile" />

      <!-- 评分排行（alpha:1871-1875）：前三高亮 · 懒加载每批 5 条 -->
      <SectionTitle title="评分排行" :more="`${rows.length} 球员在榜 · 前三高亮`" />
      <view class="rank-frame">
        <view class="rank-list">
          <RankRow
            v-for="(u, i) in shown"
            :key="u.id"
            :user="u"
            :index="i"
            :lazy="i >= lazyFrom"
            @profile="openProfile"
          />
          <!-- alpha:1873 空榜（rankRows 为空才出现） -->
          <EmptyBox v-if="!rows.length" text="第一场球打出第一版排名" />
        </view>
        <!-- alpha:1874/1774-1784 尾部：点击亦可加载；全部加载完显示完毕文案（逐字） -->
        <view class="rank-tail" @click="loadMoreRank">
          <template v-if="done">
            <text class="tl-dim">· 全圈 {{ rows.length }} 位球员已加载完毕 ·</text>
          </template>
          <template v-else>
            <text class="tl-lemon">↑ 上滑显示更多</text>
            <!-- alpha:1782 两段间原有空格，这里用 4px 间距近似 -->
            <text class="tl-dim tl-gap">({{ rankLimit }}/{{ rows.length }}) · 点击亦可加载</text>
          </template>
        </view>
      </view>

      <!-- 规则折叠（alpha:1876-1885，四条文案逐字） -->
      <view class="rulefold" :class="{ open: rOpen }">
        <view class="rfhead" @click="rOpen = !rOpen">
          <text>积分怎么算的？</text>
          <text class="q">?</text>
        </view>
        <view class="rfbody">
          <view>· <text class="b">分制切换</text>：右上角开关随时切换 Elo (1500 起步原始分) 与 NTRP (2.0-5.0 国际分级)。</view>
          <view>· <text class="b">赢强者涨得多</text>：K=24，爆冷大涨、碾压小涨。</view>
          <view>· <text class="b">输了不掉肉</text>：败方只扣胜方涨分的六成，地板 400 分。</view>
          <view>· <text class="b">访客半权重、双打按队算</text>：两队人均分结算落到个人；访客不进榜。</view>
        </view>
      </view>

      <!-- alpha:1886 <div style="height:10px"> -->
      <view class="tailpad" />
    </view>
  </PageShell>
</template>

<script setup lang="ts">
/* 战力页（alpha.html:1824-1889 renderPower · P9）。
   分制切换调 ui.setScoreMode（alpha:1739-1744，切档 toast 由 store 发）；
   榜单懒加载 = alpha:1774-1822 的滚动通道（§2.4：IntersectionObserver → onPageScroll 距底 160px）；
   榜单/打架图/我的卡点击 → ui.openSheet({type:'profile',userId})。 */
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { onPageScroll, onShow } from '@dcloudio/uni-app';
import PageShell from '@/components/biz/PageShell.vue';
import MyPowerCard from '@/components/biz/MyPowerCard.vue';
import BrawlStage from '@/components/biz/BrawlStage.vue';
import RankRow from '@/components/biz/RankRow.vue';
import SectionTitle from '@/components/ui/SectionTitle.vue';
import EmptyBox from '@/components/ui/EmptyBox.vue';
import { useUiStore } from '@/stores/ui';
import { useUserStore } from '@/stores/user';

const ui = useUiStore();
const userStore = useUserStore();

/** alpha:865 rankRows：hasPlayed（!shadow && play>0，谓词单一源在 user store），按 elo 降序 */
const rows = computed(() =>
  Object.values(userStore.users)
    .filter(userStore.hasPlayed)
    .sort((a, b) => b.elo - a.elo),
);
/** alpha:1826 myRank = rows.findIndex(u=>u.id===me.id)+1（响应式 me.id） */
const myRank = computed(() => rows.value.findIndex((u) => u.id === userStore.me.id) + 1);
/** alpha:1827 t3 = rows.slice(0,3) */
const t3 = computed(() => rows.value.slice(0, 3));

/** alpha:1763 RANK_PAGE=5（框架最多 5 行，懒加载） */
const RANK_PAGE = 5;
/** alpha:1764 rankLimit */
const rankLimit = ref(RANK_PAGE);
/** 本批懒加载起始位次：≥ 此位的行带 lazy-in 入场（alpha:1768 isLazy，初始 5 行不带） */
const lazyFrom = ref(RANK_PAGE);
/** alpha:1873 rows.slice(0,rankLimit) */
const shown = computed(() => rows.value.slice(0, rankLimit.value));
/** alpha:1777 done = rankLimit>=total */
const done = computed(() => rankLimit.value >= rows.value.length);

/** 规则折叠展开态（alpha:1877 classList.toggle('open')） */
const rOpen = ref(false);

/** alpha:1768/1755 openProfileById → openSheet profile */
function openProfile(id: number): void {
  ui.openSheet({ type: 'profile', userId: id });
}

/* —— 懒加载（alpha:1774-1822 语义；容器滚动 → 页面 onPageScroll） —— */
const winH = ref(0);
let lastTop = 0; // 最近一次 onPageScroll 的 scrollTop
let pageH = 0; // 页面总内容高（=.page 的 bottom + 当时 scrollTop 折算）
let measuring = false; // Vue DOM 更新异步：本批量完页高前禁止连发（alpha 同步 innerHTML 无此问题）

/** 量 .page（PageShell 容器，含底部 nav 预留 padding）得到页面总高 */
function measure(after?: () => void): void {
  uni
    .createSelectorQuery()
    .select('.page')
    .boundingClientRect()
    .exec((res) => {
      const r = res && res[0];
      if (r && typeof r.bottom === 'number') pageH = lastTop + r.bottom;
      if (after) after();
    });
}

/** alpha:1785-1800 loadMoreRank：+RANK_PAGE，全部加载完即止 */
function loadMoreRank(): void {
  if (measuring || rankLimit.value >= rows.value.length) return;
  lazyFrom.value = rankLimit.value;
  rankLimit.value = Math.min(rows.value.length, rankLimit.value + RANK_PAGE);
  measuring = true;
  nextTick(() => measure(() => (measuring = false)));
}

/** alpha:1808-1813 距底 160px 自动加载 */
onPageScroll((e) => {
  lastTop = e.scrollTop;
  if (!pageH || done.value) return;
  if (lastTop + winH.value >= pageH - 160) loadMoreRank();
});

onMounted(() => {
  winH.value = uni.getSystemInfoSync().windowHeight || 0;
  nextTick(() => measure());
});

/** alpha:874 go('power')：每次进页 rankLimit 归 5 并回顶 */
onShow(() => {
  rankLimit.value = RANK_PAGE;
  lazyFrom.value = RANK_PAGE;
  uni.pageScrollTo({ scrollTop: 0, duration: 0 });
  nextTick(() => measure());
});

/** 折叠展开改变页高 → 重测，保持 160px 触发线准确 */
watch(rOpen, () => nextTick(() => measure()));
</script>

<style lang="scss" scoped>
/* alpha:1832 头行 flex 两端 · 底对齐 */
.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
}
/* alpha:1835 power 大字 margin-bottom:0（其余 brand/em 版式走全局 .brand 类） */
.brand {
  margin: 6px 0 0;
}
/* alpha:1842 sub margin-top:6px */
.sub-mt {
  margin-top: 6px;
}
/* alpha.html:493-494 .rank-frame */
.rank-frame {
  border: 1px solid rgba(245, 241, 232, 0.12);
  border-radius: var(--r-lg);
  background: rgba(20, 20, 26, 0.65);
  padding: 10px 10px 4px;
  margin-bottom: 12px;
  position: relative;
}
/* alpha.html:516-518 .rank-tail */
.rank-tail {
  text-align: center;
  font-family: var(--mono);
  font-size: 11px;
  color: var(--dim);
  padding: 11px 0 8px;
  cursor: pointer;
  border-radius: 10px;
  transition: background 0.2s, color 0.2s;
  user-select: none;
}
.rank-tail:active {
  color: var(--lemon);
  background: rgba(255, 212, 0, 0.05);
}
/* alpha:1779/1782 尾部两态配色 */
.tl-dim {
  color: var(--dim);
}
.tl-lemon {
  color: var(--lemon);
  font-weight: 700;
}
.tl-gap {
  margin-left: 4px;
}
/* alpha.html:532 .rulefold */
.rulefold {
  border: 1px dashed rgba(245, 241, 232, 0.16);
  border-radius: var(--r-md);
  margin-top: 10px;
  overflow: hidden;
}
/* alpha.html:533-534 .rfhead */
.rfhead {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  background: none;
  color: var(--cream);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  font-family: var(--sans);
}
/* alpha.html:535-536 .q */
.q {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 1px solid var(--lemon);
  color: var(--lemon);
  display: grid;
  place-items: center;
  font-size: 11px;
  font-family: var(--mono);
  flex: none;
}
/* alpha.html:537-538 .rfbody 默认收起 */
.rfbody {
  display: none;
  padding: 0 14px 12px;
  font-size: 12px;
  color: var(--dim);
  line-height: 1.9;
}
.rulefold.open .rfbody {
  display: block;
}
/* alpha.html:539 .rfbody b */
.rfbody .b {
  color: var(--lemon);
}
/* alpha:1886 页尾 10px 垫高 */
.tailpad {
  height: 10px;
}
</style>
