<template>
  <!-- 确认类弹层（三用一壳）：退局 quit / 取消局 cancel / 加场 add-court
       （alpha.html:1106-1263 的确认分支 · P5b 填充，按 kind 出文案） -->
  <SheetStub title="确认操作" phase="P5b" :lines="[`kind: ${kind}`, `gameId: ${gameId}`]" />
</template>

<script setup lang="ts">
import type { PropType } from 'vue';

defineProps({
  kind: { type: String as PropType<'quit' | 'cancel' | 'add-court'>, required: true },
  gameId: { type: Number, required: true },
});
</script>
