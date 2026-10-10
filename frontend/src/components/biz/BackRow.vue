<template>
  <!-- 子页统一返回行（mine 系子页 bills/logs/signup/login/dress/detail 共用；原为各页同值三件套）。
       视觉仍是 11px mono 暗灰小字（不抢戏）；热区整行 44px 高——透明 padding 撑出触控面，
       「按得中」不靠「看得大」。长页滚动吸附：内容滚起后钉在页首原位（垫半透明底防正文穿透），
       上面那条缝（safe-area+页首距）用 ::before 同色补齐——翻到一半想走，不必滚回顶部。
       短页（dress/login）滚不动，吸附永不触发，无副作用。 -->
  <view class="backrow" :class="{ stuck }" @click="goBack">◂ 返回</view>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";

function goBack(): void {
  uni.navigateBack();
}

/* 吸附感知：滚动超过一小格即视为钉住（阈值 4px 顺带滤掉 iOS 回弹毛刺）。
   两条「正路」实测都不通才落这里：onPageScroll 是页面级生命周期、子组件不触发
   （uni 官方口径）；IntersectionObserver（uni 的与原生的）在 uni H5 页面容器里
   均零回调（走查实证）。window scroll 在 H5/webview 稳定——正是本项目验收面；
   app-vue 逻辑层无 window：监听不挂、钉住底色不亮，sticky 钉行与返回本身不受影响。 */
const stuck = ref(false);
function onScroll(): void {
  stuck.value = window.scrollY > 4;
}
onMounted(() => {
  if (typeof window === "undefined") return;
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll(); // 挂载即对表一次：带着滚动位置进来（如返回恢复）不至于漏亮
});
onUnmounted(() => {
  if (typeof window === "undefined") return;
  window.removeEventListener("scroll", onScroll);
});
</script>

<style lang="scss" scoped>
/* mono 11px dim · :active lemon（视觉与旧版一致）；min-height 44 = 触控下限。
   sticky 直落页面流：本组件是片段根、无多余包裹——若再包一层容器，sticky
   只能在父盒内滑动就永远钉不住了 */
.backrow {
  position: sticky;
  /* 钉在页首原位：page 顶距 = safe-area + 14px，吸附前后文字位置不变、无跳动 */
  top: calc(env(safe-area-inset-top) + 14px);
  z-index: 40;
  display: flex;
  align-items: center;
  min-height: 44px;
  font-family: var(--mono);
  font-size: 11px;
  color: var(--dim);
  /* 负 margin 满幅出血：整行宽度都是热区（页面左右 padding 18px 的补偿） */
  margin: 0 -18px;
  padding: 0 20px;
  cursor: pointer;
  transition:
    background 0.2s,
    box-shadow 0.2s;
}
.backrow:active {
  color: var(--lemon);
}
/* 钉住态：半透明底 + 发丝线，防正文从字底穿透；::before 把底色向上补满
   safe-area 那条缝（纯装饰性溢出，不占布局、文字零位移） */
.backrow.stuck {
  background: rgba(14, 14, 18, 0.86);
  backdrop-filter: blur(8px);
  box-shadow: 0 1px 0 var(--line);
}
.backrow.stuck::before {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  top: calc(-1 * (env(safe-area-inset-top) + 14px));
  height: calc(env(safe-area-inset-top) + 14px);
  background: rgba(14, 14, 18, 0.86);
}
</style>
