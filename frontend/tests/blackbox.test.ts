/* 6.1 批6【前端三小件】黑匣子锁：环形 30 条滚动覆盖、exportText 轨迹+环境+手机号打码、
   trackErr 带 ERR-XXX、initBlackbox 拦截器+launch、storage 抛错降级不炸（spec 4.7）、
   http 层集成（act 只记 POST / 失败记 err 带）。stub 掉 uni 全局、喂 uni.request 的
   success 回调，不触网（http-error-id.test.ts 同惯例）。 */
import { afterAll, beforeEach, describe, expect, it, vi } from "vitest";
import {
  exportText,
  initBlackbox,
  trackAct,
  trackErr,
  trackNav,
  type BlackboxEntry,
} from "@/utils/blackbox";
import { request } from "@/api/http";

const KEY = "blackbox";
const store = new Map<string, unknown>();
const addInterceptor = vi.hoisted(() => vi.fn());
const requestMock = vi.hoisted(() => vi.fn());

vi.stubGlobal("uni", {
  getStorageSync: (k: string) => (store.has(k) ? store.get(k) : ""),
  setStorageSync: (k: string, v: unknown) => void store.set(k, v),
  removeStorageSync: (k: string) => void store.delete(k),
  addInterceptor: (m: string, o: unknown) => addInterceptor(m, o),
  getSystemInfoSync: () => ({
    platform: "devtools",
    system: "iOS 17",
    version: "3.9.9",
    appVersion: "1.0.0",
  }),
  request: (opts: unknown) => requestMock(opts),
});

afterAll(() => vi.unstubAllGlobals());

/** storage 里现存的轨迹（黑匣子每次 append 全量回写，读它即读黑匣子） */
function entries(): BlackboxEntry[] {
  return (store.get(KEY) as BlackboxEntry[]) ?? [];
}

/** 喂一次 uni.request 成功回调：statusCode+data 原样进 http 层 */
function respond(statusCode: number, data: unknown) {
  requestMock.mockImplementationOnce(
    (opts: { success?: (r: unknown) => void }) =>
      opts.success?.({ statusCode, data }),
  );
}

beforeEach(() => {
  store.clear();
  addInterceptor.mockReset();
  requestMock.mockReset();
});

