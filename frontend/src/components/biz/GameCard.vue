<template>
  <!-- 球局卡 · alpha.html:898-917 gameCard 为基底（P5a 全量版）：
       时间大字（dd 大字 + tt 小字两行）· 局名 · 地点行 · foot 状态 chips（进行中 = live-dot + 「进行中」hot；满员 = 「满员 · 候补」full；
       否则「剩 N 坑」ok；5.1 done = 「已结束」+ 比分胜/负，隐去满员/剩坑与人数 chip）+「min-cap 人」chip。
       与 alpha 的差异（用户要求 2026-10-04）：
       ① 头像叠层（前 5 + +N ·含随行）在卡片右上（name 行右端），角色标签（我发起 org / 被邀请 inv / 已加入 dim）移到 foot 行右端；
       ② 「人均 ¥N」chip 从 foot 行移除（含 done 形态；人均信息仍在局详情与报名弹层）——均勿改回。
       is-live：珊瑚描边 + LIVE 角标（alpha:122-126）；is-inv：被邀请珊瑚描边（alpha:329）。
       静态阶段只 emit('tap')：openDetail 或 joinSheet 分支由父层决定（alpha:908，P4/P7 接线）。 -->
  <view class="gcard" :class="{ 'is-live': live, 'is-inv': inv }" @click="emit('tap')">
    <view class="gd">
      <!-- alpha:909 时间位：大字 = t 第二段（时刻），小字 = t 第一段（今晚/周六…） -->
      <view class="time">
        {{ td }}
        <text class="tt">{{ tt }}</text>
      </view>
      <view class="meta">
        <view class="name">
          <text class="title-txt">{{ game.name }}</text>
          <!-- 用户要求（2026-10-04）：头像叠层与角色标签上下互换——叠层右上、角色标签右下（与 alpha 相反，勿"修"回） -->
          <view class="stack-line">
            <!-- alpha:895-897 stackOf：前 5 个 joined 头像；plusn 文案逐字（+ / +N / ·含随行） -->
            <AvatarStack :avatars="stackChibis" :max="5" />
            <text class="plusn">{{ plusn }}</text>
          </view>
        </view>
        <view class="loc">{{ game.loc }}</view>
        <view class="foot">
          <!-- 5.1 done 形态：[已结束][比分 胜/负][人均]，隐去满员/剩坑与人数 chip（角色标签/头像叠层照旧） -->
          <template v-if="done">
            <AppChip>已结束</AppChip>
            <AppChip v-if="result">
              <text :class="result.myWin ? 'res-w' : 'res-l'">{{ result.sa }} · {{ result.sb }} {{ result.myWin ? '胜' : '负' }}</text>
            </AppChip>
          </template>
          <template v-else-if="live">
            <view class="live-dot" />
            <AppChip kind="hot">进行中</AppChip>
          </template>
          <AppChip v-else-if="full" kind="full">满员 · 候补</AppChip>
          <AppChip v-else kind="ok">剩 {{ game.cap - hs }} 坑</AppChip>
          <AppChip v-if="!done">{{ game.min }}-{{ game.cap }} 人</AppChip>
          <view class="sp" />
          <AppChip v-if="role" :kind="role">{{ roleTxt }}</AppChip>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
/* alpha.html:898-917 gameCard + 895-897 stackOf（P5a） */
import { computed } from 'vue'
import type { PropType } from 'vue'
import AppChip from '@/components/ui/AppChip.vue'
import AvatarStack from '@/components/ui/AvatarStack.vue'
import type { Game } from '@/api/types'
import { heads, myEntry, isOrg } from '@/utils/format'

const props = defineProps({
  game: { type: Object as PropType<Game>, required: true },
})
const emit = defineEmits<{ (e: 'tap'): void }>()

const hs = computed(() => heads(props.game))
const live = computed(() => props.game.status === 'live') // alpha:899 liveing
const full = computed(() => hs.value >= props.game.cap) // alpha:899 full
/* 5.1 done 形态：已结束局渲染「已结束 + 比分胜/负」，隐去满员/剩坑与人数 chip（人均 chip 已按用户要求移除） */
const done = computed(() => props.game.status === 'done')
const result = computed(() => props.game.result)

/* alpha:900-901 角色：org 优先 → 被邀请（未加入）→ 已加入 → 无标签 */
const joined = computed(() => !!myEntry(props.game))
const inv = computed(() => !!props.game.invitedMe && !joined.value)
const role = computed(() => (isOrg(props.game) ? 'org' : inv.value ? 'inv' : joined.value ? 'dim' : null))
const roleTxt = computed(() => (role.value === 'org' ? '我发起' : role.value === 'inv' ? '被邀请' : '已加入'))

/* alpha:905 const [tt,td]=g.t.split(' ')：大字 td=时刻、小字 tt=时段 */
const parts = computed(() => props.game.t.split(' '))
const tt = computed(() => parts.value[0] ?? '')
const td = computed(() => parts.value[1] ?? '')

/* alpha:895-897 stackOf：头像取 joined 前 5；plusn = '+' + 超 5 的人数 + 含随行标记（alpha 原样：
   不足 5 人时也渲染裸 '+'，逐字保留） */
const stackChibis = computed(() => props.game.joined.slice(0, 5).map((e) => e.u.chibi))
const plusn = computed(
  () => `+${hs.value - 5 > 0 ? hs.value - 5 : ''}${props.game.joined.some((e) => e.u.shadow) ? ' ·含随行' : ''}`,
)
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
/* 5.1 done 比分 chip 的胜负色：AppChip kind 无黄红两态，默认 dim 色 chip 内嵌 text 覆盖 */
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
/* alpha:132 .plusn（AvatarStack 内部 plusn 只覆盖 >max 情形，这里的裸 '+' / ·含随行 为 alpha 逐字）。
   不设 nowrap：alpha 的 plusn 在窄位会换成两行（+8 含 / 随行），全局 uni-text 已 inherit */
.plusn {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  margin-left: 2px;
}
</style>
