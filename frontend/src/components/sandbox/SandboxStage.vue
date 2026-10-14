<template>
  <!-- 教学态宿主（2.7 批3）：布局复刻真局在打的结构——横幅（常驻）+ 沙盒顶条 +
       滚动对局区 + 候场条 + 教学底盘 + 弹层（结算窗 + 二维码示意；抽屉族批4）。
       顶条沙盒版做在本文件（沙盒只需 LiveTopbar 的一个切面：kicker/局名/组织者 chip/
       定格遥测/跑马灯/二维码钮——真局组件零改动，这里照长相复刻）。
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
          <!-- 二维码钮照常在（点了示意浮层，§4.4：不出真码） -->
          <view class="sb-qrbtn" @click="qrOpen = true">
            <view class="sb-qric">
              <view class="sb-qrbox tl" /><view class="sb-qrbox tr" /><view
                class="sb-qrbox bl"
              />
              <view class="sb-qrdot d1" /><view class="sb-qrdot d2" /><view
                class="sb-qrdot d3"
              />
            </view>
          </view>
        </view>
      </view>

      <!-- 遥测三格：剩余时间定格假数（A4）；场地格只读（组织卡直填批4）；
           赛制模式格本批渲染不可点（参与卡规则抽屉批4，点了无反应即如实） -->
      <view class="sb-tele">
        <view class="sb-tcell">
          <text class="sb-tk">剩余时间</text>
          <text class="sb-timer">{{ TIME_LEFT_FROZEN }}</text>
        </view>
        <view class="sb-tcell">
          <text class="sb-tk">打球场地</text>
          <view class="sb-tv">
            <text class="sb-cn">{{ s.courtsCount }}</text>
            <text class="sb-tunit">片</text>
          </view>
        </view>
        <view class="sb-tcell">
          <text class="sb-tk">赛制模式</text>
          <view class="sb-modev"
            >双打 · {{ DOWN_NAMES[SANDBOX_GAME.down] }} ▾</view
          >
        </view>
      </view>

      <!-- 单行轮播（3.2s 换条）：吃 engine feed（开赛句/比分句都由动作落 feed）+ 候场状 -->
      <view v-if="curTick" class="sb-ticker">▸ {{ curTick }}</view>
    </view>

    <!-- 滚动对局区：一片一卡（playing/idle 由卡自判） -->
    <view class="sb-courts">
      <SandboxCourtCard
        v-for="c in s.courts"
        :key="c.no"
        :court="c"
        @point="sandbox.point"
        @undo="sandbox.undoPoint"
        @clear="onClear"
        @pull="goMeet"
      />
    </view>

    <SandboxQueueBar @arrive="sandbox.checkInMe()" @checkin="onCheckin" />
    <TutorBar />

    <!-- 弹层：结算窗（store.settleWindow 单一源自驱）+ 二维码示意浮层（demo 不出真码）；
         点人抽屉批4（卡上 person emit 暂不接——教学不干预，点了没反应就是如实） -->
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
import { computed, onUnmounted, ref } from "vue";
import SandboxBanner from "@/components/sandbox/SandboxBanner.vue";
import SandboxCourtCard from "@/components/sandbox/SandboxCourtCard.vue";
import SandboxQueueBar from "@/components/sandbox/SandboxQueueBar.vue";
import SandboxSettle from "@/components/sandbox/SandboxSettle.vue";
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
/** ＋到场：代办工具，身份随卡走（§4.4）——参与卡普通球员如实拦下（唯一的干预种）；
     组织卡全权亮钮等代办抽屉，批4 接 */
function onCheckin(): void {
  if (sandbox.mode !== "participate") return;
  ui.toast("请找组织者或管理员");
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
/* 二维码钮（3 角框 + 3 粒点，真局 qrbtn 同款） */
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
.sb-cn {
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
