/* wechat utils（1.7 微信钥匙浏览器侧工具）单测：环境探测 / 转场包 / 落点导航 /
   出发编排。uni 存储与 getCurrentPages 用 stub 全局换装（node 环境没有）；
   api/auth 整体 mock（不触网）。 */
import { beforeEach, describe, expect, it, vi } from "vitest";

const authApi = vi.hoisted(() => ({ apiWechatUrl: vi.fn() }));

vi.mock("@/api/auth", () => authApi);

import {
  backPathForAuth,
  beginWechatAuth,
  clearWechatCtx,
  ctxFresh,
  genState,
  isWeChatBrowser,
  navToPath,
  readWechatCtx,
  saveWechatCtx,
} from "@/utils/wechat";

/* uni 存读写假实现（内存 map） */
function stubUni() {
  const store = new Map<string, unknown>();
  vi.stubGlobal("uni", {
    setStorageSync: (k: string, v: unknown) => store.set(k, v),
    getStorageSync: (k: string) => (store.has(k) ? store.get(k) : ""),
    removeStorageSync: (k: string) => store.delete(k),
    switchTab: vi.fn(),
    redirectTo: vi.fn(),
  });
  return store;
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
  stubUni();
});

describe("isWeChatBrowser（微信内置浏览器探测）", () => {
  it("UA 带 MicroMessenger → true", () => {
    vi.stubGlobal("navigator", {
      userAgent: "Mozilla/5.0 ... MicroMessenger/8.0.49",
    });
    expect(isWeChatBrowser()).toBe(true);
  });
  it("普通浏览器 / 无 navigator → false", () => {
    vi.stubGlobal("navigator", { userAgent: "Mozilla/5.0 Chrome/129" });
    expect(isWeChatBrowser()).toBe(false);
  });
});

describe("转场包（跳微信往返的本机存取）", () => {
  it("存取清一圈：save → read 回原样 → clear 后读空", () => {
    const ctx = {
      state: "s1",
      back: "/pages/detail/detail?id=5",
      ts: Date.now(),
    };
    saveWechatCtx(ctx);
    expect(readWechatCtx()).toEqual(ctx);
    clearWechatCtx();
    expect(readWechatCtx()).toBeNull();
  });
  it("ctxFresh：记号对且十分钟内才新鲜", () => {
    const ctx = { state: "s1", back: "/pages/meet/meet", ts: Date.now() };
    expect(ctxFresh(ctx, "s1")).toBe(true);
    expect(ctxFresh(ctx, "s2")).toBe(false); // 记号不符（防顶替）
    expect(ctxFresh(null, "s1")).toBe(false);
    expect(ctxFresh({ ...ctx, ts: Date.now() - 11 * 60_000 }, "s1")).toBe(
      false,
    ); // 超十分钟
  });
  it("genState：两次不重样", () => {
    expect(genState()).not.toBe(genState());
  });
  it("快进位（1.8）：fast 随包存取；新鲜度只看记号+时刻，与快进位无关", () => {
    const ctx = {
      state: "s1",
      back: "/pages/detail/detail?id=5",
      fast: true,
      ts: Date.now(),
    };
    saveWechatCtx(ctx);
    expect(readWechatCtx()).toEqual(ctx);
    expect(ctxFresh(readWechatCtx(), "s1")).toBe(true); // 带快进位的包照常过双闸
    expect(ctxFresh({ ...ctx, ts: Date.now() - 11 * 60_000 }, "s1")).toBe(
      false,
    ); // 超十分钟照旧不认
    clearWechatCtx();
    expect(readWechatCtx()).toBeNull();
  });
});

describe("落点（backPathForAuth / navToPath）", () => {
  it("栈里有两层 → 回到带来登录页的那层（带查询串）", () => {
    vi.stubGlobal(
      "getCurrentPages",
      () =>
        [
          { route: "pages/meet/meet", options: {} },
          { route: "pages/detail/detail", options: { id: "7" } },
          { route: "pages/mine/login", options: {} },
        ] as never[],
    );
    expect(backPathForAuth()).toBe("/pages/detail/detail?id=7");
  });
  it("栈顶不是登录页（名片卡上的微信键）→ 栈顶即宿主页，回它自己", () => {
    vi.stubGlobal(
      "getCurrentPages",
      () =>
        [
          { route: "pages/meet/meet", options: {} },
          { route: "pages/detail/detail", options: { id: "9" } },
        ] as never[],
    );
    expect(backPathForAuth()).toBe("/pages/detail/detail?id=9");
  });
  it("名片卡开在 tab 页（栈只有一层 tab）→ 回该 tab", () => {
    vi.stubGlobal(
      "getCurrentPages",
      () => [{ route: "pages/meet/meet", options: {} }] as never[],
    );
    expect(backPathForAuth()).toBe("/pages/meet/meet");
  });
  it("栈只有登录页 → 兜底回约球页", () => {
    vi.stubGlobal(
      "getCurrentPages",
      () => [{ route: "pages/mine/login" }] as never[],
    );
    expect(backPathForAuth()).toBe("/pages/meet/meet");
  });
  it("tab 落点走 switchTab（redirectTo 进不了 tabbar），普通页走 redirectTo", () => {
    navToPath("/pages/meet/meet?x=1");
    expect(uni.switchTab).toHaveBeenCalledWith({ url: "/pages/meet/meet" });
    navToPath("/pages/detail/detail?id=9");
    expect(uni.redirectTo).toHaveBeenCalledWith(
      expect.objectContaining({ url: "/pages/detail/detail?id=9" }),
    );
  });
  it("redirectTo 失败（页面已不存在）→ 兜底切约球页", () => {
    vi.stubGlobal("uni", {
      ...uni,
      redirectTo: vi.fn(({ fail }: { fail?: () => void }) => fail?.()),
      switchTab: vi.fn(),
    });
    navToPath("/pages/detail/detail?id=404");
    expect(uni.switchTab).toHaveBeenCalledWith({ url: "/pages/meet/meet" });
  });
});

