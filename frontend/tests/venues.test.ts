import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  VENUE_RECENT_KEY,
  getRecentVenues,
  getTopVenues,
  matchVenues,
  recordVenue,
} from "@/utils/venues";
import { venueSuggestions } from "@/api/dict";

const mockStore = new Map<string, unknown>();

vi.stubGlobal("uni", {
  getStorageSync: (k: string) => (mockStore.has(k) ? mockStore.get(k) : ""),
  setStorageSync: (k: string, v: unknown) => void mockStore.set(k, v),
  removeStorageSync: (k: string) => void mockStore.delete(k),
});

describe("venues 常用场地管理", () => {
  beforeEach(() => {
    mockStore.clear();
  });

  it("无缓存时兜底返回默认 5 个球馆", () => {
    const list = getRecentVenues();
    expect(list).toEqual(venueSuggestions);
    expect(getTopVenues(3)).toEqual(venueSuggestions.slice(0, 3));
  });

  it("recordVenue 成功记录新场地并置顶 (LRU)", () => {
    recordVenue("青秀山匹克球场");
    const top3 = getTopVenues(3);
    expect(top3[0]).toBe("青秀山匹克球场");
    expect(top3.length).toBe(3);

    // 再次记录同一个，移动到最前面且不重复
    recordVenue(venueSuggestions[1]);
    const nextTop3 = getTopVenues(3);
    expect(nextTop3[0]).toBe(venueSuggestions[1]);
    expect(nextTop3[1]).toBe("青秀山匹克球场");
  });

  it("matchVenues 模糊匹配并限制数量，过滤完全一致的值", () => {
    // 搜“李”应该匹配到“李宁（体育园）”
    const matches = matchVenues("李", 3);
    expect(matches).toContain("李宁（体育园）");

    // 全字完全一致时不返回该项本身
    const exact = matchVenues("李宁（体育园）", 3);
    expect(exact).not.toContain("李宁（体育园）");

    // 空字返回空
    expect(matchVenues("", 3)).toEqual([]);
  });

  it("异常 JSON 数据能平稳容错并兜底", () => {
    mockStore.set(VENUE_RECENT_KEY, "{corrupted json");
    expect(getRecentVenues()).toEqual(venueSuggestions);
  });
});
