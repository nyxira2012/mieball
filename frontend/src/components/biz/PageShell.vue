<template>
  <!-- 页面布局壳：背景装饰圆环 + 统一 padding 容器 + 全局宿主（TabBar 仅 tab 页）。
       6 个页面统一组合本组件，页面自身只做内容接线（迁移计划 §1 组件库铁律）。
       层级：BizBackdrop z-0（底色+圆环，内容之下）→ .page 内容 z-1 →
       sheet 遮罩/面板 80/90 → nav 100 → winpop 110 → confetti 115 → toast 120。 -->
  <view class="shell">
    <BizBackdrop />
    <!-- alpha.html:75-76 .page padding：safe-area 顶距 14px · 左右 18px · 底部 nav 高 + safe-area + 86px -->
    <view class="page">
      <slot />
    </view>
    <TabBar v-if="tab" :current="tab" />
    <ToastHost />
    <ConfettiHost />
    <SheetHost />
    <WinPopup />
  </view>
</template>

<script setup lang="ts">
import type { PropType } from 'vue';
import BizBackdrop from './BizBackdrop.vue';
import TabBar from './TabBar.vue';
import ToastHost from './ToastHost.vue';
import ConfettiHost from './ConfettiHost.vue';
import SheetHost from './SheetHost.vue';
import WinPopup from './WinPopup.vue';

defineProps({
  /** 当前 tab 键；不传 = 非 tab 页（detail/live，无 TabBar） */
  tab: { type: String as PropType<'home' | 'meet' | 'power' | 'mine'>, default: undefined },
});
</script>

<style lang="scss" scoped>
.shell {
  /* 容器本身不设底色：底色由 BizBackdrop（fixed z-0）铺 var(--ink)，
     内容区透出两条旋转圆环（alpha:60-67 圆环在 #pages z-1 之下的同构图） */
  position: relative;
}
.page {
  position: relative;
  z-index: 1;
  box-sizing: border-box;
  min-height: 100vh;
  /* alpha.html:75-76（去掉 alpha SPA 页签的 opacity/transform 过渡，uni 路由自带转场） */
  padding: calc(env(safe-area-inset-top) + 14px) 18px
    calc(var(--nav-h) + env(safe-area-inset-bottom) + 86px);
}
</style>
