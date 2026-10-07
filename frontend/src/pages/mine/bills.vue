<template>
  <!-- 账单页（5.1 子页 · 1.3 批4 切真）：期间筛选 + 三数总览 + 费用未定提醒 + 谁还欠你 +
       逐笔列表（结算/收款行内动作，点行进原局详情）。数据全在 bill store（后端定值直读，
       A4 界面不自算）；确认问句/断网重试精修批5，本批动作直调 + 整树换新 -->
  <PageShell>
    <!-- 子页统一返回行（BackRow；uni 多页无返回手势兜底） -->
    <BackRow />

    <view class="stag">
      <view class="kicker">Bills</view>
      <view class="brand">账<text class="bem">单</text></view>
    </view>

    <!-- 游客态（4.9）：钱的地方假数字必须标明 + 登录入口 -->
    <view v-if="bill.isDemo" class="demo-banner">
      <text class="demo-txt">未登录 · 以下是演示数据</text>
      <text class="demo-link" @click="goLogin">登录 ▸</text>
    </view>

    <!-- 期间筛选（4.6：三数、逐笔、谁还欠你一起跟着走——切换即重拉） -->
    <FilterChips v-model="period" :options="PERIOD_OPTS" />

    <!-- A2 加载中：占位（真请求在途时；演示态无请求不占位） -->
    <view v-if="bill.loading && !bill.rows.length" class="ph"
      >正在打开账单…</view
    >

    <template v-else-if="!failed">
      <!-- 三数总览（后端定值）；三数版式内聚在 BillSummaryCard -->
      <BillSummaryCard
        class="trio-gap"
        :due="bill.summary.due"
        :paid="bill.summary.paid"
        :receivable="bill.summary.receivable"
      />

      <!-- 费用未定提醒条（4.5：仅组织者数据里有；可点直达局页补填总价。
           逐条带自己的局名——「你有 N 场」的总句式只在单条时成立，多条照念就错了） -->
      <view
        v-for="u in bill.unfixed"
        :key="u.gameId"
        class="unfixed"
        @click="goGame(u.gameId)"
      >
        「{{ u.gameName }}」费用未定，补填后才出账 · 去补 ▸
      </view>

      <!-- 「谁还欠你」按人汇总：后端跨场聚合定值；小字常显（5.1 小改③，spec 无 all 豁免） -->
      <view v-if="bill.debtors.length" class="debtors">
        <view class="dhead">谁还欠你 · 只算所选期间内散场的局</view>
        <view v-for="d in bill.debtors" :key="d.accountId" class="drow">
          <text class="dname">{{ d.name }}</text>
          <text class="damt">¥{{ d.total }} · {{ d.games }} 场</text>
        </view>
      </view>

      <!-- 逐笔列表（后端按散场日新到旧）；应收行点开=行内展开按人明细，
           其余行点行进原局页看摊账。template v-for 双根：行 + 行下展开区 -->
      <view v-if="bill.rows.length" class="list">
        <template v-for="b in bill.rows" :key="b.gameId">
          <view class="lrow" @click="tapBill(b)">
            <view class="lmain">
              <view class="gname">{{ b.gameName }}</view>
              <view class="gdate">{{ rowSub(b) }}</view>
              <view v-if="b.peerReceived" class="gray-flag"
                >对方已收款 · 记得回来点结算</view
              >
            </view>
            <view class="lright">
              <view class="amt" :class="amtCls(b.kind)">{{ amtTxt(b) }}</view>
              <view class="st"
                >{{ BILL_STATUS_NAMES[b.kind]
                }}{{
                  expandable(b) ? (openId === b.gameId ? " ▴" : " ▾") : ""
                }}</view
              >
            </view>
            <!-- 行内动作（4.3）：待付行「结算」；终态不可逆，确认问句批5 接 -->
            <view
              v-if="b.kind === 'payable'"
              class="tbtn"
              @click.stop="onSettle(b)"
              >结算</view
            >
          </view>
          <!-- 应收行展开区（4.2/4.4）：按人明细 + 末行「总价 · 我自己那份」 -->
          <view v-if="openId === b.gameId && b.payerRows" class="pays">
            <view v-for="p in b.payerRows" :key="p.accountId" class="prow">
              <view class="pcol">
                <text class="pname">{{ p.name }}</text>
                <text v-if="p.paidAt && !p.receivedAt" class="gray-flag"
                  >已转 · 待收</text
                >
              </view>
              <text class="pamt" :class="{ dim: !!p.receivedAt }"
                >¥{{ p.amount }}</text
              >
              <text v-if="p.receivedAt" class="pdone">已收 ✓</text>
              <view v-else class="tbtn rec pbtn" @click.stop="onReceive(b, p)"
                >已收</view
              >
            </view>
            <view class="psum">
              总价 ¥{{ b.feeTotal }} · 我自己那份 ¥{{ b.myShare
              }}<template v-if="(b.myGuestCount ?? 0) > 0"
                >（含带来的朋友 ×{{ b.myGuestCount }}）</template
              >
            </view>
          </view>
        </template>
      </view>
      <EmptyBox v-if="!bill.rows.length" text="这段期间没有账单 · 换个筛法" />
    </template>

    <!-- A2 出错：断网提示 + 重试（已点成功的动作不丢——整树只在成功响应后换新） -->
    <view v-else class="ph retry" @click="refresh()"
      >账单没打开 · 点这里重试</view
    >
  </PageShell>
