<template>
  <!-- 参加登记页（5.1 子页）：已报名/组局的局一屏看全（含已结束局看签到行），点卡进原约球详情。
       列表口径/局卡与约球页同族（GameCard 复用），本页只做筛选与导航。 -->
  <PageShell>
    <!-- 子页统一返回行（bills.vue 同形态） -->
    <view class="backrow" @click="goBack">◂ 返回</view>

    <view class="stag">
      <view class="kicker">My Games</view>
      <view class="brand">登<text class="bem">记</text></view>
    </view>

    <!-- 头统计：共 N 局 = 下方全量条数（不随筛选变）；签到 = 其中 done 且留了 checkIn 的局数（mine.vue 双卡同口径） -->
    <view class="stat">共 {{ mine.length }} 局 · 签到 {{ checkins }} 次</view>

    <!-- 状态筛选（5.1 辅助功能：登记按状态） -->
    <FilterChips v-model="mode" :options="MODE_OPTS" />

    <template v-if="list.length">
      <view v-for="g in list" :key="g.id" class="cell">
        <GameCard :game="g" @tap="openGame(g)" />
        <!-- 签到底账行（验收故事 3「签到 19:02 · 早退 21:30」）：仅 done 且有 myLog 才渲染（94 局无 myLog 不出该行） -->
        <view v-if="g.myLog?.checkIn" class="logline">
          签到 {{ g.myLog.checkIn }}{{ g.myLog.checkOut ? ' · 早退 ' + g.myLog.checkOut : '' }}
        </view>
      </view>
    </template>
    <EmptyBox v-else :text="emptyTxt" />
  </PageShell>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import PageShell from '@/components/biz/PageShell.vue';
import GameCard from '@/components/biz/GameCard.vue';
import FilterChips from '@/components/ui/FilterChips.vue';
import EmptyBox from '@/components/ui/EmptyBox.vue';
import { useGameStore } from '@/stores/game';
import { isOrg, myEntry } from '@/utils/format';
import { dayOrd, gameTime } from '@/utils/time';
import type { Game } from '@/api/types';

const game = useGameStore();

/** 我的登记全集：我组织 / 已报名 且未终止（含 done —— 已结束局要在登记页看到签到行）。mine.vue 头卡同口径 */
const mine = computed(() => game.games.filter((g) => !g.dead && (isOrg(g) || myEntry(g))));
/** 其中留有签到底账的局数 */
const checkins = computed(() => mine.value.filter((g) => g.status === 'done' && g.myLog?.checkIn).length);

/* 状态单选（string|number 对齐 FilterChips v-model 联合类型，meet.vue fTime 同法） */
const mode = ref<string | number>('all');
const MODE_OPTS = [
  { value: 'all', label: '全部' },
  { value: 'open', label: '未开场' },
  { value: 'done', label: '已结束' },
];

/* 未开场按 gameTime 升序；done 按 d 倒序 —— d 是 'M.DD' 且月份不补零，跨月时字符串比较
   会把 9.x 排到 10.x 之后，必须走 dayOrd（月*100+日）才与账单页同源单调 */
const openGames = computed(() =>
  mine.value.filter((g) => g.status !== 'done').sort((a, b) => gameTime(a.t).getTime() - gameTime(b.t).getTime()),
);
const doneGames = computed(() =>
  mine.value.filter((g) => g.status === 'done').sort((a, b) => dayOrd(b.d) - dayOrd(a.d)),
);
/** 全部档 = 未开场在前 + done 在后（5.1：登记页主看 upcoming） */
const list = computed<Game[]>(() => {
  if (mode.value === 'open') return openGames.value;
  if (mode.value === 'done') return doneGames.value;
  return [...openGames.value, ...doneGames.value];
});

const emptyTxt = computed(() => {
  if (mode.value === 'open') return '没有待开场的局 · 去约球页找一局';
  if (mode.value === 'done') return '还没有打完的局';
  return '还没有报过名 · 去约球页找一局';
});

/** 局卡点击进原约球详情页（5.1） */
function openGame(g: Game): void {
  uni.navigateTo({ url: '/pages/detail/detail?id=' + g.id });
}
function goBack(): void {
  uni.navigateBack();
}
</script>

<style lang="scss" scoped>
/* ---------- 子页统一返回行（mono 11px dim · :active lemon） ---------- */
.backrow {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--dim);
  padding: 8px 2px;
  cursor: pointer;
  display: inline-block;
}
.backrow:active {
  color: var(--lemon);
}

/* ---------- 头部 brand（bills.vue 同款） ---------- */
.brand {
  font-family: var(--disp);
  font-size: 34px;
  line-height: 1.04;
  margin: 6px 0 2px;
  font-weight: 700;
}
.brand .bem {
  font-style: normal;
  color: var(--lemon);
}

/* 头统计行（mono 10px dim） */
.stat {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  margin: 4px 2px 8px;
}

/* 签到行：贴在局卡下沿（GameCard 自带 margin-bottom 12px，负 margin 收拢） */
.logline {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  margin: -8px 4px 8px;
}
</style>
