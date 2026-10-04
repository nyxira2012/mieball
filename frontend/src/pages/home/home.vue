<template>
  <PageShell tab="home">
    <!-- alpha:612-629 ① 首页 -->
    <!-- alpha:613-618 头部区块（.stag 入场 stagger，类在全局 base.scss） -->
    <view class="stag">
      <view class="kicker">Pickle · Tonight</view>
      <!-- alpha:615 h1.brand：夜<em>球</em>场<br>今夜有球 —— uni 模板不用 h1/br，
           页面自带同值 .brand 类 + block text 断行（同 detail 页约定） -->
      <view class="brand">夜<text class="bem">球</text>场<text class="brand-line">今夜有球</text></view>
      <!-- alpha:936 日期行逐字 -->
      <view class="sub">{{ dateLine }}</view>
      <!-- alpha:937-940 跑马灯：四段固定文案逐字，内容 ×2 无缝循环由 Ticker 内部负责 -->
      <Ticker :items="tickerItems" />
    </view>

    <!-- alpha:619 球局区（GAMES ▸ 在 alpha 为静态文案，无点击行为） -->
    <SectionTitle title="球局" more="GAMES ▸" />
    <view>
      <GameCard v-for="g in openGames" :key="g.id" :game="g" @tap="onGameTap(g)" />
    </view>

    <!-- alpha:621 约球区头（alpha:950 go-intent → go('meet')） -->
    <SectionTitle title="约球" more="去约球 ▸" @more="goMeet" />
    <!-- alpha:622-628 wave 卡（546-548 样式）·整卡点击 switchTab 约球页 -->
    <view class="wave" @click="goMeet">
      <view class="kicker wave-k">INTENT · 意向</view>
      <view class="wave-body">
        <view class="bignum">{{ waveN }}</view>
        <view class="wave-txt">
          <text>{{ waveLine1 }}</text>
          <text class="line2">{{ waveLine2 }}</text>
        </view>
      </view>
    </view>
  </PageShell>
</template>

<script setup lang="ts">
/* 首页（P4 · alpha:611-629 模板 + 933-950 renderHome）：
   日期行 / 跑马灯固定文案 / 球局列表（!dead 逐张 GameCard）/ 约球入口 wave 卡（有意向 · 无意向两态）。
   点卡分支照 alpha:907 —— 被邀请且未加入 → joinSheet；其余 → openDetail。 */
import { computed } from 'vue';
import PageShell from '@/components/biz/PageShell.vue';
import GameCard from '@/components/biz/GameCard.vue';
import SectionTitle from '@/components/ui/SectionTitle.vue';
import Ticker from '@/components/ui/Ticker.vue';
import type { TickerItem } from '@/components/ui/Ticker.vue';
import type { Game } from '@/api/types';
import { communityMeta } from '@/api';
import { useGameStore } from '@/stores/game';
import { useUiStore } from '@/stores/ui';
import { freqName, myEntry, slotName } from '@/utils/format';

const gameStore = useGameStore();
const ui = useUiStore();

/* ---- 头部（alpha:613-618） ---- */
/* alpha:936 日期行逐字：`${月} 月 ${日} 日 · 星期X · ${圈子} · ${版本}` */
const dateLine = computed(() => {
  const d = new Date();
  return `${d.getMonth() + 1} 月 ${d.getDate()} 日 · 星期${'日一二三四五六'[d.getDay()]} · ${communityMeta.name} · ${communityMeta.channel}`;
});

/* alpha:938-939 首页跑马灯四段逐字（NOW/ELO/INTENT/SHARE，源自 communityMeta mock 数据） */
const tickerItems: TickerItem[] = communityMeta.tickerItems;

/* ---- 球局列表（alpha:948 games.filter(g=>!g.dead)；5.1 起 games[] 混入 done 局，首页只列可参加局） ---- */
const openGames = computed(() => gameStore.games.filter((g) => !g.dead && g.status !== 'done'));

/* alpha:907 点卡分支：inv（被邀请且未加入）→ joinSheet(g.id)；其余 → openDetail(g.id) */
function onGameTap(g: Game): void {
  if (!!g.invitedMe && !myEntry(g)) {
    ui.openSheet({ type: 'join', gameId: g.id });
    return;
  }
  uni.navigateTo({ url: `/pages/detail/detail?id=${g.id}` });
}

/* ---- 约球入口 wave 卡（alpha:941-947 两态） ---- */
/* alpha:950 go('meet') + alpha:622 整卡 onclick go('meet') */
const goMeet = () => uni.switchTab({ url: '/pages/meet/meet' });

/* alpha:942/945 有意向 = waveCount()，无意向 = '—' */
const waveN = computed(() => (gameStore.myIntent ? String(gameStore.waveCount) : '—'));
/* alpha:943/946 文案两行逐字；有意向第二行 = 「时段 · 频率」 */
const waveLine1 = computed(() => (gameStore.myIntent ? '人正和你在同一个波段' : '还没留打球意向'));
const waveLine2 = computed(() =>
  gameStore.myIntent
    ? `「${slotName(gameStore.myIntent.slots[0])} · ${freqName(gameStore.myIntent.freq)}」`
    : '去「约球」留下你的波段');
</script>

<style lang="scss" scoped>
/* 页面专属样式。kicker/sub/sec-t 排版类在全局 base.scss；brand 因 uni 模板不能用 h1，
   页面自带同值类（alpha:86-87，同 detail 页约定）。 */
.brand {
  font-family: var(--disp);
  font-size: 34px;
  line-height: 1.04;
  margin: 6px 0 2px;
}
/* alpha:87 h1.brand em */
.brand .bem {
  font-style: normal;
  color: var(--lemon);
}
/* alpha:615 <br> 两行结构的等价实现（同 detail 页 .brand-line） */
.brand .brand-line {
  display: block;
}

/* ---------- wave 卡（alpha:546-548 + 622-628 内联样式） ---------- */
.wave {
  border: 1px solid rgba(111, 231, 255, 0.25);
  border-radius: var(--r-lg);
  padding: 18px;
  margin-bottom: 14px;
  background:
    radial-gradient(circle at 85% 0%, rgba(111, 231, 255, 0.08), transparent 55%),
    var(--ink2);
  cursor: pointer;
}
/* alpha:623 内联 style="color:var(--ice)" 的 kicker（电青） */
.wave .wave-k {
  color: var(--ice);
}
/* alpha:624 内联 flex 行 */
.wave-body {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 6px;
}
/* alpha:548 .wave .bignum */
.bignum {
  font-family: var(--disp);
  font-size: 54px;
  line-height: 1;
  color: var(--ice);
}
/* alpha:626 文案位 */
.wave-txt {
  font-size: 12px;
  color: var(--dim);
}
/* alpha:626 <br> 两行文案 */
.wave-txt .line2 {
  display: block;
}
</style>
