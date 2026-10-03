<template>
  <view class="sec-t">
    <view class="t">
      <slot>{{ title }}</slot>
    </view>
    <view class="more" @click="emit('more')">
      <slot name="more">{{ more }}</slot>
    </view>
  </view>
</template>

<script setup lang="ts">
/* alpha.html:89-91 .sec-t 区块标题行（左大字标题 · 右 more 链接）。
   排版样式在全局 base.scss（styles/base.scss「通用排版」段），组件只做结构封装 */
defineProps({
  title: { type: String, default: '' },
  /** 右侧链接文案，如「GAMES ▸」；空则不占位 */
  more: { type: String, default: '' },
})
const emit = defineEmits<{ (e: 'more'): void }>()
</script>
