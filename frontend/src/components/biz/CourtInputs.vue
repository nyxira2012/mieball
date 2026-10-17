<template>
  <!-- 场地号逐框输入（单一源）：一框一片，尾框填入内容自动添下一空框，带内容的框
       可单个删（退一片删一个号）。识别口径收编在此：去空格 → 去重保序，空框天然滤掉
       ——片数就是识别出的个数（订场登记同源）。原版内联在 BookingSheet（2026-10-10
       订场改版），直接开场抽屉与顶条改场号面板出现后按「第二使用方收编」提为公共件。
       v-model 抛的是清洗后的数组；框内原始文本（含未去重的重复项）不回传。 -->
  <view class="courts-row">
    <view v-for="(c, i) in boxes" :key="i" class="court-box">
      <AppInput
        :model-value="c"
        :maxlength="4"
        placeholder="如：16"
        @update:model-value="onInput(i, $event)"
      />
      <view v-if="c.trim()" class="court-del" @click="remove(i)">×</view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import AppInput from "@/components/ui/AppInput.vue";

const props = defineProps({
  /** 清洗后的场地号数组（去空去重保序）；外部回填时逐框带出（尾补一空框） */
  modelValue: { type: Array as () => string[], default: () => [] },
});
const emit = defineEmits<{ (e: "update:modelValue", v: string[]): void }>();

/** 框内原始文本态（可能有空串/重复），清洗口径在 emit 处统一 */
const boxes = ref<string[]>(
  props.modelValue.length ? [...props.modelValue, ""] : [""],
);

/* 外部回填对齐：只在与当前清洗结果不同时重建（防自己 emit 的值绕回来把输入中的
   重复框/空框抖掉） */
watch(
  () => props.modelValue,
  (v) => {
    const cur = cleaned();
    if (v.join("\u0001") !== cur.join("\u0001")) {
      boxes.value = v.length ? [...v, ""] : [""];
    }
  },
);

function cleaned(): string[] {
  const seen = new Set<string>();
  return boxes.value
    .map((s) => s.trim())
    .filter((s) => {
      if (!s || seen.has(s)) return false;
      seen.add(s);
      return true;
    });
}

function emitClean(): void {
  emit("update:modelValue", cleaned());
}

function onInput(i: number, v: string): void {
  boxes.value[i] = v;
  if (i === boxes.value.length - 1 && v.trim()) {
    boxes.value.push("");
  }
  emitClean();
}

function remove(i: number): void {
  boxes.value.splice(i, 1);
  if (!boxes.value.length) boxes.value.push("");
  emitClean();
}
</script>

<style lang="scss" scoped>
/* 一框一片，wrap 排布；:deep 只收本组件，不动公共 AppInput（登录页/装扮页等表单
   共用）。框宽按内容收——场号最多三个字符（数字+字母/号）+ 左右边距（2026-10-10
   用户定），容纳 3 个汉字兜底 */
.courts-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.court-box {
  position: relative;
  width: 64px;
}
.court-box :deep(.inp) {
  height: 40px;
  padding: 0 6px;
  text-align: center;
}
/* 单框删除角标（退一片删一个号）：只挂在有内容的框上 */
.court-del {
  position: absolute;
  top: -7px;
  right: -7px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--ink2);
  border: 1px solid rgba(245, 241, 232, 0.2);
  color: var(--dim);
  font-size: 14px;
  line-height: 18px;
  text-align: center;
}
</style>