describe("beginWechatAuth（出发编排）", () => {
  it("不在微信里：toast 说明并短路，不写转场包、不问后端", async () => {
    vi.stubGlobal("navigator", { userAgent: "Mozilla/5.0 Chrome" });
    const toast = vi.fn();
    await expect(beginWechatAuth({ toast })).rejects.toThrow("not-in-wechat");
    expect(toast).toHaveBeenCalledWith(
      expect.stringContaining("请在微信里打开本页"),
    );
    expect(authApi.apiWechatUrl).not.toHaveBeenCalled();
    expect(readWechatCtx()).toBeNull();
  });

  it("在微信里：存转场包、拿授权地址（后端拼好整条）", async () => {
    vi.stubGlobal("navigator", { userAgent: "MicroMessenger/8.0" });
    vi.stubGlobal(
      "getCurrentPages",
      () => [{ route: "pages/mine/login" }] as never[],
    );
    authApi.apiWechatUrl.mockResolvedValue({
      url: "https://open.weixin.qq.com/xxx",
    });
    const url = await beginWechatAuth({ phone: "13800001234", toast: vi.fn() });
    expect(url).toBe("https://open.weixin.qq.com/xxx");
    expect(authApi.apiWechatUrl).toHaveBeenCalledWith(
      expect.stringContaining("/pages/mine/login"),
      expect.any(String),
    );
    const ctx = readWechatCtx();
    expect(ctx?.phone).toBe("13800001234");
    expect(ctx?.back).toBe("/pages/meet/meet");
  });

  it("在微信里（名片卡出发·认人门）：挂起动作进转场包、不带手机号、落点是宿主页", async () => {
    vi.stubGlobal("navigator", { userAgent: "MicroMessenger/8.0" });
    vi.stubGlobal(
      "getCurrentPages",
      () =>
        [
          { route: "pages/meet/meet", options: {} },
          { route: "pages/detail/detail", options: { id: "9" } },
        ] as never[],
    );
    authApi.apiWechatUrl.mockResolvedValue({
      url: "https://open.weixin.qq.com/xxx",
    });
    await beginWechatAuth({
      pending: { pendingJoin: { gameId: 9, bring: 0 } },
      toast: vi.fn(),
    });
    const ctx = readWechatCtx();
    expect(ctx?.phone).toBeUndefined();
    expect(ctx?.pending).toEqual({ pendingJoin: { gameId: 9, bring: 0 } });
    expect(ctx?.back).toBe("/pages/detail/detail?id=9");
  });

  it("在微信里（动作弹卡主钮·快进出发 1.8）：fast+卡上手填昵称进转场包、不带手机号", async () => {
    vi.stubGlobal("navigator", { userAgent: "MicroMessenger/8.0" });
    vi.stubGlobal(
      "getCurrentPages",
      () =>
        [
          { route: "pages/meet/meet", options: {} },
          { route: "pages/detail/detail", options: { id: "9" } },
        ] as never[],
    );
    authApi.apiWechatUrl.mockResolvedValue({
      url: "https://open.weixin.qq.com/xxx",
    });
    await beginWechatAuth({
      fast: true,
      pending: { pendingJoin: { gameId: 9, bring: 0 } },
      toast: vi.fn(),
    });
    const ctx = readWechatCtx();
    expect(ctx?.fast).toBe(true);
    expect(ctx?.phone).toBeUndefined(); // 快进建号不看卡上手机号
    expect(ctx?.back).toBe("/pages/detail/detail?id=9");
  });

  it("登录页微信键出发（不传 fast）：转场包不带快进位（回跳走 1.7 原路，4.7 护栏）", async () => {
    vi.stubGlobal("navigator", { userAgent: "MicroMessenger/8.0" });
    vi.stubGlobal(
      "getCurrentPages",
      () => [{ route: "pages/mine/login" }] as never[],
    );
    authApi.apiWechatUrl.mockResolvedValue({
      url: "https://open.weixin.qq.com/xxx",
    });
    await beginWechatAuth({ toast: vi.fn() });
    const ctx = readWechatCtx();
    expect(ctx?.fast).toBeUndefined();
  });

  it("要地址失败（通道没开）：转场包清掉、错误文案透给 toast", async () => {
    vi.stubGlobal("navigator", { userAgent: "MicroMessenger/8.0" });
    authApi.apiWechatUrl.mockRejectedValue(
      Object.assign(new Error("x"), {
        code: "wechat_off",
        message: "微信登录即将开通",
      }),
    );
    const toast = vi.fn();
    await expect(beginWechatAuth({ toast })).rejects.toThrow();
    expect(readWechatCtx()).toBeNull();
  });
});
