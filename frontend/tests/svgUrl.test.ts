import { describe, expect, it } from "vitest";
import { svgDataUrl } from "@/utils/svgUrl";

/* SVG→data URL 替身通道（小程序端 <image> 渲染 v-html 出口的 SVG）：
   钉三件——前缀口径 / currentColor 现换 / 无色纯透传不改动原文。 */

const PREFIX = "data:image/svg+xml;charset=utf-8,";
const SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" stroke="currentColor"><path stroke="currentColor"/></svg>';

describe("svgDataUrl（小程序端 v-html 出口的 image 替身）", () => {
  it("产出 data:image/svg+xml 前缀 + 全量百分号编码", () => {
    const url = svgDataUrl(SVG);
    expect(url.startsWith(PREFIX)).toBe(true);
    expect(decodeURIComponent(url.slice(PREFIX.length))).toBe(SVG);
  });

  it("带色把所有 currentColor 现换成实色", () => {
    const url = svgDataUrl(SVG, "#FFD400");
    expect(decodeURIComponent(url.slice(PREFIX.length))).toBe(
      '<svg xmlns="http://www.w3.org/2000/svg" stroke="#FFD400"><path stroke="#FFD400"/></svg>',
    );
  });

  it("无色幂等：原文一字不动（currentColor 留给 CSS 端消费）", () => {
    expect(svgDataUrl(SVG)).toBe(PREFIX + encodeURIComponent(SVG));
    expect(svgDataUrl("plain")).toBe(svgDataUrl("plain"));
  });
});
