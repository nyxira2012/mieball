<template>
  <!-- 本地结算窗（2.3 记分本地化重造）：开关/片/模式单一源=store.settleWindow（直读，
       一次一扇，页面不再透传 visible/courtId）。upload=上传结算（谁都能传，后端把关
       到场者）：比分起点吃本机账 localScores[courtId]（不再吃视图比分——服务端不记
       进行中比分）；overwrite=改分重落（全权闸在 store.overwriteSettle）：预填该片
       最新落账 match 的比分胜方（视图 matches 按 courtNo 找最新行）。
       两队名单吃视图 players（courtNo/courtSide）。±积分预演读视图 elo_preview 双分支
       （批1 起挂 playing 片：A 胜/B 胜两套数随画面给、与落账同一条公式路——预演即
       落账）：点胜方在两套现成数间切换，仍当场变不等网络；访客行带「不计积分」标识
       （1.4 §4 不落账不进榜）。球友可操作（上传权=任意到场者）：全权只读态与
       「请组织者或管理员确认」旁注已删。
       「暂不结算」=closeSettleWindow 保本地分接着打（P2-2，唯一非上传出口）；± 纠偏
       upload 模式当场写回本机账——暂不结算后场卡接着打的就是纠偏后的分。
       窗内「撤一分」已删（P2-1）：场卡记分行撤分就在手边，撤分唯一入口=场卡本地。
       z-110 fixed 居中；遮罩不可关（旧裁决仍成立——关窗会丢待上传的账；遮罩纯视觉
       背板无点击事件），非上传出口只有「暂不结算」。 -->
  <view class="mwrap" :class="{ on: win != null }">
    <view class="mmask" />
    <view class="modal">
      <view class="md-kick">{{ kick }}</view>
      <view class="md-title">
        {{ mode === "overwrite" ? "改分" : "上传"
        }}<text class="bem">{{ mode === "overwrite" ? "重落" : "比分" }}</text>
      </view>
      <view v-if="mode === 'overwrite'" class="md-mode-tip"
        >把这场已落的账按新分重写 · 积分重算</view
      >

      <!-- 胜方点选：A 柠檬 / B 冰蓝；分低方选不中（§4.6） -->
      <view class="win-pick">
        <view
          class="wp a"
          :class="{ on: winA === true, off: !canA }"
          @click="pick('a')"
        >
          <view class="t">TEAM A</view>
          <view class="n">{{ namesA }}</view>
        </view>
        <view
          class="wp b"
          :class="{ on: winA === false, off: !canB }"
          @click="pick('b')"
        >
          <view class="t">TEAM B</view>
          <view class="n">{{ namesB }}</view>
        </view>
      </view>

      <!-- 大比分 + ± 改分（min 0；upload 模式纠偏当场写回本机账） -->
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
      </view>
      <view class="md-tools">
        <text class="edit">比分可点改</text>
      </view>

      <!-- ±积分预览（胜队在前；平分未点胜方时不显示）；访客带「不计积分」标识 -->
      <view v-for="(r, i) in preview" :key="i" class="elo-row">
        <text class="nm"
          >{{ r.name
          }}<text v-if="r.guest" class="gtag">访客 · 不计积分</text></text
        >
        <text class="d" :class="r.up ? 'up' : 'dn'">{{
          r.up ? `+${r.d}` : `−${Math.abs(r.d)}`
        }}</text>
      </view>
      <view class="md-note">±积分为结算预演 · 确认后落账生效</view>

      <view class="md-btns">
        <AppButton
          variant="pri"
          block
          :disabled="!canConfirm"
          @click="onConfirm"
          >{{
            mode === "overwrite" ? "确认改分 · 重落这场" : "确认上传 · 落账"
          }}</AppButton
        >
        <view v-if="winA === null" class="md-full-tip"
          >平分不分胜负 · 先点胜方</view
        >
        <!-- 唯一非上传出口（P2-2）：关窗不丢本机账，回场卡接着打 -->
        <AppButton variant="ghost" block @click="liveStore.closeSettleWindow()"
          >暂不结算 · 接着打</AppButton
        >
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
/* 本地结算窗呈现与联动（2.3 记分本地化；编排归 store）：本地态只有 winA/sa/sb——
   开窗时按模式重置（upload 吃本机账、胜方预选=分高方与 followWinner 同口径；
   overwrite 吃该片最新落账 match），± 只动本地（upload 模式写回本机账），确认直调
   store（uploadSettle/overwriteSettle：落账·关窗·toast 都在 store；清扫态 noRedeal
   随 settleWindow 透传）。
   联动纯函数（followWinner/canPickWinner）单一源在 store 模块，测试落 live-store.test.ts。
   上传权=任意到场者（后端 _require_arrived 把关）：窗内无全权只读态；改分重落全权
   闸在 store.overwriteSettle（needFull）。 */
import { computed, ref, watch } from "vue";
import AppButton from "@/components/ui/AppButton.vue";
import {
  canPickWinner,
  courtNoOf,
  followWinner,
  latestMatchOf,
  useLiveStore,
} from "@/stores/live";
import { courtDisplayName } from "@/utils/format";
import type { LivePlayer } from "@/api/types";

