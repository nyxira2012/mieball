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

    <!-- 死链态（2.6 §4.6）：带 id 进入但局拉不到（真没有/已撤销/断网）——页面级
         一句+出口替代「toast+白骨架」；「找不到…已撤销」为链接死局专用句，不说「已
         结束」（散场局 apiLiveView 照回 200 回看视图，吃不到这句） -->
    <template v-else-if="deadGame">
      <view class="empty-wrap">
        <view class="kicker kt30">Court</view>
        <view class="brand">现<text class="bem">场</text></view>
        <EmptyBox class="et20">
          <view>{{ DEAD_LINK_MSG }}</view>
          <view class="dl-btns">
            <AppButton
              variant="ghost"
              size="sm"
              class="flex1"
              @click="retryDead"
              >重试</AppButton
            >
            <AppButton variant="pri" size="sm" class="flex1" @click="goMeet"
              >去约球看看</AppButton
            >
          </view>
        </EmptyBox>
      </view>
    </template>

    <!-- 只读回看（2.3 §4.10，批6）：散场后扫码/从我的局点进=回看态——LiveRecap 替代
         现场编排（零写按钮；写动作 sealGate 拒收兜底）。recap 由 ensureLive endedAt
         分流与 endGame 响应两路落地（散场即回看）。2.6 门牌：完成=收摊编排、
         分享=shareLink、来约场球吧=goMeet——编排全在页面（组件只 emit） -->
    <template v-else-if="liveStore.recap">
      <LiveRecap
        :view="liveStore.recap"
        @complete="onRecapComplete"
        @share="onRecapShare"
        @meet="goMeet"
      />
    </template>

    <!-- 教学态（2.7 批2 骨架）：sandbox store 全屏接管（分支在真局之前——自动态永不
         截胡，§4.7；onLoad 冷启动分发与 onShow 接局照旧，这里只拦渲染）。批3 换
         SandboxStage；本批先保 exit 通路（切 tab 散场在 onHide，这里先给小字钮） -->
    <template v-else-if="sandbox.mode !== 'pick'">
      <view class="sb-root">
        <SandboxBanner />
        <view class="sb-hold">教学中…</view>
        <view class="sb-exit" @click="sandbox.exit()">退出教学</view>
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
            @settle="onSettle"
            @cancel="onCancelMatch"
            @redeal="onRedealCourt"
            @autodeal="liveStore.autoDeal"
            @pull="goPull"
            @person="onPerson"
          />
        </view>

        <QueueBar
          @queue="liveSheet = { k: 'queue' }"
          @checkin="onCheckin"
          @arrive="onArriveMe"
        />
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
        @person="onPerson"
      />
      <LedgerSheet :visible="liveSheet?.k === 'ledger'" @close="closeLocal" />
      <RulesSheet :visible="liveSheet?.k === 'rules'" @close="closeLocal" />
      <!-- 本地结算窗（2.3 记分本地化）：开关/片/模式单一源在 store.settleWindow——
           自动到分与手动入口（场卡「本场完成」/残局清单「上传比分」）开的是同一扇，
           组件直读 store 自驱，页面零透传零监听 -->
      <EndSettleModal />
      <!-- 散场残局清单（§4.9 清扫流，批6）：startSweep 开、全清后「确认散场」二次确认
           放行；「上传比分」组件直开结算窗（noRedeal），cancel/cancelAll/end 的编排
           与危险确认在页面。z 序沿 AppSheet（90），结算窗（z-110）盖在它上面 -->
      <SweepSheet
        :visible="liveStore.sweepState"
        @close="closeSweep"
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

    <!-- 无局空态=选卡屏（2.7 §4.1）：两张体验卡+随便逛逛+常驻横幅接替 2.1 的
         「还没有进行中的球局」一句话空态（2.1 文档已挂指针空态由 2.7 接替） -->
    <template v-else>
      <SandboxPicker />
    </template>
  </PageShell>
