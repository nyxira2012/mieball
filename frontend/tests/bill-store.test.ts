import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';

/* 每个用例 vi.resetModules() 重新求值模块图 → 拿到全新 mock 数据（等价 alpha 刷新页面） */
beforeEach(async () => {
  vi.resetModules();
  setActivePinia(createPinia());
});

async function loadStore() {
  const mod = await import('@/stores/bill');
  return mod.useBillStore();
}

describe('期间过滤（今日=2026-10-04：7d 自 9.27、30d 自 9.04，边界当天含）', () => {
  it('默认 all：种子 6 笔全在，倒序即种子顺序', async () => {
    const s = await loadStore();
    expect(s.period).toBe('all');
    expect(s.filtered.map((b) => b.id)).toEqual([1, 2, 3, 4, 5, 6]);
  });

  it('7d：10.01/10.02 两笔；9.26 不含、9.27 当天含（>= 边界）', async () => {
    const s = await loadStore();
    s.period = '7d';
    expect(s.filtered.map((b) => b.id)).toEqual([1, 2]);
    s.bills.push(
      { id: 91, gameId: 0, gname: '边界当天', date: '9.27', amt: 1, status: 'paid', role: 'member' },
      { id: 92, gameId: 0, gname: '边界前一天', date: '9.26', amt: 1, status: 'paid', role: 'member' },
    );
    const ids = s.filtered.map((b) => b.id);
    expect(ids).toContain(91);
    expect(ids).not.toContain(92);
  });

  it('30d：种子 6 笔全在；9.04 当天含、9.03 不含', async () => {
    const s = await loadStore();
    s.period = '30d';
    expect(s.filtered.map((b) => b.id)).toEqual([1, 2, 3, 4, 5, 6]);
    s.bills.push(
      { id: 91, gameId: 0, gname: '边界当天', date: '9.04', amt: 1, status: 'paid', role: 'member' },
      { id: 92, gameId: 0, gname: '边界前一天', date: '9.03', amt: 1, status: 'paid', role: 'member' },
    );
    const ids = s.filtered.map((b) => b.id);
    expect(ids).toContain(91);
    expect(ids).not.toContain(92);
  });
});

describe('三数总览 summary（基于 filtered，received 不进三数）', () => {
  it('30d / all：应付 86 · 已付 120 · 该收 200（已收 720 不计入）', async () => {
    const s = await loadStore();
    s.period = '30d';
    expect(s.summary).toEqual({ due: 86, paid: 120, receivable: 200 });
    s.period = 'all';
    expect(s.summary).toEqual({ due: 86, paid: 120, receivable: 200 });
  });

  it('7d：只剩 10.02/10.01 两笔 → 应付 45 · 已付 0 · 该收 200', async () => {
    const s = await loadStore();
    s.period = '7d';
    expect(s.summary).toEqual({ due: 45, paid: 0, receivable: 200 });
  });
});

describe('settle / receive 状态迁移（due→paid · receivable→received）', () => {
  it('settle due 行：状态落 paid，三数随之此消彼长', async () => {
    const s = await loadStore();
    const msg = s.settleBill(1); // 10.02 待付 45
    expect(msg).toBe('已结算 · 应付变已付');
    expect(s.bills.find((b) => b.id === 1)?.status).toBe('paid');
    expect(s.summary.due).toBe(41); // 86 − 45
    expect(s.summary.paid).toBe(165); // 120 + 45
  });

  it('settle 非 due 行 → null 且状态不动', async () => {
    const s = await loadStore();
    expect(s.settleBill(2)).toBeNull(); // receivable
    expect(s.settleBill(3)).toBeNull(); // paid
    expect(s.bills.find((b) => b.id === 2)?.status).toBe('receivable');
  });

  it('receive 该收行：状态落 received，该收归零', async () => {
    const s = await loadStore();
    const msg = s.receiveBill(2); // 10.01 该收 200（我垫付）
    expect(msg).toBe('已收讫 · 该收变已收');
    expect(s.bills.find((b) => b.id === 2)?.status).toBe('received');
    expect(s.summary.receivable).toBe(0);
  });

  it('receive 非 receivable 行 → null', async () => {
    const s = await loadStore();
    expect(s.receiveBill(1)).toBeNull(); // due
    expect(s.receiveBill(6)).toBeNull(); // received
  });
});
