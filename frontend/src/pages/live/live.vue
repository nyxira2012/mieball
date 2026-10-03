<template>
  <!-- 现场页（alpha.html:1531-1729 · P8a/P8b 填充）。非 tab 页：无 TabBar，
       仍挂全部宿主（记分收局要弹 WinPopup / 撒花）。url query 的 id 暂存待 P8 接 live store。 -->
  <PageShell>
    <view class="ph">live · P8 待实现</view>
    <view v-if="liveId != null" class="ph-id">liveId: {{ liveId }}</view>
  </PageShell>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { onLoad } from '@dcloudio/uni-app';
import PageShell from '@/components/biz/PageShell.vue';

/** 从 url query 接 id（onLoad options）暂存，P8a 用它 startLive */
const liveId = ref<number | null>(null);

onLoad((options) => {
  const raw = (options as Record<string, string | undefined> | undefined)?.id;
  const n = raw != null ? Number(raw) : NaN;
  liveId.value = Number.isFinite(n) ? n : null;
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
