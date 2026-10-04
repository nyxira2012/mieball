<template>
  <!-- 账单页（5.1 子页）：期间筛选 + 三数总览 + 逐笔列表（结算/收款行内动作，点行进原局详情看摊账） -->
  <PageShell>
    <!-- 子页统一返回行（uni 多页无返回手势兜底；后续 5.1 子页同形态） -->
    <view class="backrow" @click="goBack">◂ 返回</view>

    <view class="stag">
      <view class="kicker">Bills</view>
      <view class="brand">账<text class="bem">单</text></view>
    </view>

    <!-- 期间筛选（5.1 辅助功能：近 7 天 / 近 30 天 / 全部） -->
    <FilterChips v-model="period" :options="PERIOD_OPTS" />

    <!-- 三数总览（store summary 已基于 filtered 求和）；三数版式内聚在 BillSummaryCard -->
    <BillSummaryCard
      class="trio-gap"
      :due="bill.summary.due"
      :paid="bill.summary.paid"
      :receivable="bill.summary.receivable"
    />

    <!-- 逐笔列表（filtered 倒序由 store 保序给出）；整行进原参加场次页看摊账明细。
         包一层 .list 是为首行上边框取 :first-child —— uni 下 :first-of-type 会被卡片的
         根 view 占掉，匹配不到首行 -->
    <view v-if="bill.filtered.length" class="list">
      <view v-for="b in bill.filtered" :key="b.id" class="lrow" @click="openBill(b)">
        <view class="lmain">
          <view class="gname">{{ b.gname }}</view>
          <view class="gdate">{{ b.date }}</view>
        </view>
        <view class="lright">
          <view class="amt" :class="amtCls(b.status)">{{ amtTxt(b) }}</view>
          <view class="st">{{ BILL_STATUS_NAMES[b.status] }}</view>
        </view>
        <!-- 行内动作（5.1 账单结算）：due→结算 / receivable→收款，toast 在 store 内 -->
        <view v-if="b.status === 'due'" class="tbtn" @click.stop="bill.settleBill(b.id)">结算</view>
        <view v-else-if="b.status === 'receivable'" class="tbtn rec" @click.stop="bill.receiveBill(b.id)">收款</view>
      </view>
    </view>
    <EmptyBox v-if="!bill.filtered.length" text="这段期间没有账单 · 换个筛法" />
  </PageShell>
</template>

<script setup lang="ts">
/* 账单页（5.1 子页）：我的花钱底账。数据全在 bill store（过滤/汇总/结算/收款，toast 内聚），
   本页只做筛选接线、展示与导航。 */
import { computed } from 'vue';
import PageShell from '@/components/biz/PageShell.vue';
import BillSummaryCard from '@/components/biz/BillSummaryCard.vue';
import FilterChips from '@/components/ui/FilterChips.vue';
import EmptyBox from '@/components/ui/EmptyBox.vue';
import { useBillStore, BILL_STATUS_NAMES, type BillPeriod } from '@/stores/bill';
import type { Bill, BillStatus } from '@/api/types';

const bill = useBillStore();

const PERIOD_OPTS = [
  { value: 'all', label: '全部' },
  { value: '7d', label: '近 7 天' },
  { value: '30d', label: '近 30 天' },
];

/** FilterChips 的宽类型（string|number，meet.vue fTime 同法）与 BillPeriod 窄类型之间的桥 */
const period = computed<string | number>({
  get: () => bill.period,
  set: (v) => {
    bill.period = v as BillPeriod;
  },
});

/** 金额状态色：due→coral / receivable→lemon / paid·received→dim */
function amtCls(st: BillStatus): string {
  return st === 'due' ? 'due' : st === 'receivable' ? 'rec' : 'dim';
}
/** 已收加「✓ 」前缀（结清凭据感），其余裸金额 */
function amtTxt(b: Bill): string {
  return (b.status === 'received' ? '✓ ' : '') + `¥${b.amt}`;
}
/** 点一笔进原参加场次页看摊账明细（5.1） */
function openBill(b: Bill): void {
  uni.navigateTo({ url: '/pages/detail/detail?id=' + b.gameId });
}
function goBack(): void {
  uni.navigateBack();
}
</script>

<style lang="scss" scoped>
/* ---------- 子页统一返回行（mono 11px dim · :active lemon） ---------- */
.backrow {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--dim);
  padding: 8px 2px;
  cursor: pointer;
  display: inline-block;
}
.backrow:active {
  color: var(--lemon);
}

/* ---------- 头部 brand（同 home/meet/mine 页本地类，base.scss h1.brand 匹配不上 uni-view） ---------- */
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

/* 总览卡与逐笔列表之间的间距（卡本体样式在 BillSummaryCard） */
.trio-gap {
  margin-bottom: 6px;
}

/* ---------- 逐笔行（旧 mine.vue .lrow 版式：上下边框分隔 · 左局名+日期｜右金额+状态） ---------- */
.lrow {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 2px;
  border-bottom: 1px solid rgba(245, 241, 232, 0.07);
  cursor: pointer;
}
.lrow:first-child {
  border-top: 1px solid rgba(245, 241, 232, 0.07);
}
.lrow:active {
  background: rgba(255, 212, 0, 0.04);
}
.lmain {
  flex: 1;
  min-width: 0;
}
.gname {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.gdate {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  margin-top: 2px;
}
.lright {
  text-align: right;
  flex: none;
}
.amt {
  font-family: var(--mono);
  font-size: 13px;
  font-weight: 500;
}
.amt.due {
  color: var(--coral);
}
.amt.rec {
  color: var(--lemon);
}
.amt.dim {
  color: var(--dim);
}
.st {
  font-size: 10px;
  color: var(--dim);
  margin-top: 2px;
}

/* 行内动作小钮（meet.vue .tbtn 风格；receivable 收款 lemon 描边） */
.tbtn {
  flex: none;
  padding: 7px 12px;
  border-radius: 10px;
  border: 1px solid rgba(245, 241, 232, 0.16);
  background: none;
  color: var(--dim);
  font-size: 12px;
  font-weight: 700;
  transition: 0.15s;
  font-family: var(--sans);
}
.tbtn:active {
  transform: scale(0.93);
}
.tbtn.rec {
  border-color: rgba(255, 212, 0, 0.5);
  color: var(--lemon);
}
</style>
