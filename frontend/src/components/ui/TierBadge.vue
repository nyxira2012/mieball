<template>
  <view class="tierb" :style="{ background: TIER_BG[tier], color: TIER_FG[tier] }">{{ tier }}</view>
</template>

<script setup lang="ts">
/* alpha.html:408-409 .tierb 段位徽章 + 861-862 TIER_BG/TIER_FG 配色（配色唯一真值在 utils/elo.ts）
   段位值由 utils/elo.ts 的 tier()（P2）从 Elo 分算出后传入，本组件只管展示 */
import type { PropType } from 'vue';
import { TIER_BG, TIER_FG, type Tier } from '@/utils/elo';

defineProps({
  tier: { type: String as PropType<Tier>, required: true },
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
