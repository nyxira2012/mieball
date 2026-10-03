<template>
  <!-- 邀请入局弹层：to-game=局详情翻意向列表拉人（alpha.html:1213）
       / to-slot=球员档案选局邀请（alpha.html:1239）· P5b 填充 -->
  <SheetStub title="邀请入局" phase="P5b" :lines="[`mode: ${mode}`, gameId != null ? `gameId: ${gameId}` : `userId: ${userId ?? '-'}`]" />
</template>

<script setup lang="ts">
import type { PropType } from 'vue';

defineProps({
  mode: { type: String as PropType<'to-game' | 'to-slot'>, required: true },
  gameId: { type: Number, default: undefined },
  userId: { type: Number, default: undefined },
});
</script>