</template>

<script setup lang="ts">
/* 打球页编排层（2.1 改版批2 重写）：数据与动作全在 live store / 组件内，页面只管
   卡片名映射、弹层次序（liveSheet 单槽）、跨页跳转（档案/拉人/深链）、撒花。 */
import { computed, ref, watch } from "vue";
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
import SandboxPicker from "@/components/sandbox/SandboxPicker.vue";
import SandboxBanner from "@/components/sandbox/SandboxBanner.vue";
import { useLiveStore } from "@/stores/live";
import { useGameStore } from "@/stores/game";
import { useSessionStore } from "@/stores/session";
import { useUiStore } from "@/stores/ui";
import { useSandboxStore } from "@/stores/sandbox";
import { goMeet } from "@/utils/nav";
import { shareLink } from "@/utils/share";
import { gameShareUrl } from "@/utils/deeplink";
import { DEAD_LINK_MSG } from "@/utils/recap";

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
/** 教学沙盒（2.7）：模式路由的渲染分支与 onHide 散场在这，编排全在 sandbox store */
const sandbox = useSandboxStore();

const L = computed(() => liveStore.live);
/** 现场权限单一源在 store（组织者 ∨ 管理员，2.2 §4.7）：页面只消费，不再内联 isOrganizer */
const full = computed(() => liveStore.isFullPower);

const liveSheet = ref<LocalSheet | null>(null);
const qrOpen = ref(false);
/** A2 加载中：ensureLive 在途的骨架开关（进页先拉详情的窗口期；hasLive 即撤） */
const booting = ref(false);
/** 死链态（2.6 §4.6）：只对带 id 进入生效——ensureLive 判负（真没有/已撤销/断网）
    时亮，替代旧的「toast 后停骨架」；断网同页可重试，重试与去约球都是出口 */
const deadGame = ref(false);
const deadId = ref<number | null>(null);

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
/** 取消对局（§4.7）：卡上/残局清单入口都带 courtId。动作本体与权限把关都在
    store（needFull 兜底），这里只管「先确认」；
    清扫态（sweepState）透传 noRedeal——作废照常、不重发牌（§4.9） */
function onCancelMatch(courtId: number): void {
  askConfirm("这场将不计分，场上的人回候场队最前面", () =>
    liveStore.cancelMatch(courtId, liveStore.sweepState),
  );
}
/** 重排这片（2.8 §4.4，全权）：责任模型=按下的人担保「这场还没人开始记分」
    （比分在各手机本地，服务器判不了）——确认句先落这句话再执行；清扫态闸与
    动作本体都在 store（sweepState 前闸），这里只管「先确认」 */
function onRedealCourt(courtId: number): void {
  askConfirm(
    "重排会推翻当前这场——确认还没人开始记分，场上的人回队首立刻重排",
    () => liveStore.redealCourt(courtId),
  );
}
/** 长按清零重开（本地记分）：长按撤回即归零重开，零弹窗打扰，轻量 toast 反馈 */
function onClearScore(courtId: number): void {
  liveStore.clearScore(courtId);
  ui.toast("比分已清零");
}
/** 本场完成（记分本地化；术语「结束对局」指同一动作）：卡上入口=手动开本地上传窗
    ——与自动到分同一扇窗（一次一扇的闸在 store），先传先落 */
