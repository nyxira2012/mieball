<template>
  <view class="inp-shell" :class="{ 'is-focus': focused }">
    <input
      v-if="type !== 'textarea'"
      class="inp"
      :value="modelValue"
      :type="inputType"
      :placeholder="placeholder"
      :disabled="disabled"
      :maxlength="maxlength"
      @input="onInput"
      @focus="focused = true"
      @blur="focused = false"
    />
    <textarea
      v-else
      class="inp inp-textarea"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      :maxlength="maxlength"
      :auto-height="false"
      @input="onInput"
      @focus="focused = true"
      @blur="focused = false"
    />
  </view>
</template>

<script setup lang="ts">
/* alpha.html:176-179 .inp 输入框（含 textarea 态）；:focus 描边用受控 focus 类实现
   （uni input 为自定义元素，CSS :focus 在多端表现不一） */
import { computed, ref } from 'vue'
import type { PropType } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  /** text/number/digit 渲染 <input>（uni type 透传），textarea 渲染 <textarea> */
  type: { type: String as PropType<'text' | 'textarea' | 'number' | 'digit'>, default: 'text' },
  placeholder: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  maxlength: { type: Number, default: 140 },
})
const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>()

const focused = ref(false)
const inputType = computed(() => (props.type === 'textarea' ? 'text' : props.type))

/* uni input 事件为 CustomEvent（detail.value）；浏览器原生 input 则退回 target.value */
const onInput = (ev: Event) => {
  const detail = (ev as { detail?: { value?: unknown } }).detail
  const val =
    detail && typeof detail.value === 'string'
      ? detail.value
      : ((ev.target as { value?: string } | null)?.value ?? '')
  emit('update:modelValue', val)
}
</script>

<style lang="scss" scoped>
/* alpha.html:176-178 */
.inp-shell {
  width: 100%;
}
.inp {
  width: 100%;
  background: var(--ink);
  border: 1px solid rgba(245, 241, 232, 0.12);
  border-radius: 12px;
  color: var(--cream);
  font-size: 15px;
  font-family: var(--sans);
  padding: 12px 14px;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
}
.is-focus .inp {
  border-color: var(--lemon);
}
/* alpha:179 textarea.inp */
.inp-textarea {
  resize: none;
  min-height: 64px;
  width: 100%;
}
</style>
