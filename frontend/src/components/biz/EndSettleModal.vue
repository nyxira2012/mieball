<template>
  <!-- 确认窗（2.3 §4.3-4.6 重造）：到分自动 / 提前结算人工开——同一扇窗。数据全读
       live store 视图（A4 画面不自算）：片号/比分/胜方预选吃 courts[].preselect，
       两队名单吃 players[].courtNo/courtSide。多片各弹各的互不等待——页面一次只渲染
       片号最小的一片，确认/关窗后下一片顶上（窗位在 store.settling Record）。
       §4.6 联动：点胜方可改预选（防左右记反、分低方选不中）；± 改分胜方自动跟分高方、
       平分清空禁确认。§4.5 窗内撤一分走后端 undo，响应视图驱动两路（auto 不够线自动关
       回在打 / manual 保窗只改比分），窗内比分显示吃视图。
       §4.11 ±积分预览当场算（settleElo，访客按新人初始等级 1500 代入当正常玩家——
       与后端 elo 镜像同口径）：预览只展示不落账，落账以确认响应 elo_rows
       为准（显示吃视图）。§4.3-2 清零重开与取消对局的待确认入口收在窗里（仅全权可见，
       emit 由页面危险确认槽接）；球友看窗只读：确认灰+旁注「请组织者或管理员确认」。
       z-110 fixed 居中；遮罩不可关（批5b 验收官销号，§4.3-2 出口全在窗内——遮罩纯视觉
       背板，无点击事件）：窗只按合同路径关——确认/清零/取消成功、auto 窗撤到分线下，
       均由响应视图驱动；遮罩关窗会把待确认片困成「冻结但无处处理」。 -->
  <view class="mwrap" :class="{ on: visible }">
    <view class="mmask" />
    <view class="modal">
      <view class="md-kick">CONFIRM · {{ courtName }}</view>
      <view class="md-title">确认<text class="bem">结束</text></view>

      <!-- 胜方点选：A 柠檬 / B 冰蓝；分低方与球友视角 .off 置灰 -->
      <view class="win-pick">
        <view
          class="wp a"
          :class="{ on: winA === true, off: !full || !canA }"
          @click="pick('a')"
        >
          <view class="t">TEAM A</view>
          <view class="n">{{ namesA }}</view>
        </view>
        <view
          class="wp b"
          :class="{ on: winA === false, off: !full || !canB }"
          @click="pick('b')"
        >
          <view class="t">TEAM B</view>
          <view class="n">{{ namesB }}</view>
        </view>
      </view>

      <!-- 大比分 + ± 改分（min 0，只改本地；确认时随 confirmSettle 写回） -->
      <view class="md-score">
        <view class="md-side">
          <view class="num a">{{ sa }}</view>
          <view class="adj">
            <view class="adj-btn" :class="{ off: !full }" @click="adj('a', -1)"
              >−</view
            >
            <view class="adj-btn" :class="{ off: !full }" @click="adj('a', 1)"
              >＋</view
            >
          </view>
        </view>
        <view class="c">:</view>
        <view class="md-side">
          <view class="num b">{{ sb }}</view>
          <view class="adj">
            <view class="adj-btn" :class="{ off: !full }" @click="adj('b', -1)"
              >−</view
            >
            <view class="adj-btn" :class="{ off: !full }" @click="adj('b', 1)"
              >＋</view
            >
          </view>
        </view>
      </view>
      <view class="md-tools">
        <text class="edit">比分可点改</text>
        <text v-if="full" class="md-undo" @click="undoInWindow">撤一分</text>
      </view>

      <!-- ±积分预览（胜队在前；平分未点胜方时不显示）；访客带「不计积分」标识（§4.11） -->
      <view v-for="(r, i) in preview" :key="i" class="elo-row">
        <text class="nm"
          >{{ r.name
          }}<text v-if="r.guest" class="gtag">访客 · 不计积分</text></text
        >
        <text class="d" :class="r.up ? 'up' : 'dn'">{{
          r.up ? `+${r.d}` : `−${Math.abs(r.d)}`
        }}</text>
      </view>
      <view class="md-note">±积分为当场估算 · 落账以结算为准</view>

      <view class="md-btns">
        <AppButton
          variant="pri"
          block
          :disabled="!canConfirm"
          @click="onConfirm"
          >确认结束 · 排下一场</AppButton
        >
        <view v-if="!full" class="md-full-tip">请组织者或管理员确认</view>
        <view v-else-if="winA === null" class="md-full-tip"
          >平分不分胜负 · 先点胜方</view
        >
        <!-- 待确认的出口（§4.3-2 收在窗里，仅全权）：先弹后果再执行，确认槽在页面 -->
        <view v-if="full" class="md-danger">
          <text class="md-link" @click="emit('clear')">清零重开</text>
          <text class="md-link danger" @click="emit('cancel')">取消对局</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
