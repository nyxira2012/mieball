import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import type { BillPayerApi, BillsViewApi, BillRowApi } from "@/api/types";
import { demoBillsView } from "@/api/mock";
import { ApiError } from "@/api/http";

/* 1.3 批4 切真重写：bill store 动作全是真接口调用——api 层整体 mock，用例喂 crafted
   BillsViewApi（形状与后端 bills.py view 输出逐字对齐），测的是游客回落演示（4.9）、
   snake→camel 映射、三数/rows/debtors 定值直读（A4）、期间切换重拉与两向记账整树换。 */
const api = vi.hoisted(() => ({
  apiBills: vi.fn(),
  apiBillSettle: vi.fn(),
  apiBillReceive: vi.fn(),
}));

vi.mock("@/api/bills", () => api);

beforeEach(() => {
  vi.clearAllMocks();
  vi.resetModules();
  setActivePinia(createPinia());
});

async function loadStore() {
  const mod = await import("@/stores/bill");
  return {
    store: mod.useBillStore(),
    session: (await import("@/stores/session")).useSessionStore(),
    ui: (await import("@/stores/ui")).useUiStore(),
  };
}

/* ---- BillsViewApi 造数（线上 snake 形状） ---- */
let seq = 0;
function mkRow(p: Partial<BillRowApi> = {}): BillRowApi {
  seq += 1;
  return {
    kind: "payable",
    game_id: seq,
    game_name: `测试局 ${seq}`,
    ended_day: "2026-10-01",
    amount: 58,
    payee_name: "朝阳反手王",
    payee_deactivated: false,
    peer_received: false,
    ...p,
  };
}

function mkPayer(p: Partial<BillPayerApi> = {}): BillPayerApi {
  return {
    account_id: 5,
    name: "小赵",
    deactivated: false,
    amount: 58,
    guest_count: 0,
    paid_at: null,
    received_at: null,
    ...p,
  };
}

function mkView(p: Partial<BillsViewApi> = {}): BillsViewApi {
  return {
    period: "all",
    summary: { due: 58, paid: 0, receivable: 0 },
    rows: [mkRow()],
    debtors: [],
    unfixed: [],
    ...p,
  };
}

describe("游客回落演示（4.9：未登录 · 演示数据，不冒充真账）", () => {
  it("load 不发请求：view=演示视图、isDemo 亮、total 同源", async () => {
    const { store } = await loadStore();
    await store.load();
    expect(api.apiBills).not.toHaveBeenCalled();
    expect(store.isDemo).toBe(true);
    expect(store.view?.rows).toHaveLength(demoBillsView.rows.length);
    expect(store.rows[0]?.gameName).toBe("周五夜光局");
    expect(store.summary).toEqual(demoBillsView.summary);
    expect(store.debtors).toEqual(demoBillsView.debtors);
    expect(store.unfixed).toEqual(demoBillsView.unfixed);
    expect(store.totalSummary).toEqual(demoBillsView.summary);
  });

  it("演示态点结算/已收：只提示引导登录，不调 API", async () => {
    const { store, ui } = await loadStore();
    await store.load();
    await store.settleBill(98);
    await store.receivePayer(97, 5);
    expect(api.apiBillSettle).not.toHaveBeenCalled();
    expect(api.apiBillReceive).not.toHaveBeenCalled();
    expect(ui.toastMsg).toBe("演示数据 · 登录后才能记真账");
  });
});

