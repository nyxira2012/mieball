/* 账单 store（5.1 我的页：期间筛选 + 三数总览 + 结算/收讫）
   硬约束：动作只改状态与返回/弹出文案 —— 不做路由跳转、不直接调 uni.*（导航由页面层做）。 */
import { computed, reactive, ref } from 'vue';
import { defineStore } from 'pinia';
import { bills as seedBills } from '@/api';
import type { Bill, BillStatus } from '@/api/types';
import { dayOrd } from '@/utils/time';
import { useUiStore } from './ui';

/** 账单状态四态 ↔ 文案（枚举↔文案常量表，PART_NAMES 先例） */
export const BILL_STATUS_NAMES: Record<BillStatus, string> = { due: '待付', paid: '已付', receivable: '该收', received: '已收' };

export type BillPeriod = '7d' | '30d' | 'all';

/* 期间下界（M.DD，含当天）：今天=2026-10-04 → 近 7 天自 9.27、近 30 天自 9.04。
   mock 无真实时钟，与 data.ts 的日期硬编码同源口径；'all' 不过滤。 */
const PERIOD_FROM: Record<Exclude<BillPeriod, 'all'>, string> = { '7d': '9.27', '30d': '9.04' };

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
    due: sumBy('due'),
    paid: sumBy('paid'),
    receivable: sumBy('receivable'),
  }));
  function sumBy(st: BillStatus): number {
    return filtered.value.filter((b) => b.status === st).reduce((s, b) => s + b.amt, 0);
  }

  /** 全量三数（不随 period 漂移）：我的页账单卡、注销守卫等「永远看全部」的口径专用。
      period 是 pinia 单例跨页存活——账单页切过筛选后 filtered 会带着走，这两处不能消费 summary。 */
  const totalSummary = computed(() => {
    const by = (st: BillStatus) => bills.filter((b) => b.status === st).reduce((s, b) => s + b.amt, 0);
    return { due: by('due'), paid: by('paid'), receivable: by('receivable') };
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

  /** 收讫（5.1 辅助功能）：该收 → 已收；receivable 仅组织者垫付行（mock 口径：参与者不存在垫付） */
  function receiveBill(id: number): string | null {
    const b = bills.find((x) => x.id === id);
    if (!b || b.status !== 'receivable') return null;
    b.status = 'received';
    const msg = '已收讫 · 该收变已收';
    useUiStore().toast(msg);
    return msg;
  }

  return { bills, period, filtered, summary, totalSummary, settleBill, receiveBill };
});
