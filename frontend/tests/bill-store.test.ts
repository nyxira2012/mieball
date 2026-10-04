import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { U } from '@/api/mock'; // 人名↔id 锚定（li=5、wu=3、bei=8…），比裸数字可读；id 是种子常量，resetModules 不变

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
  it('30d / all：应付 86 · 已付 120 · 该收 280（未结口径：bill2 li 100 + bill6 li/wu 各 90；种子已结行不算）', async () => {
    const s = await loadStore();
    s.period = '30d';
    expect(s.summary).toEqual({ due: 86, paid: 120, receivable: 280 });
    s.period = 'all';
    expect(s.summary).toEqual({ due: 86, paid: 120, receivable: 280 });
    // 同源锚：该收三数 === Σ debtors.amt（同一份未结明细的两种加总方向）
    expect(s.summary.receivable).toBe(s.debtors.reduce((t, d) => t + d.amt, 0));
  });

  it('7d：只剩 10.02/10.01 两笔 → 应付 45 · 已付 0 · 该收 100（bill2 li 未结）', async () => {
    const s = await loadStore();
    s.period = '7d';
    expect(s.summary).toEqual({ due: 45, paid: 0, receivable: 100 });
  });
});

describe('settle 状态迁移（due→paid）', () => {
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
});

describe('receivePayer 逐人清账（5.1 修订：整笔一键收款作废）', () => {
  it('部分结清不翻整笔：msg 报到人，行仍 receivable，该收只减他那份', async () => {
    const s = await loadStore();
    const msg = s.receivePayer(6, U.wu.id); // bill6 未结：li/wu
    expect(msg).toBe(`已收 ${U.wu.name} 这笔`);
    expect(s.bills.find((b) => b.id === 6)?.status).toBe('receivable');
    expect(s.summary.receivable).toBe(190); // 280 − 90（wu 结了）
  });

  it('全清翻整笔：最后一人收掉 → 行落 received（received 态的运行期来源）', async () => {
    const s = await loadStore();
    const msg = s.receivePayer(2, U.li.id); // bill2 仅剩 li 未结
    expect(msg).toBe('已收讫 · 这场全结清');
    expect(s.bills.find((b) => b.id === 2)?.status).toBe('received');
    expect(s.summary.receivable).toBe(180); // 独立 store 实例从种子起算：只剩 bill6 的 li+wu 未结
  });

  it('已结再收 → null；对 due/paid 行收 → null', async () => {
    const s = await loadStore();
    expect(s.receivePayer(6, U.bei.id)).toBeNull(); // bei 已结，不重复收
    expect(s.receivePayer(1, U.hai.id)).toBeNull(); // due 行无按人明细
    expect(s.receivePayer(3, U.wang.id)).toBeNull(); // paid 行
  });
});

describe('debtors「谁还欠你」（filtered 同口径，按人聚合未结 payer，amt 降序）', () => {
  it('all：li 190·2场（bill2+bill6 同人聚合）· wu 90·1场', async () => {
    const s = await loadStore();
    expect(s.debtors).toEqual([
      { u: U.li, amt: 190, n: 2 },
      { u: U.wu, amt: 90, n: 1 },
    ]);
  });

  it('7d：bill6 被筛掉 → 只剩 li 100·1场', async () => {
    const s = await loadStore();
    s.period = '7d';
    expect(s.debtors).toEqual([{ u: U.li, amt: 100, n: 1 }]);
  });

  it('结清后移出：收掉 bill2 的 li 与 bill6 的 wu、li → debtors 空', async () => {
    const s = await loadStore();
    s.receivePayer(2, U.li.id);
    s.receivePayer(6, U.wu.id);
    s.receivePayer(6, U.li.id); // bill6 最后一笔 → 整笔翻 received
    expect(s.debtors).toEqual([]);
  });
});
