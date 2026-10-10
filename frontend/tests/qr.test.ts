import { describe, expect, it } from "vitest";
import { qrSvg } from "@/utils/qr";

/* 二维码 SVG 纯函数：只验形状契约（确定性/差异/方阵/暗格/长文不炸）——
   矩阵编码正确性是 qrcode-generator 库的职责，不在此复测。 */

const URL_A = "https://nightcourt.example/#/pages/live/live?id=3";
const URL_B = "https://nightcourt.example/#/pages/live/live?id=42";

describe("qrSvg（深链 → SVG 码图）", () => {
  it("同输入两次输出全等（确定性）", () => {
    expect(qrSvg(URL_A)).toBe(qrSvg(URL_A));
  });

  it("不同输入输出不同", () => {
    expect(qrSvg(URL_A)).not.toBe(qrSvg(URL_B));
  });

  it("输出以 <svg 开头，viewBox 为整数方阵 0 0 N N（N≥21）", () => {
    for (const u of [URL_A, URL_B]) {
      const svg = qrSvg(u);
      expect(svg.startsWith("<svg")).toBe(true);
      const m = svg.match(/viewBox="0 0 (\d+) (\d+)"/);
      expect(m).not.toBeNull();
      const n = Number(m![1]);
      expect(m![2]).toBe(m![1]); // 宽=高（方阵）
      expect(Number.isInteger(n)).toBe(true);
      expect(n).toBeGreaterThanOrEqual(21); // QR 最小版 Version 1 = 21×21
    }
  });

  it("暗格 rect 数量 >0 且每个 fill=currentColor（码色随容器走）", () => {
    const rects = qrSvg(URL_A).match(/<rect [^>]*\/>/g) ?? [];
    expect(rects.length).toBeGreaterThan(0);
    for (const r of rects) expect(r).toContain('fill="currentColor"');
  });

  it("长文本（120 字符 URL）不炸且仍是合法码图", () => {
    const long = `https://nightcourt.example/#/pages/detail/detail?id=${"1".repeat(68)}`; // 前缀 52 + 68 = 120
    expect(long).toHaveLength(120);
    const svg = qrSvg(long);
    expect(svg.startsWith("<svg")).toBe(true);
    expect(svg.match(/<rect [^>]*\/>/g)).not.toBeNull();
  });
});
