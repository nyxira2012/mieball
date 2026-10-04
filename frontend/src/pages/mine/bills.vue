<template>
  <!-- 账单页（5.1 子页）：期间筛选 + 三数总览 + 逐笔列表（结算/收款行内动作，点行进原局详情看摊账） -->
  <PageShell>
    <!-- 子页统一返回行（BackRow；uni 多页无返回手势兜底） -->
    <BackRow />

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

    <!-- 「谁还欠你」按人汇总（5.1 修订：debtors 与三数同口径；没人欠整块不渲染） -->
    <view v-if="bill.debtors.length" class="debtors">
      <view class="dhead">谁还欠你</view>
      <view v-for="d in bill.debtors" :key="d.u.id" class="drow">
        <text class="dname">{{ d.u.name }}</text>
        <text class="damt">¥{{ d.amt }} · {{ d.n }} 场</text>
      </view>
    </view>

    <!-- 逐笔列表（filtered 倒序由 store 保序给出）；该收行点开=行内展开按人名单，
         其余行点行进原参加场次页看摊账明细。template v-for 双根：行 + 行下的展开区。
         包一层 .list 是为首行上边框取 :first-child —— uni 下 :first-of-type 会被卡片的
         根 view 占掉，匹配不到首行 -->
    <view v-if="bill.filtered.length" class="list">
      <template v-for="b in bill.filtered" :key="b.id">
        <view class="lrow" @click="tapBill(b)">
          <view class="lmain">
            <view class="gname">{{ b.gname }}</view>
            <!-- 待付行写明欠谁（5.1）：收款人＝那场局的组织者 -->
            <view class="gdate">{{ b.status === 'due' && b.payee ? `欠 ${b.payee.name} · ${b.date}` : b.date }}</view>
          </view>
          <view class="lright">
            <view class="amt" :class="amtCls(b.status)">{{ amtTxt(b) }}</view>
            <view class="st">{{ BILL_STATUS_NAMES[b.status] }}{{ b.status === 'receivable' ? (openId === b.id ? ' ▴' : ' ▾') : '' }}</view>
          </view>
          <!-- 行内动作（5.1 账单结算）：due→结算；该收逐人清账，整笔收款作废，收款钮在展开区 -->
          <view v-if="b.status === 'due'" class="tbtn" @click.stop="bill.settleBill(b.id)">结算</view>
        </view>
        <!-- 该收行展开区（5.1 修订）：按人明细由数据侧给好，逐人点「已收」清账 -->
        <view v-if="openId === b.id && b.payers" class="pays">
          <view v-for="p in b.payers" :key="p.u.id" class="prow">
            <text class="pname">{{ p.u.name }}</text>
            <text class="pamt" :class="{ dim: p.settled }">¥{{ p.amt }}</text>
            <text v-if="p.settled" class="pdone">已收 ✓</text>
            <view v-else class="tbtn rec pbtn" @click.stop="bill.receivePayer(b.id, p.u.id)">已收</view>
          </view>
        </view>
      </template>
    </view>
    <EmptyBox v-if="!bill.filtered.length" text="这段期间没有账单 · 换个筛法" />
  </PageShell>
</template>

<script setup lang="ts">
/* 账单页（5.1 子页）：我的花钱底账。数据全在 bill store（过滤/汇总/结算/逐人收款，toast 内聚），
   本页只做筛选接线、行展开/导航与展示。 */
import { computed, ref } from 'vue';
import PageShell from '@/components/biz/PageShell.vue';
import BackRow from '@/components/biz/BackRow.vue';
import BillSummaryCard from '@/components/biz/BillSummaryCard.vue';
import FilterChips from '@/components/ui/FilterChips.vue';
import EmptyBox from '@/components/ui/EmptyBox.vue';
import { useBillStore, BILL_STATUS_NAMES, PERIOD_OPTS, payerSum, type BillPeriod } from '@/stores/bill';
import type { Bill, BillStatus } from '@/api/types';

const bill = useBillStore();

/** FilterChips 的宽类型（string|number，meet.vue fTime 同法）与 BillPeriod 窄类型之间的桥 */
const period = computed<string | number>({
  get: () => bill.period,
  set: (v) => {
    bill.period = v as BillPeriod;
  },
});

/** 行点击按状态分类：该收行行内展开（不跳页）；其余行（含全清翻转成 received 的）点行进原参加场次页看摊账明细 */
const openId = ref<number | null>(null);
function tapBill(b: Bill): void {
  if (b.status === 'receivable') openId.value = openId.value === b.id ? null : b.id;
  else uni.navigateTo({ url: '/pages/detail/detail?id=' + b.gameId });
}

/** 金额状态色：due→coral / receivable→lemon / paid·received→dim */
function amtCls(st: BillStatus): string {
  return st === 'due' ? 'due' : st === 'receivable' ? 'rec' : 'dim';
}
/** received→✓ 金额；receivable→有已收小计时「已收 ¥X / 共 ¥Y」，否则裸金额 */
function amtTxt(b: Bill): string {
  if (b.status === 'received') return '✓ ¥' + b.amt;
  if (b.status === 'receivable') {
    const got = payerSum(b, true);
    return got > 0 ? `已收 ¥${got} / 共 ¥${b.amt}` : `¥${b.amt}`;
  }
  return `¥${b.amt}`;
}
</script>

<style lang="scss" scoped>
/* ---------- 头部 brand：版式走全局 .brand 类，只补 700 加粗（mine 系约定，补 alpha h1 的 UA 默认加粗） ---------- */
.brand {
  font-weight: 700;
}

/* 总览卡与逐笔列表之间的间距（卡本体样式在 BillSummaryCard） */
.trio-gap {
  margin-bottom: 6px;
}

/* ---------- 「谁还欠你」按人汇总（5.1 修订：与三数同口径，没欠收起） ---------- */
.debtors {
  margin: 6px 0 12px;
  padding: 12px 2px;
  border-top: 1px solid rgba(245, 241, 232, 0.07);
  border-bottom: 1px solid rgba(245, 241, 232, 0.07);
}
.dhead {
  font-size: 10px;
  color: var(--dim);
  margin-bottom: 8px;
}
.drow {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  padding: 5px 0;
}
.dname {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.damt {
  font-family: var(--mono);
  font-size: 13px;
  font-weight: 500;
  color: var(--lemon);
  flex: none;
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

/* ---------- 该收行展开区（5.1 修订：视觉上属于该行——左缩进、无边框） ---------- */
.pays {
  padding: 4px 0 8px 14px;
}
.prow {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 2px;
}
.pname {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pamt {
  font-family: var(--mono);
  font-size: 12px;
  font-weight: 500;
  flex: none;
}
.pamt.dim {
  color: var(--dim);
}
.pdone {
  font-size: 10px;
  color: var(--dim);
  flex: none;
}
/* 未结的逐人「已收」小钮：复用 .tbtn.rec，行内收窄 */
.pbtn {
  padding: 5px 10px;
  font-size: 11px;
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
