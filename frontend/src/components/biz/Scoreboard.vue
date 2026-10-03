<template>
  <!-- 记分板 · alpha.html:1657-1672 逐字（P8b）：COURT kicker、A 队两人（tp 头像 46，可点开档案）、
       76px 大比分（A 黄 / B 青、珊瑚冒号）、B 队两人、A/B 得分钮、误记撤回 ghost sm 钮。
       得分数字弹跳 = alpha:1684 Element.animate(scale 1.35→1 + 珊瑚闪色 260ms) 的 CSS class 等价（迁移计划 §2.4）。 -->
  <view class="scoreboard">
    <!-- alpha:1659 kicker 逐字 -->
    <view class="sb-kick">COURT 1 · FIRST TO {{ target }} · WIN BY 2</view>
    <!-- alpha:1660 A 队两人（team 内联 margin:14px 0 4px）；点队员 emit('profile') 同 alpha:1656 openProfileById -->
    <view class="team tm-a">
      <view v-for="id in cur.A" :key="`a${id}`" class="tp" @click="emit('profile', id)">
        <ChibiAvatar :chibi="byId(id).chibi" :size="46" />
        <view class="nm">{{ byId(id).name }}</view>
      </view>
    </view>
    <!-- alpha:1661-1665 大比分 -->
    <view class="scores">
      <view class="scol a">
        <view class="sn">TEAM A</view>
        <!-- :key 自增强制重挂载 → 连点同侧也能重触发弹跳动画（alpha:1684 每次得分都调 animate 的等价） -->
        <view :key="`a${bumpTick}`" class="num" :class="{ bump: bumpSide === 'a' }">{{ cur.sa }}</view>
      </view>
      <view class="sminus">:</view>
      <view class="scol b">
        <view class="sn">TEAM B</view>
        <view :key="`b${bumpTick}`" class="num" :class="{ bump: bumpSide === 'b' }">{{ cur.sb }}</view>
      </view>
    </view>
    <!-- alpha:1666 B 队两人（team 内联 margin:2px 0 6px） -->
    <view class="team tm-b">
      <view v-for="id in cur.B" :key="`b${id}`" class="tp" @click="emit('profile', id)">
        <ChibiAvatar :chibi="byId(id).chibi" :size="46" />
        <view class="nm">{{ byId(id).name }}</view>
      </view>
    </view>
    <!-- alpha:1667-1670 得分钮（scbtn 内 <b>A</b> → text.ltr，小程序不支持 b 标签） -->
    <view class="score-ops">
      <view class="scbtn" @click="emit('point', 'a')"><text class="ltr">A</text>得分 ＋</view>
      <view class="scbtn" @click="emit('point', 'b')"><text class="ltr">B</text>得分 ＋</view>
    </view>
    <!-- alpha:1671 内联 margin-top:10px + btn ghost sm -->
    <view class="undo-wrap">
      <AppButton variant="ghost" size="sm" @click="emit('undo')">误记 · 撤回一分</AppButton>
    </view>
  </view>
</template>

<script setup lang="ts">
/* alpha.html:1651-1674 renderScore 的 scoreboard 块（1656-1672）（P8b）。
   纯展示：point/undo/档案全走 emit，数据动作在 live store（页面接线）。 */
import { onUnmounted, ref, watch } from 'vue';
import type { PropType } from 'vue';
import ChibiAvatar from '@/components/ui/ChibiAvatar.vue';
import AppButton from '@/components/ui/AppButton.vue';
import type { LiveMatch, User } from '@/api/types';
import { pById } from '@/utils/rotate';
import { useLiveStore } from '@/stores/live';

const props = defineProps({
  /** live.cur 进行中的一场（A/B 存玩家 id + sa/sb） */
  cur: { type: Object as PropType<LiveMatch>, required: true },
  /** 分制 target（live.g.score，先到 N 且净胜 2） */
  target: { type: Number, required: true },
});
const emit = defineEmits<{
  (e: 'point', side: 'a' | 'b'): void;
  (e: 'undo'): void;
  (e: 'profile', id: number): void;
}>();

