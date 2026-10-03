<template>
  <!-- 撒花层：fixed 全屏容器，粒子走 v-for 渲染（避免直接操纵 DOM，接口留 canvas 化余地）；
       .cf 样式与 cfall 动画来自全局 animations.scss（alpha:588-589） -->
  <view class="cf-layer">
    <view v-for="p in parts" :key="p.id" class="cf" :style="p.style" />
  </view>
</template>

<script setup lang="ts">
/* alpha.html:839-845 confetti(n)：n 粒、四色轮换、1/3 圆形、随机时长与延迟的 cfall 下落，
   3200ms 后移除。两种触发方式：expose 的 burst(n)（命令式）与 trigger prop（声明式） */
import { ref, watch } from 'vue'
import type { PropType } from 'vue'

const props = defineProps({
  /** trigger 数值变化时自动 burst(count)，供声明式用法 */
  trigger: { type: Number, default: 0 },
  count: { type: Number as PropType<number>, default: 46 },
})

interface CfPart {
  id: number
  style: Record<string, string>
}

const parts = ref<CfPart[]>([])
let seq = 0

/* alpha.html:842 四色 */
const CF_COLORS = ['#FFD400', '#FF5A36', '#F5F1E8', '#B8A9FF']

const burst = (n = props.count) => {
  for (let i = 0; i < n; i++) {
    const id = ++seq
    const style: Record<string, string> = {
      left: Math.random() * 100 + '%',
      background: CF_COLORS[i % 4],
      animation: `cfall ${1.4 + Math.random() * 1.4}s ${Math.random() * 0.5}s cubic-bezier(.3,.6,.6,1) forwards`,
    }
    if (i % 3) style.borderRadius = '50%'
    parts.value.push({ id, style })
    setTimeout(() => {
      parts.value = parts.value.filter((p) => p.id !== id)
    }, 3200)
  }
}

watch(
  () => props.trigger,
  (v) => {
    if (v > 0) burst(props.count)
  },
)

defineExpose({ burst })
</script>

<style lang="scss" scoped>
.cf-layer {
  position: fixed;
  inset: 0;
  z-index: 115;
  pointer-events: none;
  overflow: hidden;
}
/* P11 桌面宽屏（§2.5）：>560px 时撒花层约束到 480px 画布居中（alpha confetti 在 #phone 内） */
@media (min-width: 561px) {
  .cf-layer {
    max-width: 480px;
    margin: 0 auto;
  }
}
</style>
