<template>
  <view v-if="isRole" class="roletag" :class="kind">{{ text }}<slot /></view>
  <view v-else class="chip" :class="kind">{{ text }}<slot /></view>
</template>

<script setup lang="ts">
/* alpha.html:116-120 .chip（hot/full/ok） + alpha.html:325-328 .roletag（org/inv/dim） */
import { computed } from 'vue'
import type { PropType } from 'vue'

const props = defineProps({
  /**
   * chip 态：default 灰描边 / hot 珊瑚 / full 淡紫 / ok 电光黄；
   * roletag 变体（按角色标签渲染）：org 我发起 / inv 被邀请 / dim 已结束等弱化态
   */
  kind: {
    type: String as PropType<'default' | 'hot' | 'full' | 'ok' | 'org' | 'inv' | 'dim'>,
    default: 'default',
  },
  /** 也可不用 prop、直接写进插槽 */
  text: { type: String, default: '' },
})

const ROLE_KINDS = ['org', 'inv', 'dim']
const isRole = computed(() => ROLE_KINDS.includes(props.kind))
</script>

<style lang="scss" scoped>
/* ---- chip（alpha:116-120） ---- */
.chip {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  padding: 3px 9px;
  border-radius: 99px;
  border: 1px solid rgba(245, 241, 232, 0.16);
  color: var(--dim);
  display: inline-block;
  line-height: 1.4;
}
.chip.hot {
  border-color: var(--coral);
  color: var(--coral);
}
.chip.full {
  border-color: var(--lilac);
  color: var(--lilac);
}
.chip.ok {
  border-color: rgba(255, 212, 0, 0.5);
  color: var(--lemon);
}

/* ---- roletag（alpha:325-328） ---- */
.roletag {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.12em;
  padding: 2px 7px;
  border-radius: 6px;
  flex: none;
  display: inline-block;
  line-height: 1.5;
}
.roletag.org {
  background: rgba(255, 212, 0, 0.14);
  color: var(--lemon);
}
.roletag.inv {
  background: rgba(255, 90, 54, 0.16);
  color: var(--coral);
}
.roletag.dim {
  background: rgba(245, 241, 232, 0.08);
  color: var(--dim);
}
</style>
