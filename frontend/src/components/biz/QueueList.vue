<template>
  <!-- 候场队列 · alpha.html:1618-1624 qbox 逐字（P8a）：横滚队列，序号 01/02、头像 44、名、
       歇一轮/连战（互斥三元）· 迟到 · 随行 badge 角标；空队列「队列为空」（alpha:1624）。 -->
  <view v-if="items.length" class="queue">
    <view v-for="(p, i) in items" :key="p.id" class="qp">
      <text class="no">{{ String(i + 1).padStart(2, '0') }}</text>
      <ChibiAvatar :chibi="p.chibi" :size="44" />
      <view class="nm">{{ p.name }}</view>
      <text v-if="p.skip" class="badge rest">歇一轮</text>
      <text v-else-if="p.fire" class="badge fire">连战</text>
      <text v-if="p.check === 'late'" class="badge rest">迟到</text>
      <text v-if="p.shadow" class="badge shadow">随行</text>
    </view>
  </view>
  <view v-else class="sub qempty">队列为空</view>
</template>

<script setup lang="ts">
/* alpha.html:1618-1624 renderCourts 的 qbox 段（P8a）。 */
import { computed } from 'vue';
import type { PropType } from 'vue';
import ChibiAvatar from '@/components/ui/ChibiAvatar.vue';
import type { User } from '@/api/types';
import { pById } from '@/utils/rotate';
import { useLiveStore } from '@/stores/live';

const props = defineProps({
  /** live.queue（玩家 id 顺序 = 上场顺序） */
  queue: { type: Array as PropType<number[]>, required: true },
});

const liveStore = useLiveStore();
/* alpha:1619 pById 查不到的 id 跳过（return ''） */
const items = computed<User[]>(() => {
  const l = liveStore.live;
  if (!l) return [];
  return props.queue.map((id) => pById(l, id)).filter((p): p is User => !!p);
});
</script>

<style lang="scss" scoped>
/* alpha.html:286-294 queue/qp/no/nm（.qp .av 44px 由 ChibiAvatar :size 承载；居中由 .qp text-align 承担）
   + badge 三色副本（styles/ 不允许新增文件，各组件持副本）。
   空队列的 .sub 为 base.scss 全局类 + alpha:1624 内联 style="padding:8px"。 */
.queue {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 4px 2px 10px;
  scroll-snap-type: x mandatory;
}
.qp {
  flex: none;
  width: 64px;
  text-align: center;
  scroll-snap-align: start;
  position: relative;
}
.qp .no {
  position: absolute;
  top: -3px;
  left: 2px;
  font-family: var(--mono);
  font-size: 9px;
  color: var(--lemon);
}
.qp .nm {
  font-size: 10px;
  margin-top: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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
.badge.shadow {
  background: rgba(184, 169, 255, 0.15);
  color: var(--lilac);
}
.qempty {
  padding: 8px;
}
</style>
