/* 装扮页保存把关派生（utils/dress.ts）单测：三族「还差 X」怎么算、
   未定级台阶款只显原文、保存把关含未解锁件报差什么。
   阈值/进度数值与后端册子口径一致（rating 档位是×10 整数）。 */
import { describe, expect, it } from "vitest";
import type { CosmeticItemApi, CosmeticsPageApi } from "@/api/cosmetics";
import { dressBlock, honorGap, isUnlocked } from "@/utils/dress";

const PROGRESS = {
  matches: 13,
  rating: 3.2,
  rating_provisional: false,
  organizes: 6,
};

function item(over: Partial<CosmeticItemApi>): CosmeticItemApi {
  return {
    cid: "x",
    kind: "avatar",
    tier: "honor",
    name: "某件",
    family: null,
    threshold: null,
    lock_text: null,
    fx: 0,
    fy: 0,
    asset: "/cosmetics/x.webp",
    ...over,
  };
}

const MATCHES_20 = item({
  cid: "a-m20",
  family: "matches",
  threshold: 20,
  lock_text: "参与 20 场对局解锁",
});
const RATING_35 = item({
  cid: "a-t35",
  family: "rating",
  threshold: 35,
  lock_text: "当前分数达到 3.5 即解锁",
});
const ORGANIZE_10 = item({
  cid: "a-o10",
  family: "organize",
  threshold: 10,
  lock_text: "张罗 10 局正常散场的球局解锁",
});

describe("isUnlocked（清单外=公共款人人可穿）", () => {
  it("不在 unlocks 清单 → 可穿（公共款不入清单）", () => {
    expect(isUnlocked("a-p1", {})).toBe(true);
  });
  it("清单里 unlocked=false → 带锁", () => {
    expect(
      isUnlocked("a-m20", { "a-m20": { unlocked: false, is_new: false } }),
    ).toBe(false);
  });
});

describe("honorGap 三族「还差 X」派生", () => {
  it("场数族：20 档已打 13 → 还差 7 场对局", () => {
    expect(honorGap(MATCHES_20, PROGRESS)).toBe("还差 7 场对局");
  });
  it("组局族：10 档已张罗 6 → 还差 4 局", () => {
    expect(honorGap(ORGANIZE_10, PROGRESS)).toBe("还差 4 局");
  });
  it("台阶族已定级：3.5 档现 3.2 分 → 还差 0.3 分（一位小数）", () => {
    expect(honorGap(RATING_35, PROGRESS)).toBe("还差 0.3 分");
  });
  it("台阶族未定级：只显原文不算分（分数还不算数）", () => {
    expect(
      honorGap(RATING_35, { ...PROGRESS, rating_provisional: true }),
    ).toBeNull();
  });
  it("已达标（不该再带锁）：回 null", () => {
    expect(honorGap(MATCHES_20, { ...PROGRESS, matches: 20 })).toBeNull();
    expect(honorGap(RATING_35, { ...PROGRESS, rating: 3.5 })).toBeNull();
  });
  it("公共/定制款（无族无阈值）：不派生", () => {
    expect(honorGap(item({ tier: "common" }), PROGRESS)).toBeNull();
  });
});

/** 最小整页：进度 13 场 / 3.2 分已定级 / 张罗 6 局——5 场档已解锁带新标，
    20 场档、3.5 台阶档、10 局档带锁（与核算后的真实状态同构） */
function pageFixture(): CosmeticsPageApi {
  return {
    items: [
      item({ cid: "a-p1", tier: "common", name: "球友1" }),
      item({ cid: "b-c1", kind: "back", tier: "common", name: "基础卡背1" }),
      item({
        cid: "a-m5",
        family: "matches",
        threshold: 5,
        lock_text: "参与 5 场对局解锁",
      }),
      MATCHES_20,
      RATING_35,
      ORGANIZE_10,
    ],
    unlocks: {
      "a-m5": { unlocked: true, is_new: true },
      "a-m20": { unlocked: false, is_new: false },
      "a-t35": { unlocked: false, is_new: false },
      "a-o10": { unlocked: false, is_new: false },
    },
    wearing: { avatar: "a-p1", back: "b-c1" },
    progress: PROGRESS,
    wechat_avatar_available: false,
  };
}

describe("dressBlock 保存把关（按钮灰的文字来源）", () => {
  it("全公共款/已解锁款 → 可保存（null）", () => {
    expect(
      dressBlock(pageFixture(), { avatar: "a-p1", back: "b-c1" }),
    ).toBeNull();
    expect(
      dressBlock(pageFixture(), { avatar: "a-m5", back: "b-c1" }),
    ).toBeNull();
  });
  it("所选含未解锁场数款 → 还差 7 场对局解锁这件", () => {
    expect(dressBlock(pageFixture(), { avatar: "a-m20", back: "b-c1" })).toBe(
      "还差 7 场对局解锁这件",
    );
  });
  it("未解锁的是组局款 → 同样拦（还差几局）", () => {
    expect(dressBlock(pageFixture(), { avatar: "a-o10", back: "b-c1" })).toBe(
      "还差 4 局解锁这件",
    );
  });
  it("未解锁的是卡背 → 头像过、卡背报差", () => {
    const p = pageFixture();
    p.items.push(
      item({
        cid: "b-o10",
        kind: "back",
        family: "organize",
        threshold: 10,
        lock_text: "张罗 10 局正常散场的球局解锁",
      }),
    );
    // 后端 unlocks 收全量荣誉款：新入册的带锁卡背同样在清单里
    p.unlocks["b-o10"] = { unlocked: false, is_new: false };
    expect(dressBlock(p, { avatar: "a-p1", back: "b-o10" })).toBe(
      "还差 4 局解锁这件",
    );
  });
  it("未解锁台阶款已定级 → 报差多少分", () => {
    expect(dressBlock(pageFixture(), { avatar: "a-t35", back: "b-c1" })).toBe(
      "还差 0.3 分解锁这件",
    );
  });
  it("未解锁台阶款未定级 → 册子条件原文（界面不自造规则）", () => {
    const p = pageFixture();
    p.progress = { ...PROGRESS, rating_provisional: true };
    expect(dressBlock(p, { avatar: "a-t35", back: "b-c1" })).toBe(
      "当前分数达到 3.5 即解锁",
    );
  });
  it("'wechat' 不是册子编号：微信头像选项页面把门，把关不误伤", () => {
    expect(
      dressBlock(pageFixture(), { avatar: "wechat", back: "b-c1" }),
    ).toBeNull();
  });
});
