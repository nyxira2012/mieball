import { afterEach, describe, expect, it, vi } from "vitest";
import { deepUrl, sceneGameId } from "@/utils/deeplink";

/* 深链拼装：H5 hash 路由（根路径部署）→ origin + "/#" + path；
   无 location 的端（小程序/测试环境 node 默认）返回裸 path。
   vitest 环境是 node（无 location），两态都用 stubGlobal 钉死，用完还原。 */

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("deepUrl（path → 完整深链）", () => {
  it("有 location：拼 origin + /# + path（hash 路由）", () => {
    vi.stubGlobal("location", { origin: "https://nightcourt.example" });
    expect(deepUrl("/pages/live/live?id=3")).toBe(
      "https://nightcourt.example/#/pages/live/live?id=3",
    );
    expect(deepUrl("/pages/detail/detail?id=7")).toBe(
      "https://nightcourt.example/#/pages/detail/detail?id=7",
    );
  });

  it("无 location（非 H5 端）：返回裸 path", () => {
    vi.stubGlobal("location", undefined);
    expect(deepUrl("/pages/live/live?id=3")).toBe("/pages/live/live?id=3");
  });
});

describe("sceneGameId（扫现场小程序码的 scene 解析）", () => {
  it("g=<id> 认出球局 id：encode 形态（微信塞参的真实形态）与裸形态都解", () => {
    expect(sceneGameId("g%3D42")).toBe(42);
    expect(sceneGameId("g=7")).toBe(7);
  });
  it("非 g= 前缀 / 非数字：不认，回 null（照旧走 ?id=/信号位分发）", () => {
    expect(sceneGameId("x=5")).toBeNull();
    expect(sceneGameId("g=abc")).toBeNull();
    expect(sceneGameId("%zz")).toBeNull(); // 畸形百分号序列：当没扫过
  });
  it("空 scene / 缺省：回 null", () => {
    expect(sceneGameId("")).toBeNull();
    expect(sceneGameId(undefined)).toBeNull();
    expect(sceneGameId(null)).toBeNull();
  });
});
