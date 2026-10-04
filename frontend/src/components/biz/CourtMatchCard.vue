<template>
  <!-- 块二对局卡三态（temp/打球页原型 .court-matchcard 逐字）：
       playing = 正在打（对阵 + 卡底记分框「比分即按钮」+ 组织者工具行）；
       ready = 待开（同对阵、半透明，NEXT · 待开打，中缝提示上一场终局即开打）；
       idle = 空闲虚线卡（候场人数提示 + 自动排阵/去拉人双钮）。
       点数字记分；非组织者点数字 toast 拦截（卡内直调 ui store，同项目先例）。 -->
  <view class="court-matchcard" :class="variant">
    <!-- ---------- playing / ready：对阵区 ---------- -->
    <template v-if="variant !== 'idle'">
      <view class="match-header">
        <view class="court-title">
          <text class="court-name">{{ name }}</text>
          <text class="court-no">{{ A.length >= 2 ? '双打' : '单打' }}</text>
        </view>
        <text v-if="variant === 'ready'" class="chip ice">NEXT · 待开打</text>
      </view>

      <view class="match-arena">
        <view class="arena-side">
          <view class="side-label team-a">TEAM A</view>
          <view class="players-duo">
            <view v-for="id in A" :key="`a${id}`" class="player-unit" @click="emit('profile', id)">
              <view class="avatar-wrap"><ChibiAvatar :chibi="byId(id).chibi" :size="44" /></view>
              <text class="pname">{{ byId(id).name }}</text>
              <text class="pelo">{{ byId(id).elo || '新' }}</text>
              <text v-if="byId(id).shadow" class="badge guest">访客</text>
              <text v-else-if="byId(id).skip" class="badge rest">歇</text>
            </view>
          </view>
        </view>
        <view class="scoreboard-center">
          <view class="vs-big">VS</view>
          <view v-if="variant === 'ready'" class="score-rule-tip">上一场终局即开打</view>
        </view>
        <view class="arena-side">
          <view class="side-label team-b">TEAM B</view>
          <view class="players-duo">
            <view v-for="id in B" :key="`b${id}`" class="player-unit" @click="emit('profile', id)">
              <view class="avatar-wrap"><ChibiAvatar :chibi="byId(id).chibi" :size="44" /></view>
              <text class="pname">{{ byId(id).name }}</text>
              <text class="pelo">{{ byId(id).elo || '新' }}</text>
              <text v-if="byId(id).shadow" class="badge guest">访客</text>
              <text v-else-if="byId(id).skip" class="badge rest">歇</text>
            </view>
          </view>
        </view>
      </view>

      <!-- 卡底记分框（原型 .score-plate）：点左数字 = A +1，点右 = B +1；领先侧 .lead 高亮 -->
      <view v-if="variant === 'playing'" class="score-plate">
        <view class="sp-num a-side" @click="onPoint('a')">
          <view :key="`a${bumpTick}`" class="sp-v" :class="{ bump: bumpSide === 'a', lead: sa > sb }">{{ sa }}</view>
          <text class="sp-t">TEAM A · 记分</text>
        </view>
        <view class="sp-mid">
          <view class="sp-colon">:</view>
          <text class="sp-tip">点数字记分</text>
        </view>
        <view class="sp-num b-side" @click="onPoint('b')">
          <view :key="`b${bumpTick}`" class="sp-v" :class="{ bump: bumpSide === 'b', lead: sb > sa }">{{ sb }}</view>
          <text class="sp-t">TEAM B · 记分</text>
        </view>
      </view>

      <!-- 组织者工具行（非 org 不渲染；换人不设独立入口，走「点人」抽屉） -->
      <view v-if="variant === 'playing' && org" class="match-card-tools">
        <text class="tool-link" @click="emit('undo')">撤一分</text>
        <text class="tool-link" @click="emit('clear')">清零</text>
        <text class="tool-link" @click="emit('settle')">终局结算</text>
        <text class="tool-link danger" @click="emit('cancel')">取消对局</text>
      </view>
    </template>

    <!-- ---------- idle：空闲待开（虚线态） ---------- -->
    <template v-else>
      <view class="match-header">
        <view class="court-title">
          <text class="court-name">{{ name }}</text>
        </view>
        <text class="chip">空闲待开</text>
      </view>
      <view class="idle-hint">{{ waiting >= 4 ? `候场 ${waiting} 人 · 够开 1 片` : `还差 ${4 - waiting} 人 · 候场 ${waiting} / 需 4 人` }}</view>
      <view class="idle-sub">按积分蛇形均衡派单 · 上场次数少者优先</view>
      <view class="idle-btns">
        <AppButton variant="pri" class="flex1" :disabled="waiting < 4" @click="emit('autodeal')">⚡ 自动排阵</AppButton>
        <AppButton variant="ghost" class="flex1" @click="emit('pull')">📢 去拉人</AppButton>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
