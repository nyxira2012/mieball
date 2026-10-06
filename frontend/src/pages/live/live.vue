<template>
  <!-- 打球页（2.1 改版 · 2.4 批2 多片并行）：一屏三块——顶条（LiveTopbar）/ 滚动对局区
       （CourtMatchCard 一片一卡，playing/idle 卡自判）/ 置底候场条（QueueBar）
       + 六抽屉一弹窗一浮层（本页本地弹层，liveSheet 单槽替换语义，不走全局 SheetPayload；
       confirm 槽=危险动作先确认，A3）。
       页面只做编排：卡片/抽屉的数据与动作全在 live store 与各组件内，这里接打开次序与跨页跳转。
       url query 的 id：onShow 时若现场未开则自动 startLive（深链/刷新兜底；hasLive 已开不重复，避免重置名册）。
       扫码签到深链（2.1·选项A）：二维码编码 {origin}/#/pages/live/live?id=<球局id>，
       uni-app H5 hash 路由原生承接；游客点「＋到场」先弹名片建号（SignupSheet），建号成功自动签到进候场区。 -->
  <PageShell bare tab="live">
    <!-- 加载骨架（A2 · 批2 遗留）：ensureLive 在途时几条灰条脉动不空白，hasLive 后整块让位 -->
    <template v-if="booting && !liveStore.hasLive">
      <view class="skel-wrap" aria-hidden="true">
        <view class="sk sk-t" />
        <view class="sk sk-card" />
        <view class="sk sk-card d1" />
        <view class="sk sk-bar" />
      </view>
    </template>

    <!-- 无 live 空态（alpha:1532-1535 逐字；bare 壳下自补边距） -->
    <template v-else-if="!liveStore.hasLive">
      <view class="empty-wrap">
        <view class="kicker kt30">Court</view>
        <view class="brand">现<text class="bem">场</text></view>
        <EmptyBox class="et20">
          <view>还没有进行中的球局</view>
          <AppButton
            variant="pri"
            size="sm"
            class="go-btn"
            @click="goOpenTonight"
            >去开今晚的局 ▸</AppButton
          >
        </EmptyBox>
      </view>
    </template>

    <template v-else-if="L">
      <view class="live-root">
        <LiveTopbar
          @qr="qrOpen = true"
          @rules="onRules"
          @ledger="onLedger"
          @end="onEnd"
        />

        <!-- 块二：滚动对局区（2.4 批2 起多片并行：一片一卡，playing/idle 由卡自判；
             记分/终局/取消 emit 带 courtId，页面直连 store 同签名动作） -->
        <view class="courts">
          <CourtMatchCard
            v-for="c in L.courts"
            :key="c.id"
            :court="c"
            :full="full"
            @point="liveStore.point"
            @undo="liveStore.undoPoint"
            @clear="onClearScore"
            @settle="liveStore.openSettle"
            @cancel="onCancelMatch"
            @sub="liveStore.subFirst"
            @autodeal="liveStore.autoDeal"
            @pull="goPull"
            @profile="openProfile"
          />
        </view>

        <QueueBar @queue="liveSheet = { k: 'queue' }" @checkin="onCheckin" />
      </view>

      <!-- 本地弹层：点人（含换人二段）/ 签到 / 队列 / 规则；开新的自动顶旧的（单槽） -->
      <PersonSheet
        :visible="personOpen"
        :person-id="personId"
        :swap="personSwap"
        @close="closeLocal"
        @profile="openProfile"
        @swap-mode="onSwapMode"
        @swap-target="onSwapTarget"
      />
      <CheckinSheet :visible="liveSheet?.k === 'checkin'" @close="closeLocal" />
      <QueueSheet
        :visible="liveSheet?.k === 'queue'"
        @close="closeLocal"
        @person="onQueuePerson"
      />
      <LedgerSheet :visible="liveSheet?.k === 'ledger'" @close="closeLocal" />
      <RulesSheet :visible="liveSheet?.k === 'rules'" @close="closeLocal" />
      <!-- 终局结算（store.settling 驱动，按片开窗）与签到二维码浮层：z-110，顶替退役 WinPopup 层级 -->
      <EndSettleModal
        :visible="!!liveStore.settling"
        :full="full"
        :court-id="liveStore.settling?.courtId ?? -1"
        @close="liveStore.closeSettle()"
        @cancel="onCancelMatch"
      />
      <!-- 危险动作先确认（A3）：后果句+双纽，本地确认槽不走全局 union；叠在结算窗之上 -->
      <AppSheet
        class="confirm-sheet"
        :visible="confirmOpen"
        @close="closeLocal"
      >
        <view v-if="liveSheet?.k === 'confirm'" class="cf">
          <view class="sheet-t">确定要这么做？</view>
          <view class="sheet-hint">{{ liveSheet.msg }}</view>
          <view class="cf-btns">
            <AppButton variant="ghost" class="flex1" @click="closeLocal"
              >再想想</AppButton
            >
            <AppButton variant="burn" class="flex1" @click="confirmGo"
              >确认</AppButton
            >
          </view>
        </view>
      </AppSheet>
      <QrOverlay :visible="qrOpen" @close="qrOpen = false" />
    </template>
  </PageShell>
