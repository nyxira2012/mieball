<template>
  <!-- 教学态宿主（2.7 批3）：布局复刻真局在打的结构——横幅（常驻）+ 沙盒顶条 +
       滚动对局区 + 候场条 + 教学底盘 + 弹层（抽屉族 + 结算窗 + 二维码示意）。
       顶条沙盒版做在本文件（沙盒只需 LiveTopbar 的一个切面：kicker/局名/组织者 chip/
       定格遥测/跑马灯/二维码钮/散场钮——真局组件零改动，这里照长相复刻）。
       防误认（规格 §6）：局名场馆带「示例」、剩余时间定格不走表、不出真码 -->
  <view v-if="s" class="sb-stage">
    <view class="sb-bannerrow"><SandboxBanner /></view>

    <!-- 顶条（沙盒版） -->
    <view class="sb-top">
      <view class="sb-btop">
        <view class="sb-bmeta">
          <view class="sb-kicker">
            <view class="sb-dot" /> LIVE · 第 {{ round }} 轮
          </view>
          <view class="sb-brand">{{ SANDBOX_GAME.name }}</view>
          <view class="sb-bloc">
            <text class="sb-loctxt">{{ SANDBOX_GAME.venueName }}</text>
            <!-- 组织者位（§8 顶条裁决）：参与卡「组织者 · 阿豪」、组织卡「组织者 · 你」
                 ——organizerId 单一源在 engine，同一式两卡都对 -->
            <text class="sb-chip ok">组织者 · {{ orgName }}</text>
          </view>
        </view>
        <view class="sb-tacts">
          <!-- 二维码钮照常在（点了示意浮层，§4.4：不出真码）；参与卡「亮码收人」步
               （v2.8）光圈指这颗钮；散场钮组织卡常显（你是组织者，canEnd 真局同位；
               参与卡不渲染）——进清扫流（第十步，锚 sweep-entry） -->
          <view
            class="sb-qrbtn"
            :class="{ 'sb-glow': sandbox.spot === 'qr-btn' }"
            @click="onQr"
          >
            <view class="sb-qric">
              <view class="sb-qrbox tl" /><view class="sb-qrbox tr" /><view
                class="sb-qrbox bl"
              />
              <view class="sb-qrdot d1" /><view class="sb-qrdot d2" /><view
                class="sb-qrdot d3"
              />
            </view>
          </view>
          <view
            v-if="sandbox.isFull"
            class="sb-mini"
            :class="{
              danger: !s.ended,
              'sb-glow': sandbox.spot === 'sweep-entry',
            }"
            @click="sandbox.openSweep()"
            >散场</view
          >
        </view>
      </view>

      <!-- 遥测三格：剩余时间定格假数（A4）；场地格组织卡直填（第八步「填 2」——
           本地解析 1~9，加片出口自动补片）、参与卡只读；赛制模式格两卡都可点开
           规则抽屉（参与卡抽屉内只读，验收「轮换可预期」要看它） -->
      <view class="sb-tele">
        <view class="sb-tcell">
          <text class="sb-tk">剩余时间</text>
          <text class="sb-timer">{{ TIME_LEFT_FROZEN }}</text>
        </view>
        <view
          class="sb-tcell"
          :class="{ 'sb-glow': sandbox.spot === 'courts-cell' }"
        >
          <text class="sb-tk">打球场地</text>
          <view class="sb-tv">
            <input
              v-if="sandbox.isFull"
              class="sb-cinp"
              :value="courtsText"
              type="number"
              @input="onCourtsInput"
              @blur="commitCourts"
              @confirm="commitCourts"
            />
            <text v-else class="sb-cro">{{ s.courtsCount }}</text>
            <text class="sb-tunit">片</text>
          </view>
        </view>
        <view
          class="sb-tcell sb-modecell"
          :class="{ 'sb-glow': sandbox.spot === 'rules-entry' }"
          @click="sandbox.openRules()"
        >
          <text class="sb-tk">赛制模式</text>
          <view class="sb-modev"
            >双打 · {{ DOWN_NAMES[SANDBOX_GAME.down] }} ▾</view
          >
        </view>
      </view>

      <!-- 单行轮播（3.2s 换条）：吃 engine feed（开赛句/比分句都由动作落 feed）+ 候场状 -->
      <view v-if="curTick" class="sb-ticker">▸ {{ curTick }}</view>
    </view>

    <!-- 滚动对局区：一片一卡（playing/idle 由卡自判）；full 随卡走——组织卡全权
         （⚡ 亮、工具行「本场完成」），参与卡=普通球员 -->
    <view class="sb-courts">
      <SandboxCourtCard
        v-for="c in s.courts"
        :key="c.no"
        :court="c"
        :full="sandbox.isFull"
        @point="sandbox.point"
        @undo="sandbox.undoPoint"
        @clear="onClear"
        @settle="sandbox.openSettle"
        @autodeal="sandbox.autoDeal"
        @pull="goMeet"
        @person="sandbox.openPerson"
      />
    </view>

    <SandboxQueueBar
      @arrive="sandbox.checkInMe()"
      @checkin="sandbox.tapCheckin()"
      @person="sandbox.openPerson"
    />
    <TutorBar />

    <!-- 弹层：抽屉族（点人/签到代办/规则/散场——开关单槽在 store）+ 结算窗
         （store.settleWindow 自驱，z-110 盖过抽屉）+ 二维码示意浮层（demo 不出真码） -->
    <SandboxSheets />
    <SandboxSettle />
    <QrOverlay
      :visible="qrOpen"
      demo
      :demo-name="SANDBOX_GAME.name"
      :demo-venue="SANDBOX_GAME.venueName"
      :demo-arrived="arrivedCount"
      :demo-note="QR_DEMO_NOTE"
      @close="qrOpen = false"
    />
  </view>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";
