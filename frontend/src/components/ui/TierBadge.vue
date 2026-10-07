<template>
  <view class="tierb" :style="{ background: DUPR_TIER_BG[tier], color: DUPR_TIER_FG[tier] }">{{ tier }}</view>
</template>

<script setup lang="ts">
/* alpha.html:408-409 .tierb 段位徽章。批4v1 起吃 string 档名（"2.0"~"4.0+"，DUPR 段位口径），
   档名由 utils/elo.ts 的 duprTier() 算出后传入，配色唯一真值也在 utils/elo.ts
   （DUPR_TIER_BG/FG；旧 Tier 型与 TIER_BG/TIER_FG 归批4v2 删），本组件只管展示 */
import type { PropType } from 'vue';
import { DUPR_TIER_BG, DUPR_TIER_FG } from '@/utils/elo';

defineProps({
  tier: { type: String as PropType<string>, required: true },
});
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
