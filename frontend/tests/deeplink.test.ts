import { afterEach, describe, expect, it, vi } from "vitest";
import { deepUrl } from "@/utils/deeplink";

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