import SandboxBanner from "@/components/sandbox/SandboxBanner.vue";
import SandboxCourtCard from "@/components/sandbox/SandboxCourtCard.vue";
import SandboxQueueBar from "@/components/sandbox/SandboxQueueBar.vue";
import SandboxSettle from "@/components/sandbox/SandboxSettle.vue";
import SandboxSheets from "@/components/sandbox/SandboxSheets.vue";
import TutorBar from "@/components/sandbox/TutorBar.vue";
import QrOverlay from "@/components/biz/QrOverlay.vue";
import { useSandboxStore } from "@/stores/sandbox";
import { useUiStore } from "@/stores/ui";
import { goMeet } from "@/utils/nav";
import { DOWN_NAMES } from "@/utils/format";
import { arrived } from "@/sandbox/engine";
import { QR_DEMO_NOTE, SANDBOX_GAME, TIME_LEFT_FROZEN } from "@/sandbox/data";

const sandbox = useSandboxStore();
const ui = useUiStore();
const s = computed(() => sandbox.state);
const qrOpen = ref(false);

/** 第 N 轮：全场场数=战报长度（batch1 定形），开打前即第 1 轮（真局 round+1 同口径） */
const round = computed(() => s.value!.matches.length + 1);
const orgName = computed(
  () => s.value!.players.find((p) => p.id === s.value!.organizerId)!.name,
);
/** 示意浮层人数 = engine 在场数（真局读 roster 的同位） */
const arrivedCount = computed(() => s.value!.players.filter(arrived).length);

/** 长按清零（本地记分，零弹窗打扰 + 轻提示——真局 onClearScore 同编排） */
function onClear(courtNo: number): void {
  sandbox.clearScore(courtNo);
  ui.toast("比分已清零");
}

/** 二维码示意浮层：开浮层 + 给「亮码收人」步报点开事件（判据只认这一下） */
function onQr(): void {
  qrOpen.value = true;
  sandbox.qrShown();
}

