<template>
  <view class="field">
    <text v-if="label" class="field-label">{{ label }}</text>
    <slot />
  </view>
</template>

<script setup lang="ts">
/* alpha.html:173-175 .field 表单字段壳（等宽大写 label + 内容插槽） */
defineProps({
  label: { type: String, default: '' },
})
</script>

<style lang="scss" scoped>
.field {
  margin-bottom: 14px;
}
/* alpha:174-175 */
.field-label {
  display: block;
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--dim);
  margin-bottom: 7px;
}
</style>
