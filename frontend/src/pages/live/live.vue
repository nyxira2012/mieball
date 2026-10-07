<template>
  <!-- 打球页（2.1 改版 · 2.4 批2 多片并行 · 2.3 批6 散场清扫+回看）：一屏三块——顶条
       （LiveTopbar）/ 滚动对局区（CourtMatchCard 一片一卡，playing/idle 卡自判）/
       置底候场条（QueueBar）+ 抽屉弹窗浮层（本页本地弹层，liveSheet 单槽替换语义，
       不走全局 SheetPayload；confirm 槽=危险动作先确认，A3；SweepSheet=散场残局清单）。
       页面只做编排：卡片/抽屉的数据与动作全在 live store 与各组件内，这里接打开次序与跨页跳转。
       回看态（recap 非空）：LiveRecap 替代现场编排——散场后扫码/从我的局点进只读翻旧账（§4.10）。
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

    <!-- 只读回看（2.3 §4.10，批6）：散场后扫码/从我的局点进=回看态——LiveRecap 替代
         现场编排（零写按钮；写动作 sealGate 拒收兜底）。recap 由 ensureLive endedAt
         分流与 endGame 响应两路落地（散场即回看） -->
    <template v-else-if="liveStore.recap">
      <LiveRecap :view="liveStore.recap" />
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
      <!-- 确认窗（store.settling 驱动、按片渲染：一次一扇=片号最小，确认/关窗后下一片
           顶上，多片互不等待 §4.3）；清扫态由 sweepTarget 定位——残局清单点哪片开哪片
           （压过「片号最小」的兜底）。清零/取消入口在窗内 emit，走下方危险确认槽。
           与签到二维码浮层：z-110，顶替退役 WinPopup 层级 -->
      <EndSettleModal
        :visible="(sweepTarget ?? liveStore.settlingCourtId) != null"
        :court-id="sweepTarget ?? liveStore.settlingCourtId ?? -1"
        @clear="onClearScore()"
        @cancel="onCancelMatch()"
      />
      <!-- 散场残局清单（§4.9 清扫流，批6）：startSweep 开、全清后「确认散场」二次确认
           放行；行内三选一只 emit、编排与危险确认在页面。z 序沿 AppSheet（90），
           确认窗盖在它上面开同一扇窗 -->
      <SweepSheet
        :visible="liveStore.sweepState"
        @close="closeSweep"
        @confirm="onSweepConfirm"
        @early="onSweepEarly"
        @cancel="onCancelMatch"
        @cancel-all="onSweepCancelAll"
        @end="onSweepEnd"
      />
      <!-- 危险动作先确认（A3）：后果句+双纽，本地确认槽不走全局 union；叠在结算窗之上。
           内容壳类名勿用 .cf——那是全局 animations.scss 的撒花粒子类（absolute 9px 见方 +
           pointer-events:none），撞上即面板塌成 9px 宽、按钮全不可点（批6 走查 P1 根因） -->
      <AppSheet
        class="confirm-sheet"
        :visible="confirmOpen"
        @close="closeLocal"
      >
        <view v-if="liveSheet?.k === 'confirm'" class="cfm">
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
import { computed, ref, watch, watchEffect } from "vue";
import { onHide, onLoad, onShow, onUnload } from "@dcloudio/uni-app";
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
import SweepSheet from "@/components/biz/SweepSheet.vue";
import LiveRecap from "@/components/biz/LiveRecap.vue";
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
/** 取消对局（§4.7）：卡上带 courtId；确认窗/残局清单入口不带（窗从当前渲染片取）。
    动作本体与权限把关都在 store（needFull 兜底），这里只管「先确认」；
    清扫态（sweepState）透传 noRedeal——作废照常、不重发牌（§4.9） */
