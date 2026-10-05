<template>
  <!-- 终局结算弹窗（temp/打球页原型 .modal-wrap/.modal 逐字；全场唯一弹窗）：
       胜方二选一（可改判）→ 比分 ± 可改 → ±积分预览（settleElo 纯函数实时算）→ 确认落账/取消对局。
       z-110 fixed 居中（顶替退役 WinPopup 的层级生态）；遮罩可关 = closeSettle 保留比分回来重打。 -->
  <view class="mwrap" :class="{ on: visible }">
    <!-- 遮罩层垫底（先渲染居下）：点空白处关窗 = closeSettle 保留比分回来重打 -->
    <view class="mmask" @click="emit('close')" />
    <view class="modal">
      <view class="md-kick">MATCH POINT · {{ courtName }}</view>
      <view class="md-title">终局 <text class="bem">结算</text></view>

      <!-- 胜方点选：A 柠檬 / B 冰蓝 -->
      <view class="win-pick">
        <view class="wp a" :class="{ on: winA }" @click="winA = true">
          <view class="t">TEAM A</view>
          <view class="n">{{ namesA }}</view>
        </view>
        <view class="wp b" :class="{ on: !winA }" @click="winA = false">
          <view class="t">TEAM B</view>
          <view class="n">{{ namesB }}</view>
        </view>
      </view>

      <!-- 大比分 + ± 改分（min 0） -->
      <view class="md-score">
        <view class="md-side">
          <view class="num a">{{ sa }}</view>
          <view class="adj">
            <view class="adj-btn" @click="adj('a', -1)">−</view>
            <view class="adj-btn" @click="adj('a', 1)">＋</view>
          </view>
        </view>
        <view class="c">:</view>
        <view class="md-side">
          <view class="num b">{{ sb }}</view>
          <view class="adj">
            <view class="adj-btn" @click="adj('b', -1)">−</view>
            <view class="adj-btn" @click="adj('b', 1)">＋</view>
          </view>
        </view>
        <text class="edit">比分可点改</text>
      </view>

      <!-- ±积分预览（settleElo 纯函数，随胜方/比分实时变） -->
      <view v-for="(r, i) in preview" :key="i" class="elo-row">
        <text class="nm">{{ r.name }}</text>
        <text class="d" :class="r.up ? 'up' : 'dn'">{{ r.up ? `+${r.d}` : `−${Math.abs(r.d)}` }}</text>
      </view>
      <view class="md-note">访客半权重 · 输家少扣的俱乐部友好制</view>

      <view class="md-btns">
        <AppButton variant="pri" block @click="liveStore.confirmSettle(winA, sa, sb)">确认终局 · 排下一场</AppButton>
        <view class="md-cancel" @click="liveStore.cancelMatch()">取消对局</view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
/* 终局结算（2.1 §5 confirm-before-settle）：读 store.settling 快照 + cur 的 A/B；
   本地态 winA/sa/sb 在快照开窗时重置；确认/取消直调 store（落账·排场·toast 都在 store，
   撒花由页面 watch history 做）。预览行复用 WinChange 形状（settleElo 与落账同一入参 → 幂等一致）。 */
import { computed, ref, watch } from 'vue';
import AppButton from '@/components/ui/AppButton.vue';
import { useLiveStore } from '@/stores/live';
import { settleElo } from '@/utils/elo';
import { courtLabel } from '@/utils/format';
import type { WinChange } from '@/api/types';

defineProps({
  visible: { type: Boolean, default: false },
});
const emit = defineEmits<{ (e: 'close'): void }>();

const liveStore = useLiveStore();

const winA = ref(true);
const sa = ref(0);
const sb = ref(0);
/* 快照开窗 → 本地态重置为快照值（胜方默认按比分大者） */
watch(
  () => liveStore.settling,
  (s) => {
    if (!s) return;
    sa.value = s.sa;
    sb.value = s.sb;
    winA.value = s.sa >= s.sb;
  },
  { immediate: true },
);

/** 当前场显示名（口径在 utils/format 的 courtLabel 单一源：playing 卡同款） */
const courtName = computed(() => courtLabel(liveStore.live?.g.booked, 0));

const namesA = computed(() => (liveStore.live?.cur?.A ?? []).map((id) => liveStore.byId(id).name).join(' / '));
const namesB = computed(() => (liveStore.live?.cur?.B ?? []).map((id) => liveStore.byId(id).name).join(' / '));

/** ± 改分：min 0（只改弹窗本地值，确认时随 confirmSettle 写回） */
function adj(side: 'a' | 'b', d: number): void {
  if (side === 'a') sa.value = Math.max(0, sa.value + d);
  else sb.value = Math.max(0, sb.value + d);
}

