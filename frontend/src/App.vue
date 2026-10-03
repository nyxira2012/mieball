<script setup lang="ts">
import { onLaunch, onShow } from '@dcloudio/uni-app'

// 自绘 TabBar（components/biz/TabBar.vue）替代原生条；onShow 再补一次防时序
onLaunch(() => {
  try { uni.hideTabBar({ animation: false, fail: () => {} }) } catch { /* 非 tabBar 环境 */ }
})
onShow(() => {
  try { uni.hideTabBar({ animation: false, fail: () => {} }) } catch { /* 同上 */ }
})
</script>

<style lang="scss">
@import '@/styles/tokens.scss';
@import '@/styles/base.scss';
@import '@/styles/animations.scss';
</style>
