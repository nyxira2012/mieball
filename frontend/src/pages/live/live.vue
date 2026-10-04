<template>
  <!-- 打球页（2.1 改版）：一屏三块——顶条（LiveTopbar）/ 滚动对局区（CourtMatchCard 三态）/ 置底候场条
       （QueueBar）+ 四抽屉一弹窗一浮层（本页本地弹层，liveSheet 单槽替换语义，不走全局 SheetPayload）。
       页面只做编排：卡片/抽屉的数据与动作全在 live store 与各组件内，这里接打开次序与跨页跳转。
       url query 的 id：onShow 时若现场未开则自动 startLive（深链/刷新兜底；hasLive 已开不重复，避免重置名册）。
       扫码签到深链（2.1·选项A）：二维码编码 {origin}/#/pages/live/live?id=<球局id>，
       uni-app H5 hash 路由原生承接；游客点「＋到场」先弹名片建号（SignupSheet），建号成功自动签到进候场区。 -->
  <PageShell bare>
    <!-- 无 live 空态（alpha:1532-1535 逐字；bare 壳下自补边距） -->
    <template v-if="!liveStore.hasLive">
      <view class="empty-wrap">
        <view class="kicker kt30">Court</view>
        <view class="brand">现<text class="bem">场</text></view>
        <EmptyBox class="et20">
          <view>还没有进行中的球局</view>
          <AppButton variant="pri" size="sm" class="go-btn" @click="goOpenTonight">去开今晚的局 ▸</AppButton>
        </EmptyBox>
      </view>
    </template>

    <template v-else-if="L">
      <view class="live-root">
        <LiveTopbar @qr="qrOpen = true" @rules="liveSheet = { k: 'rules' }" />

        <!-- 块二：滚动对局区（playing cur + ready 各待开片 + 空闲卡补位） -->
        <view class="courts">
          <CourtMatchCard
            v-if="L.cur"
            variant="playing"
            :cur="L.cur"
            :name="courtName(0)"
            :org="org"
            @point="liveStore.point"
            @undo="liveStore.undoPoint"
            @clear="liveStore.clearScore"
            @settle="liveStore.openSettle"
            @cancel="liveStore.cancelMatch"
            @pull="goPull"
            @profile="openProfile"
          />
          <CourtMatchCard
            v-for="(c, i) in L.courts"
            :key="`ready${i}`"
            variant="ready"
            :court="c"
            :name="courtName(i + 1)"
            :org="org"
            @profile="openProfile"
          />
          <CourtMatchCard
            v-for="idx in idleIdx"
            :key="`idle${idx}`"
            variant="idle"
            :name="courtName(idx)"
            :org="org"
            @autodeal="liveStore.autoDeal"
            @pull="goPull"
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
      <QueueSheet :visible="liveSheet?.k === 'queue'" @close="closeLocal" @person="onQueuePerson" />
      <RulesSheet :visible="liveSheet?.k === 'rules'" @close="closeLocal" />
      <!-- 终局结算（store.settling 驱动）与签到二维码浮层：z-110，顶替退役 WinPopup 层级 -->
      <EndSettleModal :visible="!!liveStore.settling" @close="liveStore.closeSettle()" />
      <QrOverlay :visible="qrOpen" @close="qrOpen = false" />
    </template>
  </PageShell>
</template>

<script setup lang="ts">
/* 打球页编排层（2.1 改版批2 重写）：数据与动作全在 live store / 组件内，页面只管
   卡片名映射、弹层次序（liveSheet 单槽）、跨页跳转（档案/拉人/深链）、撒花。 */
import { computed, ref, watch } from 'vue';
import { onHide, onLoad, onShow } from '@dcloudio/uni-app';
import PageShell from '@/components/biz/PageShell.vue';
import AppButton from '@/components/ui/AppButton.vue';
import EmptyBox from '@/components/ui/EmptyBox.vue';
import LiveTopbar from '@/components/biz/LiveTopbar.vue';
import CourtMatchCard from '@/components/biz/CourtMatchCard.vue';
import QueueBar from '@/components/biz/QueueBar.vue';
import PersonSheet from '@/components/biz/PersonSheet.vue';
import CheckinSheet from '@/components/biz/CheckinSheet.vue';
import QueueSheet from '@/components/biz/QueueSheet.vue';
import RulesSheet from '@/components/biz/RulesSheet.vue';
import EndSettleModal from '@/components/biz/EndSettleModal.vue';
import QrOverlay from '@/components/biz/QrOverlay.vue';
import { useLiveStore } from '@/stores/live';
import { useSessionStore } from '@/stores/session';
import { useUiStore } from '@/stores/ui';
import { isOrg, courtLabel } from '@/utils/format';
import { maxCourts } from '@/utils/rotate';

