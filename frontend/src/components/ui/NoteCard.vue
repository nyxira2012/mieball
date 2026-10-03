<template>
  <view class="notecard">
    <slot>{{ text }}</slot>
  </view>
</template>

<script setup lang="ts">
/* alpha.html:600-602 .notecard 提示卡（左侧淡紫描边） */
defineProps({
  text: { type: String, default: '' },
})
</script>

<style lang="scss" scoped>
/* alpha.html:600-602 */
.notecard {
  border-left: 3px solid var(--lilac);
  background: rgba(184, 169, 255, 0.06);
  border-radius: 0 12px 12px 0;
  padding: 12px 14px;
  font-size: 12px;
  color: var(--cream);
  margin-bottom: 14px;
}
.notecard :deep(b) {
  color: var(--lilac);
}
</style>
