<template>
  <!-- 我的页（P10）· 5.1 重做：形象区（点形象进装扮页）/ 账单卡（全量三数）/ 记录双卡 / 账号区。
       版式承袭 alpha:644-673 的 stag/mecard/acc-row；旧「本期账本」卡、换装行、我的球局列表
       分别由账单页（bills）、装扮页（dress）、登记/记录页（signup/logs）接管。 -->
  <PageShell tab="mine">
    <!-- alpha:645-648 头部：kicker + brand（「的」字黄色） -->
    <view class="stag">
      <view class="kicker">Player Card</view>
      <view class="brand">我<text class="bem">的</text>球场</view>
    </view>

    <!-- 头部形象区（5.1 页面设计）：点形象即进装扮页 -->
    <view class="mecard">
      <view class="av" @click="go('/pages/mine/dress')">
        <ChibiAvatar :chibi="me.chibi" :size="88" />
      </view>
      <view class="minfo">
        <view class="mname">{{ meName }}</view>
        <view class="mrecord">{{ record }}</view>
        <view class="mchips">
          <!-- alpha:1939 me-elo：tierB 徽章 + ELO 分 + 段位（chip ok） -->
          <AppChip kind="ok">
            <TierBadge :tier="meTier" /> ELO {{ me.elo }} · {{ meTier }} 段
          </AppChip>
          <!-- alpha:656 尾号 chip：登录后是账号真实尾号，游客回落演示尾号 -->
          <AppChip>尾号 ···{{ session.phoneTail }}</AppChip>
          <!-- 档案卡 = 别人看到的完整档案（与打球页名单点击同支弹层，userId 0 = 我） -->
          <AppChip @click="onProfileCard">档案卡 ▸</AppChip>
          <!-- 装扮入口（与点头像同页） -->
          <AppChip @click="go('/pages/mine/dress')">装扮 ▸</AppChip>
        </view>
      </view>
    </view>

    <!-- 账单卡（5.1）：totalSummary 是 store 的全量口径——period 单例跨页存活，
         账单页切过筛选后 summary 会带着漂，主页卡/注销守卫不能消费它；
         整卡可点进账单页看期间筛选与逐笔（class/@click 透传到 BillSummaryCard 根） -->
    <SectionTitle title="账单" more="明细 ▸" @more="go('/pages/mine/bills')" />
    <BillSummaryCard
      class="bill-card"
      :due="bill.totalSummary.due"
      :paid="bill.totalSummary.paid"
      :receivable="bill.totalSummary.receivable"
      @click="go('/pages/mine/bills')"
    />

    <!-- 记录双卡（5.1 页面设计）：登记局数/签到次数统一走 game store 的 mySignups/myCheckins 单一口径 -->
    <view class="duo">
      <view class="d-card" @click="go('/pages/mine/signup')">
        <view class="d-t">参加登记</view>
        <view class="d-s">共 {{ gameStore.mySignups.length }} 局 · 签到 {{ gameStore.myCheckins.length }} 次</view>
      </view>
      <view class="d-card" @click="go('/pages/mine/logs')">
        <view class="d-t">打球记录</view>
        <view class="d-s">累计 {{ me.play }} 场</view>
      </view>
    </view>

    <!-- 账号区（1.1/5.1 对齐）：密码与微信授权已随 MVP 下架（D1）；游客给找回入口 -->
    <SectionTitle title="账号" />
    <view class="acc-links">
      <view v-if="session.isGuest" class="acc-link" @click="go('/pages/mine/login')">
        登录 · 我是老球友（手机号找回） <text class="arr">▸</text>
      </view>
      <view v-else class="acc-link" @click="go('/pages/mine/dress')">
        手机号 {{ maskedPhone }} · 唯一钥匙 <text class="arr">▸</text>
      </view>
    </view>
    <view class="acc-row">
      <AppButton variant="ghost" size="sm" class="grow" @click="onLogout">退出账号</AppButton>
      <AppButton variant="ghost" size="sm" class="grow danger" @click="onDeleteAcc">注销账号</AppButton>
    </view>
  </PageShell>
</template>

<script setup lang="ts">
/* 我的页（P10）· 5.1 我的页主页面：底账入口聚合（账单/登记/记录）+ 账号区。
   alpha:1931-1976 的 meName/战绩/ELO 段位口径保留，其余换装与账本逻辑退场。 */
import { computed } from 'vue';
import PageShell from '@/components/biz/PageShell.vue';
import ChibiAvatar from '@/components/ui/ChibiAvatar.vue';
import AppChip from '@/components/ui/AppChip.vue';
import AppButton from '@/components/ui/AppButton.vue';
import TierBadge from '@/components/ui/TierBadge.vue';
import SectionTitle from '@/components/ui/SectionTitle.vue';
import BillSummaryCard from '@/components/biz/BillSummaryCard.vue';
import { useUserStore } from '@/stores/user';
import { useSessionStore } from '@/stores/session';
import { useGameStore } from '@/stores/game';
import { useUiStore } from '@/stores/ui';
import { useBillStore } from '@/stores/bill';
import { tier } from '@/utils/elo';

