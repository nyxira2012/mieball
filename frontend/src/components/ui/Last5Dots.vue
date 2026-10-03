<template>
  <view v-if="results.length" class="last5">
    <view v-for="(r, i) in results" :key="i" class="last5-dot" :class="r === 'W' ? 'w' : 'l'" />
  </view>
</template>

<script setup lang="ts">
/* alpha.html:450-452 .last5 近 5 场 W/L 点 + 864 last5dots() 数据形态（'W'|'L'[]） */
import type { PropType } from 'vue'

defineProps({
  /** 近 5 场结果，按时间顺序，如 ['W','L','W','W','L'] */
  results: { type: Array as PropType<string[]>, default: () => [] },
})
</script>

<style lang="scss" scoped>
/* alpha.html:450-452 */
.last5 {
  display: inline-flex;
  gap: 4px;
  vertical-align: middle;
}
.last5-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.last5-dot.w {
  background: var(--lemon);
}
.last5-dot.l {
  background: var(--coral);
  opacity: 0.85;
}
</style>
