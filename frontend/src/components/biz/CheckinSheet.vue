<template>
  <!-- 签到抽屉（temp/打球页原型 sh-check 逐字）：段1 迟到待签到（absent 行黄钮「到场」/late 行灰显已到）
       · 段2 带访客（AppInput 称呼 + AppStepper 人数 + OptionChips 介绍人 + 带上场）
       · 段3 空降说明 NoteCard。动作直调 live store（setCheck/addGuests，toast 在 store）。 -->
  <AppSheet :visible="visible" title="签到 · 到场" hint="来没来、几点走，清清楚楚" @close="emit('close')">
    <!-- ---------- 段1 迟到待签到 ---------- -->
    <view class="ck-sec">
      <view class="ck-t">迟到待签到</view>
      <template v-if="absents.length || lates.length">
        <view v-for="row in absents" :key="row.id" class="ck-row">
          <view class="row-av"><ChibiAvatar :chibi="row.chibi" :size="30" /></view>
          <view class="who">
            <view class="nm">{{ row.name }}<text v-if="row.id === U.me.id" class="me-badge">我</text></view>
            <view class="st late">{{ lateTxt }}</view>
          </view>
          <AppButton variant="pri" size="sm" @click="liveStore.setCheck(row.id, 'late')">到场</AppButton>
        </view>
        <view v-for="row in lates" :key="row.id" class="ck-row done">
          <view class="row-av"><ChibiAvatar :chibi="row.chibi" :size="30" /></view>
          <view class="who">
            <view class="nm">{{ row.name }}<text v-if="row.id === U.me.id" class="me-badge">我</text></view>
            <view class="st ok">已到场 ✓</view>
          </view>
        </view>
      </template>
      <EmptyBox v-else text="都到齐了" />
    </view>

    <!-- ---------- 段2 带访客 ---------- -->
    <view class="ck-sec">
      <view class="ck-t">带访客</view>
      <view class="ck-input">
        <AppInput v-model="gName" placeholder="访客称呼（可空，自动命名）" />
        <AppStepper v-model="gCount" :min="1" :max="6" />
      </view>
      <view class="set-row">
        <OptionChips :options="introOptions" :model-value="introId" @update:model-value="introId = $event as number" />
      </view>
      <AppButton variant="pri" block @click="onBring">带上场</AppButton>
    </view>

    <!-- ---------- 段3 空降说明 ---------- -->
    <NoteCard>
      <text class="nk-lead">空降的人不用学：</text>没报名的直接扫场上二维码 → 填个称呼就进局——按访客计，积分打半折、费用照常摊。
    </NoteCard>
  </AppSheet>
</template>

<script setup lang="ts">
/* 签到抽屉（2.1 §1/§2）：迟到 = setCheck late（排队尾、下一轮发牌即可上场，avail 放行）；
   带访客 = addGuests（shadow 半权重、队尾进候场）。介绍人 = 已到场非访客成员，默认「我」在册则选中。 */
import { computed, ref, watch } from 'vue';
import AppSheet from '@/components/ui/AppSheet.vue';
import AppButton from '@/components/ui/AppButton.vue';
import AppInput from '@/components/ui/AppInput.vue';
import AppStepper from '@/components/ui/AppStepper.vue';
import OptionChips from '@/components/ui/OptionChips.vue';
import NoteCard from '@/components/ui/NoteCard.vue';
import EmptyBox from '@/components/ui/EmptyBox.vue';
import ChibiAvatar from '@/components/ui/ChibiAvatar.vue';
import { useLiveStore } from '@/stores/live';
import { gameTime } from '@/utils/time';
import { U } from '@/api';

defineProps({
  visible: { type: Boolean, default: false },
});
const emit = defineEmits<{ (e: 'close'): void }>();

const liveStore = useLiveStore();

/** 未到/迟到的迟到分钟数：floor((now − 开场)/60000)，≤0 显示「未到」（2.1 §2 口径） */
const lateTxt = computed(() => {
  const g = liveStore.live?.g;
  if (!g) return '未到';
  const mins = Math.floor((Date.now() - gameTime(g.t).getTime()) / 60000);
  return mins > 0 ? `已迟到 ${mins} 分钟` : '未到';
});

const absents = computed(() => (liveStore.live?.roster ?? []).filter((p) => p.check === 'absent'));
const lates = computed(() => (liveStore.live?.roster ?? []).filter((p) => p.check === 'late'));

/* ---------- 带访客本地态：带上场后重置（名字清空、人数回 1） ---------- */
const gName = ref('');
const gCount = ref(1);
const introId = ref<number>(U.me.id);

/** 介绍人候选：已到场（ok/join）的非访客成员；「我」在册默认选中，否则取首位 */
const introOptions = computed(() =>
  (liveStore.live?.roster ?? [])
    .filter((p) => ['ok', 'join'].includes(p.check ?? '') && !p.shadow)
    .map((p) => ({ value: p.id, label: p.id === U.me.id ? '介绍人 · 我' : p.name })),
);
watch(introOptions, (opts) => {
  if (!opts.some((o) => o.value === introId.value)) introId.value = opts[0]?.value ?? U.me.id;
}, { immediate: true });

function onBring(): void {
  const introducer = (liveStore.live?.roster ?? []).find((p) => p.id === introId.value) ?? U.me;
  liveStore.addGuests(gCount.value, gName.value.trim(), introducer);
  gName.value = '';
  gCount.value = 1;
}
</script>

<style lang="scss" scoped>
/* ---------- 原型 .ck-sec/.ck-t/.ck-row/.ck-input（逐字换 tokens） ---------- */
.ck-sec {
  margin-bottom: 16px;
}
.ck-t {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.2em;
  color: var(--dim);
  margin-bottom: 8px;
}
.ck-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid rgba(245, 241, 232, 0.1);
  border-radius: 12px;
  background: var(--ink2);
  margin-bottom: 6px;
}
.ck-row.done {
  opacity: 0.45;
}
.row-av {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: var(--ink3);
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}
.ck-row .who {
  flex: 1;
  min-width: 0;
}
.ck-row .nm {
  font-size: 13px;
  font-weight: 600;
}
.me-badge {
  display: inline-block;
  font-family: var(--mono);
  font-size: 9px;
  border: 1px solid rgba(255, 212, 0, 0.5);
  color: var(--lemon);
  border-radius: 6px;
  padding: 0 5px;
  margin-left: 6px;
  vertical-align: 1px;
}
.ck-row .st {
  font-size: 10px;
  color: var(--dim);
  margin-top: 2px;
}
.ck-row .st.late {
  color: var(--coral);
}
.ck-row .st.ok {
  color: var(--ice);
}
.ck-input {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.set-row {
  margin-bottom: 12px;
}
.nk-lead {
  color: var(--lilac);
  font-weight: 600;
}
</style>
