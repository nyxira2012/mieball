<template>
  <!-- 场地卡 · alpha.html:1609-1617 court 块逐字（P8a）：COURT N ·（打球中）角标、
       A 队两人、net 虚线、VS、B 队。队员 tp = 头像 46 + 名 + 歇/燃徽章 + TEAM A/B side 字
       （alpha:1626-1628 tp()，pById 查不到兜底「—」）；点队员 emit('profile', id)
       → 页面唤起 ProfileSheet（alpha:1626 openProfileById）。 -->
  <view class="court">
    <view class="cn">{{ name || `COURT ${index}` }}{{ playing ? ' · 打球中' : '' }}</view>
    <view class="team">
      <view v-for="id in court.A" :key="`a${id}`" class="tp a" @click="emit('profile', id)">
        <ChibiAvatar :chibi="byId(id).chibi" :size="46" />
        <view class="nm">{{ byId(id).name }}</view>
        <text v-if="byId(id).skip" class="badge rest">歇</text>
        <text v-else-if="byId(id).fire" class="badge fire">燃</text>
        <view class="side">TEAM A</view>
      </view>
    </view>
    <view class="net" />
    <view class="vsline"><text class="vs">VS</text></view>
    <view class="net" />
    <view class="team">
      <view v-for="id in court.B" :key="`b${id}`" class="tp b" @click="emit('profile', id)">
        <ChibiAvatar :chibi="byId(id).chibi" :size="46" />
        <view class="nm">{{ byId(id).name }}</view>
        <text v-if="byId(id).skip" class="badge rest">歇</text>
        <text v-else-if="byId(id).fire" class="badge fire">燃</text>
        <view class="side">TEAM B</view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
/* alpha.html:1609-1617 renderCourts 的 court 块 + 1626-1628 tp()（P8a）。 */
import type { PropType } from 'vue';
import ChibiAvatar from '@/components/ui/ChibiAvatar.vue';
import type { LiveCourt, User } from '@/api/types';
import { pById } from '@/utils/rotate';
import { useLiveStore } from '@/stores/live';

const props = defineProps({
  /** 一片场地（A/B 存玩家 id）：live.cur 的进行片或 live.courts 的待打片 */
  court: { type: Object as PropType<LiveCourt>, required: true },
  /** live.cur 的片带「打球中」标（alpha:1608） */
  playing: { type: Boolean, default: false },
  /** 场次序号（alpha:1611 COURT ${i+1}，页面传 1 起） */
  index: { type: Number, required: true },
  /** 3.2 订场改版：已订场的局传登记的场地号（如「3号」），没登记回退 COURT N 序号 */
  name: { type: String, default: '' },
});
const emit = defineEmits<{ (e: 'profile', id: number): void }>();

const liveStore = useLiveStore();
/** alpha:1626 tp 的 pById 兜底 {name:'—',chibi:{}}（补齐 User 必填字段） */
const byId = (id: number): User =>
  (liveStore.live ? pById(liveStore.live, id) : undefined) ?? {
    id: -1, name: '—', elo: 0, play: 0, win: 0, month: 0, chibi: {},
  };
</script>

<style lang="scss" scoped>
/* alpha.html:268-283 court/cn/net/team/tp/side/vsline（.tp .av 46px 由 ChibiAvatar :size 承载）
   + alpha:291-294 badge 的 rest/fire 两色副本（styles/ 不允许新增文件，各组件持副本）。 */
.court {
  border: 1px solid rgba(255, 212, 0, 0.22);
  border-radius: var(--r-lg);
  padding: 16px;
  margin-bottom: 14px;
  background:
    radial-gradient(circle at 50% 0%, rgba(255, 212, 0, 0.06), transparent 60%),
    var(--ink2);
  position: relative;
  overflow: hidden;
}
.cn {
  position: absolute;
  top: 10px;
  left: 14px;
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.24em;
  color: var(--lemon);
}
.net {
  height: 1px;
  background: repeating-linear-gradient(90deg, rgba(255, 212, 0, 0.5) 0 8px, transparent 8px 16px);
  margin: 10px 0;
}
.team {
  display: flex;
  gap: 10px;
  justify-content: center;
}
.tp {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  width: 72px;
  cursor: pointer; /* alpha:280 .tp.clickable */
}
.tp:active {
  transform: scale(0.94); /* alpha:281 */
}
.tp .nm {
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 70px;
}
.tp .side {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.2em;
  color: var(--dim);
}
.tp.a .side {
  color: var(--lemon);
}
.tp.b .side {
  color: var(--ice);
}
.vsline {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: center;
  margin: 4px 0;
}
.vsline .vs {
  font-family: var(--disp);
  font-size: 15px;
  color: var(--coral);
  letter-spacing: 0.1em;
}
.badge {
  display: inline-block;
  font-family: var(--mono);
  font-size: 9px;
  border-radius: 6px;
  padding: 1px 5px;
  margin-top: 2px;
}
.badge.rest {
  background: rgba(111, 231, 255, 0.15);
  color: var(--ice);
}
.badge.fire {
  background: rgba(255, 90, 54, 0.18);
  color: var(--coral);
}
</style>