const liveStore = useLiveStore();
/** alpha:1656 nm 的 pById；查不到兜底 {name:'—'}（补齐 User 必填字段，同 CourtCard 约定） */
const byId = (id: number): User =>
  (liveStore.live ? pById(liveStore.live, id) : undefined) ?? {
    id: -1, name: '—', elo: 0, play: 0, win: 0, month: 0, chibi: {},
  };

/* 得分数字弹跳（alpha:1684 Element.animate([{scale(1.35),coral},{scale(1)}],260ms) 的 CSS 等价）：
   watch sa/sb，上涨侧挂 .bump（撤回数字回落不弹跳）；300ms 后摘 class。 */
const bumpSide = ref<'a' | 'b' | null>(null);
const bumpTick = ref(0);
let bumpTimer: ReturnType<typeof setTimeout> | null = null;
watch(
  () => [props.cur.sa, props.cur.sb] as const,
  ([na, nb], [oa, ob]) => {
    if (na > oa) setBump('a');
    else if (nb > ob) setBump('b');
  },
);
function setBump(s: 'a' | 'b'): void {
  bumpSide.value = s;
  bumpTick.value++;
  if (bumpTimer) clearTimeout(bumpTimer);
  bumpTimer = setTimeout(() => { bumpSide.value = null; }, 300);
}
onUnmounted(() => { if (bumpTimer) clearTimeout(bumpTimer); });
</script>

<style lang="scss" scoped>
/* ---------- alpha.html:303-318 记分板（逐字） ---------- */
.scoreboard {
  border: 1px solid rgba(255, 212, 0, 0.25);
  border-radius: var(--r-lg);
  overflow: hidden;
  background: linear-gradient(180deg, var(--ink3), var(--ink2));
  text-align: center;
  padding: 20px 14px 18px;
}
.sb-kick {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.34em;
  color: var(--dim);
  text-transform: uppercase;
}
/* alpha:274 .team（记分板两行 team 的布局） */
.team {
  display: flex;
  gap: 10px;
  justify-content: center;
}
/* alpha:1660 / 1666 team 行内联 margin */
.tm-a {
  margin: 14px 0 4px;
}
.tm-b {
  margin: 2px 0 6px;
}
/* alpha:275-281 .tp（nm() 只渲染头像+名；clickable 手感同 CourtCard 的 scoped 副本） */
.tp {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  width: 72px;
  cursor: pointer;
}
.tp:active {
  transform: scale(0.94);
}
.tp .nm {
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 70px;
}
.scores {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 18px;
  margin: 10px 0 4px;
}
.scol {
  flex: 1;
}
.scol .sn {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.18em;
  margin-bottom: 6px;
  height: 14px;
}
.scol.a .sn {
  color: var(--lemon);
}
.scol.b .sn {
  color: var(--ice);
}
.scol .num {
  font-family: var(--disp);
  font-size: 76px;
  line-height: 1;
  color: var(--cream);
}
.scol.a .num {
  color: var(--lemon);
}
.scol.b .num {
  color: var(--ice);
}
.sminus {
  font-family: var(--disp);
  font-size: 34px;
  color: var(--coral);
}
.score-ops {
  display: flex;
  gap: 10px;
  margin-top: 14px;
}
.scbtn {
  flex: 1;
  display: flex; /* alpha 原生 button 的居中，view 版等价 */
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(245, 241, 232, 0.16);
  border-radius: 16px;
  background: var(--ink);
  color: var(--cream);
  padding: 14px 0;
  font-family: var(--sans);
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: 0.15s;
}
.scbtn:active {
  transform: scale(0.95);
  border-color: var(--lemon);
}
/* alpha:318 .scbtn b（b 标签 → .ltr） */
.scbtn .ltr {
  font-family: var(--disp);
  font-size: 18px;
  color: var(--lemon);
  margin-right: 6px;
}
/* alpha:1671 内联 margin-top:10px */
.undo-wrap {
  margin-top: 10px;
}

/* alpha:1684 得分弹跳 CSS 等价：scale 1.35→1 + 珊瑚闪色（#FF5A36=var(--coral)），260ms；
   to 不写 color → 自动回落本侧 .num 自身色（A 黄 / B 青），同 Element.animate 语义 */
.num.bump {
  animation: numBump 260ms ease-out;
}
@keyframes numBump {
  from {
    transform: scale(1.35);
    color: var(--coral);
  }
  to {
    transform: scale(1);
  }
}
</style>
