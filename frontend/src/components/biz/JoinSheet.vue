<template>
  <!-- 加入球局弹层：带人 stepper、满员进候补、不足最少按最少摊（alpha.html:1107-1138 · P5b 填充） -->
  <SheetStub title="加入球局" phase="P5b" :lines="[`gameId: ${gameId}`]" />
</template>

<script setup lang="ts">
defineProps({
  gameId: { type: Number, required: true },
});
</script>
