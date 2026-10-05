<template>
  <!-- 底部导航：首页 / 约球 / FAB / 战力 / 我的。
       结构与样式逐类移植 alpha.html:677-696（结构）与 135-156（#nav/.nbtn/#fab 样式）。
       4 个 tab 走 uni.switchTab（pages.json 已注册），保留页面实例；
       FAB 不导航，点开全局组局抽屉 ui.openSheet({type:'launch'})（对应 alpha:686 openLaunch）。
       v-html 例外登记：tab 图标与 FAB 加号为静态 SVG 字符串（alpha:681-694 逐字抄录），
       与 ChibiAvatar 并列为全库唯二 v-html 出口——后续小程序化时集中替换为 image 静态资源。 -->
  <view class="nav">
    <view class="bar">
      <view
        v-for="t in TABS_L"
        :key="t.k"
        class="nbtn"
        :class="{ on: current === t.k }"
        @click="go(t.k)"
      >
        <view class="ico" v-html="ICONS[t.k]" />
        <text class="lbl">{{ t.label }}</text>
        <!-- LIVE 红点：live store 有进行中球局时点亮（alpha:150 .dot · alpha:681 #live-dot-nav） -->
        <view v-if="t.k === 'home' && live.hasLive" class="dot" />
      </view>
      <!-- 发局 FAB（alpha:686 button#fab）：开抽屉不跳页 -->
      <view class="fab" @click="openLaunch">
        <view class="fab-ico" v-html="ICONS.fab" />
      </view>
      <view
        v-for="t in TABS_R"
        :key="t.k"
        class="nbtn"
        :class="{ on: current === t.k }"
        @click="go(t.k)"
      >
        <view class="ico" v-html="ICONS[t.k]" />
        <text class="lbl">{{ t.label }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import type { PropType } from 'vue';
import { useUiStore } from '@/stores/ui';
import { useLiveStore } from '@/stores/live';

/* 图标 SVG：alpha.html:681-694 逐字（stroke/fill 线型由下方 :deep(svg) 统一给） */
const ICONS = {
  home: '<svg viewBox="0 0 24 24"><path d="M3 11l9-8 9 8"/><path d="M5 10v10h5v-6h4v6h5V10"/></svg>',
  meet: '<svg viewBox="0 0 24 24"><circle cx="9" cy="8.5" r="3.2"/><path d="M3.5 19c.8-3 3-4.5 5.5-4.5s4.7 1.5 5.5 4.5"/><circle cx="17" cy="9.5" r="2.4"/><path d="M15.5 14.6c2.4.2 4.2 1.6 5 4.4"/></svg>',
  fab: '<svg viewBox="0 0 24 24" fill="none"><path d="M12 5v14M5 12h14"/></svg>',
  power: '<svg viewBox="0 0 24 24"><path d="M4 20V10M12 20V4M20 20v-7"/></svg>',
  mine: '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 5-6 8-6s6.5 2 8 6"/></svg>',
} as const;

/** 4 个 tab 键（与 pages.json tabBar 顺序一致；detail/live 非 tab 页不挂本组件） */
type TabKey = 'home' | 'meet' | 'power' | 'mine';

/** tab 配置（label/键单一来源；FAB 夹在 meet 与 power 之间，故拆左右两组渲染） */
const TABS = [
  { k: 'home', label: '首页' },
  { k: 'meet', label: '约球' },
  { k: 'power', label: '战力' },
  { k: 'mine', label: '我的' },
] as const satisfies readonly { k: TabKey; label: string }[];
const TABS_L = TABS.slice(0, 2);
const TABS_R = TABS.slice(2);

const props = defineProps({
  /** 当前所在 tab（由页面壳传入；detail/live 等非 tab 页不挂 TabBar） */
  current: { type: String as PropType<TabKey>, required: true },
});

const ui = useUiStore();
const live = useLiveStore();

const ROUTES: Record<TabKey, string> = {
  home: '/pages/home/home',
  meet: '/pages/meet/meet',
  power: '/pages/power/power',
  mine: '/pages/mine/mine',
};

function go(k: TabKey): void {
  if (k === props.current) return; // 原地不跳
  uni.switchTab({ url: ROUTES[k] });
}

/** alpha:686 onclick="openLaunch()"：FAB 开全局组局抽屉 */
function openLaunch(): void {
  ui.openSheet({ type: 'launch' });
}
</script>

<style lang="scss" scoped>
/* alpha.html:135-142 #nav */
.nav {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 100;
  height: calc(var(--nav-h) + env(safe-area-inset-bottom));
  padding-bottom: env(safe-area-inset-bottom);
  background: rgba(14, 14, 18, 0.96); /* alpha:137，即 --ink 的 96% 不透明 */
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-top: 1px solid var(--line); /* 黄线 border-top（alpha:140） */
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.6);
  display: flex;
  justify-content: center;
}
/* alpha.html:143 #nav .bar */
.bar {
  display: flex;
  width: 100%;
  max-width: 380px;
  align-items: flex-end;
  justify-content: space-around;
  padding: 0 8px;
}
/* alpha.html:144-147 .nbtn */
.nbtn {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 9px 0 10px;
  color: var(--dim);
  cursor: pointer;
  transition: color 0.2s;
  position: relative;
}
/* alpha.html:146 .nbtn svg（v-html 注入的 svg 无 scope 属性，用 :deep 命中） */
.nbtn :deep(svg) {
  width: 22px;
  height: 22px;
  stroke: currentColor;
  fill: none;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}
/* alpha.html:147 .nbtn span */
.lbl {
  font-size: 10px;
  letter-spacing: 0.06em;
}
/* alpha.html:148-149 选中黄字 + 顶部短横条 */
.nbtn.on {
  color: var(--lemon);
}
.nbtn.on::before {
  content: '';
  position: absolute;
  top: 2px;
  width: 16px;
  height: 2px;
  border-radius: 2px;
  background: var(--lemon);
}
/* alpha.html:150 LIVE 红点（挂首页按钮右上） */
.dot {
  position: absolute;
  top: 6px;
  right: calc(50% - 16px);
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--coral);
}
/* alpha.html:151-156 #fab 黄色圆钮 */
.fab {
  width: 54px;
  height: 54px;
  border-radius: 50%;
  background: var(--lemon);
  color: var(--ink);
  display: grid;
  place-items: center;
  margin: 0 6px 10px;
  cursor: pointer;
  flex: none;
  box-shadow: 0 6px 24px rgba(255, 212, 0, 0.35);
  transition: transform 0.18s;
}
.fab:active {
  transform: scale(0.9) rotate(90deg);
}
.fab :deep(svg) {
  width: 24px;
  height: 24px;
  stroke: var(--ink);
  stroke-width: 2.4;
  stroke-linecap: round;
}
</style>
