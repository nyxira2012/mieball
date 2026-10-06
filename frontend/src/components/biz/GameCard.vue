<template>
  <!-- 球局卡 · alpha.html:898-917 gameCard 为基底（P5a 全量版）：
       时间大字（dd 大字 + tt 小字两行）· 局名 · 地点行 · foot 状态 chips（进行中 = live-dot + 「进行中」hot；满员 = 「满员 · 候补」full；
       否则「剩 N 坑」ok；done = 「已结束」+ 比分胜/负，隐去满员/剩坑与人数 chip）+「min-max 人」chip。
       批4 裁决①：props 收窄为卡面展示原子（GameCardModel）——meet 传真局映射、登记/记录页传 mock 映射，
       组件不再认识任何一种 Game 形状（与数据源解耦）。头像叠层右上、角色标签右下（2026-10-04 定，勿改回）。
       人均 chip 已按用户要求移除（信息仍在局详情与报名弹层）。
       is-live：珊瑚描边 + LIVE 角标；is-inv：被邀请珊瑚描边（alpha:329）。
       只 emit('tap')：进详情或 joinSheet 分支由父层决定（gameTapAction）。 -->
  <view class="gcard" :class="{ 'is-live': live, 'is-inv': inv }" @click="emit('tap')">
    <view class="gd">
      <!-- alpha:909 时间位：大字 = 时刻，小字 = 日段（今晚 / 10.06 周一） -->
      <view class="time">
        {{ card.hmText }}
        <text class="tt">{{ card.dayText }}</text>
      </view>
      <view class="meta">
        <view class="name">
          <text class="title-txt">{{ card.name }}</text>
          <view class="stack-line">
            <AvatarStack :avatars="card.stackAvatars" :max="5" />
            <text class="plusn">{{ card.stackPlus }}</text>
          </view>
        </view>
        <view class="loc">{{ card.venueText }}</view>
        <view class="foot">
          <!-- done 形态：[已结束][比分 胜/负]，隐去满员/剩坑与人数 chip -->
          <template v-if="done">
            <AppChip>已结束</AppChip>
            <AppChip v-if="card.result">
              <text :class="card.result.myWin ? 'res-w' : 'res-l'">{{ card.result.sa }} · {{ card.result.sb }} {{ card.result.myWin ? '胜' : '负' }}</text>
            </AppChip>
          </template>
          <template v-else-if="live">
            <view class="live-dot" />
            <AppChip kind="hot">进行中</AppChip>
          </template>
          <AppChip v-else-if="full" kind="full">满员 · 候补</AppChip>
          <AppChip v-else kind="ok">剩 {{ card.slotsLeft }} 坑</AppChip>
          <!-- 必打标：已订场=「已订场 · 必开」，仅手动锁=「必开」；未开打的局才显示 -->
          <AppChip v-if="card.forcedLabel && !done && !live" kind="ok">{{ card.forcedLabel }}</AppChip>
          <AppChip v-if="!done">{{ card.minPlayers }}-{{ card.maxPlayers }} 人</AppChip>
          <view class="sp" />
          <AppChip v-if="role" :kind="role">{{ roleTxt }}</AppChip>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
/* alpha.html:898-917 gameCard（P5a）。卡面字段契约见 types.ts GameCardModel（批4 裁决①）。 */
import { computed } from 'vue'
import type { PropType } from 'vue'
import AppChip from '@/components/ui/AppChip.vue'
import AvatarStack from '@/components/ui/AvatarStack.vue'
import type { GameCardModel } from '@/api/types'

const props = defineProps({
  card: { type: Object as PropType<GameCardModel>, required: true },
})
const emit = defineEmits<{ (e: 'tap'): void }>()

const live = computed(() => props.card.status === 'live')
const full = computed(() => props.card.slotsLeft <= 0)
const done = computed(() => props.card.status === 'done')
const inv = computed(() => props.card.myRole === 'inv')

const role = computed(() => (props.card.myRole === 'joined' ? 'dim' : props.card.myRole))
const roleTxt = computed(() => (props.card.myRole === 'org' ? '我发起' : props.card.myRole === 'inv' ? '被邀请' : '已加入'))
</script>

<style lang="scss" scoped>
/* gcard 家族样式（alpha:104-126）为本组件所有；chip/roletag 归 AppChip、stack 归 AvatarStack。
   （DeadCard 的未成局卡壳同源，各自持有副本——styles/ 不允许新增文件。） */
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
/* alpha:123-125 live-dot 呼吸灯（pulse 在 animations.scss） */
.live-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--coral);
  box-shadow: 0 0 0 0 rgba(255, 90, 54, 0.6);
  animation: pulse 1.6s infinite;
  flex: none;
}
/* 5.1 done 比分 chip 的胜负色 */
.res-w {
  color: var(--lemon);
}
.res-l {
  color: var(--coral);
}
/* alpha:126-129 is-live 珊瑚描边 + LIVE 角标 */
.gcard.is-live {
  border-color: rgba(255, 90, 54, 0.5);
}
.gcard.is-live::after {
  content: 'LIVE';
  position: absolute;
  top: 12px;
  right: 14px;
  font-family: var(--disp);
  font-size: 12px;
  letter-spacing: 0.2em;
  color: var(--coral);
}
/* alpha:329 is-inv 被邀请描边 */
.gcard.is-inv {
  border-color: rgba(255, 90, 54, 0.45);
}
.stack-line {
  display: flex;
  align-items: center;
  flex: none;
}
/* alpha:132 .plusn。不设 nowrap：窄位换行是 alpha 原样 */
.plusn {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  margin-left: 2px;
}
</style>