/** 本地弹层槽（单槽替换语义：开新的自动顶旧的；与全局 SheetPayload 互不相干） */
type LocalSheet =
  | { k: 'person'; id: number; swap?: boolean }
  | { k: 'checkin' }
  | { k: 'queue' }
  | { k: 'rules' };

const liveStore = useLiveStore();
const session = useSessionStore();
const ui = useUiStore();

const L = computed(() => liveStore.live);
const org = computed(() => (L.value ? isOrg(L.value.g) : false));

const liveSheet = ref<LocalSheet | null>(null);
const qrOpen = ref(false);

const personOpen = computed(() => liveSheet.value?.k === 'person');
const personId = computed(() => (liveSheet.value?.k === 'person' ? liveSheet.value.id : 0));
const personSwap = computed(() => (liveSheet.value?.k === 'person' ? !!liveSheet.value.swap : false));

function closeLocal(): void {
  liveSheet.value = null;
}
function onSwapMode(on: boolean): void {
  if (liveSheet.value?.k === 'person') liveSheet.value = { ...liveSheet.value, swap: on };
}
/** 换人落子：swapPlayers 后关抽屉（toast 在 store） */
function onSwapTarget(t: number): void {
  if (liveSheet.value?.k === 'person') {
    liveStore.swapPlayers(liveSheet.value.id, t);
    liveSheet.value = null;
  }
}
/** 队列抽屉点行 → 顶替为点人抽屉 */
function onQueuePerson(id: number): void {
  liveSheet.value = { k: 'person', id };
}

/** 战力档案：先关本地抽屉再开全局 ProfileSheet（全局单例只留一个弹层） */
function openProfile(id: number): void {
  liveSheet.value = null;
  ui.openSheet({ type: 'profile', userId: id });
}

/** ＋到场：游客先名片建号（选项A 扫码自签到链路保留），球友直接开签到抽屉 */
function onCheckin(): void {
  const g = L.value?.g;
  if (!g) return;
  if (session.isGuest) ui.openSheet({ type: 'signup-card', pendingCheckin: { gameId: g.id } });
  else liveSheet.value = { k: 'checkin' };
}

/** 空闲卡「去拉人」→ 约球页找球友 */
function goPull(): void {
  uni.switchTab({ url: '/pages/meet/meet' });
}

/* ---------- 卡片名映射（口径在 utils/format 的 courtLabel 单一源） ---------- */
function courtName(idx: number): string {
  return courtLabel(L.value?.g.booked, idx);
}

/** 空闲卡：片数上限在 utils/rotate 的 maxCourts 单一源；只出「下一片可开」一张
    （原型口径单张空闲卡：候场够了点自动排阵，不逐片刷屏）；候场有人时才出。 */
const idleIdx = computed<number[]>(() => {
  const l = L.value;
  if (!l) return [];
  const dealt = (l.cur ? 1 : 0) + l.courts.length;
  return maxCourts(l.g) - dealt > 0 && l.queue.length ? [dealt] : [];
});

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
});
onShow(() => {
  if (liveId.value != null && !liveStore.hasLive) liveStore.startLive(liveId.value);
});
/** 页面隐藏（切 tab/进退页面）清本地弹层，避免残留到别的页 */
onHide(() => {
  liveSheet.value = null;
  qrOpen.value = false;
});

/** alpha:1534-1535 空态按钮 → openDetail(101) */
function goOpenTonight(): void {
  uni.navigateTo({ url: '/pages/detail/detail?id=101' });
}
</script>

<style lang="scss" scoped>
/* 编排层布局：三块全屏（bare 壳 padding 归零，safe-area 由顶条/候场条各自处理） */
.live-root {
  height: 100vh;
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
.kt30 {
  margin-top: 30px;
}
.et20 {
  margin-top: 20px;
}
.go-btn {
  margin-top: 20px;
}
</style>