const user = useUserStore();
const session = useSessionStore();
const gameStore = useGameStore();
const ui = useUiStore();
const bill = useBillStore();

/** 账号区行：登录后手机号打码展示（完整号只在装扮页/档案给自己看，§C2） */
const maskedPhone = computed(() => {
  const p = session.account?.phone;
  return p ? `${p.slice(0, 3)}****${p.slice(-4)}` : '';
});

/** 我（alpha:1935 U.me；user store 与 games/live 同源引用，装扮保存全产品同步） */
const me = computed(() => user.me);
/** alpha:1937：默认名「我」显示为「我的球场小人」 */
const meName = computed(() => (me.value.name === '我' ? '我的球场小人' : me.value.name));
/** alpha:1938 战绩行：N 场 · N 胜 · 胜率 N% */
const record = computed(
  () => `${me.value.play} 场 · ${me.value.win} 胜 · 胜率 ${Math.round((me.value.win / me.value.play) * 100)}%`,
);
/** alpha:1939 ELO chip 的段位（utils/elo.ts tier） */
const meTier = computed(() => tier(me.value.elo));

/* —— 导航（uni 路由集中在页面层，store 不碰 uni.*；路由在模板处直读） —— */
function go(url: string): void {
  uni.navigateTo({ url });
}
/** 档案卡弹层 = 别人看到的完整档案卡（userId 0 = 我） */
function onProfileCard(): void {
  ui.openSheet({ type: 'profile', userId: 0 });
}
/** 退出/注销走确认弹层（5.1 弹窗：两步/守卫逻辑在 AccountSheet） */
function onLogout(): void {
  ui.openSheet({ type: 'logout-confirm' });
}
function onDeleteAcc(): void {
  ui.openSheet({ type: 'delete-confirm' });
}
</script>

<style lang="scss" scoped>
/* ---------- 头部 brand（alpha:85-87 h1.brand / h1.brand em）：
   base.scss 的 h1.brand 选择器带元素名、匹配不上 uni-view，故在页面内按同值复制类；
   font-weight 700 补 alpha h1 的 UA 默认加粗 ---------- */
.brand {
  font-family: var(--disp);
  font-size: 34px;
  line-height: 1.04;
  margin: 6px 0 2px;
  font-weight: 700;
}
.brand .bem {
  font-style: normal;
  color: var(--lemon);
}

/* ---------- mecard（alpha:394-397 · 结构 alpha:649-659） ---------- */
.mecard {
  display: flex;
  gap: 16px;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  padding: 18px;
  background: linear-gradient(150deg, var(--ink3), var(--ink2));
}
.mecard .av {
  width: 88px;
  height: 88px;
  flex: none;
  cursor: pointer;
  transition: transform 0.2s;
}
.mecard .av:active {
  transform: scale(0.92) rotate(-6deg);
}
/* alpha:651 flex:1 信息列 */
.minfo {
  flex: 1;
  min-width: 0;
}
/* alpha:652 名字 */
.mname {
  font-size: 20px;
  font-weight: 800;
}
/* alpha:653 战绩行 */
.mrecord {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--dim);
  margin: 3px 0 8px;
}
/* alpha:654 chips 行（4 枚起换行兜底） */
.mchips {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

/* ---------- 账单卡（三数版式与配色内聚在 BillSummaryCard，此处只挂点击态） ---------- */
.bill-card {
  cursor: pointer;
}
.bill-card:active {
  border-color: rgba(255, 212, 0, 0.4);
}

/* ---------- 记录双卡（5.1：参加登记 / 打球记录，mecard 简化版式） ---------- */
.duo {
  display: flex;
  gap: 10px;
  margin-top: 14px;
}
.d-card {
  flex: 1;
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  padding: 14px 16px;
  background: linear-gradient(150deg, var(--ink3), var(--ink2));
  cursor: pointer;
}
.d-card:active {
  border-color: rgba(255, 212, 0, 0.4);
}
.d-t {
  font-size: 15px;
  font-weight: 800;
}
.d-s {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  margin-top: 4px;
}

/* ---------- 账号区（5.1：行式入口 + 退出/注销） ---------- */
.acc-links {
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  overflow: hidden;
  background: var(--ink2);
  margin-bottom: 14px;
}
.acc-link {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 13px 16px;
  font-size: 13px;
  cursor: pointer;
}
.acc-link + .acc-link {
  border-top: 1px solid var(--line);
}
.acc-link .arr {
  font-family: var(--mono);
  color: var(--dim);
}
.acc-link:active {
  color: var(--lemon);
}
/* alpha:669 flex + 按钮 flex:1 */
.acc-row {
  display: flex;
  gap: 10px;
}
.acc-row .grow {
  flex: 1;
}
/* 注销 = 珊瑚描边强化（同 detail.vue .cancel-btn 口径；双类选择器压过 AppButton 内部 .btn-ghost） */
.acc-row .danger {
  color: var(--coral);
  border-color: rgba(255, 90, 54, 0.4);
}
</style>