describe("登录读链（三数/rows/debtors 直读定值，A4）", () => {
  it("load 拉 apiBills：snake→camel 映射抽查 + period 回带", async () => {
    api.apiBills.mockResolvedValue(
      mkView({
        period: "7d",
        summary: { due: 174, paid: 0, receivable: 638 },
        rows: [
          mkRow({
            kind: "payable",
            game_id: 9,
            amount: 174,
            guest_count: 2,
            peer_received: true,
          }),
          mkRow({
            kind: "receivable",
            game_id: 8,
            ended_day: "2026-09-30",
            amount: 638,
            fee_total: 700,
            my_share: 62,
            my_guest_count: 0,
            payer_rows: [mkPayer({ paid_at: "2026-10-01T20:00:00+08:00" })],
          }),
        ],
        debtors: [
          {
            account_id: 5,
            name: "小赵",
            deactivated: false,
            total: 638,
            games: 1,
          },
        ],
        unfixed: [
          { game_id: 7, game_name: "周三夜战", ended_day: "2026-09-28" },
        ],
      }),
    );
    const { store, session } = await loadStore();
    session.status = "ready"; // 登录态
    await store.load("7d");
    expect(api.apiBills).toHaveBeenCalledWith("7d");
    expect(store.isDemo).toBe(false);
    expect(store.summary).toEqual({ due: 174, paid: 0, receivable: 638 });
    const pay = store.rows[0]!;
    expect(pay.gameId).toBe(9);
    expect(pay.guestCount).toBe(2); // 「含带来的朋友 ×2」
    expect(pay.peerReceived).toBe(true); // 「对方已收款」灰字旗
    const rec = store.rows[1]!;
    expect(rec.payerRows?.[0]).toEqual({
      accountId: 5,
      name: "小赵",
      deactivated: false,
      amount: 58,
      guestCount: 0,
      paidAt: "2026-10-01T20:00:00+08:00", // 「已转 · 待收」的数据半边
      receivedAt: null,
    });
    expect(rec.myShare).toBe(62); // 明细末行「总价 · 我自己那份」
    expect(store.debtors).toEqual([
      { accountId: 5, name: "小赵", deactivated: false, total: 638, games: 1 },
    ]);
    expect(store.unfixed).toEqual([
      { gameId: 7, gameName: "周三夜战", endedDay: "2026-09-28" },
    ]);
  });

  it("期间切换=重新 load（服务端过滤，不自算）", async () => {
    api.apiBills.mockResolvedValue(mkView());
    const { store, session } = await loadStore();
    session.status = "ready";
    await store.load("all");
    await store.load("30d");
    expect(api.apiBills).toHaveBeenLastCalledWith("30d");
    expect(store.period).toBe("30d");
  });

  it("load 失败不吞：原样上抛给页面（A2 出错态），loading 复位", async () => {
    api.apiBills.mockRejectedValue(new Error("网络不给力，请稍后再试"));
    const { store, session } = await loadStore();
    session.status = "ready";
    await expect(store.load()).rejects.toThrow("网络不给力，请稍后再试");
    expect(store.loading).toBe(false);
  });

  it("loadTotal 全量口径：恒拉 all，与随筛选漂的 summary 分开", async () => {
    api.apiBills.mockImplementation(async (p: string) =>
      mkView({
        period: p as "7d" | "30d" | "all",
        summary:
          p === "all"
            ? { due: 999, paid: 0, receivable: 321 }
            : { due: 1, paid: 0, receivable: 0 },
      }),
    );
    const { store, session } = await loadStore();
    session.status = "ready";
    await store.load("7d");
    await store.loadTotal();
    expect(api.apiBills).toHaveBeenLastCalledWith("all");
    expect(store.summary.due).toBe(1); // 账单页卡随筛选
    expect(store.totalSummary.due).toBe(999); // 我的页卡/注销守卫看全部
    expect(store.totalSummary.receivable).toBe(321); // 注销双检（1.3 §4.8）：没收完的应收也在全量口径
  });
});

describe("N2 化石清理：calcPeriodFrom 零外部消费，收归模块私有", () => {
  it("模块出口不再含 calcPeriodFrom；PERIOD_FROM/PERIOD_OPTS 仍导出（logs 页契约）", async () => {
    const mod = await import("@/stores/bill");
    expect(Object.keys(mod)).not.toContain("calcPeriodFrom");
    expect(Object.keys(mod)).toEqual(
      expect.arrayContaining(["PERIOD_FROM", "PERIOD_OPTS"]),
    );
  });
});

