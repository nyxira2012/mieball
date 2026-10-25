<template>
  <!-- MP 端根元素换原生 button：open-type（转发面板等）只有原生 button 拉得动——
       微信默认的灰底/::after 描边在样式块头部清零，观感全由 .btn 变体接管；
       H5 端照旧 view 一字不动 -->
  <!-- #ifdef MP-WEIXIN -->
  <button
    class="btn"
    :class="[`btn-${variant}`, { 'btn-blk': block, 'btn-sm': size === 'sm' }]"
    :open-type="openType"
    :aria-disabled="disabled"
    hover-class="none"
    @click="onTap"
  >
    <slot />
  </button>
  <!-- #endif -->
  <!-- #ifndef MP-WEIXIN -->
  <view
    class="btn"
    :class="[`btn-${variant}`, { 'btn-blk': block, 'btn-sm': size === 'sm' }]"
    :aria-disabled="disabled"
    @click="onTap"
  >
    <slot />
  </view>
  <!-- #endif -->
</template>

<script setup lang="ts">
/* alpha.html:159-170 .btn 全变体（default/pri/burn/ghost · blk 通栏 · sm 小号 · disabled） */
import type { PropType } from "vue";

const props = defineProps({
  /** 视觉变体：pri 电光黄 / burn 珊瑚橙 / ghost 描边 / default 透明 */
  variant: {
    type: String as PropType<"default" | "pri" | "burn" | "ghost">,
    default: "default",
  },
  /** sm 小按钮（alpha:.btn.sm） */
  size: { type: String as PropType<"md" | "sm">, default: "md" },
  /** 通栏（alpha:.btn.blk） */
  block: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  /** 小程序原生动作（如 "share" 拉转发面板）：H5 无此概念不渲染属性——设了它
      点击就交给微信原生动作，不再向宿主发 click（宿主的 H5 分享路别在 MP 重跑） */
  openType: {
    type: String as PropType<string | undefined>,
    default: undefined,
  },
});
const emit = defineEmits<{ (e: "click", ev: Event): void }>();

const onTap = (ev: Event) => {
  if (props.disabled) return; // alpha 用 pointer-events:none 屏蔽点击，这里等价拦截
  if (props.openType) return; // 点击即原生动作（share=拉转发面板+触发页面分享钩子）
  emit("click", ev);
};
</script>

<style lang="scss" scoped>
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-radius: 14px;
  padding: 13px 20px;
  font-family: var(--sans);
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.04em;
  border: 1px solid transparent;
  cursor: pointer;
  transition:
    transform 0.15s,
    filter 0.15s;
  user-select: none;
}
/* #ifdef MP-WEIXIN */
/* 原生 button 壳的 UA 默认清零（须在变体之前声明，变体才能盖住）：灰底/黑字/
   大行高清掉后与 H5 view 壳同一起点；hover-class="none" 关掉微信自带的按压变灰 */
.btn {
  background: transparent;
  color: inherit;
  line-height: inherit;
}
.btn::after {
  border: none;
}
/* #endif */
.btn:active {
  transform: scale(0.96);
}
.btn-pri {
  background: var(--lemon);
  color: var(--ink);
  box-shadow: 0 4px 18px rgba(255, 212, 0, 0.28);
}
.btn-pri:active {
  box-shadow: none;
}
.btn-burn {
  background: var(--coral);
  color: var(--ink);
  box-shadow: 0 4px 18px rgba(255, 90, 54, 0.3);
}
.btn-ghost {
  background: transparent;
  border-color: rgba(245, 241, 232, 0.2);
  color: var(--cream);
}
.btn-ghost:active {
  border-color: var(--lemon);
  color: var(--lemon);
}
.btn-blk {
  width: 100%;
}
.btn-sm {
  padding: 8px 14px;
  font-size: 12px;
  border-radius: 11px;
}
.btn[aria-disabled="true"],
.btn[aria-disabled=""] {
  opacity: 0.35;
  pointer-events: none;
}
</style>
