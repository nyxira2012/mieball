<template>
  <view class="seg" :class="density">
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
   组局表单时长/频率段用它（战力页切换胶囊是小 pill 形态，样式在 power.vue
   scoped——2026-10-12 已恢复，形态不同不共用本组件）。
   字号自适应（2026-10-17 用户裁决）：按最长选项的字数降档——短选项（≤3 字，
   如 11/15/21、双打/单打）保持 17px 原型大字段；长词行（怎么配四档五字词）
   缩到 13px 收进格宽，不折行不顶边，高亮块形态不变。 */
import { computed } from "vue";
import type { PropType } from "vue";

export interface SegOption {
  value: string | number;
  label: string;
  sub?: string;
}

const props = defineProps({
  options: { type: Array as PropType<SegOption[]>, required: true },
  modelValue: {
    type: [String, Number] as PropType<string | number>,
    default: "",
  },
});
const emit = defineEmits<{
  (e: "update:modelValue", v: string | number): void;
}>();

/** 密度档：最长选项 ≥5 字 = dense（13px）、4 字 = mid（15px）、否则原型大字 */
const density = computed(() => {
  const maxLen = Math.max(0, ...props.options.map((o) => o.label.length));
  return maxLen >= 5 ? "dense" : maxLen >= 4 ? "mid" : "";
});

const select = (v: string | number) => emit("update:modelValue", v);
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
  white-space: nowrap;
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
/* 密度降档：只动字号与纵向 padding，块状高亮形态保持一族 */
.seg.mid .seg-btn {
  padding: 10px 3px;
}
.seg.mid .seg-label {
  font-size: 15px;
}
.seg.dense .seg-btn {
  padding: 11px 3px;
}
.seg.dense .seg-label {
  font-family: var(--sans);
  font-weight: 700;
  font-size: 13px;
  letter-spacing: 0.02em;
}
</style>
