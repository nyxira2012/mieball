<template>
  <!-- 块二对局卡（2.4 批2 单卡自足）：一片一实例，playing/idle 由 court.A/B 空否自判——
     playing = 对阵区 + 卡底记分框「比分即按钮」+ 全权工具行；
     idle = 空片差人卡（还差 N 人 · courtSize-aware + 自动排阵/去拉人双钮）。
     卡头 = 场地号 + 单双打标识（读 court.singles，选了什么显什么）+ 分制 +
     连庄 chip（仅 down=loser 且该边 streak>0 显示，2.4 新增显示）。
     点数字记分与撤回对所有人开放（2.2 §4.8）；清零/提前结算/取消是全权手柄，
     其中清零/取消先弹后果确认（A3，确认槽在页面层）。
     待确认态（2.3 §4.3）：卡头「待确认」chip + 记分框压暗不可点 + 工具行收起——
     整片冻结（记分/撤分/换人锁死），清零/取消/调分出口收进确认窗。 -->
  <view class="court-matchcard" :class="{ idle: !playing, frozen }">
    <!-- ---------- playing：对阵区 ---------- -->
    <template v-if="playing">
      <view class="match-header">
        <view class="court-title">
          <text class="court-name">{{ label }}</text>
          <text class="court-no"
            >{{ court.singles ? "单打" : "双打" }} · {{ scoring }}分</text
          >
        </view>
        <!-- §4.3 待确认标识：该片冻结中（记分/撤分/换人锁死，出口收在确认窗） -->
        <text v-if="frozen" class="chip frozen-chip">待确认</text>
      </view>

      <view class="match-arena">
        <template v-for="(s, si) in sides" :key="s.k">
          <view class="arena-side">
            <view class="side-label" :class="s.team">
              {{ s.label }}
              <text v-if="streakOf(s.k)" class="streak-tag"
                >连庄 {{ streakOf(s.k) }}</text
              >
            </view>
            <view class="players-duo">
              <view
                v-for="pl in s.players"
                :key="`${s.k}${pl.id}`"
                class="player-unit"
                @click="emit('person', pl.id)"
              >
                <view class="avatar-wrap"
                  ><ChibiAvatar :chibi="pl.p.chibi" :size="44"
                /></view>
                <text class="pname">{{ pl.p.name }}</text>
                <text class="pelo"
                  >DUPR {{ fmtDupr1(pl.p.dupr ?? GUEST_DUPR) }}</text
                >
                <text v-if="pl.p.shadow" class="badge guest">访客</text>
                <text v-else-if="pl.p.skip" class="badge rest">歇</text>
              </view>
            </view>
          </view>
          <view v-if="si === 0" class="scoreboard-center">
            <view class="vs-big">VS</view>
          </view>
        </template>
      </view>

      <!-- 卡底记分框（原型 .score-plate）：点左数字 = A +1，点右 = B +1；领先侧 .lead 高亮；
           待确认片冻结（§4.3）：记分框压暗不可点、撤分入口收起——处理入口在确认窗 -->
      <view class="score-plate" :class="{ off: frozen }">
        <view class="sp-num a-side" @click="emit('point', court.id, 'a')">
          <view
            :key="`a${bumpTick}`"
            class="sp-v"
            :class="{ bump: bumpSide === 'a', lead: court.sa > court.sb }"
            >{{ court.sa }}</view
          >
          <text class="sp-t">TEAM A · 记分</text>
        </view>
        <view class="sp-mid">
          <view class="sp-colon">:</view>
          <text class="sp-tip">{{
            frozen ? "待确认 · 窗内处理" : "点数字记分"
          }}</text>
          <!-- 撤回对所有人可见（§4.8：记分±1 是球友手柄，撤回同族；store 本就无 guard） -->
          <text v-if="!frozen" class="sp-undo" @click="emit('undo', court.id)"
            >撤回</text
          >
        </view>
        <view class="sp-num b-side" @click="emit('point', court.id, 'b')">
          <view
            :key="`b${bumpTick}`"
            class="sp-v"
            :class="{ bump: bumpSide === 'b', lead: court.sb > court.sa }"
            >{{ court.sb }}</view
          >
          <text class="sp-t">TEAM B · 记分</text>
        </view>
      </view>

      <!-- 全权工具行（非 full 不渲染；换人不设独立入口，走「点人」抽屉）：
          清零/取消先确认由页面接（A3）；撤回已挪记分行对所有人开放（§4.8），
          不再占工具行；待确认片整行收起（§4.3-2：清零/取消/提前结算入口收进确认窗） -->
      <view v-if="full && !frozen" class="match-card-tools">
        <text class="tool-link" @click="emit('clear', court.id)">清零</text>
        <text class="tool-link" @click="emit('settle', court.id)"
          >提前结算</text
        >
        <text class="tool-link danger" @click="emit('cancel', court.id)"
          >取消对局</text
        >
      </view>
    </template>

    <!-- ---------- idle：空片差人卡 ---------- -->
    <template v-else>
      <view class="match-header">
        <view class="court-title">
          <text class="court-name">{{ label }}</text>
        </view>
        <text class="chip">空闲待开</text>
      </view>
      <view class="idle-hint">{{
        waiting >= size
          ? `候场 ${waiting} 人 · 够开 1 片`
          : `还差 ${size - waiting} 人 · 候场 ${waiting} / 需 ${size} 人`
      }}</view>
      <view class="idle-btns">
        <AppButton
          variant="pri"
          class="flex1"
          :disabled="waiting < size || !full"
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
/* 对局卡（2.1 §2-4 · 2.4 批2 多片化）：数据读 live store（byId/queue/rules），
   动作走 emit 由页面接 store（记分/终局/取消 emit 均带 court.id）。
   bump 弹跳 = Scoreboard 的 watch+key 方案移植（连点同侧重触发）。 */
