<template>
  <!-- 到场管理行 · alpha.html:1578-1589 renderAttend 的 prow 逐字（P8a）：
       头像 42 · 名 + 随行/我徽章 · 五态状态行（alpha:1579 状态表逐字）·
       右侧四操作钮 ✓/⏰/↩/＋（alpha:1585-1588 的 ib on 高亮态；title 提示为 H5 专属属性不搬）。
       点击只 emit('check', status)，副作用（迟到排队尾/早退清场/中途加入队首）在 live store setCheck（alpha:1591）。 -->
  <view class="prow">
    <ChibiAvatar :chibi="player.chibi" :size="42" />
    <view class="info">
      <view class="nm">{{ player.name }} <text v-if="player.shadow" class="badge shadow">随行</text> <text v-if="player.id === CURRENT_USER_ID" class="badge fire">我</text></view>
      <view class="st" :class="st[1]">● {{ st[0] }}</view>
    </view>
    <view class="ops">
      <view class="ib" :class="{ on: player.check === 'ok' || player.check === 'join' }" @click="emit('check', 'ok')">✓</view>
      <view class="ib warn" :class="{ on: player.check === 'late' }" @click="emit('check', 'late')">⏰</view>
      <view class="ib warn" :class="{ on: player.check === 'left' }" @click="emit('check', 'left')">↩</view>
      <view class="ib" :class="{ on: player.check === 'join' }" @click="emit('check', 'join')">＋</view>
    </view>
  </view>
</template>

<script setup lang="ts">
/* alpha.html:1578-1589 renderAttend 行模板（P8a）。 */
import { computed } from 'vue';
import type { PropType } from 'vue';
import ChibiAvatar from '@/components/ui/ChibiAvatar.vue';
import { CURRENT_USER_ID } from '@/api';
import type { CheckStatus, User } from '@/api/types';

const props = defineProps({
  /** 现场名册球员（live.roster 直接引用球员对象，check/skip/fire 由 startLive 挂上） */
  player: { type: Object as PropType<User>, required: true },
});
const emit = defineEmits<{ (e: 'check', st: CheckStatus): void }>();

/* alpha:1579 五态文案与样式类（逐字） */
const ST: Record<CheckStatus, [string, string]> = {
  ok: ['已到场', 'ok'],
  late: ['迟到 · 排队尾', 'late'],
  left: ['已早退', 'left'],
  absent: ['未到', 'absent'],
  join: ['中途加入', 'ok'],
};
const st = computed(() => ST[props.player.check ?? 'absent']);
</script>

<style lang="scss" scoped>
/* alpha.html:254-266 prow/info/nm/st/ops/ib（.prow .av 42px 由 ChibiAvatar :size 承载）
   + alpha:291-294 badge 的 shadow/fire 两色副本（styles/ 不允许新增文件，各组件持副本）。 */
.prow {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 10px 12px;
  border: 1px solid rgba(245, 241, 232, 0.1);
  border-radius: 14px;
  background: var(--ink2);
  margin-bottom: 8px;
}
.info {
  flex: 1;
  min-width: 0;
}
.nm {
  font-size: 14px;
  font-weight: 600;
}
.st {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.1em;
}
.st.ok {
  color: var(--lemon);
}
.st.late {
  color: var(--coral);
}
.st.left {
  color: var(--dim);
}
.st.absent {
  color: var(--dim);
}
.ops {
  display: flex;
  gap: 6px;
}
.ib {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  border: 1px solid rgba(245, 241, 232, 0.14);
  background: none;
  color: var(--dim);
  display: grid;
  place-items: center;
  cursor: pointer;
  font-size: 13px;
  transition: 0.15s;
}
.ib:active {
  transform: scale(0.88);
}
.ib.on {
  background: var(--lemon);
  color: var(--ink);
  border-color: var(--lemon);
}
.ib.warn.on {
  background: var(--coral);
  border-color: var(--coral);
  color: var(--ink);
}
.badge {
  display: inline-block;
  font-family: var(--mono);
  font-size: 9px;
  border-radius: 6px;
  padding: 1px 5px;
  margin-top: 2px;
}
.badge.shadow {
  background: rgba(184, 169, 255, 0.15);
  color: var(--lilac);
}
.badge.fire {
  background: rgba(255, 90, 54, 0.18);
  color: var(--coral);
}
</style>
