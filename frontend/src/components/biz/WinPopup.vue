<template>
  <!-- 胜利结算卡：层级最高（alpha.html:565 #winpop z-110，压过 sheet 90 / confetti 115 之下、
       toast 120 之下），不走 SheetHost——由 ui store 的 win 状态直接驱动（P8b 填充：
       胜队、比分、胜者头像、每人 Elo 涨跌、confetti(56)、收下·下一轮）。
       stub 提供「收下」按钮避免占位层把页面锁死。 -->
  <view v-if="ui.win" class="winpop">
    <view class="mask" @click="ui.closeWin()" />
    <view class="wincard">
      <view class="t">胜利结算</view>
      <view class="p">P8b 待实现（WinPopup · alpha:1688-1729）</view>
      <view class="ln">{{ ui.win.names }} · {{ ui.win.sa }}:{{ ui.win.sb }}</view>
      <AppButton variant="pri" @click="ui.closeWin()">收下 · 下一轮</AppButton>
    </view>
  </view>
</template>

<script setup lang="ts">
import { useUiStore } from '@/stores/ui';
import AppButton from '@/components/ui/AppButton.vue';

const ui = useUiStore();
</script>

<style lang="scss" scoped>
/* alpha.html:565-567 #winpop：全屏居中（stub 简化为占位卡，正式卡样式 P8b 移植） */
.winpop {
  position: fixed;
  inset: 0;
  z-index: 110;
  display: grid;
  place-items: center;
}
.mask {
  position: absolute;
  inset: 0;
  background: rgba(4, 4, 6, 0.78); /* alpha:551 遮罩色加重 */
}
.wincard {
  position: relative;
  width: calc(100% - 72px);
  background: var(--ink2);
  border: 1px solid rgba(255, 212, 0, 0.25); /* alpha:555 顶部黄描边语义 */
  border-radius: 26px;
  padding: 26px 22px;
  text-align: center;
  animation: pop 0.32s cubic-bezier(0.22, 1.4, 0.36, 1); /* pop 来自 animations.scss（alpha:571） */
}
.t {
  font-family: var(--disp);
  font-size: 21px;
  margin-bottom: 6px;
}
.p {
  font-size: 13px;
  color: var(--dim);
  margin-bottom: 6px;
}
.ln {
  font-family: var(--mono);
  font-size: 12px;
  letter-spacing: 0.08em;
  color: var(--lemon);
  margin-bottom: 18px;
}
</style>