</template>

<script setup lang="ts">
/* 账单页（5.1 子页 · 1.3 批4）：真数据账单的主场。数据全在 bill store（后端定值直读，
   toast 在 store 内），本页只做筛选接线、行展开/导航、加载/出错/游客三态与动作兜底。 */
import { computed, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import PageShell from "@/components/biz/PageShell.vue";
import BackRow from "@/components/biz/BackRow.vue";
import BillSummaryCard from "@/components/biz/BillSummaryCard.vue";
import FilterChips from "@/components/ui/FilterChips.vue";
import EmptyBox from "@/components/ui/EmptyBox.vue";
import {
  useBillStore,
  BILL_STATUS_NAMES,
  PERIOD_OPTS,
  type BillPeriod,
} from "@/stores/bill";
import type { Bill, BillPayer, BillStatus } from "@/api/types";
import { errText } from "@/api/http";
import { useUiStore } from "@/stores/ui";
import { goGame } from "@/utils/nav";

const bill = useBillStore();
const ui = useUiStore();

/** 账单期（切换=重新 load，服务端过滤；BillPeriod 窄类型双向绑定） */
const period = computed<BillPeriod>({
  get: () => bill.period,
  set: (v) => {
    void refresh(v);
  },
});

/** A2 出错态：load 抛错（断网/未登录失效）→ 提示 + 重试入口 */
const failed = ref(false);

async function refresh(p: BillPeriod = bill.period): Promise<void> {
  failed.value = false;
  try {
    await bill.load(p);
  } catch (e) {
    failed.value = true;
    ui.toast(errText(e));
  }
}

onShow(() => {
  void refresh();
});

/** 游客态登录入口（4.9：演示数据照显，登录后换真账） */
function goLogin(): void {
  uni.navigateTo({ url: "/pages/mine/login" });
}

/** 行副标题：待付写明欠谁（4.1），其余只记散场那天；带了朋友加一行小字（5.1 小改①） */
function rowSub(b: Bill): string {
  const day = dayTxt(b.endedDay);
  return (b.kind === "payable" || b.kind === "paid") && b.payeeName
    ? `欠 ${b.payeeName} · ${day}`
    : day;
}

/** 'YYYY-MM-DD' → 'M.DD'（散场那天；账单日期口径与旧演示一致） */
function dayTxt(day: string): string {
  const [, m, d] = day.split("-");
  return `${Number(m)}.${d}`;
}

/** 行点击按态分类：应收/已收行行内展开按人明细（不跳页）；待付/已付行进原局页 */
const openId = ref<number | null>(null);
function expandable(b: Bill): boolean {
  return b.kind === "receivable" || b.kind === "received";
}
function tapBill(b: Bill): void {
  if (expandable(b)) openId.value = openId.value === b.gameId ? null : b.gameId;
  else goGame(b.gameId);
}

/** 金额状态色：待付→coral / 应收→lemon / 已付·已收→dim */
function amtCls(st: BillStatus): string {
  return st === "payable" ? "due" : st === "receivable" ? "rec" : "dim";
}
/** 已收→✓ 金额；应收行金额=未收合计（点一人少一笔，后端定值） */
function amtTxt(b: Bill): string {
  return b.kind === "received" ? `✓ ¥${b.amount}` : `¥${b.amount}`;
}

/** 两向记账动作：store 内调 API + 整树换新 + toast；失败原样抛，这里兜 toast */
function onSettle(b: Bill): void {
  bill.settleBill(b.gameId).catch((e) => ui.toast(errText(e)));
}
function onReceive(b: Bill, p: BillPayer): void {
  bill.receivePayer(b.gameId, p.accountId).catch((e) => ui.toast(errText(e)));
}
</script>

<style lang="scss" scoped>
/* ---------- 头部 brand：版式走全局 .brand 类，只补 700 加粗（mine 系约定） ---------- */
.brand {
  font-weight: 700;
}

/* 总览卡与逐笔列表之间的间距（卡本体样式在 BillSummaryCard） */
.trio-gap {
  margin-bottom: 6px;
}

/* ---------- 游客横幅（4.9：未登录 · 演示数据 + 登录入口） ---------- */
.demo-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin: 4px 0 10px;
  padding: 9px 12px;
  border: 1px dashed rgba(255, 212, 0, 0.35);
  border-radius: var(--r-lg);
  font-size: 11px;
  color: var(--dim);
}
.demo-link {
  color: var(--lemon);
  flex: none;
}