</template>

<script setup lang="ts">
/* 打球页编排层（2.1 改版批2 重写）：数据与动作全在 live store / 组件内，页面只管
   卡片名映射、弹层次序（liveSheet 单槽）、跨页跳转（档案/拉人/深链）、撒花。 */
import { computed, ref, watch } from "vue";
import { onHide, onLoad, onShow } from "@dcloudio/uni-app";
import PageShell from "@/components/biz/PageShell.vue";
import AppButton from "@/components/ui/AppButton.vue";
import AppSheet from "@/components/ui/AppSheet.vue";
import EmptyBox from "@/components/ui/EmptyBox.vue";
import LiveTopbar from "@/components/biz/LiveTopbar.vue";
import CourtMatchCard from "@/components/biz/CourtMatchCard.vue";
import QueueBar from "@/components/biz/QueueBar.vue";
import PersonSheet from "@/components/biz/PersonSheet.vue";
import CheckinSheet from "@/components/biz/CheckinSheet.vue";
import QueueSheet from "@/components/biz/QueueSheet.vue";
import LedgerSheet from "@/components/biz/LedgerSheet.vue";
import RulesSheet from "@/components/biz/RulesSheet.vue";
import EndSettleModal from "@/components/biz/EndSettleModal.vue";
import QrOverlay from "@/components/biz/QrOverlay.vue";
import { useLiveStore } from "@/stores/live";
import { useGameStore } from "@/stores/game";
import { useSessionStore } from "@/stores/session";
import { useUiStore } from "@/stores/ui";
import { goMeet } from "@/utils/nav";

/** 本地弹层槽（单槽替换语义：开新的自动顶旧的；与全局 SheetPayload 互不相干）。
    confirm=危险动作确认（A3）：后果句 + 执行动作，确认后才跑 */
type LocalSheet =
  | { k: "person"; id: number; swap?: boolean }
  | { k: "checkin" }
  | { k: "queue" }
  | { k: "ledger" }
  | { k: "rules" }
  | { k: "confirm"; msg: string; action: () => void };

const liveStore = useLiveStore();
const gameStore = useGameStore();
const session = useSessionStore();
const ui = useUiStore();

const L = computed(() => liveStore.live);
/** 现场权限单一源在 store（组织者 ∨ 管理员，2.2 §4.7）：页面只消费，不再内联 isOrganizer */
const full = computed(() => liveStore.isFullPower);

const liveSheet = ref<LocalSheet | null>(null);
const qrOpen = ref(false);
/** A2 加载中：ensureLive 在途的骨架开关（进页先拉详情的窗口期；hasLive 即撤） */
const booting = ref(false);

