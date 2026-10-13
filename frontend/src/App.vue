<script setup lang="ts">
import { onLaunch, onShow } from '@dcloudio/uni-app'
import { useSessionStore } from '@/stores/session'
import { readOauthReturn } from '@/utils/wechat'

const session = useSessionStore()

// 自绘 TabBar（components/biz/TabBar.vue）替代原生条；onShow 再补一次防时序
onLaunch(() => {
  try { uni.hideTabBar({ animation: false, fail: () => {} }) } catch { /* 非 tabBar 环境 */ }
  // 启动认人（1.1 §4.3）：本机有钥匙→换本人档案；没有/失效→游客进场，不拦启动
  void session.init()

  // 微信网页授权回跳（1.7）：微信跳回不带 # 的地址，code 和 state 落在 search
  const { code, state } = readOauthReturn()
  if (code) {
      uni.reLaunch({
        url: `/pages/mine/login?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state || '')}`
      });
    }
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