function onCancelMatch(courtId?: number): void {
  const id = courtId ?? liveStore.settlingCourtId;
  if (id == null) return;
  askConfirm("这场将不计分，场上的人回候场队最前面", () =>
    liveStore.cancelMatch(id, liveStore.sweepState),
  );
}
/** 清零重开（§4.2）：卡上带 courtId；确认窗入口不带（从当前渲染窗的片取） */
function onClearScore(courtId?: number): void {
  const id = courtId ?? liveStore.settlingCourtId;
  if (id == null) return;
  askConfirm("比分将清零重开一盘，已得的分不算了", () =>
    liveStore.clearScore(id),
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

/** 规则抽屉入口（2.4 §4.1 推翻 2.2 批1 入口拦截）：球友照开、抽屉内只读化
    （RulesSheet full=false 罩层）；改规则动作的 store guard 仍在——双保险 */
function onRules(): void {
  liveSheet.value = { k: "rules" };
}

/** 散场入口（§4.9 清扫流，批6 切真）：点「散场」进清扫态——残局清单逐片强制处理，
    全清后「确认散场」二次确认放行（无残局直接二次确认）。权限/残局判定都在
    store.startSweep 单点（canEndLive：组织者或组织者早退时的管理员代收） */
function onEnd(): void {
  void liveStore.startSweep();
}

/* ---------- 清扫流编排（§4.9） ---------- */
/** 残局清单点开的确认窗定位：清单点哪片开哪片（压过 settlingCourtId「片号最小」的
     兜底；片退出 pending 即清——窗位回到视图驱动） */
const sweepTarget = ref<number | null>(null);
watchEffect(() => {
  if (sweepTarget.value != null && !liveStore.isPending(sweepTarget.value))
    sweepTarget.value = null;
});
/** 清单「确认比分」（pending 片）：窗本来就开着（settling 随视图），定位到这片即可 */
function onSweepConfirm(courtId: number): void {
  sweepTarget.value = courtId;
}
/** 清单「提前结束」（playing 片）：先 settle-open 转待确认，响应视图落地后开同一扇窗 */
async function onSweepEarly(courtId: number): Promise<void> {
  await liveStore.openSettle(courtId);
  if (liveStore.isPending(courtId)) sweepTarget.value = courtId;
}
/** 一键全取消（§4.9）：后果确认后 sweepCancelAll（逐片 cancel 语义一个事务在后端） */
function onSweepCancelAll(): void {
  askConfirm("未完对局将全部作废不计分，场上的人回候场队最前面", () =>
    liveStore.sweepCancelAll(),
  );
}
/** 确认散场（§4.9 放行后的二次确认）：后果句点明不可撤销，确认执行 endGame */
function onSweepEnd(): void {
  askConfirm("球局将收工封存，此操作不可撤销", () => liveStore.endGame());
}
/** 关清扫清单：连定位窗一起收（sweepState 是 store 开关，页面编排翻转） */
function closeSweep(): void {
  liveStore.sweepState = false;
  sweepTarget.value = null;
}

/** 远程散场预约落地（meet 页「我的局」入口落 sweepOnArrive）：进对局现场后自动开
     清扫流——远程散场与现场散场同一条链；对不上局/已散场就静默丢弃 */
function maybeRemoteSweep(): void {
  const target = liveStore.sweepOnArrive;
  if (target == null) return;
  liveStore.sweepOnArrive = null;
  if (liveStore.live?.g.id === target && !liveStore.live.endedAt)
    void liveStore.startSweep();
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
  if (liveStore.hasLive) {
    liveStore.startPolling(liveStore.live!.g.id); // 回前台续轮询（onHide 停的；同局幂等不重开）
    maybeRemoteSweep(); // 远程散场预约：局已在现场时直接开清扫
    return;
  }
  /* 带 id 深链（扫码/detail 进现场）优先；入口页直进（#/ 无 query）时自动接上唯一
     进行中的局。冷启动无局已被 onLoad 分发去约球页，走到这说明是用户主动回现场键。
     A2 加载中：ensureLive 在途（拉详情等）骨架占位不空白，成败都收骨架 */
  const id = liveId.value ?? gameStore.liveGame?.id;
  if (id != null) {
    booting.value = true;
    liveStore.ensureLive(id).finally(() => {
      booting.value = false;
      maybeRemoteSweep(); // 开账/拉读落地后再开清扫（预约位已在对的局上）
    });
  }
});
/** 页面隐藏（切 tab/进退页面）清本地弹层，避免残留到别的页；轮询随之停（§4.8 对表只在看现场时发生） */
onHide(() => {
  liveSheet.value = null;
  qrOpen.value = false;
  liveStore.stopPolling();
});
onUnload(() => liveStore.stopPolling());

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
