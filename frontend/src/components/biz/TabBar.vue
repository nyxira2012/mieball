<template>
  <!-- 底部导航：现场 / 约球 / FAB / 战力 / 我的（2026-10-05 起 home 页退役、现场升首 tab，1.5 灵活首页第一档）。
       结构与样式逐类移植 alpha.html:677-696（结构）与 135-156（#nav/.nbtn/#fab 样式）。
       4 个 tab 走 uni.switchTab（pages.json 已注册），保留页面实例；
       FAB 不导航，点开全局组局抽屉 ui.openSheet({type:'launch'})（对应 alpha:686 openLaunch）。
       v-html 例外登记：tab 图标与 FAB 加号为静态 SVG 字符串（alpha:681-694 逐字抄录），
       系全库 v-html 例外出口之一，出口清单见 src/api/types.ts——小程序端已换
       svgDataUrl+image 替身（CSS 进不了 image 图内，线型/颜色烤进 data URL）。 -->
  <view class="nav">
    <view class="bar">
      <view
        v-for="t in TABS_L"
        :key="t.k"
        class="nbtn"
        :class="{ on: current === t.k }"
        @click="goTab(t.k)"
      >
        <!-- #ifdef MP-WEIXIN -->
        <image class="ico" :src="mpTabIcon(t.k, current === t.k)" />
        <!-- #endif -->
        <!-- #ifndef MP-WEIXIN -->
        <view class="ico" v-html="ICONS[t.k]" />
        <!-- #endif -->
        <text class="lbl">{{ t.label }}</text>
        <!-- LIVE 红点：live store 有进行中球局时点亮现场键（alpha:150 .dot · alpha:681 #live-dot-nav） -->
        <view v-if="t.k === 'live' && live.hasLive" class="dot" />
      </view>
      <!-- 发局 FAB（alpha:686 button#fab）：开抽屉不跳页 -->
      <view class="fab" @click="openLaunch">
        <!-- #ifdef MP-WEIXIN -->
        <image class="fab-ico" :src="MP_FAB_ICON" />
        <!-- #endif -->
        <!-- #ifndef MP-WEIXIN -->
        <view class="fab-ico" v-html="ICONS.fab" />
        <!-- #endif -->
      </view>
      <view
        v-for="t in TABS_R"
        :key="t.k"
        class="nbtn"
        :class="{ on: current === t.k }"
        @click="goTab(t.k)"
      >
        <!-- #ifdef MP-WEIXIN -->
        <image class="ico" :src="mpTabIcon(t.k, current === t.k)" />
        <!-- #endif -->
        <!-- #ifndef MP-WEIXIN -->
        <view class="ico" v-html="ICONS[t.k]" />
        <!-- #endif -->
        <text class="lbl">{{ t.label }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import type { PropType } from "vue";
import { useUiStore } from "@/stores/ui";
import { useLiveStore } from "@/stores/live";
import { goTab } from "@/utils/nav";
import type { TabKey } from "@/utils/nav";
// #ifdef MP-WEIXIN
import { svgDataUrl } from "@/utils/svgUrl";
// #endif

/* 图标 SVG：alpha.html:681-694 逐字（stroke/fill 线型由下方 :deep(svg) 统一给）；
   live 球场图标为本轮新画（球场+中网，对齐 1.7 线型） */
const ICONS = {
  live: '<svg viewBox="0 0 24 24"><rect x="4" y="5" width="16" height="14" rx="2"/><path d="M4 12h16"/><path d="M12 5v4"/><path d="M12 15v4"/></svg>',
  meet: '<svg viewBox="0 0 24 24"><circle cx="9" cy="8.5" r="3.2"/><path d="M3.5 19c.8-3 3-4.5 5.5-4.5s4.7 1.5 5.5 4.5"/><circle cx="17" cy="9.5" r="2.4"/><path d="M15.5 14.6c2.4.2 4.2 1.6 5 4.4"/></svg>',
  fab: '<svg viewBox="0 0 24 24" fill="none"><path d="M12 5v14M5 12h14"/></svg>',
  power: '<svg viewBox="0 0 24 24"><path d="M4 20V10M12 20V4M20 20v-7"/></svg>',
  mine: '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 5-6 8-6s6.5 2 8 6"/></svg>',
} as const;

// #ifdef MP-WEIXIN
/* 小程序 image 替身：CSS 进不了图内，H5 由 :deep(svg) 统一给的线型与两态色
   须烤进 svg 本体——currentColor 占位 + svgDataUrl 现换实色（两态色与
   pages.json tabBar color/selectedColor 同值）。tab 串无 fill/stroke 属性、
   fab 串自带 fill="none"，注入属性互不重样（data-URL 里 svg 按 XML 解析，
   重属性即坏图） */
const TAB_ICON_LINE =
  'xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"';
function mpTabIcon(k: TabKey, active: boolean): string {
  return svgDataUrl(
    ICONS[k].replace("<svg ", `<svg ${TAB_ICON_LINE} `),
    active ? "#FFD400" : "#9b96a6",
  );
}
const MP_FAB_ICON = svgDataUrl(
  ICONS.fab.replace(
    "<svg ",
    '<svg xmlns="http://www.w3.org/2000/svg" stroke="#0e0e12" stroke-width="2.4" stroke-linecap="round" ',
  ),
);
// #endif

/** tab 配置（label/键单一来源；键与路径契约在 utils/nav 的 TabKey/TAB_ROUTES，
    FAB 夹在 meet 与 power 之间，故拆左右两组渲染） */
const TABS = [
  { k: "live", label: "现场" },
  { k: "meet", label: "约球" },
  { k: "power", label: "战力" },
  { k: "mine", label: "我的" },
] as const satisfies readonly { k: TabKey; label: string }[];
const TABS_L = TABS.slice(0, 2);
const TABS_R = TABS.slice(2);

defineProps({
  /** 当前所在 tab 键（由页面壳传入，仅高亮用；点击切换与原地拦截由 nav.goTab 统一管） */
  current: { type: String as PropType<TabKey>, required: true },
});

const ui = useUiStore();
const live = useLiveStore();

/** alpha:686 onclick="openLaunch()"：FAB 开全局组局抽屉 */
function openLaunch(): void {
  ui.openSheet({ type: "launch" });
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
  height: var(--nav-total-h);
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
  content: "";
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
/* #ifdef MP-WEIXIN */
/* 小程序图标 image（v-html 替身）：线型/颜色已烤进 data URL，此处只复刻
   :deep(svg) 的尺寸（image 默认 320×240，不钉尺寸即撑破底栏） */
.ico {
  width: 22px;
  height: 22px;
}
.fab-ico {
  width: 24px;
  height: 24px;
}
/* #endif */
</style>
