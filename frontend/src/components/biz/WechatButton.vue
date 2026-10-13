<template>
  <!-- 微信键公共件（2026-10-13 环境收口）：微信内置浏览器（含小程序 webview，UA 同源）
       外一概不渲染——「环境里用不了的入口就不出现」，替代旧「点了弹说明」的死入口。
       微信内按下交宿主编排授权跳转（占卡带手机号、快进带 fast——参数各处不同，
       本件只管环境门与样式，不碰转场包）。通道未开时按钮照旧可见、点了 toast
       「即将开通」（1.7 4.7 占位语义：配置一填上自动变真）。 -->
  <AppButton
    v-if="inWx && variant === 'pri'"
    variant="pri"
    block
    @click="emit('press')"
  >
    {{ label }}
  </AppButton>
  <view v-else-if="inWx" class="wx-row" @click="emit('press')">
    <text>{{ label }}</text>
    <text v-if="note" class="wx-note">{{ note }}</text>
  </view>
</template>

<script setup lang="ts">
import AppButton from "@/components/ui/AppButton.vue";
import { isWeChatBrowser } from "@/utils/wechat";

defineProps<{
  /** 形态：pri=实心主钮（名片卡微信内主钮）；row=虚线行（登录页/占卡出口） */
  variant?: "pri" | "row";
  /** 主文案，如「微信授权登录」「微信验证进入」 */
  label: string;
  /** 行形态右侧小字（如「正式绑过的微信两下进门」） */
  note?: string;
}>();

const emit = defineEmits<{ press: [] }>();

/* UA 一次定性（会话内不变、无响应式依赖），非微信环境两支模板都不落——组件整体不出现 */
const inWx = isWeChatBrowser();
</script>

<style lang="scss" scoped>
.wx-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1px dashed var(--line);
  border-radius: var(--r-md);
  padding: 11px 14px;
  font-size: 13px;
  cursor: pointer;
}
.wx-row:active {
  border-color: rgba(255, 212, 0, 0.4);
}
.wx-note {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
}
</style>
