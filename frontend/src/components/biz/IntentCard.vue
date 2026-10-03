<template>
  <!-- 意向卡 · alpha.html:1025-1049 intentCard() 逐字对齐（P7）：
       与球局卡同一套规范与统一高度（大字=时段 slotBig 拆两行 / 小字=工作日·周末）·
       名 + TierBadge（玩过的才显，inline-flex gap 6px）· ♥喜欢的人 / 熟人 标签（liked 优先）·
       时段列表·频率·note 行 · foot = 频率 ok chip +「+N 时段」+ 分值 chip（lemon 字淡 lemon 描边，
       分值随 ui.scoreMode 联动）+ 单人头像叠层。整卡点击 → openProfileById（alpha:1029，emit 由父层开档案）。 -->
  <view class="gcard" @click="emit('tap')">
    <view class="gd">
      <!-- alpha:1031 时间位：slotBig 拆两行（'工作日晚间' → 大字'晚间' + 小字'工作日'） -->
      <view class="time">
        {{ big }}
        <text v-if="small" class="tt">{{ small }}</text>
      </view>
      <view class="meta">
        <view class="name">
          <!-- alpha:1034 名 + 段位徽章（玩过的） -->
          <view class="nm-left">
            <text class="title-txt">{{ intent.u.name }}</text>
            <TierBadge v-if="played" :tier="tier(intent.u.elo)" />
          </view>
          <!-- alpha:1028 标签：liked → ♥喜欢的人，否则同局打过 → 熟人 -->
          <text v-if="intent.u.liked" class="hearttag">♥ 喜欢的人</text>
          <AppChip v-else-if="known(intent.u)" kind="dim">熟人</AppChip>
        </view>
        <!-- alpha:1037 时段列表 · 频率 · 「note」 -->
        <view class="loc">{{ locLine }}</view>
        <view class="foot">
          <!-- alpha:1039-1043 foot chips -->
          <AppChip kind="ok">{{ freqName(intent.freq) }}</AppChip>
          <AppChip v-if="intent.slots.length > 1">+{{ intent.slots.length - 1 }} 时段</AppChip>
          <AppChip class="score-chip">
            <text class="sc-l">分值</text>
            <text class="sc-v">{{ played ? fmtScore(intent.u.elo, ui.scoreMode) : '—' }}</text>
          </AppChip>
          <view class="sp" />
          <!-- alpha:1045 .stack 单头像（.stack .av 同款 → AvatarStack 单头像承载） -->
          <AvatarStack :avatars="[intent.u.chibi]" />
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
/* alpha.html:1025-1049 intentCard（P7）。分值展示走 utils/elo.fmtScore + ui.scoreMode
   （alpha:859 fmtScore 读全局 scoreMode，同源联动）。 */
import { computed } from 'vue';
import type { PropType } from 'vue';
import AppChip from '@/components/ui/AppChip.vue';
import AvatarStack from '@/components/ui/AvatarStack.vue';
import TierBadge from '@/components/ui/TierBadge.vue';
import type { Intent } from '@/api/types';
import { useUiStore } from '@/stores/ui';
import { fmtScore, tier } from '@/utils/elo';
import { freqName, known, slotBig, slotName } from '@/utils/format';

const props = defineProps({
  intent: { type: Object as PropType<Intent>, required: true },
});
const emit = defineEmits<{ (e: 'tap'): void }>();

const ui = useUiStore();

/* alpha:1026 [big,small]=slotBig(i.slots[0]) */
const big = computed(() => slotBig(props.intent.slots[0])[0]);
const small = computed(() => slotBig(props.intent.slots[0])[1]);
/* alpha:1027 played = !u.shadow && u.play>0 */
const played = computed(() => !props.intent.u.shadow && props.intent.u.play > 0);
/* alpha:1037 时段 · 频率 · 「note」 */
const locLine = computed(
  () =>
    `${props.intent.slots.map(slotName).join(' · ')} · ${freqName(props.intent.freq)}${
      props.intent.note ? ` · 「${props.intent.note}」` : ''
    }`,
);
</script>

<style lang="scss" scoped>
/* gcard 家族样式（alpha:104-132）与 GameCard.vue 同源副本（styles/ 不允许新增文件）；
   chip 归 AppChip、tierb 归 TierBadge、stack 归 AvatarStack。 */
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
/* alpha:1034 title-txt 内联 display:inline-flex;align-items:center;gap:6px */
.nm-left {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
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
/* alpha:1041-1043 分值 chip：lemon 字 + 淡 lemon 描边（内联样式搬入，作用于 AppChip 根） */
.score-chip {
  color: var(--lemon);
  border-color: rgba(255, 212, 0, 0.35);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
/* alpha:1041 内层 span「分值」灰字 9px；b 加粗 */
.score-chip .sc-l {
  color: var(--dim);
  font-size: 9px;
}
.score-chip .sc-v {
  font-weight: 700;
}
/* alpha:352-353 hearttag */
.hearttag {
  font-family: var(--mono);
  font-size: 9px;
  background: rgba(255, 90, 54, 0.16);
  color: var(--coral);
  padding: 2px 7px;
  border-radius: 6px;
  flex: none;
}
</style>