/* ---------- 费用未定提醒条（4.5：可点直达局页补填） ---------- */
.unfixed {
  margin: 8px 0;
  padding: 10px 12px;
  border: 1px solid rgba(255, 159, 67, 0.35);
  border-radius: var(--r-lg);
  font-size: 12px;
  color: var(--lemon);
  cursor: pointer;
}
.unfixed:active {
  border-color: rgba(255, 212, 0, 0.6);
}

/* ---------- 「谁还欠你」按人汇总（后端跨场聚合定值 + 期间说明小字常显） ---------- */
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

/* ---------- 逐笔行（上下边框分隔 · 左局名+副题｜右金额+状态） ---------- */
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
/* 两向灰字旗（4.3b/4.4）：只提示、不改态 */
.gray-flag {
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

/* ---------- 应收行展开区（视觉上属于该行——左缩进、无边框） ---------- */
.pays {
  padding: 4px 0 8px 14px;
}
.prow {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 2px;
}
.pcol {
  flex: 1;
  min-width: 0;
}
.pname {
  display: block;
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
/* 明细末行（4.2）：「总价 · 我自己那份」——组织者兜的零头不用自己心算 */
.psum {
  margin-top: 6px;
  padding-top: 7px;
  border-top: 1px dashed rgba(245, 241, 232, 0.12);
  font-family: var(--mono);
  font-size: 11px;
  color: var(--dim);
}
/* 未结的逐人「已收」小钮：复用 .tbtn.rec，行内收窄 */
.pbtn {
  padding: 5px 10px;
  font-size: 11px;
}

/* 行内动作小钮：基础形走全局 .tbtn（base.scss 收源）；收款 lemon 描边为本页私变体 */
.tbtn.rec {
  border-color: rgba(255, 212, 0, 0.5);
  color: var(--lemon);
}

/* ---------- 加载/出错占位（A2：3 秒内补上；出错可点重试） ---------- */
.ph {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--dim);
  padding: 40px 0;
  text-align: center;
}
.retry {
  cursor: pointer;
  text-decoration: underline;
}
</style>
