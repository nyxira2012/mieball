/* 账单 store（5.1 我的页：期间筛选 + 三数总览 + 结算/逐人收款）
   硬约束：动作只改状态与返回/弹出文案 —— 不做路由跳转、不直接调 uni.*（导航由页面层做）。 */
import { computed, reactive, ref } from 'vue';
import { defineStore } from 'pinia';
import { MOCK_BASE_DATE_STR, bills as seedBills } from '@/api';
import type { Bill, BillStatus, User } from '@/api/types';
import { dayOrd } from '@/utils/time';
import { useUiStore } from './ui';

/** 账单状态四态 ↔ 文案（枚举↔文案常量表，PART_NAMES 先例） */
export const BILL_STATUS_NAMES: Record<BillStatus, string> = { due: '待付', paid: '已付', receivable: '该收', received: '已收' };

export type BillPeriod = '7d' | '30d' | 'all';

/** 期间下界计算（含当天）：根据基准日期（mock 为 2026-10-04）动态推算 M.DD */
export function calcPeriodFrom(days: number, baseStr = MOCK_BASE_DATE_STR): string {
  const [y, m, d] = baseStr.split('-').map(Number);
  const dt = new Date(y, m - 1, d);
  dt.setDate(dt.getDate() - days);
  return `${dt.getMonth() + 1}.${String(dt.getDate()).padStart(2, '0')}`;
}

/** 期间下界（M.DD，含当天）：由基准日期动态计算推导，导出供 logs 页共用 */
export const PERIOD_FROM: Record<Exclude<BillPeriod, 'all'>, string> = {
  '7d': calcPeriodFrom(7),
  '30d': calcPeriodFrom(30),
};

/** 期间筛选项（bills/logs 两页 FilterChips 共用；label 与 PERIOD_FROM 的档位一一对应） */
export const PERIOD_OPTS: { value: BillPeriod; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: '7d', label: '近 7 天' },
  { value: '30d', label: '近 30 天' },
];

/** 按人明细加总：settled 选已收/未结——只加总数据侧给定的明细，不人均倒推（页面「已收 X / 共 Y」同用此口径） */
export function payerSum(b: Bill, settled: boolean): number {
  return b.payers?.filter((p) => p.settled === settled).reduce((s, p) => s + p.amt, 0) ?? 0;
}

/** 一行账单的三数金额：该收＝别人还没还的（未结加总，与 debtors 同源）；其余按 amt——口径收口在这一处 */
function amountOf(b: Bill): number {
  return b.status === 'receivable' ? payerSum(b, false) : b.amt;
}

/** 同状态行的三数求和（summary 走 filtered、totalSummary 走全量，同调此函数不出第二个口径） */
function sumBy(list: Bill[], st: BillStatus): number {
  return list.filter((b) => b.status === st).reduce((s, b) => s + amountOf(b), 0);
}

export const useBillStore = defineStore('bill', () => {
  /* 数据源：mock 的同一份可变引用，与 game store 同法（reactive 包装 seed） */
  const bills = reactive(seedBills);
  const period = ref<BillPeriod>('all');

  /** 按期间过滤后的逐笔列表（date 倒序由种子保序给出） */
  const filtered = computed<Bill[]>(() => {
    const from = period.value === 'all' ? null : PERIOD_FROM[period.value];
    return from ? bills.filter((b) => dayOrd(b.date) >= dayOrd(from)) : bills.slice();
  });

  /** 三数总览（基于 filtered）：received 已收讫不进三数 */
  const summary = computed(() => ({
    due: sumBy(filtered.value, 'due'),
    paid: sumBy(filtered.value, 'paid'),
    receivable: sumBy(filtered.value, 'receivable'),
  }));

  /** 全量三数（不随 period 漂移）：我的页账单卡、注销守卫等「永远看全部」的口径专用。
      period 是 pinia 单例跨页存活——账单页切过筛选后 filtered 会带着走，这两处不能消费 summary。 */
  const totalSummary = computed(() => ({
    due: sumBy(bills, 'due'),
    paid: sumBy(bills, 'paid'),
    receivable: sumBy(bills, 'receivable'),
  }));

  /** 「谁还欠你」按人汇总（5.1 修订）：从 filtered（与三数同口径）的 receivable 行聚合未结 payer——
      按 u.id 聚每人累计欠额与场数，数据侧明细的加总，不碰人均；amt 降序。 */
  const debtors = computed(() => {
    const map = new Map<number, { u: User; amt: number; n: number }>();
    filtered.value
      .filter((b) => b.status === 'receivable')
      .forEach((b) =>
        b.payers?.forEach((p) => {
          if (p.settled) return;
          const d = map.get(p.u.id) ?? { u: p.u, amt: 0, n: 0 };
          d.amt += p.amt;
          d.n += 1;
          map.set(p.u.id, d);
        }),
      );
    return [...map.values()].sort((a, b) => b.amt - a.amt);
  });

  /** 结算（5.1 辅助功能）：应付 → 已付；仅 due 行可结 */
  function settleBill(id: number): string | null {
    const b = bills.find((x) => x.id === id);
    if (!b || b.status !== 'due') return null;
    b.status = 'paid';
    const msg = '已结算 · 应付变已付';
    useUiStore().toast(msg);
    return msg;
  }

  /** 逐人清账（5.1 修订：整笔一键收款作废）：谁转了钱点谁名下「已收」——只对数据侧给好的
      payers 明细置位，不自算人均；一场局全部结清后整笔翻已收（received 态的运行期来源）。 */
  function receivePayer(billId: number, uid: number): string | null {
    const b = bills.find((x) => x.id === billId);
    const p = b?.status === 'receivable' ? b.payers?.find((x) => x.u.id === uid && !x.settled) : undefined;
    if (!b || !p) return null;
    p.settled = true;
    const allIn = b.payers!.every((x) => x.settled);
    if (allIn) b.status = 'received';
    const msg = allIn ? '已收讫 · 这场全结清' : `已收 ${p.u.name} 这笔`;
    useUiStore().toast(msg);
    return msg;
  }

  return { bills, period, filtered, summary, totalSummary, settleBill, receivePayer, debtors };
});