import { computed, onUnmounted, ref, watch } from "vue";
import type { PropType } from "vue";
import ChibiAvatar from "@/components/ui/ChibiAvatar.vue";
import AppButton from "@/components/ui/AppButton.vue";
import type { LiveCourt } from "@/api/types";
import { courtSize } from "@/utils/rotate";
import { GUEST_DUPR, fmtDupr1 } from "@/utils/elo";
import { courtDisplayName } from "@/utils/format";
import { useLiveStore } from "@/stores/live";

const props = defineProps({
  /** 本片（playing/idle 由 A/B 空否自判） */
  court: { type: Object as PropType<LiveCourt>, required: true },
  /** 是否全权（组织者 ∨ 管理员，单一源在 live store）：工具行渲染与自动排阵可用性 */
  full: { type: Boolean, default: false },
});
const emit = defineEmits<{
  (e: "point", courtId: number, side: "a" | "b"): void;
  (e: "undo", courtId: number): void;
  (e: "clear", courtId: number): void;
  (e: "settle", courtId: number): void;
  (e: "cancel", courtId: number): void;
  (e: "autodeal"): void;
  (e: "pull"): void;
  /** 点场上人 → 开点人抽屉（2026-10-10 修复批 F5：此前开档案卡，组织者对场上人
      设/撤管理员无 UI 路径；点人抽屉头部即档案链接，档案卡只多一跳） */
  (e: "person", id: number): void;
}>();

const liveStore = useLiveStore();

/** playing/idle 自判：A/B 任一半边有人即在打（补满即打，无待开态） */
const playing = computed(
  () => !!props.court.A.length || !!props.court.B.length,
);

/** 待确认冻结（§4.3 单片冻结呈现）：单一源在 store 的 isPending（读视图片状态——
   pending 即有窗、窗禁遮罩关，不再有「窗召不回」的情形）；记分框压暗不可点、
   工具行收起，处理入口在确认窗 */
const frozen = computed(() => liveStore.isPending(props.court.id));

/** 显示名（court.name 存场地号 '3号' → '3号场'，单一源 format.courtDisplayName）与
    分制（片快照优先：在打片定格开赛分制、改分制下一场起生效，2.6；视图缺行的
    本地补空片无快照 → 回落全局 g.scoring） */
const label = computed(() => courtDisplayName(props.court.name));
const scoring = computed(
  () => props.court.scoring ?? liveStore.live?.g.scoring ?? 11,
);

/** 连庄 chip（2.4 §4.6 新增显示）：只有输家下才有连庄，且该边 streak>0 才显 */
function streakOf(k: "a" | "b"): number {
  const L = liveStore.live;
  if (!L || L.rules.down !== "loser") return 0;
  return k === "a" ? props.court.streakA : props.court.streakB;
}

/** A/B 两队一并解析球员（computed 一次算好，模板只读数组——逐字段 byId 是每格一次名册线性扫描） */
const sides = computed(() =>
  [
    { k: "a" as const, label: "TEAM A", team: "team-a", ids: props.court.A },
    { k: "b" as const, label: "TEAM B", team: "team-b", ids: props.court.B },
  ].map((s) => ({
    ...s,
    players: s.ids.map((id) => ({ id, p: liveStore.byId(id) })),
  })),
);

/** idle 差人卡：还差几人按当前格式每片人数算（双打 4 / 单打 2） */
const size = computed(() => courtSize(liveStore.live?.rules.singles ?? false));
const waiting = computed(() => liveStore.live?.queue.length ?? 0);

/* 得分数字弹跳（Scoreboard 同法）：watch sa/sb，上涨侧挂 .bump（撤回回落不弹）；
   :key 自增重挂载，连点同侧也能重触发 */
const bumpSide = ref<"a" | "b" | null>(null);
const bumpTick = ref(0);
let bumpTimer: ReturnType<typeof setTimeout> | null = null;
watch(
  () => [props.court.sa, props.court.sb] as const,
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
  content: "";
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

/* 卡头胶囊（原型 .court-matchcard .chip；playing 态现用作连庄位——见 .streak-tag） */
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
  display: flex;
  align-items: center;
  gap: 5px;
}
.side-label.team-a {
  color: var(--lemon);
}
.side-label.team-b {
  color: var(--ice);
}
/* 连庄 chip（2.4 §4.6）：跟半边——赢家留场连庄数跳动，手动换人不动 */
.streak-tag {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.06em;
  font-weight: 400;
  padding: 1px 7px;
  border-radius: 99px;
  border: 1px solid rgba(255, 212, 0, 0.4);
  color: var(--lemon);
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

/* 中板：VS */
.scoreboard-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 96px;
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
  transition:
    background 0.15s,
    transform 0.1s;
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
/* 撤回入口（§4.8）：记分行内小字链接，对所有人可见 */
.sp-undo {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
  margin-top: 3px;
  cursor: pointer;
  text-decoration: underline dotted rgba(245, 241, 232, 0.3);
}
.sp-undo:active {
  color: var(--lemon);
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

/* ---------- 待确认冻结（§4.3）：轻呈现——卡头「待确认」chip + 记分框压暗不可点，
   出口与改分都在确认窗，本卡不另养第二套手柄 ---------- */
.chip.frozen-chip {
  border-color: rgba(255, 212, 0, 0.4);
  color: var(--lemon);
}
.court-matchcard.frozen .match-arena {
  opacity: 0.75;
}
.score-plate.off {
  pointer-events: none;
}
.score-plate.off .sp-v {
  opacity: 0.5;
  text-shadow: none;
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
.idle-btns {
  display: flex;
  gap: 8px;
  margin-top: 14px;
}
.flex1 {
  flex: 1;
}
</style>
