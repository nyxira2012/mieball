<template>
  <!-- toast 宿主：订阅 ui store 的 toastMsg/toastKey 驱动 AppToast（P1 纯展示件）。
       2200ms 自动隐藏计时在这里管，语义同 alpha.html:833-835 的 toastTimer：
       key 自增（重复消息也重触发）→ 立即显示并清掉上一轮计时，到点收起。 -->
  <AppToast :message="ui.toastMsg" :visible="visible" />
</template>

<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue';
import { useUiStore } from '@/stores/ui';
import AppToast from '@/components/ui/AppToast.vue';

const ui = useUiStore();
const visible = ref(false);
let timer: ReturnType<typeof setTimeout> | null = null;

watch(
  () => ui.toastKey,
  () => {
    visible.value = true;
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      visible.value = false;
      timer = null;
    }, 2200);
  },
);

onUnmounted(() => {
  if (timer) clearTimeout(timer);
});
</script>
