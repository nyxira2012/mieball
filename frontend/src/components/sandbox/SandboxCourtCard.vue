<template>
  <!-- 沙盒对局卡（2.7 批3，复刻 CourtMatchCard 长相手感——真局组件零改动）：
       playing = 卡头（片号/双打/片分制快照）+ 两队人（你高亮）+ 记分框（比分即按钮：
       点数字加分/冒号旁撤回/长按清零——全走 sandbox store 本地账）；
       idle = 差人卡（还差 N 人 · 候场 M / 需 4 + ⚡灰钮【普通球员如实】 + 去拉人真出口）。
       与真局两处如实降级：假人无档案不显 DUPR 行；⚡ 排阵在参与卡灰着点不动（规格 4.4）。
       点场上人 emit person——开点人抽屉（§4.4「点任何人的头像都开点人抽屉」，权限随卡走） -->
  <view class="sb-matchcard" :class="{ idle: !playing }">
    <!-- ---------- playing：对阵区 ---------- -->
    <template v-if="playing">
      <view class="sb-mhead">
        <view class="sb-mtitle">
          <text class="sb-mname">{{ court.no }}号场</text>
          <text class="sb-msub">双打 · {{ court.scoring }}分</text>
        </view>
      </view>

      <view class="sb-arena">
        <template v-for="(sd, si) in sides" :key="sd.k">
          <view class="sb-aside">
            <view class="sb-slabel" :class="sd.k === 'a' ? 'ta' : 'tb'">{{
              sd.label
            }}</view>
            <view class="sb-duo">
              <view
                v-for="pl in sd.players"
                :key="`${sd.k}${pl.id}`"
                class="sb-unit"
                :class="{ me: pl.you }"
                @click="emit('person', pl.id)"
              >
                <!-- my-avatar=参与卡第 5 步只亮你；court-avatar=组织卡第 6 步整排亮
                     （queue-kevin 同惯例：提示语点名，光圈指路不猜人） -->
                <view
                  class="sb-avwrap"
                  :class="{
                    'sb-glow':
                      sandbox.spot === 'court-avatar' ||
                      (sandbox.spot === 'my-avatar' && pl.you),
                  }"
                  ><AvatarBadge :url="pl.avatar" :size="44"
                /></view>
                <text class="sb-pname">{{ pl.name }}</text>
                <text v-if="pl.guest" class="badge guest">访客</text>
                <text v-else-if="pl.skip" class="badge rest">歇</text>
              </view>
            </view>
          </view>
          <view v-if="si === 0" class="sb-center">
            <view class="sb-vs">VS</view>
          </view>
        </template>
      </view>

      <!-- 卡底记分框（比分即按钮）：光圈锚 my-score 只挂你队的数字（规格 A3 第 3/4/6 条） -->
      <view class="sb-plate">
        <view class="sb-num ta" @click="emit('point', court.no, 'a')">
          <view
            :key="`a${bumpTick}`"
            class="sb-v"
            :class="{
              bump: bumpSide === 'a',
              lead: local.sa > local.sb,
              'sb-glow': sandbox.spot === 'my-score' && mySide === 'a',
            }"
            >{{ local.sa }}</view
          >
          <text class="sb-nlabel">TEAM A · 记分</text>
        </view>
        <view class="sb-mid">
          <view class="sb-colon">:</view>
          <text
            class="sb-undo"
            @click="emit('undo', court.no)"
            @longpress="emit('clear', court.no)"
            >撤回</text
          >
        </view>
        <view class="sb-num tb" @click="emit('point', court.no, 'b')">
          <view
            :key="`b${bumpTick}`"
            class="sb-v"
            :class="{
              bump: bumpSide === 'b',
              lead: local.sb > local.sa,
              'sb-glow': sandbox.spot === 'my-score' && mySide === 'b',
            }"
            >{{ local.sb }}</view
          >
          <text class="sb-nlabel">TEAM B · 记分</text>
        </view>
      </view>

      <!-- 全权工具行（复刻 CourtMatchCard .match-card-tools；非 full 不渲染——
           「本场完成＋直录」是组织者/管理员的本事，参与卡普通球员没有它）：沙盒只教
           「本场完成」——开结算窗直录（组织卡第九步，光圈锚 quick-settle-N 逐片指路：
           一次亮该结的那片，结完换下一颗）；真局工具行另有改分/重排/取消三件，
           教学不教（规格 §6 非目标） -->
      <view v-if="full" class="sb-tools">
        <text
          class="sb-toollink"
          :class="{ 'sb-glow': sandbox.spot === 'quick-settle-' + court.no }"
          @click="emit('settle', court.no)"
          >本场完成</text
        >
      </view>
    </template>

    <!-- ---------- idle：差人卡 ---------- -->
    <template v-else>
      <view class="sb-mhead">
        <view class="sb-mtitle">
          <text class="sb-mname dim">{{ court.no }}号场</text>
        </view>
        <text class="sb-chip">空闲待开</text>
      </view>
      <view class="sb-idlehint">{{
        waiting >= SIZE
          ? `候场 ${waiting} 人 · 够开 1 片`
          : `还差 ${SIZE - waiting} 人 · 候场 ${waiting} / 需 ${SIZE} 人`
      }}</view>
      <view class="sb-idlebtns">
        <!-- ⚡ 纯兜底钮（2.8 口径）：参与卡普通球员如实灰着点不动（full=false）；
             组织卡批4 亮钮——发牌失败补发用 -->
        <AppButton
          variant="pri"
          class="flex1"
          :disabled="waiting < SIZE || !full"
          @click="emit('autodeal')"
          >⚡ 自动排阵</AppButton
        >
        <AppButton variant="ghost" class="flex1" @click="emit('pull')"
          >📢 去拉人</AppButton
        >
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
/* 数据读 sandbox store（名册解析/本地记分/光圈锚），动作全 emit 由 Stage 接 store——
   与 CourtMatchCard 同构（组件只管呈现）。弹跳 = watch 本机账 + :key 重挂载（连点
   同侧也重触发）。SIZE=每片人数，单源 data.COURT_SIZE（教学局锁双打 4，engine fillIdle 同吃） */
