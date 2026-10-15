import { describe, expect, it } from "vitest";
import { playEndMin } from "@/utils/wheel";

/* 2026-10-16 修复回归：改局/组局表单开打拨盘的结束列下标此前从未被消费——
   拨结束列视觉停在新时刻（uni 受控回滚不可靠），表单值纹丝不动，保存回旧时间。 */
describe("playEndMin（开打拨盘结束列换算）", () => {
  const ROW2 = 2; // 19:00 开始口径下，结束 21:00 的行号

  it("结束列被拨：行号换算成绝对分钟（行 7 = 19:00+30+210 = 23:00）", () => {
    expect(playEndMin(7, ROW2, 21 * 60, 19 * 60)).toBe(23 * 60);
  });

  it("结束列没拨（只拨日期/开始）：保持旧结束分钟——19:00–21:00 把开始拨到 18:00，结束仍 21:00", () => {
    expect(playEndMin(ROW2, ROW2, 21 * 60, 18 * 60)).toBe(21 * 60);
  });
});
