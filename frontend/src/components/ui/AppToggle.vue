<template>
  <view class="tog" :class="{ on: modelValue }" @click="toggle">
    <view class="tog-txt">
      <view class="tt">{{ title }}</view>
      <text v-if="desc" class="td">{{ desc }}</text>
    </view>
    <view class="sw" />
  </view>
</template>

<script setup lang="ts">
/* alpha.html:209-216 .tog 开关行 + .sw 圆点开关（组局表单迟到规则等） */
const props = defineProps({
  title: { type: String, required: true },
  desc: { type: String, default: '' },
  modelValue: { type: Boolean, default: false },
})
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>()

const toggle = () => emit('update:modelValue', !props.modelValue)
</script>

<style lang="scss" scoped>
/* alpha.html:209-216 */
.tog {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 13px 14px;
  border: 1px solid rgba(245, 241, 232, 0.12);
  border-radius: 12px;
  background: var(--ink2);
  margin-bottom: 10px;
  cursor: pointer;
}
.tog-txt {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.tog .tt {
  font-size: 13px;
  font-weight: 600;
}
.tog .td {
  font-size: 11px;
  color: var(--dim);
}
.sw {
  width: 44px;
  height: 26px;
  border-radius: 99px;
  background: rgba(245, 241, 232, 0.14);
  position: relative;
  transition: 0.2s;
  flex: none;
}
.sw::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 3px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--cream);
  transition: 0.2s;
}
.tog.on .sw {
  background: var(--lemon);
}
.tog.on .sw::after {
  left: 21px;
  background: var(--ink);
}
</style>
