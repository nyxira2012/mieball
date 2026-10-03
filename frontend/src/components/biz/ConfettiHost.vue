<template>
  <!-- 撒花宿主：订阅 ui store 的 confettiKey/confettiN（P3 纯增量字段），
       驱动 P1 的 Confetti 纯展示件全页单例。任何页面/组件调 ui.burst(n) 即全页撒花
       （alpha:839-845 confetti(n)；14=开下一轮、56=收局，P8a/P8b 接线）。 -->
  <Confetti :trigger="ui.confettiKey" :count="ui.confettiN" />
</template>

<script setup lang="ts">
import { useUiStore } from '@/stores/ui';
import Confetti from '@/components/ui/Confetti.vue';

const ui = useUiStore();
</script>
