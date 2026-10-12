import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  beijingAt,
  durTxt,
  isoDay,
  isoDayOff,
  isoHm,
  isoHmOrDash,
  toIso,
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

describe("toIso（修复批 F2：写侧同走北京墙钟，不随设备时区）", () => {
  it("UTC 时刻按 +08:00 墙钟直拼（19:00Z → 北京次日 03:00）", () => {
    expect(toIso(new Date("2026-10-08T11:00:00Z"))).toBe(
      "2026-10-08T19:00:00+08:00",
    );
    expect(toIso(new Date("2026-10-08T19:00:00Z"))).toBe(
      "2026-10-09T03:00:00+08:00", // 跨日不漂
    );
  });
  it("与读侧同历法：toIso → isoHm 往返还原同一墙钟", () => {
    const d = new Date("2026-10-08T03:25:00Z");
    expect(isoHm(toIso(d))).toBe("11:25");
  });
});

describe("beijingAt（拨盘「D 日 HH:mm」→ 时刻，F2 修复批正午锚 +12h 漂移的坑）", () => {
  it("午夜锚 + 拨盘分钟 = 北京当日该点（toIso 往返逐字）", () => {
    expect(toIso(beijingAt(2026, 10, 6, 19 * 60))).toBe(
      "2026-10-06T19:00:00+08:00",
    );
    expect(toIso(beijingAt(2026, 10, 6, 0))).toBe("2026-10-06T00:00:00+08:00");
  });
  it("日溢出滚动交给 Date.UTC（拨盘日列 n.d+i 跨月直喂）", () => {
    expect(toIso(beijingAt(2026, 9, 30 + 2, 19 * 60))).toBe(
      "2026-10-02T19:00:00+08:00",
    );
  });
});

describe("durTxt / isoHmOrDash（打多久文案与考勤时刻兜底）", () => {
  it("整/半小时 → 小时口径，其余 → 分钟", () => {
    expect(durTxt(1)).toBe("1 小时");
    expect(durTxt(1.5)).toBe("1.5 小时");
    expect(durTxt(115 / 60)).toBe("115 分钟");
  });
  it("isoHmOrDash：有值出时刻、缺值显 —", () => {
    expect(isoHmOrDash("2026-10-04T09:05:00+08:00")).toBe("09:05");
    expect(isoHmOrDash(null)).toBe("—");
    expect(isoHmOrDash(undefined)).toBe("—");
  });
});

describe("untilTxt（alpha:975-981）", () => {
  it("分钟 / 小时 / 天 三档", () => {
    expect(untilTxt(new Date(2026, 9, 4, 12, 30))).toBe("30分");
    expect(untilTxt(new Date(2026, 9, 4, 13, 30))).toBe("1时30分");
    expect(untilTxt(new Date(2026, 9, 7, 12, 0))).toBe("3天");
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