const personOpen = computed(() => liveSheet.value?.k === "person");
const personId = computed(() =>
  liveSheet.value?.k === "person" ? liveSheet.value.id : 0,
);
const personSwap = computed(() =>
  liveSheet.value?.k === "person" ? !!liveSheet.value.swap : false,
);

function closeLocal(): void {
  liveSheet.value = null;
}
const confirmOpen = computed(() => liveSheet.value?.k === "confirm");

/** 危险动作先确认（A3）：先弹后果句，确认才执行——取消对局（卡上/结算窗两入口）与清零比分；
    动作本体与权限把关都在 store（needFull 兜底），这里只管「先确认」 */
function askConfirm(msg: string, action: () => void): void {
  liveSheet.value = { k: "confirm", msg, action };
}
/** 取消对局：卡上带 courtId；结算窗不带（从 settling 快照取） */
function onCancelMatch(courtId?: number): void {
  const id = courtId ?? liveStore.settling?.courtId;
  if (id == null) return;
  askConfirm("这场将不计分，场上的人回候场队最前面", () =>
    liveStore.cancelMatch(id),
  );
}
function onClearScore(courtId: number): void {
  askConfirm("比分将清零重开一盘，已得的分不算了", () =>
    liveStore.clearScore(courtId),
  );
}
function confirmGo(): void {
  if (liveSheet.value?.k !== "confirm") return;
  const { action } = liveSheet.value;
  liveSheet.value = null;
  action();
}
function onSwapMode(on: boolean): void {
  if (liveSheet.value?.k === "person")
    liveSheet.value = { ...liveSheet.value, swap: on };
}
/** 换人落子：swapPlayers 后关抽屉（toast 在 store） */
function onSwapTarget(t: number): void {
  if (liveSheet.value?.k === "person") {
    liveStore.swapPlayers(liveSheet.value.id, t);
    liveSheet.value = null;
  }
}
/** 队列抽屉点行 → 顶替为点人抽屉 */
function onQueuePerson(id: number): void {
  liveSheet.value = { k: "person", id };
}

/** 战力档案：先关本地抽屉再开全局 ProfileSheet（全局单例只留一个弹层） */
function openProfile(id: number): void {
  liveSheet.value = null;
  ui.openSheet({ type: "profile", userId: id });
}

/** ＋到场：游客先名片建号（选项A 扫码自签到链路保留）；抽屉是代办工具（§4.3 代办到场/带访客），
    非全权不开（A3 入口即拦，needFull 单一源）——球友自己报到走扫码 arriveMe */
function onCheckin(): void {
  const g = L.value?.g;
  if (!g) return;
  if (session.isGuest) {
    ui.signupThen({ pendingCheckin: { gameId: g.id } });
    return;
  }
  if (!liveStore.needFull()) return;
  liveSheet.value = { k: "checkin" };
}

/** 规则抽屉入口 gate（§4.7 收权：改分制/轮换模式是全权动作；needFull 单一源把关） */
function onRules(): void {
  if (!liveStore.needFull()) return;
  liveSheet.value = { k: "rules" };
}

/** 散场收局（§4.14）：按钮先过 endGate 两道闸（权限→在打防线，toast 在 gate 单点），
    过闸才弹后果确认「散场后二维码失效、不能再进」（A3），确认执行 endLive（store 内再兜底） */
function onEnd(): void {
  if (!liveStore.endGate()) return;
  askConfirm("散场后二维码失效、不能再进", () => liveStore.endLive());
}
/** 底账抽屉（§4.14 读数据无写动作）：入口纯权限闸（isFullPower 不含封存），散场前后都可查
    ——不走 needFull：其内联 sealGate 会把散场后的底账定格拦死（底账留给事后摊钱用） */
function onLedger(): void {
  if (!full.value) return;
  liveSheet.value = { k: "ledger" };
}

