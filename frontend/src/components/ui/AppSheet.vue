<template>
  <!-- 抽屉壳：遮罩 + 底部面板。纯展示件（props/事件驱动），P3 由 SheetHost/ui store 接线。
       定位用 fixed：uni-app 页面无 #phone 画布，fixed 即覆盖整屏（视觉同 alpha） -->
  <view class="sheet-root">
    <view class="mask" :class="{ on: visible }" @click="emit('close')" />
    <view class="sheet" :class="{ on: visible }">
      <view class="grab" />
      <view v-if="title" class="sheet-title">{{ title }}</view>
      <text v-if="hint" class="hint">{{ hint }}</text>
      <slot />
    </view>
  </view>
</template>

<script setup lang="ts">
/* alpha.html:551-562 #mask/#sheet：grab 条、标题、hint、translateY(105%) 过渡、
   圆角 26px 顶部黄描边、遮罩点击关闭。transition 类切换语义与 alpha .on 一致 */
defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '' },
  hint: { type: String, default: '' },
})
const emit = defineEmits<{ (e: 'close'): void }>()
</script>

<style lang="scss" scoped>
/* alpha.html:551-553 */
.mask {
  position: fixed;
  inset: 0;
  background: rgba(4, 4, 6, 0.72);
  backdrop-filter: blur(3px);
  z-index: 80;
  opacity: 0;
  pointer-events: none;
  transition: 0.25s;
}
.mask.on {
  opacity: 1;
  pointer-events: auto;
}
/* alpha.html:554-562 */
.sheet {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 90;
  background: var(--ink2);
  border-radius: 26px 26px 0 0;
  border-top: 1px solid rgba(255, 212, 0, 0.25);
  padding: 10px 20px calc(var(--nav-h) + 20px + env(safe-area-inset-bottom));
  transform: translateY(105%);
  transition: transform 0.38s cubic-bezier(0.22, 1, 0.36, 1);
  max-height: 86%;
  overflow-y: auto;
}
.sheet.on {
  transform: none;
}
.grab {
  width: 40px;
  height: 4px;
  border-radius: 4px;
  background: rgba(245, 241, 232, 0.25);
  margin: 4px auto 16px;
}
.sheet-title {
  font-family: var(--disp);
  font-size: 21px;
  margin-bottom: 4px;
}
.hint {
  font-size: 12px;
  color: var(--dim);
  margin-bottom: 16px;
}
/* P11 桌面宽屏（§2.5，alpha #phone 同构）：>560px 时遮罩/面板约束到 480px 画布居中。
   两者均为 left/right 双侧定位，补 max-width + margin auto 即水平居中，其余不动。 */
@media (min-width: 561px) {
  .mask,
  .sheet {
    max-width: 480px;
    margin: 0 auto;
  }
}
</style>
