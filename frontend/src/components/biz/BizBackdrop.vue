<template>
  <!-- 页面背景装饰：巨大网球孔洞圆环 ×2（alpha.html:60-67 #phone::before/after）。
       fixed 常驻视口 + 底色 var(--ink)（alpha:48 画布底色），z-index 0 在页面内容
       （z-index 1）之下、各宿主层（nav 100 / sheet 90 / confetti 115 / toast 120）之下。
       用真实子节点而非伪元素：小程序端 view 不保证伪元素可用，H5 同渲染。 -->
  <view class="bd">
    <view class="ring ring-a" />
    <view class="ring ring-b" />
  </view>
</template>

<script setup lang="ts"></script>

<style lang="scss" scoped>
.bd {
  position: fixed;
  inset: 0;
  z-index: 0;
  background: var(--ink); /* alpha.html:48 #phone background */
  overflow: hidden;
  pointer-events: none;
}
/* alpha.html:61-63 黄色虚线大环 · 右上 · 90s 正转 */
.ring-a {
  position: absolute;
  width: 560px;
  height: 560px;
  border-radius: 50%;
  border: 1.5px dashed rgba(255, 212, 0, 0.1);
  top: -180px;
  right: -160px;
  animation: spin 90s linear infinite;
}
/* alpha.html:64-66 珊瑚虚线小环 · 左下 · 70s 逆转 */
.ring-b {
  position: absolute;
  width: 340px;
  height: 340px;
  border-radius: 50%;
  border: 1.5px dashed rgba(255, 90, 54, 0.12);
  bottom: 60px;
  left: -150px;
  animation: spin 70s linear infinite reverse;
}
/* spin keyframes 来自全局 styles/animations.scss（alpha:67） */
</style>