/** ±积分预览：胜者在前（与 settleElo 返回序一致）；负号用 −（U+2212，模板里拼） */
const preview = computed<WinChange[]>(() => {
  const c = liveStore.live?.cur;
  if (!c) return [];
  const wIds = winA.value ? c.A : c.B;
  const lIds = winA.value ? c.B : c.A;
  const users = [...wIds, ...lIds].map((id) => liveStore.byId(id));
  return settleElo(users.slice(0, wIds.length), users.slice(wIds.length)).map((r, i) => ({
    name: users[i].name,
    up: r.up,
    d: r.d,
  }));
});
</script>

<style lang="scss" scoped>
/* z-110（AppSheet 90 之上；confetti 115 / toast 120 仍在其上）。原型用 class 切换 + transition
   （animations.scss 的 pop keyframes 可用，但原型本体即 transition 方案，逐字从原型） */
.mwrap {
  position: fixed;
  inset: 0;
  z-index: 110;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  pointer-events: none; /* 关窗态不挡页面；on 态整层可点（遮罩关/卡片操作） */
}
.mwrap.on {
  pointer-events: auto;
}
.mmask {
  position: absolute;
  inset: 0;
  background: rgba(8, 8, 11, 0.72);
  backdrop-filter: blur(3px);
  /* 关窗态必须连 visibility 一起收：backdrop-filter 对 opacity:0 的元素照样生效，
     只切透明度会把整页常驻压糊（走查实录：mmask 漏收 → 全屏发糊） */
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.22s, visibility 0.22s;
}
.mwrap.on .mmask {
  opacity: 1;
  visibility: visible;
}
.modal {
  position: relative;
  width: 82%;
  max-width: 330px;
  background: linear-gradient(180deg, var(--ink3), var(--ink2));
  border: 1px solid rgba(255, 212, 0, 0.25);
  border-radius: var(--r-lg);
  padding: 20px 16px 16px;
  transform: scale(0.94);
  opacity: 0;
  transition: 0.22s;
  pointer-events: none;
}
.mwrap.on .modal {
  transform: scale(1);
  opacity: 1;
  pointer-events: auto;
}
.md-kick {
  text-align: center;
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.34em;
  color: var(--dim);
  text-transform: uppercase;
}
.md-title {
  text-align: center;
  font-family: var(--disp);
  font-size: 24px;
  margin: 6px 0 14px;
}
.md-title .bem {
  color: var(--lemon);
}

/* ---------- 胜方二选一 ---------- */
.win-pick {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.wp {
  flex: 1;
  text-align: center;
  border: 1px solid rgba(245, 241, 232, 0.16);
  border-radius: 13px;
  background: var(--ink);
  padding: 10px 4px;
  cursor: pointer;
  transition: 0.15s;
  min-width: 0;
}
.wp .t {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.18em;
  color: var(--dim);
}
.wp .n {
  font-size: 12px;
  font-weight: 700;
  margin-top: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.wp.on {
  border-color: var(--lemon);
  background: rgba(255, 212, 0, 0.08);
}
.wp.on .t {
  color: var(--lemon);
}
.wp.b.on {
  border-color: var(--ice);
  background: rgba(111, 231, 255, 0.08);
}
.wp.b.on .t {
  color: var(--ice);
}

/* ---------- 大比分 + ± 小钮 ---------- */
.md-score {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  margin: 4px 0 14px;
}
.md-side {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.md-score .num {
  font-family: var(--disp);
  font-size: 44px;
  line-height: 1;
}
.md-score .num.a {
  color: var(--lemon);
}
.md-score .num.b {
  color: var(--ice);
}
.md-score .c {
  font-family: var(--disp);
  font-size: 22px;
  color: var(--coral);
}
.md-score .edit {
  font-size: 10px;
  color: var(--dim);
  align-self: center;
}
.adj {
  display: flex;
  gap: 6px;
}
.adj-btn {
  width: 24px;
  height: 22px;
  border-radius: 7px;
  border: 1px solid rgba(245, 241, 232, 0.16);
  color: var(--cream);
  font-family: var(--mono);
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.adj-btn:active {
  border-color: var(--lemon);
  color: var(--lemon);
}

/* ---------- ±积分预览行 ---------- */
.elo-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid rgba(245, 241, 232, 0.08);
  border-radius: 12px;
  background: var(--ink2);
  margin-bottom: 6px;
}
.elo-row .nm {
  flex: 1;
  font-size: 12px;
  font-weight: 600;
}
.elo-row .d {
  font-family: var(--mono);
  font-size: 13px;
  font-weight: 700;
}
.elo-row .d.up {
  color: var(--lemon);
}
.elo-row .d.dn {
  color: var(--coral);
}
.md-note {
  text-align: center;
  font-size: 10px;
  color: var(--dim);
  margin: 8px 0 12px;
}

/* ---------- 按钮 ---------- */
.md-btns {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.md-cancel {
  border: 1px solid rgba(255, 90, 54, 0.4);
  background: none;
  color: var(--coral);
  font-size: 13px;
  font-weight: 600;
  font-family: var(--sans);
  border-radius: 16px;
  padding: 11px 0;
  text-align: center;
  cursor: pointer;
}
.md-cancel:active {
  background: rgba(255, 90, 54, 0.1);
}
</style>
