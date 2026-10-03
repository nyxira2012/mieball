<template>
  <view class="stepper">
    <view class="stepper-btn" @click="dec">−</view>
    <text class="val">{{ modelValue }}</text>
    <view class="stepper-btn" @click="inc">+</view>
  </view>
</template>

<script setup lang="ts">
/* alpha.html:181-185 .stepper 步进器（− 数值 +） */
import type { PropType } from 'vue'

const props = defineProps({
  modelValue: { type: Number, required: true },
  min: { type: Number, default: 0 },
  max: { type: Number, default: 99 },
  step: { type: Number as PropType<number>, default: 1 },
})
const emit = defineEmits<{ (e: 'update:modelValue', v: number): void }>()

const clamp = (v: number) => Math.min(props.max, Math.max(props.min, v))
const dec = () => emit('update:modelValue', clamp(props.modelValue - props.step))
const inc = () => emit('update:modelValue', clamp(props.modelValue + props.step))
</script>

<style lang="scss" scoped>
/* alpha.html:181-185 */
.stepper {
  display: flex;
  align-items: center;
  gap: 0;
  border: 1px solid rgba(245, 241, 232, 0.12);
  border-radius: 12px;
  overflow: hidden;
  background: var(--ink2);
}
.stepper-btn {
  width: 44px;
  height: 44px;
  background: none;
  border: none;
  color: var(--lemon);
  font-size: 20px;
  font-family: var(--mono);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.val {
  flex: 1;
  text-align: center;
  font-family: var(--disp);
  font-size: 20px;
}
</style>
