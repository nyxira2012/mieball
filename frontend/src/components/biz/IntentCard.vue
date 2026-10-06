<template>
  <!-- 意向卡 · alpha.html:1025-1049 intentCard 对齐（P7；1.2 接线重塑）：
       与球局卡同一套规范与统一高度（大字=时段 slotBig 拆两行 / 小字=工作日·周末）·
       名 +「打过」徽章（intent.known 后端定值，裁决②）+ 已邀标 +「note」行 · foot = 频率 chip +「+N 时段」
       + 单人头像叠层。分值/段位随名单 Person 形状退役（后端无此数据，A4 画面不自算）。
       整卡点击 → openProfileById（alpha:1029，emit 由父层开档案）。 -->
  <view class="gcard" @click="emit('tap')">
    <view class="gd">
      <!-- alpha:1031 时间位：slotBig 拆两行（'工作日晚间' → 大字'晚间' + 小字'工作日'） -->
      <view class="time">
        {{ big }}
        <text v-if="small" class="tt">{{ small }}</text>
      </view>
      <view class="meta">
        <view class="name">
          <text class="title-txt">{{ intent.account.nickname }}</text>
          <!-- alpha:1028 标签：同局打过 → 打过；被我邀过 → 已邀 -->
          <AppChip v-if="intent.known" kind="dim">打过</AppChip>
          <AppChip v-if="intent.invited" kind="full">已邀</AppChip>
        </view>
        <!-- alpha:1037 时段列表 · 频率 · 「note」 -->
        <view class="loc">{{ locLine }}</view>
        <view class="foot">
          <AppChip kind="ok">{{ freqName(intent.frequency) }}</AppChip>
          <AppChip v-if="intent.slots.length > 1">+{{ intent.slots.length - 1 }} 时段</AppChip>
          <view class="sp" />
          <!-- alpha:1045 .stack 单头像 -->
          <AvatarStack :avatars="[intent.account.chibi]" />
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
/* 意向卡 IntentCard（alpha.html:1025-1049 · P7 · 1.2 重塑）。 */
import { computed } from 'vue';
import type { PropType } from 'vue';
import AppChip from '@/components/ui/AppChip.vue';
import AvatarStack from '@/components/ui/AvatarStack.vue';
import type { Intent } from '@/api/types';
import { freqName, slotBig, slotName } from '@/utils/format';

const props = defineProps({
  intent: { type: Object as PropType<Intent>, required: true },
});
const emit = defineEmits<{ (e: 'tap'): void }>();

/* alpha:1026 [big,small]=slotBig(i.slots[0]) */
const big = computed(() => slotBig(props.intent.slots[0])[0]);
const small = computed(() => slotBig(props.intent.slots[0])[1]);
/* alpha:1037 时段 · 频率 · 「note」 */
const locLine = computed(
  () =>
    `${props.intent.slots.map(slotName).join(' · ')} · ${freqName(props.intent.frequency)}${
      props.intent.note ? ` · 「${props.intent.note}」` : ''
    }`,
);
</script>

<style lang="scss" scoped>
/* gcard 家族样式（alpha:104-132）与 GameCard.vue 同源副本（styles/ 不允许新增文件）；
   chip 归 AppChip、stack 归 AvatarStack。 */
.gcard {
  position: relative;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: linear-gradient(160deg, var(--ink3), var(--ink2));
  padding: 16px 16px 14px;
  margin-bottom: 12px;
  height: 108px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: center;
  transition: transform 0.18s ease, border-color 0.18s;
  overflow: hidden;
  cursor: pointer;
}
.gcard:active {
  transform: scale(0.975);
  border-color: rgba(255, 212, 0, 0.4);
}
.gd {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}
.time {
  font-family: var(--disp);
  font-size: 30px;
  line-height: 0.95;
  color: var(--lemon);
  min-width: 64px;
  flex: none;
}
/* alpha:108 .time small */
.time .tt {
  display: block;
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  letter-spacing: 0.2em;
  margin-top: 4px;
}
.meta {
  flex: 1;
  min-width: 0;
}
.name {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 2px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  line-height: 1.2;
}
.title-txt {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.loc {
  font-size: 12px;
  color: var(--dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.3;
}
.foot {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  flex-wrap: nowrap;
  overflow: hidden;
}
.sp {
  flex: 1;
}
</style>