import { computed, onUnmounted, ref, watch } from "vue";
import type { PropType } from "vue";
import AvatarBadge from "@/components/ui/AvatarBadge.vue";
import AppButton from "@/components/ui/AppButton.vue";
import type { SandCourt, SandPlayer } from "@/sandbox/engine";
import { COURT_SIZE } from "@/sandbox/data";
import { emptyLocal } from "@/utils/localScore";
import { useSandboxStore } from "@/stores/sandbox";

const props = defineProps({
  court: { type: Object as PropType<SandCourt>, required: true },
  /** 全权（组织卡批4 用；参与卡普通球员恒 false）——⚡ 兜底钮的可用性 */
  full: { type: Boolean, default: false },
});
const emit = defineEmits<{
  (e: "point", courtNo: number, side: "a" | "b"): void;
  (e: "undo", courtNo: number): void;
  (e: "clear", courtNo: number): void;
  (e: "settle", courtNo: number): void;
  (e: "autodeal"): void;
  (e: "pull"): void;
  (e: "person", id: number): void;
}>();

const sandbox = useSandboxStore();
const SIZE = COURT_SIZE;

const playing = computed(
  () => !!props.court.a.length || !!props.court.b.length,
);

const waiting = computed(() => sandbox.state?.queue.length ?? 0);

/** A/B 两队一并解析（computed 一次算好，模板只读数组） */
const sides = computed<
  { k: "a" | "b"; label: string; players: SandPlayer[] }[]
>(() => {
  const players = sandbox.state?.players ?? [];
  const of = (ids: number[]) =>
    ids
      .map((id) => players.find((p) => p.id === id))
      .filter((p): p is SandPlayer => !!p);
  return [
    { k: "a", label: "TEAM A", players: of(props.court.a) },
    { k: "b", label: "TEAM B", players: of(props.court.b) },
  ];
});

/** 你在本片哪一半边（光圈 my-score/my-avatar 的锚定依据；不在本片为 null） */
const mySide = computed<"a" | "b" | null>(() => {
  const you = sandbox.state?.players.find((p) => p.you);
  if (!you) return null;
  if (props.court.a.includes(you.id)) return "a";
  if (props.court.b.includes(you.id)) return "b";
  return null;
});

/** 本机账（无账显示 0:0；记分本地化与真局同语义，空账形状单一源 emptyLocal） */
const local = computed(
  () => sandbox.localScores[props.court.no] ?? emptyLocal(),
);

/* 得分数字弹跳（CourtMatchCard 同法）：上涨侧挂 .bump，撤回回落不弹 */
const bumpSide = ref<"a" | "b" | null>(null);
const bumpTick = ref(0);
let bumpTimer: ReturnType<typeof setTimeout> | null = null;
watch(
  () => [local.value.sa, local.value.sb] as const,
  ([na, nb], [oa, ob]) => {
    if (na > oa) setBump("a");
    else if (nb > ob) setBump("b");
  },
);
function setBump(s: "a" | "b"): void {
  bumpSide.value = s;
  bumpTick.value++;
  if (bumpTimer) clearTimeout(bumpTimer);
  bumpTimer = setTimeout(() => {
    bumpSide.value = null;
  }, 300);
}
onUnmounted(() => {
  if (bumpTimer) clearTimeout(bumpTimer);
});
</script>

