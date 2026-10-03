<template>
  <!-- 现场页（2.1）· alpha.html:1531-1648 renderLive/renderAttend/renderCourts 的 Vue 化（P8a）；
       记分 tab 本阶段为 P8b 占位。非 tab 页：无 TabBar，仍挂全部宿主（记分收局要弹 WinPopup/撒花）。
       url query 的 id：onShow 时若现场未开则自动 startLive（alpha 里 startLive 由详情页「开始打球」
       调用，这里兜底直链/刷新场景；hasLive 已开则不重复，避免重置名册）。 -->
  <PageShell>
    <!-- 无 live 空态（alpha:1532-1535 逐字：kicker margin-top:30px · 现场大字 · empty margin-top:20px） -->
    <template v-if="!liveStore.hasLive">
      <view class="kicker kt30">Court</view>
      <view class="brand">现<text class="bem">场</text></view>
      <EmptyBox class="et20">
        <view>还没有进行中的球局</view>
        <AppButton variant="pri" size="sm" class="go-btn" @click="goOpenTonight">去开今晚的局 ▸</AppButton>
      </EmptyBox>
    </template>

    <template v-else-if="L">
      <!-- alpha:1539-1541 头部：kicker · brand（t 首段+夜战）· sub（模式·分制·LIVE 灯） -->
      <view class="kicker">Court Live · Round {{ L.round + 1 }}</view>
      <view class="brand">{{ brandHead }}<text class="bem">夜战</text></view>
      <view class="sub">{{ modeName }} · {{ L.g.score }} 分制 · <view class="live-dot" /> LIVE</view>

      <!-- alpha:1542-1546 segtab 三页签（到场/轮转/记分） -->
      <view class="segtab">
        <view v-for="t in TABS" :key="t.k" class="seg-btn" :class="{ on: tab === t.k }" @click="tab = t.k">{{ t.n }}</view>
      </view>

      <!-- alpha:1548-1551 到场 panel：说明行 + 名册逐行 AttendRow（alpha:1549 说明逐字） -->
      <view class="panel" :class="{ on: tab === 'attend' }">
        <view class="sub pn-sub">签到 / 迟到 / 早退 / 中途加入——来没来、几点走，清清楚楚。</view>
        <AttendRow v-for="p in L.roster" :key="p.id" :player="p" @check="(s) => onCheck(p.id, s)" />
      </view>

      <!-- alpha:1553-1563 轮转 panel：歇/连战互斥双钮 · 说明行 · 场地列表 · 候场队列 · 开下一轮 -->
      <view class="panel" :class="{ on: tab === 'rotate' }">
        <view class="statbtns">
          <view class="sb" :class="{ 'on-rest': me?.skip }" @click="liveStore.toggleMine('skip')">{{ me?.skip ? '☕ 已歇一轮' : '☕ 我歇一轮' }}</view>
          <view class="sb" :class="{ 'on-fire': me?.fire }" @click="liveStore.toggleMine('fire')">{{ me?.fire ? '🔥 连战模式' : '🔥 状态好·连着打' }}</view>
        </view>
        <view class="sub pn-sub2">歇一轮＝下轮跳过我 · 连战＝排到队首；组织者按 <text class="b-lemon">{{ modeName }}</text> 发牌。</view>
        <!-- alpha:1608 cs = cur 打球中卡在最前 + 待打 courts；全空时「点「开下一轮」发牌」（alpha:1617） -->
        <template v-if="courts.length">
          <CourtCard v-for="(c, i) in courts" :key="i" :court="c" :playing="!!c.playing" :index="i + 1" @profile="openProfile" />
        </template>
        <EmptyBox v-else text="点「开下一轮」发牌" />
        <view class="sec-t"><text class="t">候场队列</text><text class="more">{{ L.queue.length }} 人</text></view>
        <QueueList :queue="L.queue" />
        <AppButton variant="pri" block class="nr-btn" @click="onNewRound">开下一轮 ▸</AppButton>
      </view>

      <!-- alpha:1565-1568 记分 panel：renderScore/历史/收局由 P8b 实现，本阶段占位（非产品文案） -->
      <view class="panel" :class="{ on: tab === 'score' }">
        <view class="ph">P8b 待实现</view>
      </view>
    </template>
  </PageShell>
</template>

<script setup lang="ts">
/* 现场页（2.1）接线层：数据与动作全在 live store（alpha:1471-1530/1591-1648），
   页面只做 segtab 切换与三 panel 组装（alpha:1531-1571 renderLive）。 */
import { computed, ref } from 'vue';
import { onLoad, onShow } from '@dcloudio/uni-app';
import PageShell from '@/components/biz/PageShell.vue';
import AppButton from '@/components/ui/AppButton.vue';
import EmptyBox from '@/components/ui/EmptyBox.vue';
import AttendRow from '@/components/biz/AttendRow.vue';
import CourtCard from '@/components/biz/CourtCard.vue';
import QueueList from '@/components/biz/QueueList.vue';
import { useLiveStore } from '@/stores/live';
import { useUiStore } from '@/stores/ui';
import { pById } from '@/utils/rotate';
import type { CheckStatus, CourtMode, LiveCourt } from '@/api/types';

const liveStore = useLiveStore();
const ui = useUiStore();

/** 从 url query 接 id（onLoad options），onShow 兜底 startLive 用 */
const liveId = ref<number | null>(null);

onLoad((options) => {
  const raw = (options as Record<string, string | undefined> | undefined)?.id;
  const n = raw != null ? Number(raw) : NaN;
  liveId.value = Number.isFinite(n) ? n : null;
});

/** alpha:1573 me() = pById(0)：轮转面板歇/连战按钮读我的标记 */
const L = computed(() => liveStore.live);
const me = computed(() => (L.value ? pById(L.value, 0) : undefined));

