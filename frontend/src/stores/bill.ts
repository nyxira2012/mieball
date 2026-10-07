/* 账单 store（1.3 批4 读链切真）：真后端 BillsView 的前端业务态。
   - 游客/未登录回落演示视图（4.9）：isDemo 旗给账单页挂「未登录 · 以下是演示数据」横幅；
   - 登录用户 load 失败不吞——抛给页面（A2 出错态：toast + 重试）；
   - 三数/rows/debtors/unfixed 全部直读后端定值（A4：界面不自算），期间切换=重新 load；
   - settle/receive 调后端、响应直出最新视图整树换（「应收与按人明细同一个数」单点保证；
     确认问句/在途防双击在 bills.vue 本地确认槽——store 只管落账与 toast，失败原样上抛）；
   硬约束不变：动作只改状态与弹出文案 —— 不做路由跳转、不直接调 uni.*。 */
import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { apiBillReceive, apiBillSettle, apiBills } from "@/api/bills";
import { demoBillsView, MOCK_BASE_DATE_STR } from "@/api/mock";
import type { Bill, BillStatus, BillsView, BillsViewApi } from "@/api/types";
import { useSessionStore } from "./session";
import { useUiStore } from "./ui";

/** 账单状态四态 ↔ 文案（5.1 小改②：「该收」改「应收」；枚举↔文案常量表） */
export const BILL_STATUS_NAMES: Record<BillStatus, string> = {
  payable: "待付",
  paid: "已付",
  receivable: "应收",
  received: "已收",
};

export type BillPeriod = "7d" | "30d" | "all";

/** 期间下界计算（含当天）：根据基准日期（mock 为 2026-10-04）动态推算 M.DD。
    模块私有（N2：导出零外部消费方——logs 只吃 PERIOD_FROM/PERIOD_OPTS），
    PERIOD_FROM 专用；记录页的期间语义是 mock 快照域，与账单真数据无关 */
function calcPeriodFrom(days: number, baseStr = MOCK_BASE_DATE_STR): string {
  const [y, m, d] = baseStr.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  dt.setDate(dt.getDate() - days);
  return `${dt.getMonth() + 1}.${String(dt.getDate()).padStart(2, "0")}`;
}

/** 期间下界（M.DD，含当天）：导出供 logs 页共用 */
export const PERIOD_FROM: Record<Exclude<BillPeriod, "all">, string> = {
  "7d": calcPeriodFrom(7),
  "30d": calcPeriodFrom(30),
};

/** 期间筛选项（bills/logs 两页 FilterChips 共用；后端同名枚举，账单页切换=重新 load） */
export const PERIOD_OPTS: { value: BillPeriod; label: string }[] = [
  { value: "all", label: "全部" },
  { value: "7d", label: "近 7 天" },
  { value: "30d", label: "近 30 天" },
];

const ZERO_SUMMARY = { due: 0, paid: 0, receivable: 0 };

/** BillsViewApi（线上 snake）→ BillsView（camel）：唯一映射点 */
function toBillView(v: BillsViewApi): BillsView {
  return {
    period: v.period,
    summary: { ...v.summary },
    rows: v.rows.map((r) => ({
      kind: r.kind,
      gameId: r.game_id,
      gameName: r.game_name,
      endedDay: r.ended_day,
      amount: r.amount,
      guestCount: r.guest_count,
      payeeName: r.payee_name,
      payeeDeactivated: r.payee_deactivated,
      peerReceived: r.peer_received,
      feeTotal: r.fee_total,
      myShare: r.my_share,
      myGuestCount: r.my_guest_count,
      payerRows: r.payer_rows?.map((p) => ({
        accountId: p.account_id,
        name: p.name,
        deactivated: p.deactivated,
        amount: p.amount,
        guestCount: p.guest_count,
        paidAt: p.paid_at,
        receivedAt: p.received_at,
      })),
    })),
    debtors: v.debtors.map((d) => ({
      accountId: d.account_id,
      name: d.name,
      deactivated: d.deactivated,
      total: d.total,
      games: d.games,
    })),
    unfixed: v.unfixed.map((u) => ({
      gameId: u.game_id,
      gameName: u.game_name,
      endedDay: u.ended_day,
    })),
  };
}

export const useBillStore = defineStore("bill", () => {
  const session = useSessionStore();
  const ui = useUiStore();

  const period = ref<BillPeriod>("all");
  const view = ref<BillsView | null>(null);
  /** 全量口径（period=all 定值）：我的页账单卡、注销守卫「永远看全部」专用——
      period 是 pinia 单例跨页存活，这两处不能消费随筛选漂的 summary */
  const total = ref<BillsView | null>(null);
  const loading = ref(false);

  /** 演示态（游客/钥匙失效）：回落演示视图；动作只提示不调后端（4.9 假数字标明） */
  const isDemo = computed(() => session.isGuest);

  /** 三数（随 period，后端定值）；未加载/加载失败回落 0（页面负责出错重试） */
  const summary = computed(() => view.value?.summary ?? ZERO_SUMMARY);
  const totalSummary = computed(() => total.value?.summary ?? ZERO_SUMMARY);
  const rows = computed<Bill[]>(() => view.value?.rows ?? []);
  const debtors = computed(() => view.value?.debtors ?? []);
  const unfixed = computed(() => view.value?.unfixed ?? []);

  function demoTree(): void {
    view.value = demoBillsView;
    total.value = demoBillsView;
  }

  /** 账单页主加载（期间切换即换档重拉；演示态不发起请求） */
  async function load(p: BillPeriod = period.value): Promise<void> {
    period.value = p;
    if (isDemo.value) {
      demoTree();
      return;
    }
    loading.value = true;
    try {
      view.value = toBillView(await apiBills(p));
    } finally {
      loading.value = false;
    }
  }

  /** 全量三数（我的页/注销守卫）；失败上抛由调用方静默兜底 */
  async function loadTotal(): Promise<void> {
    if (isDemo.value) {
      total.value = demoBillsView;
      return;
    }
    total.value = toBillView(await apiBills("all"));
  }

  /** 点「结算」（4.3）：自己那行 paid_at 置位，终态不可逆（确认步在 bills.vue），重放幂等 */
  async function settleBill(gameId: number): Promise<void> {
    if (isDemo.value) {
      ui.toast("演示数据 · 登录后才能记真账");
      return;
    }
    view.value = toBillView(await apiBillSettle(gameId, period.value));
    ui.toast("已结算 · 应付变已付");
  }

  /** 逐人点「已收」（4.4）：该行 received_at 置位，终态不可逆——最后一人收掉整笔
      自动翻已收（后端推导，无 0 元行），toast 按整笔/单人分支 */
  async function receivePayer(
    gameId: number,
    accountId: number,
  ): Promise<void> {
    if (isDemo.value) {
      ui.toast("演示数据 · 登录后才能记真账");
      return;
    }
    const name = rows.value
      .find((r) => r.gameId === gameId)
      ?.payerRows?.find((p) => p.accountId === accountId)?.name;
    view.value = toBillView(
      await apiBillReceive(gameId, accountId, period.value),
    );
    const row = view.value.rows.find((r) => r.gameId === gameId);
    ui.toast(
      row?.kind === "received"
        ? "已收讫 · 这场全结清"
        : `已收 ${name ?? "球友"} 这笔`,
    );
  }

  return {
    period,
    view,
    loading,
    isDemo,
    summary,
    totalSummary,
    rows,
    debtors,
    unfixed,
    load,
    loadTotal,
    settleBill,
    receivePayer,
  };
});
