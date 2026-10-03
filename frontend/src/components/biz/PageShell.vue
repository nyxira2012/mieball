<template>
  <!-- 页面布局壳：背景装饰圆环 + 统一 padding 容器 + 全局宿主（TabBar 仅 tab 页）。
       6 个页面统一组合本组件，页面自身只做内容接线（迁移计划 §1 组件库铁律）。
       层级：BizBackdrop z-0（底色+圆环，内容之下）→ .page 内容 z-1 →
       sheet 遮罩/面板 80/90 → grain 99 → nav 100 → winpop 110 → confetti 115 → toast 120。 -->
  <view class="shell">
    <BizBackdrop />
    <!-- alpha.html:75-76 .page padding：safe-area 顶距 14px · 左右 18px · 底部 nav 高 + safe-area + 86px -->
    <view class="page">
      <slot />
    </view>
    <!-- P11 宽屏两侧竖排装饰字（alpha:607/704 .deco，仅 >560px 显示，样式见下方媒体查询；
         alpha 的 <b> 段按项目约定用块级 text 承载，避开小程序不支持的原生标签） -->
    <view class="deco deco-l">NIGHTCOURT<text class="deco-m">PICKLEBALL</text>ALPHA BUILD · 3.1 / 5.1</view>
    <view class="deco deco-r">夜球场<text class="deco-m">SINGLE FILE</text>NO FRAMEWORK · PURE CRAFT</view>
    <TabBar v-if="tab" :current="tab" />
    <ToastHost />
    <ConfettiHost />
    <SheetHost />
    <WinPopup />
    <!-- 噪点颗粒层（alpha:70-71 .grain）：fixed 全屏、z-99、pointer-events none -->
    <view class="grain" />
  </view>
</template>

<script setup lang="ts">
import type { PropType } from 'vue';
import { onHide } from '@dcloudio/uni-app';
import BizBackdrop from './BizBackdrop.vue';
import TabBar from './TabBar.vue';
import ToastHost from './ToastHost.vue';
import ConfettiHost from './ConfettiHost.vue';
import SheetHost from './SheetHost.vue';
import WinPopup from './WinPopup.vue';
import { useUiStore } from '@/stores/ui';

defineProps({
  /** 当前 tab 键；不传 = 非 tab 页（detail/live，无 TabBar） */
  tab: { type: String as PropType<'home' | 'meet' | 'power' | 'mine'>, default: undefined },
});

/* P11 跨页弹层清理（P3 遗留）：alpha:869 go() 每次切页前必 closeSheet() 的等价——
   页面隐藏（TabBar 切换 / 进退 detail/live）时关闭全局单例弹层，避免弹层残留到别的页。
   uni-app Vue3 组件内可注册页面生命周期（onHide 由 @dcloudio/uni-app 导出）。
   WinPopup（ui.win）不随页隐 —— alpha 的 go() 同样只关 #sheet 不动 #winpop。 */
const ui = useUiStore();
onHide(() => ui.closeSheet());
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

/* ---------- P11 桌面宽屏画布（迁移计划 §2.5 · alpha:44-56 #stage/#phone） ----------
   >560px 时应用内容约束 480px 水平居中；背景圆环（BizBackdrop，fixed inset:0）随之
   收进画布：inset 定位 + max-width + margin auto = 居中 480 宽、高度仍满屏，
   其 overflow:hidden 把两条旋转圆环裁在画布内（alpha #phone overflow:hidden 同构）。 */
@media (min-width: 561px) {
  .page {
    max-width: 480px;
    margin: 0 auto;
  }
  .shell :deep(.bd) {
    max-width: 480px;
    margin: 0 auto;
  }
}

/* ---------- P11 宽屏两侧竖排装饰字（alpha:57-59 .deco + 607/704 结构，仅 >560px 显示） ---------- */
.deco {
  display: none; /* 移动端（≤560px）不渲染，同 alpha max-width:560px 分支 */
}
@media (min-width: 561px) {
  .deco {
    display: block;
    position: fixed;
    top: 50%;
    transform: translateY(-50%);
    writing-mode: vertical-rl;
    font-family: var(--disp);
    letter-spacing: 0.5em;
    color: rgba(255, 212, 0, 0.5);
    font-size: 13px;
    text-transform: uppercase;
    user-select: none;
    pointer-events: none;
    z-index: 0;
  }
  /* alpha .deco b：珊瑚色中段（块级 text 承载，见模板注释） */
  .deco .deco-m {
    display: block;
    color: var(--coral);
    margin: 18px 0;
  }
  /* 画布（居中 480px）左/右缘外挂：alpha #stage gap 为 56px，但 561-620px 视口放不下，
     取 24px（480/2+24+13 ≈ 277px 每侧，561px 视口起可完整容纳不溢出） */
  .deco-l {
    right: calc(50% + 240px + 24px);
  }
  .deco-r {
    left: calc(50% + 240px + 24px);
  }
}

/* ---------- 噪点颗粒（alpha:70-71 .grain，data-uri 逐字） ---------- */
.grain {
  position: fixed;
  inset: 0;
  z-index: 99;
  pointer-events: none;
  opacity: 0.05;
  mix-blend-mode: overlay;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='140' height='140' filter='url(%23n)'/%3E%3C/svg%3E");
}
</style>
