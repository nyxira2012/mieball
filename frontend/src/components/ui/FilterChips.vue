<template>
  <scroll-view class="fchips" scroll-x :show-scrollbar="false">
    <view
      v-for="opt in normOptions"
      :key="String(opt.value)"
      class="fchip"
      :class="{ on: isActive(opt.value) }"
      @click="select(opt.value)"
    >
      {{ opt.label }}
    </view>
  </scroll-view>
</template>

<script setup lang="ts">
/* alpha.html:334-337 .fchips/.fchip 找局打横滚筛选 chips（单选） */
import { computed } from 'vue'
import type { PropType } from 'vue'

export interface FchipOption {
  value: string | number
  label: string
}

const props = defineProps({
  options: { type: Array as PropType<Array<string | number | FchipOption>>, required: true },
  modelValue: { type: [String, Number] as PropType<string | number>, default: '' },
})
const emit = defineEmits<{ (e: 'update:modelValue', v: string | number): void }>()

const normOptions = computed<FchipOption[]>(() =>
  props.options.map((o) => (typeof o === 'object' ? o : { value: o, label: String(o) })),
)

const isActive = (v: string | number) => props.modelValue === v

const select = (v: string | number) => {
  emit('update:modelValue', v)
}
</script>

<style lang="scss" scoped>
/* alpha.html:334-337（横滚容器用 uni scroll-view 替代 overflow-x:auto） */
.fchips {
  display: flex;
  gap: 6px;
  padding: 2px 1px 4px;
  margin-bottom: 6px;
  white-space: nowrap;
}
.fchip {
  flex: none;
  display: inline-block;
  padding: 6px 12px;
  border-radius: 99px;
  border: 1px solid rgba(245, 241, 232, 0.14);
  background: var(--ink);
  color: var(--dim);
  font-size: 11px;
  font-family: var(--sans);
  cursor: pointer;
  transition: 0.15s;
  line-height: 1.5;
}
.fchip.on {
  background: var(--lemon);
  color: var(--ink);
  border-color: var(--lemon);
  font-weight: 700;
}
</style>
