<template>
  <!-- 块二对局卡（2.4 批2 单卡自足）：一片一实例，playing/idle 由 court.A/B 空否自判——
     playing = 对阵区 + 卡底记分框「比分即按钮」+ 全权工具行；
     idle = 空片差人卡（还差 N 人 · courtSize-aware + 自动排阵/去拉人双钮）。
     卡头 = 场地号 + 单双打标识（读 court.singles，选了什么显什么）+ 分制 +
     连庄 chip（仅 down=loser 且该边 streak>0 显示，2.4 新增显示）。
     记分本地化（2026-10-09）：比分显示吃本机账 localScores（服务端不记进行中比分），
     点数字/撤回/清零都是本地操作对球友开放——清零=清自己手机的本地账（各手机各记
     各的互不影响），故与撤回并列在记分框中列、不设全权门槛；「结束对局」开本地上传窗、
     「上一场 · 改分」开覆盖重落窗（均全站唯一 settleWindow，组件直开——
     与 SweepSheet/EndSettleModal 同一扇）；取消对局是全权手柄，先弹后果确认（A3，
     确认槽在页面层）。 -->
  <view class="court-matchcard" :class="{ idle: !playing }">
    <!-- ---------- playing：对阵区 ---------- -->
    <template v-if="playing">
      <view class="match-header">
        <view class="court-title">
          <text class="court-name">{{ label }}</text>
          <text class="court-no"
            >{{ court.singles ? "单打" : "双打" }} · {{ scoring }}分</text
          >
        </view>
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
           数字吃本机账 localScores（记分本地化：各手机各记各的，点数字零网络） -->
      <view class="score-plate">
        <view class="sp-num a-side" @click="emit('point', court.id, 'a')">
          <view
            :key="`a${bumpTick}`"
            class="sp-v"
            :class="{ bump: bumpSide === 'a', lead: local.sa > local.sb }"
            >{{ local.sa }}</view
          >
          <text class="sp-t">TEAM A · 记分</text>
        </view>
        <view class="sp-mid">
          <view class="sp-colon">:</view>
          <text
            class="sp-undo"
            @click="emit('undo', court.id)"
            @longpress="emit('clear', court.id)"
            >撤回</text
          >
        </view>
        <view class="sp-num b-side" @click="emit('point', court.id, 'b')">
          <view
            :key="`b${bumpTick}`"
            class="sp-v"
            :class="{ bump: bumpSide === 'b', lead: local.sb > local.sa }"
            >{{ local.sb }}</view
          >
          <text class="sp-t">TEAM B · 记分</text>
        </view>
      </view>

      <!-- 全权工具行（非 full 不渲染；换人不设独立入口，走「点人」抽屉）：
          结束对局=开本地上传窗（先传先落）；上一场·改分=覆盖重落窗（销 P2-1 后的
          纠错入口，预填最新落账）；取消对局先确认由页面接（A3）。
          清零不在本行——球友本地操作，在记分框中列与撤回并列 -->
      <view v-if="full" class="match-card-tools">
        <text
          v-if="lastMatch"
          class="tool-link"
          @click="liveStore.openSettleWindow(court.id, 'overwrite')"
          >上一场 {{ lastMatch.sa }}:{{ lastMatch.sb }} · 改分</text
        >
        <text class="tool-link" @click="emit('settle', court.id)"
          >结束对局</text
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
/* 对局卡（2.1 §2-4 · 2.4 批2 多片化 · 2.3 记分本地化）：数据读 live store（byId/queue/
   localScores），动作走 emit 由页面接 store（记分族 emit 均带 court.id）；「上一场 · 改分」
   组件直开结算窗（settleWindow 单一源在 store——与 SweepSheet/EndSettleModal 同扇）。
   bump 弹跳 = Scoreboard 的 watch+key 方案移植（连点同侧重触发）。 */
import { computed, onUnmounted, ref, watch } from "vue";
import type { PropType } from "vue";
import ChibiAvatar from "@/components/ui/ChibiAvatar.vue";
import AppButton from "@/components/ui/AppButton.vue";
import type { LiveCourt } from "@/api/types";
import { courtSize } from "@/utils/rotate";
import { GUEST_DUPR, fmtDupr1 } from "@/utils/elo";
import { courtDisplayName } from "@/utils/format";
import { courtNoOf, latestMatchOf, useLiveStore } from "@/stores/live";

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

/** 本机账（记分本地化的显示源：服务端不记进行中比分，视图 sa/sb 位恒 0）；
    无账（这片还没点过分）显示 0:0 */
const local = computed(
  () => liveStore.localScores[props.court.id] ?? { sa: 0, sb: 0, last: null },
);

/** 该片最新落账战报（「上一场 · 改分」入口的真值源，latestMatchOf 单一源——
    与改分窗预填同一行）；显示口径取宽松案：全权 + 存在落账行即显示——
    单幅视图里最新行恒是「下一场未落账」那场（下一场一落账它就不再是最新行，
    视图随 3s 轮询前移），seq/court_seq 差值判不出窗口边界；视图落后于服务端的
    窗口已关误点由后端片号闸 409 拒、store 对表 toast「现场已更新」兜底 */
const lastMatch = computed(() =>
  latestMatchOf(liveStore.liveView, courtNoOf(props.court.id)),
);

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

/* 得分数字弹跳（Scoreboard 同法）：watch 本机账，上涨侧挂 .bump（撤回回落不弹）；
   :key 自增重挂载，连点同侧也能重触发 */
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

/* 卡头胶囊（原型 .court-matchcard .chip；现 idle 态「空闲待开」用） */
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
  justify-content: space-between;
  padding: 12px 10px 8px;
  border-inline: 1px dashed rgba(245, 241, 232, 0.1);
}
.sp-colon {
  font-family: var(--disp);
  font-size: 26px;
  line-height: 1;
  color: var(--coral);
}
/* 撤回入口（§4.8）：支持撤回到底，长按清零 */
.sp-undo {
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
