<script setup lang="ts">
import { onLaunch, onShow } from '@dcloudio/uni-app'
import { useSessionStore } from '@/stores/session'

const session = useSessionStore()

// 自绘 TabBar（components/biz/TabBar.vue）替代原生条；onShow 再补一次防时序
onLaunch(() => {
  try { uni.hideTabBar({ animation: false, fail: () => {} }) } catch { /* 非 tabBar 环境 */ }
  // 启动认人（1.1 §4.3）：本机有钥匙→换本人档案；没有/失效→游客进场，不拦启动
  void session.init()
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
