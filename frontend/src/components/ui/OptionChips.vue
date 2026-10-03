<template>
  <view class="crow">
    <view
      v-for="opt in normOptions"
      :key="String(opt.value)"
      class="cbtn"
      :class="{ on: opt.value === modelValue }"
      @click="select(opt.value)"
    >
      {{ opt.label }}
    </view>
  </view>
</template>

<script setup lang="ts">
/* alpha.html:203-206 .crow/.cbtn 可选 chips 行（组局表单的时间/时长/费用等单选组） */
import { computed } from 'vue'
import type { PropType } from 'vue'

export interface CrowOption {
  value: string | number
  label: string
}

const props = defineProps({
  /** 传字符串数组（value=label）或 {value,label} 数组 */
  options: { type: Array as PropType<Array<string | number | CrowOption>>, required: true },
  modelValue: { type: [String, Number] as PropType<string | number>, default: '' },
})
const emit = defineEmits<{ (e: 'update:modelValue', v: string | number): void }>()

const normOptions = computed<CrowOption[]>(() =>
  props.options.map((o) => (typeof o === 'object' ? o : { value: o, label: String(o) })),
)
const select = (v: string | number) => emit('update:modelValue', v)
</script>

<style lang="scss" scoped>
/* alpha.html:203-206 */
.crow {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.cbtn {
  padding: 9px 14px;
  border-radius: 12px;
  border: 1px solid rgba(245, 241, 232, 0.14);
  background: var(--ink);
  color: var(--dim);
  font-size: 13px;
  cursor: pointer;
  transition: 0.15s;
  font-family: var(--sans);
}
.cbtn.on {
  background: var(--lemon);
  color: var(--ink);
  border-color: var(--lemon);
  font-weight: 700;
}
</style>