const liveStore = useLiveStore();

/** 窗位单一源在 store（一次一扇；visible/courtId/mode/noRedeal 全由它驱动） */
const win = computed(() => liveStore.settleWindow);
const mode = computed(() => win.value?.mode ?? "upload");
const kick = computed(
  () =>
    `${mode.value === "overwrite" ? "REWRITE" : "SETTLE"} · ${courtName.value}`,
);

/* 本地态：比分可 ± 纠偏、胜方可点选——起点按模式吃本机账/最新落账 */
const winA = ref<boolean | null>(null);
const sa = ref(0);
const sb = ref(0);

/** 当前结算窗这片在视图里的片号（courtNoOf(win.courtId) 三处共用单一源） */
const winCourtNo = computed(() => courtNoOf(win.value?.courtId ?? -1));

/** 这片的视图行（elo_preview 双支）与两队名单（视图单一源） */
const courtRow = computed(() =>
  liveStore.liveView?.courts.find((c) => c.courtNo === winCourtNo.value),
);
function sideRows(side: "a" | "b"): LivePlayer[] {
  const no = winCourtNo.value;
  return (
    liveStore.liveView?.players.filter(
      (p) => p.courtNo === no && p.courtSide === side,
    ) ?? []
  );
}

const courtName = computed(() =>
  courtDisplayName(
    liveStore.live?.courts.find((c) => c.id === win.value?.courtId)?.name ?? "",
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

/** overwrite 预填源=该片最新落账 match（latestMatchOf 单一源，场卡「上一场 · 改分」
    链接同一真值）；该片还没落过账（正常开不到这个模式）回落 0:0 不预选 */

/* 开窗对齐：settleWindow 变即按模式重置本地态（一次一扇，窗开着不会换片）；
   ± 只动本地不触发本 watch */
watch(
  win,
  (w) => {
    if (!w) return;
    if (w.mode === "overwrite") {
      const m = latestMatchOf(liveStore.liveView, winCourtNo.value);
      sa.value = m?.sa ?? 0;
      sb.value = m?.sb ?? 0;
      winA.value = m ? m.winA : null;
    } else {
      const acc = liveStore.localScores[w.courtId];
      sa.value = acc?.sa ?? 0;
      sb.value = acc?.sb ?? 0;
      winA.value = followWinner(sa.value, sb.value);
    }
  },
  { immediate: true },
);

/** 分低方选不中（§4.6）；平分双方均可点 */
const canA = computed(() => canPickWinner(sa.value, sb.value, "a"));
const canB = computed(() => canPickWinner(sa.value, sb.value, "b"));
/** 确认闸：已点胜方（平分未点禁确认） */
const canConfirm = computed(() => winA.value !== null);

/** 点胜方（防左右记反） */
function pick(side: "a" | "b"): void {
  if (!canPickWinner(sa.value, sb.value, side)) return;
  winA.value = side === "a";
}

/** ± 改分：改完胜方自动跟分高方、平分清空（分低的一方当不了胜方——前端联动，
    后端 settle-confirm/overwrite 仍把关）；upload 模式当场写回本机账——
    「暂不结算」后场卡接着打的就是纠偏后的分（overwrite 纠的是已落账那场，
    不碰下一盘的本机账） */
function adj(side: "a" | "b", d: number): void {
  if (side === "a") sa.value = Math.max(0, sa.value + d);
  else sb.value = Math.max(0, sb.value + d);
  winA.value = followWinner(sa.value, sb.value);
  if (mode.value === "upload") {
    const acc = liveStore.localScores[win.value?.courtId ?? -1];
    if (acc) {
      acc.sa = sa.value;
      acc.sb = sb.value;
    }
  }
}

/** ±积分预演：读视图 elo_preview 双分支——后端 _elo_settle 同一条路算好随画面给
    （批1 起挂 playing 片，A 胜/B 胜各一套，胜队在前），预演=落账；点胜方只是切换分支 */
const preview = computed(() => {
  if (winA.value === null) return [];
  const rows = courtRow.value?.eloPreview?.[winA.value ? "a" : "b"] ?? [];
  return rows.map((r) => ({
    name: r.name,
    guest: r.guest,
    up: r.delta > 0,
    d: r.delta,
  }));
});

function onConfirm(): void {
  const w = win.value;
  if (!w || winA.value === null) return;
  if (w.mode === "overwrite")
    void liveStore.overwriteSettle(w.courtId, winA.value, sa.value, sb.value);
  else
    void liveStore.uploadSettle(
      w.courtId,
      winA.value,
      sa.value,
      sb.value,
      w.noRedeal,
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
/* overwrite 模式的后果句（upload 无此行）：贴在标题下、胜方点选上 */
.md-mode-tip {
  text-align: center;
  font-size: 11px;
  color: var(--dim);
  margin: -6px 0 12px;
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
/* 分低方选不中（§4.6）：置灰不可点，预选高亮仍可见 */
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
/* 比分注 */
.md-tools {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
}
.edit {
  font-size: 11px;
  color: var(--dim);
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
</style>
