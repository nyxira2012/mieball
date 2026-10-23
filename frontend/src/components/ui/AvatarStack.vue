<template>
  <view class="stack">
    <view v-for="(u, i) in shown" :key="i" class="stack-av">
      <AvatarBadge :url="u" :size="26" />
    </view>
    <text v-if="rest > 0" class="plusn">+{{ rest }}</text>
  </view>
</template>

<script setup lang="ts">
/* alpha.html:127-132 .gcard .stack 头像叠层（前 N + +N；N 默认 5，
   「含随行」的名单展开由业务层传入 heads 数组完成）。
   1.9 换芯：吃素材 URL 数组（null 项由 AvatarBadge 兜默认公共款），
   26px 小位自动走脸特写档 */
import { computed } from "vue";
import type { PropType } from "vue";
import AvatarBadge from "./AvatarBadge.vue";

const props = defineProps({
  /** 名单头像素材 URL（含随行展开后的完整名单；null=默认公共款） */
  urls: { type: Array as PropType<(string | null)[]>, default: () => [] },
  /** 展示上限，超出部分折叠为 +N */
  max: { type: Number, default: 5 },
});

const shown = computed(() => props.urls.slice(0, props.max));
const rest = computed(() => Math.max(0, props.urls.length - props.max));
</script>

<style lang="scss" scoped>
/* alpha.html:127-132 */
.stack {
  display: flex;
}
.stack-av {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--ink2);
  border: 2px solid var(--ink2);
  margin-left: -9px;
  overflow: hidden;
  display: grid;
  place-items: center;
  box-sizing: content-box;
}
.stack-av:first-child {
  margin-left: 0;
}
.plusn {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  margin-left: 2px;
}
</style>