describe("settle / receive（调 API + 响应整树换新）", () => {
  it("settleBill：带当前档调 API，视图整体替换 + toast", async () => {
    const { store, ui, session } = await loadStore();
    session.status = "ready";
    await store.load("7d");
    api.apiBills.mockResolvedValue(mkView({ period: "7d" }));
    api.apiBillSettle.mockResolvedValue(
      mkView({ period: "7d", summary: { due: 0, paid: 58, receivable: 0 } }),
    );
    await store.settleBill(seq);
    expect(api.apiBillSettle).toHaveBeenCalledWith(seq, "7d");
    expect(store.summary).toEqual({ due: 0, paid: 58, receivable: 0 });
    expect(ui.toastMsg).toBe("已结算 · 应付变已付");
  });

  it("receivePayer 单人未收完：toast 报到人；收完最后一笔：整笔翻已收文案", async () => {
    const { store, ui, session } = await loadStore();
    session.status = "ready";
    api.apiBills.mockResolvedValue(
      mkView({
        summary: { due: 0, paid: 0, receivable: 116 },
        rows: [
          mkRow({
            kind: "receivable",
            game_id: 42,
            amount: 116,
            payer_rows: [
              mkPayer({ account_id: 5, name: "小赵", amount: 58 }),
              mkPayer({ account_id: 6, name: "小张", amount: 58 }),
            ],
          }),
        ],
        debtors: [
          {
            account_id: 5,
            name: "小赵",
            deactivated: false,
            total: 116,
            games: 1,
          },
        ],
      }),
    );
    await store.load("all");

    api.apiBillReceive.mockResolvedValue(
      mkView({
        summary: { due: 0, paid: 0, receivable: 58 },
        rows: [
          mkRow({
            kind: "receivable",
            game_id: 42,
            amount: 58,
            payer_rows: [
              mkPayer({
                account_id: 5,
                name: "小赵",
                received_at: "2026-10-02T09:00:00+08:00",
              }),
              mkPayer({ account_id: 6, name: "小张", amount: 58 }),
            ],
          }),
        ],
        debtors: [],
      }),
    );
    await store.receivePayer(42, 5);
    expect(api.apiBillReceive).toHaveBeenCalledWith(42, 5, "all");
    expect(ui.toastMsg).toBe("已收 小赵 这笔");
    expect(store.summary.receivable).toBe(58); // 点一个人少一笔（后端定值）

    api.apiBillReceive.mockResolvedValue(
      mkView({
        summary: { due: 0, paid: 0, receivable: 0 },
        rows: [
          mkRow({
            kind: "received",
            game_id: 42,
            amount: 116,
            payer_rows: [
              mkPayer({
                account_id: 5,
                name: "小赵",
                received_at: "2026-10-02T09:00:00+08:00",
              }),
              mkPayer({
                account_id: 6,
                name: "小张",
                amount: 58,
                received_at: "2026-10-02T10:00:00+08:00",
              }),
            ],
          }),
        ],
        debtors: [],
      }),
    );
    await store.receivePayer(42, 6);
    expect(ui.toastMsg).toBe("已收讫 · 这场全结清");
    expect(store.rows[0]?.kind).toBe("received"); // 整笔翻已收（不占三数，翻旧账仍在）
    expect(store.summary.receivable).toBe(0);
  });

  it("动作失败原样上抛（页面兜 toast），视图不动", async () => {
    const { store, session } = await loadStore();
    session.status = "ready";
    api.apiBills.mockResolvedValue(mkView());
    await store.load();
    const before = store.view;
    api.apiBillSettle.mockRejectedValue(new Error("网络不给力，请稍后再试"));
    await expect(store.settleBill(seq)).rejects.toThrow(
      "网络不给力，请稍后再试",
    );
    expect(store.view).toBe(before); // 失败不换树
  });

  it("receive 断网（4.10）：真实 ApiError 形状上抛、文案 spec 逐字（errText 直出）、视图不动可重试", async () => {
    const { store, session } = await loadStore();
    session.status = "ready";
    api.apiBills.mockResolvedValue(mkView());
    await store.load();
    const before = store.view;
    // http.ts 断网路抛 ApiError("network", …)，页面 catch 里 errText(e) 原样进 toast
    api.apiBillReceive.mockRejectedValue(
      new ApiError("network", "网络不给力，请稍后再试"),
    );
    await expect(store.receivePayer(seq, 5)).rejects.toThrow(
      "网络不给力，请稍后再试",
    );
    expect(store.view).toBe(before); // 行状态不变，确认层留着可重试
  });
});