function onSettle(courtId: number): void {
  liveStore.openSettleWindow(courtId, "upload");
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
/** 点人（候场队列点行 / 场上点头像）→ 顶替为点人抽屉：设/撤管理员对场上人
     也可达（2026-10-10 修复批 F5），档案卡从抽屉内链接进 */
function onPerson(id: number): void {
  liveSheet.value = { k: "person", id };
}

/** 战力档案：先关本地抽屉再开全局 ProfileSheet（全局单例只留一个弹层） */
function openProfile(id: number): void {
  liveSheet.value = null;
  ui.openSheet({ type: "profile", userId: id });
}

/** 签到族共门（＋到场/我到了同闸）：取当前局；游客先名片建号（选项A 扫码自签到
    链路保留，建号成功自动签到），登录后返回局 id 放行 */
function guestGate(): { gameId: number } | null {
  const g = L.value?.g;
  if (!g) return null;
  if (session.isGuest) {
    ui.signupThen({ pendingCheckin: { gameId: g.id } });
    return null;
  }
  return { gameId: g.id };
}

/** ＋到场：抽屉是代办工具（§4.3 代办到场/带访客），非全权不开（A3 入口即拦，
    needFull 单一源）——球友自己报到走「我到了」钮或扫码 arriveMe */
function onCheckin(): void {
  const t = guestGate();
  if (!t || !liveStore.needFull()) return;
  liveSheet.value = { k: "checkin" };
}

/** 我到了（A1 自己那行的醒目签到键；§5-2 断裂修复）：显式点一下才算签（§4.2 深链不自动签）。
    已登录成员直走 arriveMe——未入册空降建行、在册未到 setCheck 自报、已到场吃
    「你已经在场了」句，全在链内 */
function onArriveMe(): void {
  const t = guestGate();
  if (!t) return;
  void liveStore.arriveMe(t.gameId);
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
/** 关清扫清单（残局清单点「上传比分」开的结算窗由 store.settleWindow 自管，
    不随清单关） */
function closeSweep(): void {
  liveStore.sweepState = false;
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
     （组织者视角/预约卡/形象页等后续档位实现后再扩这条分发链）。
     pendingLiveId 是 goLive 的在途信号（switchTab 无 query）：有它说明详情/卡片正带 id
     进场，onShow 马上会接——不弹回（2.5 修弹回 bug：参与者冷缓存三全空必踩）。 */
  if (
    liveId.value == null &&
    !liveStore.hasLive &&
    !gameStore.liveGame &&
    liveStore.pendingLiveId == null
  ) {
    goMeet();
  }
});
onShow(() => {
  /* 教学态（2.7）：示例局接管画面期间不接真局不重启轮询（切回 tab 保持教学局面，
     真局 store 原样等着——退出教学后分支次序自然恢复真局画面）；mode 回 pick 后
     下次 onShow 走原路 */
  if (sandbox.mode !== "pick") return;
  if (liveStore.hasLive) {
    liveStore.pendingLiveId = null; // 已开分支不接新局，信号位一并兜底清（残留不跨状态）
    // 回前台续轮询（onHide 停的；同局幂等不重开）；回看态是定格视图，轮询无意义（2.6）
    if (!liveStore.recap) liveStore.startPolling(liveStore.live!.g.id);
    maybeRemoteSweep(); // 远程散场预约：局已在现场时直接开清扫
    return;
  }
  /* 带 id 深链（扫码/detail 进现场）优先，其次 goLive 落的信号位，最后入口页直进
     （#/ 无 query）时自动接上唯一进行中的局。冷启动无局已被 onLoad 分发去约球页，
     走到这说明是用户主动回现场键。A2 加载中：ensureLive 在途（拉详情等）骨架占位
     不空白，成败都收骨架；信号位消费即清（一次性；深链 id 优先时顺带清掉残留） */
  const id = liveId.value ?? liveStore.pendingLiveId ?? gameStore.liveGame?.id;
  if (id != null) connectLive(id);
});

/** 接局总入口（onShow 深链 / 收摊接在办局 / 死链重试共用）：成败都收骨架；
    判负（真没有/已撤销/断网）且没接上别的局 → 死链态（§4.6 一句+出口，不白屏） */
function connectLive(id: number): void {
  booting.value = true;
  deadGame.value = false;
  liveStore
    .ensureLive(id)
    .then((ok) => {
      if (!ok && !liveStore.hasLive) {
        deadId.value = id;
        deadGame.value = true;
      }
    })
    .finally(() => {
      booting.value = false;
      liveStore.pendingLiveId = null;
      maybeRemoteSweep(); // 开账/拉读落地后再开清扫（预约位已在对的局上）
    });
}

/** 死链重试：同一 id 再接一次（断网的解药；真死局仍是死链态） */
function retryDead(): void {
  if (deadId.value != null) connectLive(deadId.value);
}

/* ---------- 战报门牌（2.6 §4.1/§4.3） ---------- */
/** 完成=收摊（合同 4.1-3：只清本机画面，账一点不动；不弹确认）：还有别的在办局
    原地接最近开打的（liveGame 口径在 game store，同 tab 不跳页），无则落
    2.7 选卡屏。深链残留 id 一并清（§4.3-4 收摊语义）：
    不清则切走再切回 onShow `liveId ?? …` 仍拿它重接刚收掉的局，战报复活 */
function onRecapComplete(): void {
  liveStore.dismissRecap();
  liveId.value = null;
  const next = gameStore.liveGame;
  if (next) connectLive(next.id);
}
/** 分享（§4.1，2026-10-12 三处统一）：发详情链接（收链接的人详情+「查看战报」
    一跳可达）；兜底提示走 shareLink 默认句「链接已复制 · 访客可看」；局名有就带 */
function onRecapShare(): void {
  const id = liveStore.recap?.gameId;
  if (id == null) return;
  void shareLink(gameShareUrl(id), liveStore.live?.g.name ?? "球局战报");
}
/** 页面隐藏（切 tab/进退页面）清本地弹层，避免残留到别的页；轮询随之停（§4.8 对表只在看现场时发生）。
    教学局面随之散（2.7 §4.5「退出即散」：卡标记之外不落任何东西——切 tab 一律 exit；
    从真局入口进的教学，真局画面靠分支次序自然恢复，live store 没动过） */
onHide(() => {
  sandbox.exit();
  liveSheet.value = null;
  qrOpen.value = false;
  liveStore.stopPolling();
});
onUnload(() => liveStore.stopPolling());
</script>

<style lang="scss" scoped>
/* 编排层布局：三块全屏（bare 壳 padding 归零，safe-area 由顶条/候场条各自处理）；
   底部让出公共导航高度（TabBar fixed 常驻后候场条落在 nav 之上）。
   高度取 dvh：100vh 在手机动态工具栏浏览器里按「工具栏收起的大视口」取值，而 fixed
   导航贴的是当前可视区——两边错位会把候场条沉进导航后面（桌面/固定视口无此分歧，
   走查抓不到）；dvh 跟随当前可视高度，与 fixed 导航同一参照系。旧内核不认识 dvh
   则整行丢弃、回退上一行 100vh（原行为） */
.live-root {
  height: calc(100vh - var(--nav-total-h));
  height: calc(100dvh - var(--nav-total-h));
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

/* 加载骨架（A2）：.skel-wrap/.sk 族是全局类（base.scss 单一源，recap 子页同款） */

.kt30 {
  margin-top: 30px;
}
.et20 {
  margin-top: 20px;
}

/* 教学态骨架（2.7 批2 占位：批3 换 SandboxStage）——只保「认得出接管+能退出」 */
.sb-root {
  height: calc(100vh - var(--nav-total-h));
  height: calc(100dvh - var(--nav-total-h));
  display: flex;
  flex-direction: column;
  padding: calc(env(safe-area-inset-top) + 18px) 18px 8px;
  box-sizing: border-box;
}
.sb-hold {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--dim);
  font-size: 13px;
}
.sb-exit {
  text-align: center;
  padding: 10px;
  font-size: 12px;
  color: var(--dim);
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
/* 死链态出口双钮（重试 / 去约球） */
.dl-btns {
  display: flex;
  gap: 10px;
  margin-top: 16px;
}
.flex1 {
  flex: 1;
}
</style>
