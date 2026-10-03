<template>
  <!-- 榜单单行（alpha.html:1765-1773 rankRowHtml 逐字）：
       名次大字 · 头像 40 · 名 + 我徽章 + ♥ + TierBadge · Last5Dots + 近 5 场 · N 战 ·
       右列 fmtScore + (NTRP 单位) + 本月涨跌。前三 top-1/2/3 高亮，新批次行 lazy-in 入场。 -->
  <view class="rank-row" :class="[topCls, { 'lazy-in': lazy }]" @click="emit('profile', user.id)">
    <!-- alpha:1769 名次 -->
    <view class="no">{{ index + 1 }}</view>
    <ChibiAvatar :chibi="user.chibi" :size="40" />
    <view class="mid">
      <view class="nm">
        <text class="nm-t">{{ user.name }}</text>
        <!-- alpha:1770 u.id===0 → 「我」徽章 · liked → ♥ -->
        <text v-if="user.id === 0" class="badge fire">我</text>
        <text v-if="user.liked" class="hrt">♥</text>
        <TierBadge :tier="tier(user.elo)" />
      </view>
      <view class="st">
        <Last5Dots :results="user.last5 || []" />
        <text class="st-t">近 5 场 · {{ user.play }} 战</text>
      </view>
    </view>
    <view class="elo">
      <text class="sc">{{ fmtScore(user.elo, ui.scoreMode) }}</text>
      <!-- alpha:1772 ntrp 分制下才带 NTRP 角标 -->
      <text v-if="ui.scoreMode === 'ntrp'" class="unit">NTRP</text>
      <text class="d" :class="user.month >= 0 ? 'up' : 'dn'">
        {{ user.month >= 0 ? '▲' : '▼' }}{{ Math.abs(user.month) }} 本月
      </text>
    </view>
  </view>
</template>

<script setup lang="ts">
/* 评分排行单行 RankRow（alpha.html:1765-1773 · P9）。business 件：组合 ChibiAvatar/TierBadge/Last5Dots。 */
import { computed } from 'vue';
import type { PropType } from 'vue';
import ChibiAvatar from '@/components/ui/ChibiAvatar.vue';
import TierBadge from '@/components/ui/TierBadge.vue';
import Last5Dots from '@/components/ui/Last5Dots.vue';
import type { User } from '@/api/types';
import { useUiStore } from '@/stores/ui';
import { fmtScore, tier } from '@/utils/elo';

const props = defineProps({
  /** 榜单行球员（rankRows 过滤 !shadow && play>0 后的有序一条） */
  user: { type: Object as PropType<User>, required: true },
  /** 0 起榜单位次（alpha:1766/1769） */
  index: { type: Number, required: true },
  /** 本批懒加载新行 → lazy-in 入场动画（alpha:1768 isLazy） */
  lazy: { type: Boolean, default: false },
});

const emit = defineEmits<{ (e: 'profile', userId: number): void }>();

const ui = useUiStore();

/** alpha:1766 topCls = i===0?'top-1':i===1?'top-2':i===2?'top-3':'' */
const topCls = computed(() => (props.index === 0 ? 'top-1' : props.index === 1 ? 'top-2' : props.index === 2 ? 'top-3' : ''));
</script>

<style lang="scss" scoped>
/* alpha.html:495-498 .rank-row */
.rank-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 12px;
  border-radius: 14px;
  border: 1px solid rgba(245, 241, 232, 0.08);
  background: var(--ink2);
  margin-bottom: 8px;
  cursor: pointer;
  transition: border-color 0.15s, transform 0.12s;
}
.rank-row:active {
  border-color: rgba(255, 212, 0, 0.4);
  transform: scale(0.98);
}
/* alpha.html:499-508 前三行高亮 */
.rank-row.top-1 {
  border-color: rgba(255, 212, 0, 0.55);
  background: linear-gradient(150deg, rgba(255, 212, 0, 0.15), var(--ink2));
  box-shadow: inset 0 0 18px rgba(255, 212, 0, 0.08);
}
.rank-row.top-1 .no {
  color: var(--lemon);
  font-weight: 800;
  text-shadow: 0 0 10px rgba(255, 212, 0, 0.5);
}
.rank-row.top-2 {
  border-color: rgba(255, 90, 54, 0.45);
  background: linear-gradient(150deg, rgba(255, 90, 54, 0.11), var(--ink2));
  box-shadow: inset 0 0 16px rgba(255, 90, 54, 0.06);
}
.rank-row.top-2 .no {
  color: var(--coral);
  font-weight: 700;
}
.rank-row.top-3 {
  border-color: rgba(111, 231, 255, 0.45);
  background: linear-gradient(150deg, rgba(111, 231, 255, 0.1), var(--ink2));
  box-shadow: inset 0 0 16px rgba(111, 231, 255, 0.06);
}
.rank-row.top-3 .no {
  color: var(--ice);
  font-weight: 700;
}
/* alpha.html:509-514 .no/.mid/.nm/.st/.elo */
.no {
  font-family: var(--disp);
  font-size: 18px;
  width: 26px;
  color: var(--dim);
  text-align: center;
  flex: none;
}
.mid {
  flex: 1;
  min-width: 0;
}
.nm {
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}
/* alpha:1770 u.liked → ♥（内联 color:var(--coral);font-size:12px） */
.hrt {
  color: var(--coral);
  font-size: 12px;
}
.st {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  margin-top: 2px;
}
/* alpha:1771 「近 5 场 · N 战」margin-left:4px */
.st-t {
  margin-left: 4px;
}
.elo {
  font-family: var(--disp);
  font-size: 20px;
  color: var(--cream);
  text-align: right;
}
/* alpha:1772 NTRP 角标（font-size:9px · mono · dim · margin-left:2px） */
.unit {
  font-size: 9px;
  font-family: var(--mono);
  color: var(--dim);
  margin-left: 2px;
}
/* alpha.html:515 .rank-row .d（块级）+ 449 两色 */
.d {
  font-family: var(--mono);
  font-size: 10px;
  display: block;
}
.d.up {
  color: var(--lemon);
}
.d.dn {
  color: var(--coral);
}
/* alpha.html:291+293 「我」徽章（badge.fire） */
.badge {
  display: inline-block;
  font-family: var(--mono);
  font-size: 9px;
  border-radius: 6px;
  padding: 1px 5px;
  margin-top: 2px;
}
.badge.fire {
  background: rgba(255, 90, 54, 0.18);
  color: var(--coral);
}
/* alpha.html:519 懒加载新行入场（rankFadeIn keyframes 全局 animations.scss alpha:520） */
.rank-row.lazy-in {
  animation: rankFadeIn 0.28s ease-out backwards;
}
</style>
