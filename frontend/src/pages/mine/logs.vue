<template>
  <!-- 打球记录页（5.1 子页）：done 局一场一行按时间倒序 + 期间筛选，点卡进打球详情。
       局卡渲染完全复用 GameCard done 分支（已结束 + 比分胜/负）。 -->
  <PageShell>
    <!-- 子页统一返回行（BackRow） -->
    <BackRow />

    <view class="stag">
      <view class="kicker">Match Log</view>
      <view class="brand">记<text class="bem">录</text></view>
    </view>

    <!-- 头统计：累计 N 场 = me.play，与列表条数解耦 —— mock 只收录最近几场，口径同档案卡（技术设计残余决策 3） -->
    <view class="stat">累计 {{ me.play }} 场</view>

    <!-- 期间筛选（5.1 辅助功能：记录按时间） -->
    <FilterChips v-model="period" :options="PERIOD_OPTS" />

    <template v-if="list.length">
      <GameCard v-for="g in list" :key="g.id" :game="g" @tap="openGame(g)" />
    </template>
    <EmptyBox v-else text="这段期间没有打过的局 · 换个筛法" />
  </PageShell>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import PageShell from '@/components/biz/PageShell.vue';
import BackRow from '@/components/biz/BackRow.vue';
import GameCard from '@/components/biz/GameCard.vue';
import FilterChips from '@/components/ui/FilterChips.vue';
import EmptyBox from '@/components/ui/EmptyBox.vue';
import { useGameStore } from '@/stores/game';
import { useUserStore } from '@/stores/user';
import { PERIOD_FROM, PERIOD_OPTS, type BillPeriod } from '@/stores/bill';
import { dayOrd } from '@/utils/time';
import { goGame } from '@/utils/nav';
import type { Game } from '@/api/types';

const game = useGameStore();
const user = useUserStore();
const me = computed(() => user.me);

/* 期间档位与下界同源 bill store（BillPeriod/PERIOD_FROM/PERIOD_OPTS），本页不再持副本 */
const period = ref<BillPeriod>('all');

/** 记录列表：done 局按期间过滤（dayOrd 月*100+日，月份不补零不能裸比较字符串）后 d 倒序 */
const list = computed<Game[]>(() => {
  const done = game.games.filter((g) => g.status === 'done');
  const from = period.value === 'all' ? null : PERIOD_FROM[String(period.value) as Exclude<BillPeriod, 'all'>];
  const hit = from ? done.filter((g) => dayOrd(g.d) >= dayOrd(from)) : done;
  return hit.sort((a, b) => dayOrd(b.d) - dayOrd(a.d));
});

/** 局卡点击进打球详情页（5.1；路径契约在 utils/nav 单一源） */
function openGame(g: Game): void {
  goGame(g.id);
}
</script>

<style lang="scss" scoped>
/* ---------- 头部 brand：版式走全局 .brand 类，只补 700 加粗（bills 同款） ---------- */
.brand {
  font-weight: 700;
}

/* 头统计行（mono 10px dim） */
.stat {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  margin: 4px 2px 8px;
}
</style>
