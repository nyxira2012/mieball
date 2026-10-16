<template>
  <!-- 危险动作确认槽（A3）：后果句 + 双钮，确认才执行。真局现场页与账单页同吃
       一份壳——此前的双份手写已经分叉（账单版有在途禁用、现场版没有）。
       动作编排归宿主（askConfirm/confirmGo 状态机各页自持：现场页确认槽寄在
       本地弹层单槽 union 里，账单页是独立异步在途槽），本组件只管长相与双钮。
       「处理中…」仅在宿主传 acting 时出现（异步动作页）。 -->
  <AppSheet :visible="visible" @close="emit('close')">
    <view class="cfm">
      <view class="sheet-t">确定要这么做？</view>
      <view class="sheet-hint">{{ msg }}</view>
      <view class="cf-btns">
        <AppButton
          variant="ghost"
          class="flex1"
          :disabled="acting"
          @click="emit('close')"
          >再想想</AppButton
        >
        <AppButton
          variant="burn"
          class="flex1"
          :disabled="acting"
          @click="emit('confirm')"
          >{{ acting ? "处理中…" : "确认" }}</AppButton
        >
      </view>
    </view>
  </AppSheet>
</template>

<script setup lang="ts">
import AppButton from "./AppButton.vue";
import AppSheet from "./AppSheet.vue";

defineProps<{
  visible: boolean;
  /** 后果句（确认前的逐字告知） */
  msg: string;
  /** 动作在途（异步动作页防双击 + 防半路抽手） */
  acting?: boolean;
}>();
const emit = defineEmits<{
  (e: "close"): void;
  (e: "confirm"): void;
}>();
</script>

<style lang="scss" scoped>
/* 壳样式走全局 .cfm/.sheet-t/.sheet-hint；双钮排此前各页自留一份，收此一处 */
.cf-btns {
  display: flex;
  gap: 10px;
}
.flex1 {
  flex: 1;
}
</style>
