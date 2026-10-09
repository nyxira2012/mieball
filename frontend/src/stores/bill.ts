/* 账单 store（1.3 批4 读链切真）：真后端 BillsView 的前端业务态。
   - 游客/未登录：无账可看——空视图（三数 0 / 空列表），账单页挂「未登录」横幅带登录
     入口（mock 演示账单已随演示世界退役，2026-10-10）；
   - 登录用户 load 失败不吞——抛给页面（A2 出错态：toast + 重试）；
   - 三数/rows/debtors/unfixed 全部直读后端定值（A4：界面不自算），期间切换=重新 load；
   - settle/receive 调后端、响应直出最新视图整树换（「应收与按人明细同一个数」单点保证；
     确认问句/在途防双击在 bills.vue 本地确认槽——store 只管落账与 toast，失败原样上抛）；
   硬约束不变：动作只改状态与弹出文案 —— 不做路由跳转、不直接调 uni.*。 */
import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { apiBillReceive, apiBillSettle, apiBills } from "@/api/bills";
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

/** 期间下界（Date，含当天）：按当下墙钟推算——记录页（logs）与账单页共用档位；
    原以 mock 基准日（2026-10-04）推算，随演示快照退役改真钟 */
const PERIOD_DAYS: Record<Exclude<BillPeriod, "all">, number> = {
  "7d": 7,
  "30d": 30,
};

export function periodFrom(
  p: Exclude<BillPeriod, "all">,
  now: Date = new Date(),
): Date {
  const d = new Date(now);
  d.setDate(d.getDate() - PERIOD_DAYS[p]);
  return d;
}

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

  /** 未登录（游客/钥匙失效）：无账可看，空视图 + 账单页登录横幅；动作只提示不调后端 */
  const isDemo = computed(() => session.isGuest);

  /** 三数（随 period，后端定值）；未加载/加载失败回落 0（页面负责出错重试） */
  const summary = computed(() => view.value?.summary ?? ZERO_SUMMARY);
  const totalSummary = computed(() => total.value?.summary ?? ZERO_SUMMARY);
  const rows = computed<Bill[]>(() => view.value?.rows ?? []);
  const debtors = computed(() => view.value?.debtors ?? []);
  const unfixed = computed(() => view.value?.unfixed ?? []);

  /** 账单页主加载（期间切换即换档重拉；未登录不发请求——空视图自持） */
  async function load(p: BillPeriod = period.value): Promise<void> {
    period.value = p;
    if (isDemo.value) {
      view.value = null;
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
      total.value = null;
      return;
    }
    total.value = toBillView(await apiBills("all"));
  }

  /** 点「结算」（4.3）：自己那行 paid_at 置位，终态不可逆（确认步在 bills.vue），重放幂等 */
  async function settleBill(gameId: number): Promise<void> {
    if (isDemo.value) {
      ui.toast("登录后才能记真账");
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
      ui.toast("登录后才能记真账");
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
