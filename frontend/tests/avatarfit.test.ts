/* avatarfit 单测：webp XMP 取景参数的读取契约（1.9 A5 修订：取景参数随图走、
   前端照读）。RIFF 块构造在测试里独立实现——写入方住在排版工具
   scripts/picfit.html，两侧不共码，字节对拍才是契约验证。 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  FALLBACK_FIT,
  frameTransform,
  loadAvatarFit,
  parseWebpFit,
} from "@/utils/avatarfit";

function chunk(fourcc: string, payload: number[]): number[] {
  const cc = fourcc.split("").map((c) => c.charCodeAt(0));
  const len = payload.length;
  const sizeLE = [len & 255, (len >> 8) & 255, (len >> 16) & 255, len >>> 24];
  const pad = len % 2 ? [0] : []; // 奇数长度块带一个不计数的目的垫字节
  return [...cc, ...sizeLE, ...payload, ...pad];
}

function riff(chunks: number[][]): ArrayBuffer {
  const body = [87, 69, 66, 80, ...chunks.flat()]; // 'WEBP' + 各块
  const total = body.length;
  const head = [
    82,
    73,
    70,
    70,
    total & 255,
    (total >> 8) & 255,
    (total >> 16) & 255,
    (total >> 24) & 255,
  ];
  return new Uint8Array([...head, ...body]).buffer;
}

function xmpPayload(inner: string): number[] {
  const xml =
    `<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">` +
    `<rdf:Description rdf:about="" xmlns:m="urn:mieball:fit"><m:fit>${inner}</m:fit></rdf:Description>` +
    `</rdf:RDF></x:xmpmeta>`;
  return [...new TextEncoder().encode(xml)];
}

const FIT_JSON = JSON.stringify({
  v: 1,
  bust: { k: 1.3, x: -0.05, y: 0.02 },
  face: { k: 3.2, x: 0.1, y: -0.2 },
});
const vp8x = chunk("VP8X", [0x10, 0, 0, 0, 0xff, 0, 0, 0xff, 0, 0]); // ALPHA 旗标假块

describe("parseWebpFit（XMP 块 → 取景参数）", () => {
  it("规范文件解出两档参数", () => {
    const buf = riff([vp8x, chunk("XMP ", xmpPayload(FIT_JSON))]);
    expect(parseWebpFit(buf)).toEqual({
      bust: { k: 1.3, x: -0.05, y: 0.02 },
      face: { k: 3.2, x: 0.1, y: -0.2 },
    });
  });

  it("前面的奇数长度块正确跳垫字节后仍能找到 XMP", () => {
    const odd = chunk("VP8 ", [1, 2, 3]); // 3 字节奇数块 → 带垫字节
    const buf = riff([odd, chunk("XMP ", xmpPayload(FIT_JSON))]);
    expect(parseWebpFit(buf)?.bust.k).toBe(1.3);
  });

  it("无 XMP 块 / 不是 webp / 空字节 → null（回落默认摆放）", () => {
    expect(parseWebpFit(riff([vp8x]))).toBeNull();
    expect(parseWebpFit(riff([chunk("VP8 ", [1])]))).toBeNull();
    expect(parseWebpFit(new ArrayBuffer(4))).toBeNull();
  });

  it("旧烘焙工具写的裸 JSON（无 <m:fit> 包裹）不认 → null", () => {
    const raw = [...new TextEncoder().encode(FIT_JSON)];
    expect(parseWebpFit(riff([chunk("XMP ", raw)]))).toBeNull();
  });

  it("版本不认识 / JSON 坏 / 档缺数值 / k 非法 → null", () => {
    const bad = (inner: string) =>
      parseWebpFit(riff([chunk("XMP ", xmpPayload(inner))]));
    expect(
      bad(
        JSON.stringify({
          v: 2,
          bust: { k: 1, x: 0, y: 0 },
          face: { k: 1, x: 0, y: 0 },
        }),
      ),
    ).toBeNull();
    expect(bad("{oops")).toBeNull();
    expect(
      bad(
        JSON.stringify({
          v: 1,
          bust: { k: 1, x: 0 },
          face: { k: 1, x: 0, y: 0 },
        }),
      ),
    ).toBeNull();
    expect(
      bad(
        JSON.stringify({
          v: 1,
          bust: { k: 0, x: 0, y: 0 },
          face: { k: 1, x: 0, y: 0 },
        }),
      ),
    ).toBeNull();
    expect(
      bad(
        JSON.stringify({
          v: 1,
          bust: { k: "x", x: 0, y: 0 },
          face: { k: 1, x: 0, y: 0 },
        }),
      ),
    ).toBeNull();
  });

  it("尾块被截断 → null", () => {
    const whole = new Uint8Array(riff([chunk("XMP ", xmpPayload(FIT_JSON))]));
    expect(parseWebpFit(whole.slice(0, whole.length - 10).buffer)).toBeNull();
  });
});

describe("frameTransform（参数 → CSS transform）", () => {
  it("百分比位移以窗口边长为基、缩放三位小数", () => {
    expect(frameTransform({ k: 1.3, x: -0.05, y: 0.02 })).toBe(
      "translate(-5.00%, 2.00%) scale(1.300)",
    );
  });

  it("无参数兜底两档与静态 CSS 时代同值（大位原样 k1、小位 125% 居中聚脸）", () => {
    expect(FALLBACK_FIT.bust).toEqual({ k: 1, x: 0, y: 0 });
    expect(FALLBACK_FIT.face).toEqual({ k: 1.25, x: 0, y: 0 });
    expect(frameTransform(FALLBACK_FIT.face)).toBe(
      "translate(0.00%, 0.00%) scale(1.250)",
    );
  });
});

describe("loadAvatarFit（按 URL 取参 + 记忆）", () => {
  beforeEach(() => {
    vi.stubGlobal("uni", { request: vi.fn() });
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("非 /cosmetics/ 外链直接 null 且不发请求（微信头像永不带参数）", async () => {
    const r = await loadAvatarFit("https://wx.example/head.jpg");
    expect(r).toBeNull();
    expect(uni.request).not.toHaveBeenCalled();
  });

  it("取到字节解出参数；同 URL 只发一次请求", async () => {
    uni.request = vi.fn((opts: { success: (r: unknown) => void }) => {
      opts.success({ data: riff([chunk("XMP ", xmpPayload(FIT_JSON))]) });
    });
    const a = loadAvatarFit("/cosmetics/a-p9.webp");
    const b = loadAvatarFit("/cosmetics/a-p9.webp");
    expect(await a).toEqual(await b);
    expect((await a)?.face.k).toBe(3.2);
    expect(uni.request).toHaveBeenCalledTimes(1);
  });

  it("请求失败回 null 不抛（渲染回落默认档，不拦页面）", async () => {
    uni.request = vi.fn((opts: { fail: () => void }) => opts.fail());
    expect(await loadAvatarFit("/cosmetics/a-p8.webp")).toBeNull();
  });
});
