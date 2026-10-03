<template>
  <!-- 球局详情（alpha.html:1400-1467 · P5a/P5b 填充）。非 tab 页：无 TabBar，
       仍挂全部宿主（档案/加入等弹层要能弹）。url query 的 id 暂存待 P5 接 game store。 -->
  <PageShell>
    <view class="ph">detail · P5 待实现</view>
    <view v-if="gameId != null" class="ph-id">gameId: {{ gameId }}</view>
  </PageShell>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { onLoad } from '@dcloudio/uni-app';
import PageShell from '@/components/biz/PageShell.vue';

/** 从 url query 接 id（onLoad options）暂存，P5a 用它查 game store */
const gameId = ref<number | null>(null);

onLoad((options) => {
  const raw = (options as Record<string, string | undefined> | undefined)?.id;
  const n = raw != null ? Number(raw) : NaN;
  gameId.value = Number.isFinite(n) ? n : null;
});
</script>

<style lang="scss" scoped>
.ph {
  color: var(--dim);
  font-size: 14px;
}
.ph-id {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.06em;
  color: var(--lilac);
  margin-top: 8px;
}
</style>