/* ---------- 顶条场地格直填（组织卡第八步）：本地态随 store 片数走，提交成败
   由 store.courtsInput 回传决定回退（真局 LiveTopbar commitCourts 同式） ---------- */
const courtsText = ref("1");
watch(
  () => s.value?.courtsCount,
  (n) => {
    if (n != null) courtsText.value = String(n);
  },
);
function onCourtsInput(ev: Event): void {
  const detail = (ev as { detail?: { value?: unknown } }).detail;
  if (detail && typeof detail.value === "string")
    courtsText.value = detail.value;
}
function commitCourts(): void {
  if (!s.value) return;
  if (!sandbox.courtsInput(courtsText.value))
    courtsText.value = String(s.value.courtsCount); // 校验不过回退 store 值
}

/* 单行轮播：feed 句（新到旧）→ 下一场已排 → 候场人数，3.2s 换条（真局同节奏） */
const tickItems = computed<string[]>(() => {
  const st = s.value;
  if (!st) return [];
  const out = [...st.feed];
  if (st.queue.length) {
    const names = st.queue
      .slice(0, 4)
      .map((id) => st.players.find((p) => p.id === id)!.name)
      .join(" / ");
    out.push(`下一场已排：${names}`);
  }
  out.push(`候场 ${st.queue.length} 人`);
  return out;
});
const tickIdx = ref(0);
let tickTimer: ReturnType<typeof setInterval> | null = null;
tickTimer = setInterval(() => {
  tickIdx.value++;
}, 3200);
onUnmounted(() => {
  if (tickTimer) clearInterval(tickTimer);
});
const curTick = computed(
  () => tickItems.value[tickIdx.value % tickItems.value.length],
);
</script>

<style lang="scss" scoped>
/* 全屏骨架与真局 live-root 同构（bare 壳下三段：顶条/滚动区/置底条）；
   底部让出公共导航高度（dvh 跟随可视区，与 fixed 导航同一参照系） */
.sb-stage {
  height: calc(100vh - var(--nav-total-h));
  height: calc(100dvh - var(--nav-total-h));
  display: flex;
  flex-direction: column;
}
.sb-bannerrow {
  flex: none;
  padding: calc(env(safe-area-inset-top) + 10px) 14px 0;
}

