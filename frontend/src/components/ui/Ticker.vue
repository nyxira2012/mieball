<template>
  <view v-if="items.length" class="ticker">
    <view class="ticker-in">
      <!-- 内容 ×2 无缝循环（alpha:937-940 items+items 配 tick 位移 -50%） -->
      <view v-for="(it, i) in doubled" :key="i" class="ticker-item">
        <text v-if="it.tag" class="tk-tag">{{ it.tag }}</text>
        <text class="tk-txt">{{ it.text }}</text>
        <text class="tk-dot">●</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
/* alpha.html:94-100 .ticker/.ticker-in 跑马灯（26s 线性循环、b 黄 / i 珊瑚 ●） */
import { computed } from 'vue'
import type { PropType } from 'vue'

export interface TickerItem {
  /** 黄色加粗前缀，如 NOW / ELO / 邀请 */
  tag?: string
  /** 正文 */
  text: string
}

const props = defineProps({
  items: { type: Array as PropType<TickerItem[]>, default: () => [] },
})

const doubled = computed(() => [...props.items, ...props.items])
</script>

<style lang="scss" scoped>
/* alpha.html:94-100 */
.ticker {
  overflow: hidden;
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
  margin: 16px -18px 4px;
  padding: 7px 0;
  background: rgba(255, 212, 0, 0.04);
}
.ticker-in {
  display: inline-flex;
  gap: 44px;
  white-space: nowrap;
  animation: tick 26s linear infinite;
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.14em;
  color: rgba(245, 241, 232, 0.72);
}
.ticker-item {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
}
.tk-tag {
  color: var(--lemon);
}
.tk-dot {
  font-style: normal;
  color: var(--coral);
}
</style>
