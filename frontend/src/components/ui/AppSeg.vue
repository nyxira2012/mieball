<template>
  <view class="seg">
    <view
      v-for="opt in options"
      :key="String(opt.value)"
      class="seg-btn"
      :class="{ on: opt.value === modelValue }"
      @click="select(opt.value)"
    >
      <view class="seg-label">{{ opt.label }}</view>
      <text v-if="opt.sub" class="seg-sub">{{ opt.sub }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
/* alpha.html:188-192 .seg 分段选择（大字 + 可选 small 副标），
   战力页 Elo/NTRP 切换、组局表单时长/频率段均用它 */
import type { PropType } from 'vue'

export interface SegOption {
  value: string | number
  label: string
  sub?: string
}

const props = defineProps({
  options: { type: Array as PropType<SegOption[]>, required: true },
  modelValue: { type: [String, Number] as PropType<string | number>, default: '' },
})
const emit = defineEmits<{ (e: 'update:modelValue', v: string | number): void }>()

const select = (v: string | number) => emit('update:modelValue', v)
</script>

<style lang="scss" scoped>
/* alpha.html:188-192 */
.seg {
  display: flex;
  border: 1px solid rgba(245, 241, 232, 0.12);
  border-radius: 13px;
  overflow: hidden;
  background: var(--ink2);
}
.seg-btn {
  flex: 1;
  padding: 12px 4px;
  background: none;
  border: none;
  color: var(--dim);
  cursor: pointer;
  transition: 0.2s;
  text-align: center;
}
.seg-label {
  font-family: var(--disp);
  font-size: 17px;
}
.seg-sub {
  display: block;
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.1em;
}
.seg-btn.on {
  background: var(--lemon);
  color: var(--ink);
}
.seg-btn.on .seg-sub {
  color: var(--ink);
}
</style>
