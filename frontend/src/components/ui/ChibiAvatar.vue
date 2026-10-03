<template>
  <!--
    ⚠ 全库唯一允许 v-html 的组件（迁移计划 §2.1）：
    chibi() 产出参数化 inline SVG 字符串，只能以 innerHTML 注入；
    将来小程序化只改这一个组件（canvas 绘制或预渲染位图），调用方零改动。
  -->
  <view class="chibi-avatar" :style="{ width: size + 'px', height: size + 'px' }" v-html="svg" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PropType } from 'vue'
import { chibi } from '@/utils/chibi'
import type { ChibiConfig } from '@/utils/chibi'

const props = defineProps({
  /** chibi 部件配置（skin/hair/hc/shirt/face/acc 索引） */
  chibi: { type: Object as PropType<ChibiConfig>, default: null },
  /** 边长 px，默认 56（同 alpha .avatar 默认尺寸） */
  size: { type: Number, default: 56 },
})

const svg = computed(() => chibi(props.chibi, props.size))
</script>

<style lang="scss" scoped>
.chibi-avatar {
  overflow: hidden;
  flex: none;
  display: inline-block;
  line-height: 0;

  /* alpha:241 .avatar 默认即 svg 撑满容器 */
  :deep(svg) {
    width: 100%;
    height: 100%;
    display: block;
  }
}
</style>