<style lang="scss" scoped>
/* 长相与真局 CourtMatchCard 同族（tokens 同源），类名 sb- 前缀防串域 */
.sb-matchcard {
  border: 1px solid rgba(255, 212, 0, 0.28);
  border-radius: var(--r-lg);
  background: linear-gradient(180deg, var(--ink3), var(--ink2));
  padding: 16px;
  margin: 14px 14px 0;
  position: relative;
  overflow: hidden;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
}
.sb-matchcard:first-child {
  margin-top: 12px;
}
.sb-matchcard::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--lemon), transparent);
}
.sb-matchcard.idle {
  border: 1px dashed rgba(245, 241, 232, 0.2);
  background: var(--ink2);
  box-shadow: none;
}
.sb-matchcard.idle::before {
  display: none;
}

.sb-mhead {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.sb-mtitle {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.sb-mname {
  font-family: var(--disp);
  font-size: 20px;
  color: var(--lemon);
  letter-spacing: 0.05em;
}
.sb-mname.dim {
  color: var(--dim);
}
.sb-msub {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--dim);
}
.sb-chip {
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

/* 对阵区：A 队(左) — VS(中) — B 队(右) */
.sb-arena {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin: 10px 0;
}
.sb-aside {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.sb-slabel {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.15em;
  font-weight: 700;
}
.sb-slabel.ta {
  color: var(--lemon);
}
.sb-slabel.tb {
  color: var(--ice);
}
.sb-duo {
  display: flex;
  gap: 8px;
  justify-content: center;
}
.sb-unit {
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
  width: 58px;
  transition: transform 0.15s;
}
.sb-unit:active {
  transform: scale(0.92);
}
/* 你：名字提亮一档（规格「你的卡片高亮」从简——不另起配色） */
.sb-unit.me .sb-pname {
  color: var(--lemon);
}
.sb-avwrap {
  width: 44px;
  height: 44px;
  border-radius: 10px;
}
.sb-pname {
  font-size: 11px;
  font-weight: 600;
  margin-top: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 58px;
  text-align: center;
}
.sb-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 96px;
}
.sb-vs {
  font-family: var(--disp);
  font-size: 30px;
  color: var(--coral);
  letter-spacing: 0.06em;
  line-height: 1.2;
}

/* 记分框：比分即按钮 */
.sb-plate {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: stretch;
  border: 1px solid rgba(245, 241, 232, 0.14);
  border-radius: 16px;
  background: linear-gradient(180deg, var(--ink3), var(--ink2));
  margin-top: 14px;
  overflow: hidden;
}
.sb-num {
  cursor: pointer;
  padding: 10px 6px 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  transition:
    background 0.15s,
    transform 0.1s;
}
.sb-v {
  font-family: var(--disp);
  font-size: 46px;
  line-height: 1;
  min-width: 44px;
  text-align: center;
}
.sb-nlabel {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.15em;
  color: var(--dim);
}
.sb-num.ta {
  color: var(--lemon);
}
.sb-num.tb {
  color: var(--ice);
}
.sb-num.ta:active {
  background: rgba(255, 212, 0, 0.14);
  transform: scale(0.97);
}
.sb-num.tb:active {
  background: rgba(111, 231, 255, 0.14);
  transform: scale(0.97);
}
.sb-v.lead {
  text-shadow: 0 0 16px currentColor;
}
.sb-mid {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: space-between;
  padding: 12px 10px 8px;
  border-inline: 1px dashed rgba(245, 241, 232, 0.1);
}
.sb-colon {
  font-family: var(--disp);
  font-size: 26px;
  line-height: 1;
  color: var(--coral);
}
/* 撤回入口：点击撤一分、长按清零（与真局逐字同手感） */
.sb-undo {
  font-family: var(--mono);
  font-size: 13px;
  font-weight: 500;
  color: var(--dim);
  cursor: pointer;
  text-decoration: underline dotted rgba(245, 241, 232, 0.3);
  user-select: none;
  padding: 3px 6px;
  margin-bottom: 2px;
  transition:
    opacity 0.15s,
    color 0.15s;
}
.sb-undo:active {
  color: var(--lemon);
}
.sb-v.bump {
  animation: sbScoreBump 0.28s ease-out;
}
@keyframes sbScoreBump {
  0% {
    transform: scale(1.35);
    color: var(--coral);
  }
  100% {
    transform: scale(1);
  }
}

/* 徽章形色在 base.scss 全局类（.badge.rest/.guest），这里只补位 */
.sb-unit .badge {
  margin-top: 2px;
}

/* 全权工具行（CourtMatchCard .match-card-tools 同款） */
.sb-tools {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid rgba(245, 241, 232, 0.07);
}
.sb-toollink {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--dim);
  cursor: pointer;
  transition: color 0.15s;
}
.sb-toollink:active {
  color: var(--lemon);
}

/* 差人卡 */
.sb-idlehint {
  font-size: 13px;
  font-weight: 600;
  text-align: center;
  margin-top: 2px;
}
.sb-idlebtns {
  display: flex;
  gap: 8px;
  margin-top: 14px;
}
.flex1 {
  flex: 1;
}
</style>
