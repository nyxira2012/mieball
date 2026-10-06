import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  dayToken,
  gameTime,
  hmToken,
  isoDay,
  isoDayOff,
  isoHm,
  untilTxt,
} from "@/utils/time";

/* 以 2026-10-04（周日）12:00 为「现在」做确定性解析（fake timers 冻结 Date） */
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date(2026, 9, 4, 12, 0, 0));
});
afterEach(() => {
  vi.useRealTimers();
});

describe("gameTime（alpha:959-974 中文相对日解析）", () => {
  it("今晚 → 今天该点", () => {
    expect(gameTime("今晚 19:00")).toEqual(new Date(2026, 9, 4, 19, 0));
  });
  it("明晚 → 明天该点", () => {
    expect(gameTime("明晚 19:30")).toEqual(new Date(2026, 9, 5, 19, 30));
  });
  it("周六（今天周日）→ 顺延到本周六", () => {
    expect(gameTime("周六 14:00")).toEqual(new Date(2026, 9, 10, 14, 0));
  });
  it("今天的周X已过 → 顺延下周（alpha:970）", () => {
    // 今天就是周日，10:00 已过 → 下周日
    expect(gameTime("周日 10:00")).toEqual(new Date(2026, 9, 11, 10, 0));
  });
  it("本周还没到的周X → 本周", () => {
    expect(gameTime("周三 20:00")).toEqual(new Date(2026, 9, 7, 20, 0));
  });
  it("下周X → 恒定跳到下周（alpha:965-966）", () => {
    expect(gameTime("下周三 20:00")).toEqual(new Date(2026, 9, 14, 20, 0));
  });
});

describe("gameTime 组局改版（3.3）：后天与精确日期", () => {
  it("后天 → 后天该点", () => {
    expect(gameTime("后天 19:00")).toEqual(new Date(2026, 9, 6, 19, 0));
  });
  it("「10.06 周一 19:00」首段精确日期 → 当年该日（周几段仅展示）", () => {
    expect(gameTime("10.06 周一 19:00")).toEqual(new Date(2026, 9, 6, 19, 0));
  });
  it("deadline 同格式（两段精确日期）也走精确分支", () => {
    expect(gameTime("10.04 17:00")).toEqual(new Date(2026, 9, 4, 17, 0));
  });
});

describe("dayToken / hmToken（组局拨盘产物）", () => {
  it("偏移 0/1/2 天 → 今天/明天/后天", () => {
    expect(dayToken(new Date(2026, 9, 4))).toBe("今天");
    expect(dayToken(new Date(2026, 9, 5))).toBe("明天");
    expect(dayToken(new Date(2026, 9, 6))).toBe("后天");
  });
  it("更远或过去 → 「M.DD 周X」（月不补零、日补零）", () => {
    expect(dayToken(new Date(2026, 9, 7))).toBe("10.07 周三");
    expect(dayToken(new Date(2026, 8, 30))).toBe("9.30 周三");
  });
  it("hmToken 24 小时制补零", () => {
    expect(hmToken(new Date(2026, 9, 4, 9, 5))).toBe("09:05");
    expect(hmToken(new Date(2026, 9, 4, 21, 0))).toBe("21:00");
  });
});

describe("untilTxt（alpha:975-981）", () => {
  it("分钟 / 小时 / 天 三档", () => {
    expect(untilTxt(new Date(2026, 9, 4, 12, 30))).toBe("30 分钟");
    expect(untilTxt(new Date(2026, 9, 4, 13, 30))).toBe("1 小时 30 分");
    expect(untilTxt(new Date(2026, 9, 7, 12, 0))).toBe("3 天");
  });
  it("已过 → null", () => {
    expect(untilTxt(new Date(2026, 9, 4, 11, 0))).toBeNull();
  });
});

describe("isoDay / isoHm / isoDayOff（走查#1：ISO 展示一律北京墙钟，不随设备时区）", () => {
  /* 「现在」锚死北京 2026-10-04（周日）12:00——用 +08:00 时刻锚定，
     断言在任何开发机时区下都确定（函数内「北京今天」也由此刻决定） */
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-04T12:00:00+08:00"));
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("isoHm：+08:00 出参直取北京墙钟（19:00 不被海外机转成 22:00）", () => {
    expect(isoHm("2026-10-08T19:00:00+08:00")).toBe("19:00");
    expect(isoHm("2026-10-08T01:05:00+08:00")).toBe("01:05"); // h23 补零
    expect(isoHm("2026-10-08T23:30:00+08:00")).toBe("23:30");
  });
  it("isoDay：远日 → 「M.DD 周X」按北京公历日", () => {
    expect(isoDay("2026-10-08T19:00:00+08:00")).toBe("10.08 周四");
    expect(isoDay("2026-10-03T09:00:00+08:00")).toBe("10.03 周六"); // 已过日也走 M.DD 分支
  });
  it("isoDay：今天/明天/后天按北京今天判", () => {
    expect(isoDay("2026-10-04T20:00:00+08:00")).toBe("今天");
    expect(isoDay("2026-10-05T00:30:00+08:00")).toBe("明天");
    expect(isoDay("2026-10-06T23:59:00+08:00")).toBe("后天");
  });
  it("isoDayOff：距北京今天的天数（跨零点不漂）", () => {
    expect(isoDayOff("2026-10-04T23:00:00+08:00")).toBe(0);
    expect(isoDayOff("2026-10-06T00:30:00+08:00")).toBe(2);
    expect(isoDayOff("2026-10-08T19:00:00+08:00")).toBe(4);
  });
});
