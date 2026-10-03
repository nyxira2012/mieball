<template>
  <view class="stack">
    <view v-for="(c, i) in shown" :key="i" class="stack-av">
      <ChibiAvatar :chibi="c" :size="26" />
    </view>
    <text v-if="rest > 0" class="plusn">+{{ rest }}</text>
  </view>
</template>

<script setup lang="ts">
/* alpha.html:127-132 .gcard .stack 头像叠层（前 N + +N；N 默认 5，
   「含随行」的名单展开由业务层传入 heads 数组完成） */
import { computed } from 'vue'
import type { PropType } from 'vue'
import ChibiAvatar from './ChibiAvatar.vue'
import type { ChibiConfig } from '@/utils/chibi'

const props = defineProps({
  /** 名单 chibi 配置数组（含随行展开后的完整名单） */
  avatars: { type: Array as PropType<ChibiConfig[]>, default: () => [] },
  /** 展示上限，超出部分折叠为 +N */
  max: { type: Number, default: 5 },
})

const shown = computed(() => props.avatars.slice(0, props.max))
const rest = computed(() => Math.max(0, props.avatars.length - props.max))
</script>

<style lang="scss" scoped>
/* alpha.html:127-132 */
.stack {
  display: flex;
}
.stack-av {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--ink2);
  border: 2px solid var(--ink2);
  margin-left: -9px;
  overflow: hidden;
  display: grid;
  place-items: center;
  box-sizing: content-box;
}
.stack-av:first-child {
  margin-left: 0;
}
/* alpha:131 叠层小头像里 svg 放大 150% 并下移，只露脸 */
.stack-av :deep(svg) {
  width: 150%;
  height: 150%;
  margin-top: 16%;
}
.plusn {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  margin-left: 2px;
}
</style>