/* 对局卡（2.1 §2-4）：数据读 live store（byId/queue），动作走 emit 由页面接 store——
   只有非组织者记分拦截的 toast 留在卡内（原型口径「第一版仅组织者记分」）。
   bump 弹跳 = Scoreboard 的 watch+key 方案移植（连点同侧重触发）。 */
import { computed, onUnmounted, ref, watch } from 'vue';
import type { PropType } from 'vue';
import ChibiAvatar from '@/components/ui/ChibiAvatar.vue';
import AppButton from '@/components/ui/AppButton.vue';
import type { LiveCourt, LiveMatch } from '@/api/types';
import { useLiveStore } from '@/stores/live';
import { useUiStore } from '@/stores/ui';

const props = defineProps({
  /** 卡态：playing=正在打（cur）/ ready=待开（courts[i]）/ idle=空闲待开 */
  variant: { type: String as PropType<'playing' | 'ready' | 'idle'>, required: true },
  /** playing 用：live.cur */
  cur: { type: Object as PropType<LiveMatch>, default: undefined },
  /** ready 用：live.courts[i] */
  court: { type: Object as PropType<LiveCourt>, default: undefined },
  /** 显示名（页面算好，如「3号场」） */
  name: { type: String, required: true },
  /** 是否组织者（工具行渲染与记分权限） */
  org: { type: Boolean, default: false },
});
const emit = defineEmits<{
  (e: 'point', side: 'a' | 'b'): void;
  (e: 'undo'): void;
  (e: 'clear'): void;
  (e: 'settle'): void;
  (e: 'cancel'): void;
  (e: 'autodeal'): void;
  (e: 'pull'): void;
  (e: 'profile', id: number): void;
}>();

const liveStore = useLiveStore();
const ui = useUiStore();
const byId = (id: number) => liveStore.byId(id);

/** 队伍 id 列表：playing 读 cur，ready 读 court */
const A = computed<number[]>(() => (props.variant === 'playing' ? props.cur?.A : props.court?.A) ?? []);
const B = computed<number[]>(() => (props.variant === 'playing' ? props.cur?.B : props.court?.B) ?? []);
const sa = computed(() => props.cur?.sa ?? 0);
const sb = computed(() => props.cur?.sb ?? 0);

/** idle 卡的候场人数（够不够开一片的判定口径） */
const waiting = computed(() => liveStore.live?.queue.length ?? 0);

/** 记分：数字即按钮；非组织者 toast 拦截（同项目先例：卡内直调 ui store） */
function onPoint(side: 'a' | 'b'): void {
  if (!props.org) {
    ui.toast('第一版仅组织者记分');
    return;
  }
  emit('point', side);
}

/* 得分数字弹跳（Scoreboard 同法）：watch sa/sb，上涨侧挂 .bump（撤回回落不弹）；
   :key 自增重挂载，连点同侧也能重触发 */
const bumpSide = ref<'a' | 'b' | null>(null);
const bumpTick = ref(0);
let bumpTimer: ReturnType<typeof setTimeout> | null = null;
watch(
  () => [sa.value, sb.value] as const,
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
/* ---------- 原型 .court-matchcard（逐字换 tokens） ---------- */
.court-matchcard {
  border: 1px solid rgba(255, 212, 0, 0.28);
  border-radius: var(--r-lg);
  background: linear-gradient(180deg, var(--ink3), var(--ink2));
  padding: 16px;
  margin: 14px 14px 0;
  position: relative;
  overflow: hidden;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
}
.court-matchcard:first-child {
  margin-top: 12px;
}
.court-matchcard::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--lemon), transparent);
}
.court-matchcard.idle {
  border: 1px dashed rgba(245, 241, 232, 0.2);
  background: var(--ink2);
  box-shadow: none;
}
.court-matchcard.idle::before {
  display: none;
}

.match-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.court-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.court-name {
  font-family: var(--disp);
  font-size: 20px;
  color: var(--lemon);
  letter-spacing: 0.05em;
}
.idle .court-name {
  color: var(--dim);
}
.court-no {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--dim);
}

