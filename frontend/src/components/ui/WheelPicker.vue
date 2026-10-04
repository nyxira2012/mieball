<template>
  <!-- 拨盘（3.3 组局表单改版新增）：picker-view 薄封装 —— 列文案 + 表头 + 受控选中下标。
       列内容可随选中动态变化（结束时刻受开始时刻约束、截止拨盘范围受开打约束），
       夹取逻辑归父层：父层改 modelValue 下标后 :value 回传，picker-view 自行滚到位。 -->
  <view class="wp">
    <view v-if="headers.length" class="wp-head">
      <text v-for="(h, i) in headers" :key="i" class="wp-h" :style="colStyle(i)">{{ h }}</text>
    </view>
    <picker-view class="wp-view" :value="safeIdx" :style="{ height: `${viewH}px` }" @change="onChange">
      <picker-view-column v-for="(col, ci) in cols" :key="ci" :style="colStyle(ci)">
        <view v-for="(opt, oi) in col" :key="oi" class="wp-it">{{ opt }}</view>
      </picker-view-column>
    </picker-view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { PropType } from 'vue';

const props = defineProps({
  /** 每列的选项文案（外层下标=列，内层=行） */
  cols: { type: Array as PropType<string[][]>, required: true },
  /** 列表头（与 cols 等长，空数组不渲染） */
  headers: { type: Array as PropType<string[]>, default: () => [] },
  /** 各列 flex 权重（不传等分） */
  widths: { type: Array as PropType<number[]>, default: () => [] },
  /** 各列当前选中下标（受控值） */
  modelValue: { type: Array as PropType<number[]>, required: true },
});
const emit = defineEmits<{ (e: 'update:modelValue', v: number[]): void }>();

const viewH = 128; // 4 行 × 32px 指示带（行高必须与 indicator 内容区一致，uni 按它算滚动步长）

/** 越界夹取：动态列变短后旧下标可能超界，picker-view 需要始终合法的 value */
const safeIdx = computed(() =>
  props.modelValue.map((v, i) => Math.max(0, Math.min(v, (props.cols[i]?.length ?? 1) - 1))),
);

function colStyle(i: number): Record<string, string> {
  return props.widths[i] ? { flex: String(props.widths[i]) } : {};
}

function onChange(e: { detail: { value: number[] } }): void {
  emit('update:modelValue', [...e.detail.value]);
}
</script>

<style lang="scss" scoped>
.wp {
  margin-bottom: 2px;
}
/* 列表头与列同宽（mono 小字，同 .field-label 家族） */
.wp-head {
  display: flex;
  margin-bottom: 4px;
}
.wp-h {
  flex: 1;
  text-align: center;
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.2em;
  color: var(--dim);
}
.wp-view {
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--ink);
}
.wp-it {
  height: 32px;
  line-height: 32px;
  text-align: center;
  font-family: var(--mono);
  font-size: 15px;
  color: var(--cream);
}
/* 指示带（选中行）：高度必须用 border-box 的内容区口径与 .wp-it 严格一致（uni 的 ResizeSensor
   量的是内容区高度作为滚动步长，边框会造成累积错位）——发丝线用 inset 阴影画，不吃布局 */
.wp-view :deep(.uni-picker-view-indicator) {
  height: 32px;
  box-sizing: border-box;
  background: rgba(255, 212, 0, 0.05);
  box-shadow: inset 0 1px 0 rgba(255, 212, 0, 0.4), inset 0 -1px 0 rgba(255, 212, 0, 0.4);
}
.wp-view :deep(.uni-picker-view-mask) {
  background-image: linear-gradient(180deg, var(--ink), rgba(0, 0, 0, 0) 46%, rgba(0, 0, 0, 0) 54%, var(--ink));
}
</style>