/* ---------- 顶条（沙盒版 LiveTopbar 切面） ---------- */
.sb-top {
  flex: none;
  background: rgba(14, 14, 18, 0.92);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--line);
  z-index: 5;
}
.sb-btop {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 12px 14px 0;
  gap: 10px;
}
.sb-bmeta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.sb-kicker {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.3em;
  text-transform: uppercase;
  color: var(--lemon);
}
.sb-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--coral);
  flex: none;
  box-shadow: 0 0 0 0 rgba(255, 90, 54, 0.6);
  animation: sbPulse 1.6s infinite;
}
@keyframes sbPulse {
  70% {
    box-shadow: 0 0 0 9px rgba(255, 90, 54, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(255, 90, 54, 0);
  }
}
.sb-brand {
  font-family: var(--disp);
  font-size: 26px;
  font-weight: 400;
  line-height: 1.05;
  margin: 4px 0 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sb-bloc {
  font-size: 12px;
  color: var(--dim);
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.sb-loctxt {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sb-chip {
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 400;
  letter-spacing: 0.08em;
  padding: 2px 8px;
  border-radius: 99px;
  border: 1px solid rgba(245, 241, 232, 0.16);
  background: none;
  flex: none;
}
.sb-chip.ok {
  border-color: rgba(255, 212, 0, 0.5);
  color: var(--lemon);
}
.sb-tacts {
  flex: none;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 6px;
}
/* 二维码钮（3 角框 + 3 粒点，真局 qrbtn 同款）下叠底账/散场小钮（真局 mini-act 同款） */
.sb-mini {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.2em;
  color: var(--dim);
  border: 1px solid rgba(245, 241, 232, 0.16);
  border-radius: 9px;
  padding: 4px 8px;
  text-align: center;
  cursor: pointer;
  transition: 0.15s;
}
.sb-mini:active {
  transform: scale(0.94);
}
/* 散场=危险动作位：珊瑚色示警（确认流在抽屉内，A3） */
.sb-mini.danger {
  color: var(--coral);
  border-color: rgba(255, 90, 54, 0.4);
  background: rgba(255, 90, 54, 0.08);
}
.sb-qrbtn {
  flex: none;
  width: 34px;
  height: 34px;
  border-radius: 11px;
  cursor: pointer;
  border: 1px solid rgba(255, 212, 0, 0.35);
  background: rgba(255, 212, 0, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: 0.15s;
}
.sb-qrbtn:active {
  transform: scale(0.92);
}
.sb-qric {
  position: relative;
  width: 17px;
  height: 17px;
}
.sb-qrbox {
  position: absolute;
  width: 6px;
  height: 6px;
  border: 1.5px solid var(--lemon);
  border-radius: 1px;
}
.sb-qrbox.tl {
  top: 0;
  left: 0;
}
.sb-qrbox.tr {
  top: 0;
  right: 0;
}
.sb-qrbox.bl {
  bottom: 0;
  left: 0;
}
.sb-qrdot {
  position: absolute;
  width: 2.5px;
  height: 2.5px;
  background: var(--lemon);
}
.sb-qrdot.d1 {
  top: 8px;
  left: 8px;
}
.sb-qrdot.d2 {
  top: 11px;
  left: 11px;
}
.sb-qrdot.d3 {
  top: 13.5px;
  left: 13.5px;
}

/* 遥测三格 */
.sb-tele {
  display: grid;
  grid-template-columns: 1.1fr 1fr 1.1fr;
  gap: 8px;
  margin: 12px 14px 0;
}
.sb-tcell {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(245, 241, 232, 0.08);
  border-radius: 12px;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 2px;
  transition: 0.15s;
}
/* 赛制模式格=规则抽屉入口（真局 mode-cell 同位可点） */
.sb-modecell {
  cursor: pointer;
}
.sb-modecell:active {
  transform: scale(0.97);
  border-color: var(--lemon);
}
.sb-tk {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
  letter-spacing: 0.15em;
  text-transform: uppercase;
}
.sb-tv {
  font-family: var(--disp);
  font-size: 16px;
  color: var(--lemon);
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
}
.sb-timer {
  font-family: var(--mono);
  font-weight: 700;
  color: var(--coral);
  letter-spacing: 0.05em;
  font-size: 14px;
}
/* 场地格直填（组织卡；真局 .courts-inp 同款：虚线下划线）；参与卡只读文本同位 */
.sb-cinp {
  width: 40px;
  background: none;
  border: none;
  outline: none;
  border-bottom: 1px dashed rgba(255, 212, 0, 0.35);
  color: var(--lemon);
  font-family: var(--mono);
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 0.05em;
  padding: 0 2px 1px;
  height: 20px;
}
.sb-cinp:focus {
  border-bottom-color: var(--lemon);
  border-bottom-style: solid;
}
.sb-cro {
  font-family: var(--mono);
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 0.05em;
}
.sb-tunit {
  font-size: 10px;
  color: var(--dim);
}
.sb-modev {
  font-family: var(--sans);
  font-size: 13px;
  font-weight: 700;
  color: var(--lemon);
  margin-top: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 单行轮播（border-top 收口顶条） */
.sb-ticker {
  padding: 10px 14px;
  margin-top: 12px;
  border-top: 1px solid var(--line);
  font-size: 10px;
  color: var(--dim);
  white-space: nowrap;
  overflow: hidden;
}

/* 滚动对局区 */
.sb-courts {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0 16px;
}
</style>