/* 卡头胶囊（原型 .court-matchcard .chip） */
.chip {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  font-weight: 400;
  padding: 2px 8px;
  border-radius: 99px;
  border: 1px solid rgba(245, 241, 232, 0.16);
  color: var(--dim);
  background: none;
  flex: none;
}
.chip.ice {
  border-color: var(--ice);
  color: var(--ice);
}

/* ---------- 对阵区：A 队(左) — 中板(中) — B 队(右) ---------- */
.match-arena {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin: 10px 0;
}
.arena-side {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.side-label {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.15em;
  font-weight: 700;
}
.side-label.team-a {
  color: var(--lemon);
}
.side-label.team-b {
  color: var(--ice);
}
.players-duo {
  display: flex;
  gap: 8px;
  justify-content: center;
}
.player-unit {
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
  width: 58px;
  transition: transform 0.15s;
}
.player-unit:active {
  transform: scale(0.92);
}
.avatar-wrap {
  width: 44px;
  height: 44px;
  position: relative;
}
.pname {
  font-size: 11px;
  font-weight: 600;
  margin-top: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 58px;
  text-align: center;
}
.pelo {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
}
.ready .player-unit {
  opacity: 0.55;
  filter: saturate(0.6);
}

/* 中板：VS / 待开提示 */
.scoreboard-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 96px;
}
.score-rule-tip {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
  letter-spacing: 0.08em;
  margin-top: 2px;
  text-align: center;
}
.vs-big {
  font-family: var(--disp);
  font-size: 30px;
  color: var(--coral);
  letter-spacing: 0.06em;
  line-height: 1.2;
}

/* ---------- 卡底记分框：比分即按钮 ---------- */
.score-plate {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: stretch;
  border: 1px solid rgba(245, 241, 232, 0.14);
  border-radius: 16px;
  background: linear-gradient(180deg, var(--ink3), var(--ink2));
  margin-top: 14px;
  overflow: hidden;
}
.sp-num {
  cursor: pointer;
  padding: 10px 6px 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  transition: background 0.15s, transform 0.1s;
}
.sp-v {
  font-family: var(--disp);
  font-size: 46px;
  line-height: 1;
  min-width: 44px;
  text-align: center;
}
.sp-t {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.15em;
  color: var(--dim);
}
.sp-num.a-side {
  color: var(--lemon);
}
.sp-num.b-side {
  color: var(--ice);
}
.sp-num.a-side:active {
  background: rgba(255, 212, 0, 0.14);
  transform: scale(0.97);
}
.sp-num.b-side:active {
  background: rgba(111, 231, 255, 0.14);
  transform: scale(0.97);
}
/* 领先方高亮（原型无此细节，按「领先方高亮」从简：本色辉光） */
.sp-v.lead {
  text-shadow: 0 0 16px currentColor;
}
.sp-mid {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1px;
  padding: 0 6px;
  border-inline: 1px dashed rgba(245, 241, 232, 0.1);
}
.sp-colon {
  font-family: var(--disp);
  font-size: 22px;
  color: var(--coral);
}
.sp-tip {
  font-family: var(--mono);
  font-size: 8px;
  color: var(--dim);
  letter-spacing: 0.06em;
  white-space: nowrap;
}
.sp-v.bump {
  animation: scoreBump 0.28s ease-out;
}
@keyframes scoreBump {
  0% {
    transform: scale(1.35);
    color: var(--coral);
  }
  100% {
    transform: scale(1);
  }
}

/* ---------- 卡底工具行（组织者） ---------- */
.match-card-tools {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid rgba(245, 241, 232, 0.07);
}
.tool-link {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--dim);
  cursor: pointer;
  transition: color 0.15s;
}
.tool-link:active {
  color: var(--lemon);
}
.tool-link.danger:active {
  color: var(--coral);
}

/* ---------- 徽章（访客/歇）：形与色在 base.scss 全局类；此处只补头像下方的位置 margin ---------- */
.badge {
  margin-top: 2px;
}

/* ---------- idle 空闲卡 ---------- */
.idle-hint {
  font-size: 13px;
  font-weight: 600;
  text-align: center;
  margin-top: 2px;
}
.idle-sub {
  font-size: 11px;
  color: var(--dim);
  text-align: center;
  margin-top: 5px;
}
.idle-btns {
  display: flex;
  gap: 8px;
  margin-top: 14px;
}
.flex1 {
  flex: 1;
}
</style>