/** 空闲卡「去拉人」→ 约球页找球友 */
function goPull(): void {
  goMeet();
}

/** 撒花：落一场撒一波 56 粒（store 不管撒花的约定；初始/换局不触发） */
watch(
  () => L.value?.history.length,
  (n, o) => {
    if (n != null && o != null && n > o) ui.burst(56);
  },
);

/* ---------- 深链与生命周期 ---------- */
const liveId = ref<number | null>(null);
onLoad((options) => {
  const raw = (options as Record<string, string | undefined> | undefined)?.id;
  const n = raw != null ? Number(raw) : NaN;
  liveId.value = Number.isFinite(n) ? n : null;
  /* 1.5 灵活首页·状态分发（冷启动仅一次；switchTab 不重跑 onLoad，用户主动点现场键回来不受影响）：
     无深链 id、store 未在打、也无 live 局 → 现场对当下无意义，落约球页过渡
     （组织者视角/预约卡/形象页等后续档位实现后再扩这条分发链）。 */
  if (liveId.value == null && !liveStore.hasLive && !gameStore.liveGame) {
    goMeet();
  }
});
onShow(() => {
  if (liveStore.hasLive) return;
  /* 带 id 深链（扫码/detail 进现场）优先；入口页直进（#/ 无 query）时自动接上唯一
     进行中的局。冷启动无局已被 onLoad 分发去约球页，走到这说明是用户主动回现场键。
     A2 加载中：ensureLive 在途（拉详情等）骨架占位不空白，成败都收骨架 */
  const id = liveId.value ?? gameStore.liveGame?.id;
  if (id != null) {
    booting.value = true;
    liveStore.ensureLive(id).finally(() => {
      booting.value = false;
    });
  }
});
/** 页面隐藏（切 tab/进退页面）清本地弹层，避免残留到别的页 */
onHide(() => {
  liveSheet.value = null;
  qrOpen.value = false;
});

/** alpha:1534-1535 空态按钮 → 约球页找局/发局（mock 演示局已随隔离线退场，101 不再是落点） */
function goOpenTonight(): void {
  goMeet();
}
</script>

<style lang="scss" scoped>
/* 编排层布局：三块全屏（bare 壳 padding 归零，safe-area 由顶条/候场条各自处理）；
   底部让出公共导航高度（TabBar fixed 常驻后候场条落在 nav 之上） */
.live-root {
  height: calc(100vh - var(--nav-total-h));
  display: flex;
  flex-direction: column;
}
.courts {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0 16px;
}

/* 无 live 空态：自补壳层边距（同默认 .page 顶距口径）+ 原内联间距 */
.empty-wrap {
  padding: calc(env(safe-area-inset-top) + 14px) 18px;
}

/* 加载骨架（A2）：顶条/两卡/候场条的形状暗示，灰条脉动即可——不追形似 */
.skel-wrap {
  padding: calc(env(safe-area-inset-top) + 20px) 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.sk {
  border-radius: 12px;
  background: rgba(245, 241, 232, 0.06);
  animation: skpulse 1.2s ease-in-out infinite;
}
.sk-t {
  height: 96px;
}
.sk-card {
  height: 150px;
}
.sk-card.d1 {
  animation-delay: 0.15s;
}
.sk-bar {
  height: 54px;
  animation-delay: 0.3s;
}
@keyframes skpulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}

.kt30 {
  margin-top: 30px;
}
.et20 {
  margin-top: 20px;
}
.go-btn {
  margin-top: 20px;
}

/* 危险动作确认槽：叠在所有本地弹层之上（EndSettleModal z-110 也在其下；confetti 115 / toast 120 仍在上） */
.confirm-sheet :deep(.mask) {
  z-index: 111;
}
.confirm-sheet :deep(.sheet) {
  z-index: 112;
}
.cf-btns {
  display: flex;
  gap: 10px;
}
.flex1 {
  flex: 1;
}
</style>
