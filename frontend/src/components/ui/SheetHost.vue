<template>
  <AppSheet :visible="visible" :title="title" :hint="hint" @close="emit('close')">
    <component :is="comp" v-if="comp" v-bind="bodyProps" />
  </AppSheet>
</template>

<script setup lang="ts">
/* alpha.html:836-838 openSheet/closeSheet：全局单例抽屉，按 payload.type 分发渲染。
   P1 纯展示件：sheet 状态与组件映射表都由 props 传入（P3 由 ui store.openSheet(payload)
   接线，payload 联合类型 P2/P3 全量预定义，见迁移计划 §2.2 / §3 并行约束） */
import { computed } from 'vue'
import type { Component, PropType } from 'vue'
import AppSheet from './AppSheet.vue'

export interface SheetPayload {
  type: string
  title?: string
  hint?: string
  /** 其余字段原样透传给对应弹层内容组件 */
  [key: string]: unknown
}

const props = defineProps({
  /** 当前弹层 payload；null/undefined = 关闭 */
  sheet: { type: Object as PropType<SheetPayload | null>, default: null },
  /** type → 弹层内容组件 的映射表（join/profile/launch/...，P3 注册） */
  registry: { type: Object as PropType<Record<string, Component>>, default: () => ({}) },
})
const emit = defineEmits<{ (e: 'close'): void }>()

const visible = computed(() => props.sheet != null)
const comp = computed<Component | undefined>(() =>
  props.sheet ? props.registry[props.sheet.type] : undefined,
)
const title = computed(() => (props.sheet?.title as string) ?? '')
const hint = computed(() => (props.sheet?.hint as string) ?? '')
const bodyProps = computed(() => {
  if (!props.sheet) return {}
  const { type: _t, title: _ti, hint: _h, ...rest } = props.sheet
  return rest
})
</script>
