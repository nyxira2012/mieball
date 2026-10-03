<template>
  <view class="tierb" :style="{ background: TIER_BG[tier], color: TIER_FG[tier] }">{{ tier }}</view>
</template>

<script setup lang="ts">
/* alpha.html:408-409 .tierb 段位徽章 + 861-862 TIER_BG/TIER_FG 配色（原文照搬）
   段位值由 utils/elo.ts 的 tier()（P2）从 Elo 分算出后传入，本组件只管展示 */
import type { PropType } from 'vue'

defineProps({
  tier: { type: String as PropType<'SS' | 'S' | 'A' | 'B' | 'C'>, required: true },
})

/* alpha.html:861-862 */
const TIER_BG: Record<string, string> = {
  SS: 'rgba(255,90,54,.2)',
  S: 'rgba(255,212,0,.18)',
  A: 'rgba(111,231,255,.16)',
  B: 'rgba(184,169,255,.16)',
  C: 'rgba(245,241,232,.1)',
}
const TIER_FG: Record<string, string> = {
  SS: 'var(--coral)',
  S: 'var(--lemon)',
  A: 'var(--ice)',
  B: 'var(--lilac)',
  C: 'var(--dim)',
}
</script>

<style lang="scss" scoped>
/* alpha.html:408-409 */
.tierb {
  display: inline-grid;
  place-items: center;
  min-width: 24px;
  height: 19px;
  padding: 0 5px;
  border-radius: 6px;
  font-family: var(--disp);
  font-size: 11px;
  letter-spacing: 0.04em;
  vertical-align: middle;
}
</style>
