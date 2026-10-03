<template>
  <view class="toast" :class="{ on: visible && message }">{{ message }}</view>
</template>

<script setup lang="ts">
/* alpha.html:581-585 #toast 自绘 toast（黄底墨字胶囊，底部上浮出现）。
   纯展示件：message/visible 由外部控制（P3 接 ui store，2.2s 自动收起在 store 侧做，
   同 alpha.html:834-835 的 toastTimer 语义） */
defineProps({
  message: { type: String, default: '' },
  visible: { type: Boolean, default: false },
})
</script>

<style lang="scss" scoped>
/* alpha.html:581-585 */
.toast {
  position: fixed;
  left: 50%;
  bottom: calc(var(--nav-h) + 26px);
  transform: translate(-50%, 20px);
  z-index: 120;
  background: var(--lemon);
  color: var(--ink);
  font-weight: 700;
  font-size: 13px;
  padding: 11px 20px;
  border-radius: 99px;
  opacity: 0;
  pointer-events: none;
  transition: 0.3s;
  white-space: nowrap;
  box-shadow: 0 8px 30px rgba(255, 212, 0, 0.4);
  max-width: 88%;
  overflow: hidden;
  text-overflow: ellipsis;
}
.toast.on {
  opacity: 1;
  transform: translate(-50%, 0);
}
</style>