describe("黑匣子环形与采集（6.1 §4.6 / 附录 A）", () => {
  it("append 进 storage；超 30 条滚动覆盖只剩最近 30", () => {
    for (let i = 1; i <= 35; i++) trackNav(`/p${i}`);
    const list = entries();
    expect(list).toHaveLength(30);
    expect(list[0].info).toBe("/p6"); // 最老的 5 条被滚掉
    expect(list[29].info).toBe("/p35");
    expect(list[0].kind).toBe("nav");
  });

  it("trackAct 只记 POST：GET 零记录、成功 ok、失败 fail:code", () => {
    trackAct("GET", "/g");
    expect(entries()).toHaveLength(0);
    trackAct("POST", "/a", true);
    trackAct("POST", "/b", false, "phone_taken");
    const list = entries();
    expect(list[0]).toMatchObject({ kind: "act", info: "POST /a → ok" });
    expect(list[1]).toMatchObject({
      kind: "act",
      info: "POST /b → fail:phone_taken",
    });
  });

  it("trackErr 带 errorId 时 info 首段 ERR-XXX；不带时只记 code", () => {
    trackErr("internal_error", "ERR-1a2b3c");
    trackErr("network");
    const list = entries();
    expect(list[0]).toMatchObject({
      kind: "err",
      info: "ERR-1a2b3c internal_error",
    });
    expect(list[1]).toMatchObject({ kind: "err", info: "network" });
  });

  it("trackErr 防刷屏：连续同码只记第一条；夹不同 code 后再记", () => {
    // 现场页 3 秒轮询断网：每拍一条 err"network"，不防刷屏 30 条环 90 秒滚掉 nav/act 轨迹
    for (let i = 0; i < 5; i++) trackErr("network");
    expect(entries()).toHaveLength(1); // 5 条同码只 1 条
    trackErr("phone_taken"); // 出现不同 code 照记
    trackErr("phone_taken"); // 新基线上同码又被吞
    trackErr("network"); // 换回 network（≠上一条 err 的 info）再记
    expect(entries().map((e) => e.info)).toEqual([
      "network",
      "phone_taken",
      "network",
    ]);
  });

  it("trackErr 防刷屏的基线是上一条 err：中间夹的 act 不重置（POST 轮询失败 err/act 交替也只记一条 err）", () => {
    trackErr("network");
    trackAct("POST", "/poll", false, "network");
    trackErr("network");
    trackAct("POST", "/poll", false, "network");
    trackErr("network");
    const list = entries();
    expect(list.filter((e) => e.kind === "err")).toHaveLength(1);
    expect(list.filter((e) => e.kind === "act")).toHaveLength(2);
  });

  it("initBlackbox 挂四个路由拦截器 + 记一条 launch；拦截器 invoke 记目标页", () => {
    initBlackbox();
    expect(addInterceptor).toHaveBeenCalledTimes(4);
    const methods = addInterceptor.mock.calls.map((c) => c[0]);
    expect(methods).toEqual(
      expect.arrayContaining([
        "navigateTo",
        "switchTab",
        "reLaunch",
        "redirectTo",
      ]),
    );
    expect(entries()[0]).toMatchObject({ kind: "nav", info: "launch" });
    // 拦截器回调喂 url → 记一条 nav（目标页连 query 可辨哪局）
    const opts = addInterceptor.mock.calls[0][1] as {
      invoke: (a: { url: string }) => void;
    };
    opts.invoke({ url: "/pages/detail/detail?id=3" });
    expect(entries().at(-1)).toMatchObject({
      kind: "nav",
      info: "/pages/detail/detail?id=3",
    });
  });

  it("exportText 含最近报错（带号）、轨迹、环境摘要；手机号打码不落明文", () => {
    trackErr("internal_error", "ERR-1a2b3c");
    trackNav("/pages/x?tel=13812341234");
    const text = exportText();
    expect(text).toContain("最近报错：");
    expect(text).toContain("ERR-1a2b3c internal_error");
    expect(text).toContain("[nav] /pages/x?tel=");
    expect(text).toContain("platform=devtools");
    expect(text).toContain("system=iOS 17");
    expect(text).toContain("uni=3.9.9");
    expect(text).toContain("app=1.0.0");
    expect(text).toContain("138****1234");
    expect(text).not.toContain("13812341234");
  });

  it("空轨迹导出 = 暂无 + 无报错 + 环境短文字（刚装 app，spec 附录 A2）", () => {
    const text = exportText();
    expect(text).toContain("轨迹：暂无");
    expect(text).toContain("最近报错：无");
    expect(text).toContain("环境：");
  });

  it("storage 读写抛错不炸：记不进也不抛，导出退化为短文字（spec 4.7 丢日志不丢功能）", () => {
    const uniObj = uni as unknown as Record<string, unknown>;
    const [g, s] = [uniObj.getStorageSync, uniObj.setStorageSync];
    uniObj.getStorageSync = () => {
      throw new Error("boom");
    };
    uniObj.setStorageSync = () => {
      throw new Error("boom");
    };
    try {
      expect(() => trackNav("/x")).not.toThrow();
      expect(exportText()).toContain("轨迹：暂无");
    } finally {
      uniObj.getStorageSync = g;
      uniObj.setStorageSync = s;
    }
  });
});

describe("http 层集成（act/err 埋点，6.1 批6）", () => {
  it("POST 成功记 ok；GET 成功零记录", async () => {
    respond(200, {});
    await request("POST", "/x", {});
    expect(entries().at(-1)).toMatchObject({
      kind: "act",
      info: "POST /x → ok",
    });
    respond(200, {});
    await request("GET", "/y");
    expect(entries().at(-1)).toMatchObject({
      kind: "act",
      info: "POST /x → ok",
    });
  });

  it("POST ≥400 业务错：act 记 fail:code、err 行不带号", async () => {
    respond(409, { error: { code: "phone_taken", message: "x" } });
    await request("POST", "/z").catch(() => undefined);
    const list = entries();
    expect(list.at(-2)).toMatchObject({
      kind: "err",
      info: "phone_taken",
    });
    expect(list.at(-1)).toMatchObject({
      kind: "act",
      info: "POST /z → fail:phone_taken",
    });
  });

  it("500 带 error_id：err 行首段 ERR-XXX、act 记 fail:internal_error", async () => {
    respond(500, {
      error: { code: "internal_error", message: "m", error_id: "ERR-9z8y7x" },
    });
    await request("POST", "/w").catch(() => undefined);
    const list = entries();
    expect(list.at(-2)).toMatchObject({
      kind: "err",
      info: "ERR-9z8y7x internal_error",
    });
    expect(list.at(-1)).toMatchObject({
      kind: "act",
      info: "POST /w → fail:internal_error",
    });
  });

  it("断网（uni.request fail 回调）：err 记 network 不带号（服务器看不见的失败黑匣子兜底）", async () => {
    requestMock.mockImplementationOnce((opts: { fail?: () => void }) =>
      opts.fail?.(),
    );
    await request("POST", "/off").catch(() => undefined);
    const list = entries();
    expect(list.at(-2)).toMatchObject({ kind: "err", info: "network" });
    expect(list.at(-1)).toMatchObject({
      kind: "act",
      info: "POST /off → fail:network",
    });
  });
});
