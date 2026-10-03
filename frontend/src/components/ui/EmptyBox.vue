<template>
  <view class="empty">
    <slot>{{ text }}</slot>
  </view>
</template>

<script setup lang="ts">
/* alpha.html:598-599 .empty 空态（虚线框灰字居中） */
defineProps({
  text: { type: String, default: '' },
})
</script>

<style lang="scss" scoped>
/* alpha.html:598-599 */
.empty {
  border: 1px dashed rgba(245, 241, 232, 0.16);
  border-radius: var(--r-md);
  padding: 30px 16px;
  text-align: center;
  color: var(--dim);
  font-size: 13px;
}
</style>
