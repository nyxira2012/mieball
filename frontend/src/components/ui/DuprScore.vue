<template>
  <view class="dupr-score">
    <text>{{ parts.head }}</text>
    <text class="dec">{{ parts.tail }}</text>
  </view>
</template>

<script setup lang="ts">
/* DUPR 主数字（分层显示）：整数位原字号原色、小数位缩淡——数字区分度的
   通行做法（重心给档位、精度留给小数）。字号/字体/字色全由消费方 class
   落在根节点，小数位按 0.8em 相对缩放，各场景不另写样式；分段单一源
   duprParts 在 utils/elo.ts（整串 fmtDupr 已随分层退役，勿复活） */
import { computed } from "vue";
import type { PropType } from "vue";
import { duprParts } from "@/utils/elo";

const props = defineProps({
  d: { type: Number as PropType<number>, required: true },
});

const parts = computed(() => duprParts(props.d));
</script>

<style lang="scss" scoped>
.dupr-score {
  display: inline-flex;
  align-items: baseline;
}
.dec {
  font-size: 0.8em;
  opacity: 0.6;
}
</style>
