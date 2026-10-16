import { describe, expect, it } from "vitest";
import { clampEnd, endLabels, endRowOf, playEndMin } from "@/utils/wheel";

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

/* 建列/行号反推/回填夹取三件与 playEndMin 同吃 endWindow——此前组件里各写一份
   窗口常量，是「行号↔分钟错位」那类 bug 的温床，收单一源后在此挂回归。 */
describe("endLabels / endRowOf / clampEnd（结束列单一源）", () => {
  it("19:00 开始：列从 19:30 到 23:30（6 小时窗顶到网格末格），行号↔分钟互逆", () => {
    const cols = endLabels(19 * 60);
    expect(cols[0]).toBe("19:30");
    expect(cols[cols.length - 1]).toBe("23:30");
    for (let row = 0; row < cols.length; row++) {
      const min = 19 * 60 + 30 + row * 30;
      expect(endRowOf(19 * 60, min)).toBe(row);
    }
    expect(endRowOf(19 * 60, 23 * 60)).toBe(7); // 23:00 的行号（playEndMin 用例同行号）
  });

  it("窗越 23:30 封顶、回填夹取同窗：越界结束收回上沿", () => {
    expect(endLabels(23 * 60)).toEqual(["23:30"]); // 窗被网格截断只剩末格
    expect(clampEnd(19 * 60, 23 * 60 + 55)).toBe(23 * 60 + 30);
    expect(clampEnd(19 * 60, 19 * 60)).toBe(19 * 60 + 30); // 低于下沿抬起
  });
});