/* 确认窗呈现与联动（2.3 §4.3-4.6；编排归页面）：本地态只有 winA/sa/sb——起点吃视图
   （preselect/比分），± 只动本地（改完胜方跟分高方、平分清空），窗内撤分走后端、
   响应视图回来重新对齐；确认/撤分直调 store（落账·关窗·toast 都在 store），
   清零/取消 emit 由页面确认槽接（A3 危险动作先确认）。
   联动纯函数（followWinner/canPickWinner）单一源在 store 模块，测试落 live-store.test.ts。
   球友看窗只读：点选/±/撤置灰、确认灰+旁注；预览行复用 settleElo（访客代入 1500——
   与后端镜像同口径）。清扫态（store.sweepState）确认走 noRedeal=true：不排下一场不补位。 */
import { computed, ref, watch } from "vue";
import AppButton from "@/components/ui/AppButton.vue";
import {
  canPickWinner,
  courtNoOf,
  followWinner,
  useLiveStore,
} from "@/stores/live";
import { settleElo, type EloPlayer } from "@/utils/elo";
import { courtDisplayName } from "@/utils/format";
import { RANK_INIT } from "@/utils/rotate";
import type { LivePlayer } from "@/api/types";

const props = defineProps({
  visible: { type: Boolean, default: false },
  /** 确认中的片（页面从 settlingCourtId 透传；0 起片序，写动作同键） */
  courtId: { type: Number, required: true },
});
/** 清零重开 / 取消对局：待确认时的出口入口在窗里，后果确认在页面（A3） */
const emit = defineEmits<{ (e: "clear"): void; (e: "cancel"): void }>();

const liveStore = useLiveStore();
/** 全权单一源在 store（组织者 ∨ 管理员）：窗内一切手柄的前置闸 */
const full = computed(() => liveStore.isFullPower);

/* 本地态：比分可 ± 纠偏、胜方可改预选——起点吃视图 */
const winA = ref<boolean | null>(null);
const sa = ref(0);
const sb = ref(0);

/** 这片的总账片行（片序 0 起 → 片号 1 走 courtNoOf 单点）与两队名单（视图单一源） */
const courtRow = computed(() =>
  liveStore.liveView?.courts.find(
    (c) => c.courtNo === courtNoOf(props.courtId),
  ),
);
function sideRows(side: "a" | "b"): LivePlayer[] {
  return (
    liveStore.liveView?.players.filter(
      (p) => p.courtNo === courtNoOf(props.courtId) && p.courtSide === side,
    ) ?? []
  );
}

const courtName = computed(() =>
  courtDisplayName(
    liveStore.live?.courts.find((c) => c.id === props.courtId)?.name ?? "",
  ),
);
const namesA = computed(() =>
  sideRows("a")
    .map((p) => p.name)
    .join(" / "),
);
const namesB = computed(() =>
  sideRows("b")
    .map((p) => p.name)
    .join(" / "),
);

/* 开窗与窗内撤分共用一条对齐路：视图比分/预选变 → 本地态重置（± 只动本地不触发；
   撤分响应视图回来这里对齐——auto 不够线窗自动关、manual 保窗只改比分）。
   preselect 是视图算好的定值（领先方/平分 null，A4），与 followWinner 同一口径 */
watch(
  () =>
    [props.courtId, courtRow.value?.scoreA, courtRow.value?.scoreB] as const,
  ([, a, b]) => {
    sa.value = a ?? 0;
    sb.value = b ?? 0;
    winA.value =
      courtRow.value?.preselect === "a"
        ? true
        : courtRow.value?.preselect === "b"
          ? false
          : null; // 平分不预选（§4.4）
  },
  { immediate: true },
);

