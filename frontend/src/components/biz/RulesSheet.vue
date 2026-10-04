<template>
  <!-- 规则抽屉（temp/打球页原型 sh-rules 逐字）：两个分段选择——局分分制 11/15/21、
       轮换发牌模式 winner/balance/rotate。点选当场生效、不关抽屉（原型口径：改完可继续看）。 -->
  <AppSheet :visible="visible" title="现场规则调整" hint="现场临时修改 · 保存后全场对局卡即时生效" @close="emit('close')">
    <AppField label="局分分制 · First To">
      <AppSeg
        :options="SCORE_OPTS"
        :model-value="g?.score ?? 11"
        @update:model-value="liveStore.setRuleScore(Number($event))"
      />
    </AppField>
    <AppField label="轮换发牌模式">
      <AppSeg
        :options="MODE_OPTS"
        :model-value="g?.mode ?? 'winner'"
        @update:model-value="liveStore.setRuleMode($event as CourtMode)"
      />
    </AppField>
  </AppSheet>
</template>

<script setup lang="ts">
/* 规则抽屉（2.1 §3 辅助·规则修改）：直调 store（setRuleScore 当场生效 / setRuleMode 下一场生效，
   toast 在 store）；mode 副标与 MODE_NAMES 同源、不另立词表。 */
import { computed } from 'vue';
import AppSheet from '@/components/ui/AppSheet.vue';
import AppField from '@/components/ui/AppField.vue';
import AppSeg from '@/components/ui/AppSeg.vue';
import type { SegOption } from '@/components/ui/AppSeg.vue';
import { useLiveStore } from '@/stores/live';
import { MODE_NAMES } from '@/utils/format';
import type { CourtMode } from '@/api/types';

defineProps({
  visible: { type: Boolean, default: false },
});
const emit = defineEmits<{ (e: 'close'): void }>();

const liveStore = useLiveStore();
const g = computed(() => liveStore.live?.g);

/** 原型 seg-score：11 快节奏 / 15 标准局 / 21 马拉松 */
const SCORE_OPTS: SegOption[] = [
  { value: 11, label: '11', sub: '快节奏' },
  { value: 15, label: '15', sub: '标准局' },
  { value: 21, label: '21', sub: '马拉松' },
];
/** 原型 seg-mode：主标 = MODE_NAMES 单一源，副标逐字 */
const MODE_OPTS: SegOption[] = (['winner', 'balance', 'rotate'] as CourtMode[]).map((m) => ({
  value: m,
  label: MODE_NAMES[m],
  sub: m === 'winner' ? '强者守擂' : m === 'balance' ? '积分蛇形' : '排队上下',
}));
</script>