/** onShow：query 带 id 且现场未开 → 自动 startLive；hasLive 已开则跳过（避免重置名册） */
onShow(() => {
  if (liveId.value != null && !liveStore.hasLive) liveStore.startLive(liveId.value);
});

/* alpha:1537 modeName */
const MODE_NAMES: Record<CourtMode, string> = { winner: '赢家留场', rotate: '纯粹轮转', balance: '均衡配对' };
const modeName = computed(() => (L.value ? MODE_NAMES[L.value.g.mode] : ''));
/** alpha:1540 brand 大字 = t 首段（「夜战」在模板的 em 位） */
const brandHead = computed(() => (L.value ? (L.value.g.t.split(' ')[0] ?? '') : ''));

/* alpha:1572 let liveTabState='attend'（alpha:1574 liveTab 切换 → tab ref） */
type LiveTab = 'attend' | 'rotate' | 'score';
const tab = ref<LiveTab>('attend');
const TABS: { k: LiveTab; n: string }[] = [
  { k: 'attend', n: '到场' },
  { k: 'rotate', n: '轮转' },
  { k: 'score', n: '记分' },
];

/** 场地列表（alpha:1608）：live.cur 打球中卡在最前 + 待打 courts */
type CourtVm = LiveCourt & { playing?: boolean };
const courts = computed<CourtVm[]>(() => {
  const l = L.value;
  if (!l) return [];
  return l.cur ? [{ A: l.cur.A, B: l.cur.B, playing: true }, ...l.courts] : l.courts;
});

/** AttendRow check 事件 → store setCheck（alpha:1591；副作用在 store：迟到排队尾/早退清场/中途加入队首） */
const onCheck = (id: number, st: CheckStatus): void => liveStore.setCheck(id, st);

/** alpha:1626 openProfileById → 全产品共用档案弹层 ProfileSheet */
const openProfile = (id: number): void => ui.openSheet({ type: 'profile', userId: id });

/** alpha:1637-1648 newRound；confetti(14) 由页面层 Confetti 做（store 不管撒花）→ ui.burst(14) */
const onNewRound = (): void => {
  liveStore.newRound();
  ui.burst(14); // alpha:1647
};

/** alpha:1534-1535 空态按钮 → openDetail(101) */
const goOpenTonight = (): void => {
  uni.navigateTo({ url: '/pages/detail/detail?id=101' });
};
</script>

<style lang="scss" scoped>
/* 页面专属类。kicker/sub/sec-t 在全局 base.scss；brand 因 uni 模板不能用 h1，
   页面自带同值类（alpha:86-87，同 home/detail 页约定）。 */
.brand {
  font-family: var(--disp);
  font-size: 34px;
  line-height: 1.04;
  margin: 6px 0 2px;
}
/* alpha:87 h1.brand em */
.brand .bem {
  font-style: normal;
  color: var(--lemon);
}

/* alpha:1532-1535 无 live 空态的内联 margin（30px/20px）与 <br><br> 等价间距 */
.kt30 {
  margin-top: 30px;
}
.et20 {
  margin-top: 20px;
}
.go-btn {
  margin-top: 20px;
}

/* alpha:1541 live-dot（呼吸灯 keyframes pulse 在 animations.scss；内联 display:inline-block;vertical-align:-1px） */
.live-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--coral);
  box-shadow: 0 0 0 0 rgba(255, 90, 54, 0.6);
  animation: pulse 1.6s infinite;
  display: inline-block;
  vertical-align: -1px;
}

/* ---------- segtab / panel（alpha:244-251；segtab 内联 margin-top:16px + 自身 margin-bottom:16px） ---------- */
.segtab {
  display: flex;
  gap: 6px;
  background: var(--ink2);
  border: 1px solid rgba(245, 241, 232, 0.1);
  border-radius: 14px;
  padding: 5px;
  margin: 16px 0;
}
.seg-btn {
  flex: 1;
  padding: 9px 0;
  text-align: center;
  color: var(--dim);
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  font-family: var(--sans);
  cursor: pointer;
  transition: 0.2s;
}
.seg-btn.on {
  background: var(--lemon);
  color: var(--ink);
}
.panel {
  display: none;
}
.panel.on {
  display: block;
  animation: fadeUp 0.3s ease;
}

/* ---------- 到场 panel 说明行（alpha:1549 内联 margin-bottom:10px） ---------- */
.pn-sub {
  margin-bottom: 10px;
}

/* ---------- 轮转 panel（alpha:297-301 statbtns/sb + 1558 说明行/lemon 强调） ---------- */
.statbtns {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}
.sb {
  flex: 1;
  padding: 11px 4px;
  border-radius: 13px;
  border: 1px dashed rgba(245, 241, 232, 0.2);
  background: none;
  color: var(--dim);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: 0.2s;
  font-family: var(--sans);
  text-align: center;
}
.sb.on-rest {
  border-style: solid;
  border-color: var(--ice);
  color: var(--ice);
  background: rgba(111, 231, 255, 0.08);
}
.sb.on-fire {
  border-style: solid;
  border-color: var(--coral);
  color: var(--coral);
  background: rgba(255, 90, 54, 0.08);
}
.pn-sub2 {
  margin-bottom: 8px; /* alpha:1558 内联 */
}
.b-lemon {
  color: var(--lemon); /* alpha:1558 <b style="color:var(--lemon)"> */
  font-weight: 700;
}
.nr-btn {
  margin-top: 6px; /* alpha:1562 内联 */
}

/* ---------- P8b 占位（非产品文案，同 detail 页 .ph） ---------- */
.ph {
  color: var(--dim);
  font-family: var(--mono);
  font-size: 12px;
  letter-spacing: 0.1em;
}
</style>