/** 分低方选不中（§4.6）；平分双方均可点 */
const canA = computed(() => canPickWinner(sa.value, sb.value, "a"));
const canB = computed(() => canPickWinner(sa.value, sb.value, "b"));
/** 确认闸：全权 + 已点胜方（平分未点禁确认） */
const canConfirm = computed(() => full.value && winA.value !== null);

/** 点胜方（防左右记反，可改预选）；球友只看不点 */
function pick(side: "a" | "b"): void {
  if (!full.value || !canPickWinner(sa.value, sb.value, side)) return;
  winA.value = side === "a";
}

/** ± 改分：改完胜方自动跟分高方、平分清空（分低的一方当不了胜方——前端联动，
    后端 settle-confirm 仍把关） */
function adj(side: "a" | "b", d: number): void {
  if (!full.value) return;
  if (side === "a") sa.value = Math.max(0, sa.value + d);
  else sb.value = Math.max(0, sb.value + d);
  winA.value = followWinner(sa.value, sb.value);
}

/** 窗内撤一分（§4.5）：够不够分线、关不关窗，两路都由后端 undo 判——
    响应视图落地后上面的 watch 对齐窗内比分 */
function undoInWindow(): void {
  if (!full.value) return;
  void liveStore.undoPoint(props.courtId);
}

/** ±积分预览（§4.11 当场估算，只展示不落账）：settleElo 与后端 elo 镜像同公式口径
    （K=24；访客按新人初始等级 1500 代入当正常玩家）；胜队在前 */
const preview = computed(() => {
  if (winA.value === null) return [];
  const w = sideRows(winA.value ? "a" : "b");
  const l = sideRows(winA.value ? "b" : "a");
  const asPlayer = (p: LivePlayer): EloPlayer => ({
    // 访客代入新人初始等级（与后端 elo 镜像同口径：同公式全额，访客自己不落账）
    elo: p.guest ? RANK_INIT : liveStore.byId(p.id).elo,
  });
  const all = [...w, ...l];
  return settleElo(w.map(asPlayer), l.map(asPlayer)).map((r, i) => ({
    name: all[i]!.name,
    guest: all[i]!.guest,
    up: r.up,
    d: r.d,
  }));
});

function onConfirm(): void {
  if (winA.value === null) return;
  // 清扫态（§4.9）确认不排下一场不补位——noRedeal 随 store.sweepState 透传
  void liveStore.confirmSettle(
    props.courtId,
    winA.value,
    sa.value,
    sb.value,
    liveStore.sweepState,
  );
}
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
  pointer-events: none; /* 关窗态不挡页面；on 态整层可点（窗内操作；遮罩纯视觉不可关窗） */
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
  transition:
    opacity 0.22s,
    visibility 0.22s;
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
/* 分低方选不中 / 球友只看（§4.6/§4.3）：置灰不可点，预选高亮仍可见 */
.wp.off {
  opacity: 0.45;
  pointer-events: none;
}

/* ---------- 大比分 + ± 小钮 ---------- */
.md-score {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  margin: 4px 0 10px;
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
/* 球友只看（§4.3）：± 置灰与确认钮（AppButton disabled）同一观感 */
.adj-btn.off {
  opacity: 0.35;
  pointer-events: none;
}
/* 比分注 + 窗内撤一分（§4.5，仅全权）：撤走后端 undo、两路关留在响应视图 */
.md-tools {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  margin-bottom: 12px;
}
.edit {
  font-size: 10px;
  color: var(--dim);
}
.md-undo {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  cursor: pointer;
  text-decoration: underline dotted rgba(245, 241, 232, 0.3);
}
.md-undo:active {
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
.elo-row .gtag {
  margin-left: 6px;
  font-family: var(--mono);
  font-size: 9px;
  font-weight: 400;
  color: var(--lilac);
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
.md-full-tip {
  text-align: center;
  font-size: 11px;
  color: var(--dim);
}
/* 待确认的出口（§4.3-2 收在窗里，仅全权）：清零重开 / 取消对局 */
.md-danger {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 28px;
}
.md-link {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--dim);
  cursor: pointer;
}
.md-link:active {
  color: var(--lemon);
}
.md-link.danger {
  color: var(--coral);
  opacity: 0.85;
}
.md-link.danger:active {
  color: var(--coral);
  opacity: 1;
}
</style>
