import { describe, expect, it } from "vitest";
import {
  ASSET_REV,
  BACK_SPEC,
  DEFAULT_AVATAR_CID,
  DEFAULT_FOCUS,
  WIN,
  assetUrl,
  coverPos,
  isCosmeticUrl,
  resolveAssetUrl,
  slicePos,
} from "@/utils/cardbg";

/* 取景引擎公式守门（1.9）：参数逐值迁自 temp/原型-背景卡组件.html，本文件把
   对照面的关键算例钉死——改公式或 WIN 表跑红即分叉。期望值全为手算，
   公式：切片 px=(sx−k·fx)/(1−k) 钳 3~97%；cover 档 k=各轴溢出倍率同公式、
   k<1.02（位移不足 1px）兜 50%。 */

describe("assetUrl 约定拼路径（约定优于配置，册子不存路径）", () => {
  it("头像卡背同格式 /cosmetics/{cid}.webp（与后端 asset_url 同口径）", () => {
    expect(assetUrl("b-c1")).toBe("/cosmetics/b-c1.webp");
    expect(assetUrl("a-p1")).toBe("/cosmetics/a-p1.webp");
    expect(assetUrl("a-t45")).toBe("/cosmetics/a-t45.webp");
  });
  it("默认脸编号与后端册子 DEFAULT_AVATAR 同值（卡背默认款前端无消费不镜像）", () => {
    expect(DEFAULT_AVATAR_CID).toBe("g-00");
  });
});

describe("resolveAssetUrl 约定路径 → 取图真地址（基地址+版本号单点）", () => {
  it("约定路径补版本号（H5 基地址为空即根相对）；非本站外链原样放行", () => {
    expect(resolveAssetUrl("/cosmetics/a-p1.webp")).toBe(
      `/cosmetics/a-p1.webp?v=${ASSET_REV}`,
    );
    expect(resolveAssetUrl("https://wx.example/head.jpg")).toBe(
      "https://wx.example/head.jpg",
    );
  });

  it("已带查询串不重复拼（幂等——宿主层重复解析不脏地址）", () => {
    const once = resolveAssetUrl("/cosmetics/a-p1.webp");
    expect(resolveAssetUrl(once)).toBe(once);
  });

  it("isCosmeticUrl 认约定路径与解析后的真地址（avatarfit 取参口径），不认外链", () => {
    expect(isCosmeticUrl("/cosmetics/a-p1.webp")).toBe(true);
    expect(isCosmeticUrl(resolveAssetUrl("/cosmetics/a-p1.webp"))).toBe(true);
    expect(isCosmeticUrl("https://wx.example/head.jpg")).toBe(false);
  });
});

describe("缺省焦点与册子规格（与后端 FOCUS/素材规格并列单源）", () => {
  it("首批统一焦点 68,37（后端 FOCUS_X/FOCUS_Y 同值）", () => {
    expect(DEFAULT_FOCUS).toEqual({ x: 0.68, y: 0.37 });
  });
  it("卡背素材规格 1536×640（12:5 横幅，A6）", () => {
    expect(BACK_SPEC).toEqual({ w: 1536, h: 640 });
  });
});

describe("slicePos 切片档定位", () => {
  it("焦点居中（0.5,0.5）横卡档：px 偏左上、py 偏右下（公式直推）", () => {
    // c 档 k=1.28 sx=.62：(.62−.64)/(−.28)=7.14…；sy=.42：(.42−.64)/(−.28)=78.57…
    expect(slicePos(WIN.c, 0.5, 0.5)).toEqual({ px: 7.1, py: 78.6 });
  });

  it("缺省焦点（.68,.37）行卡档：py 负值钳到 3（顶边）——原型同款落点", () => {
    // r 档 k=1.32：px=(.64−.8976)/(−.32)=80.5；py=(.52−.4884)/(−.32)=−9.875→钳 3
    expect(slicePos(WIN.r, DEFAULT_FOCUS.x, DEFAULT_FOCUS.y)).toEqual({
      px: 80.5,
      py: 3,
    });
  });

  it("焦点贴两角（0/0 与 1/1）：双侧钳 3 / 97——出界即吸到可达边缘，窗内永远出血", () => {
    expect(slicePos(WIN.r, 0, 0)).toEqual({ px: 3, py: 3 });
    expect(slicePos(WIN.c, 1, 1)).toEqual({ px: 97, py: 97 });
  });
});

describe("coverPos cover 档定位（量测后由组件喂容器宽高）", () => {
  it("容器恰同 12:5：两轴 k=1 无位移余量，兜 50%（与焦点/锚点无关）", () => {
    expect(
      coverPos(BACK_SPEC.w, BACK_SPEC.h, 1536, 640, 0.68, 0.37, 0.8, 0.42),
    ).toEqual({ px: 50, py: 50 });
    expect(
      coverPos(BACK_SPEC.w, BACK_SPEC.h, 384, 160, 0.1, 0.9, 0.9, 0.1),
    ).toEqual({ px: 50, py: 50 });
  });

  it("k<1.02（溢出不足 2%）位移不足 1px，落 50% 不误导检视", () => {
    // 容器 1536×641：kx=641×2.4/1536≈1.0016
    expect(
      coverPos(BACK_SPEC.w, BACK_SPEC.h, 1536, 641, 0.68, 0.37, 0.8, 0.42).px,
    ).toBe(50);
  });

  it("横条容器（榜单行 360×52）：x 轴无溢出钉 50%，y 轴 k=2.8846 按锚点吸焦", () => {
    // ky=360/(52×2.4)=2.884615…；py=(.42−k×.37)/(1−k)=34.34…
    expect(
      coverPos(BACK_SPEC.w, BACK_SPEC.h, 360, 52, 0.68, 0.37, 0.8, 0.42),
    ).toEqual({
      px: 50,
      py: 34.3,
    });
  });

  it("竖高容器（抽屉头带 320×480）：x 轴 k=3.6 按锚点吸焦、y 轴钉 50%", () => {
    // kx=480×2.4/320=3.6；px=(.7−3.6×.68)/(1−3.6)=67.23…
    expect(
      coverPos(BACK_SPEC.w, BACK_SPEC.h, 320, 480, 0.68, 0.37, 0.7, 0.45),
    ).toEqual({
      px: 67.2,
      py: 50,
    });
  });

  it("竖版素材（640×1536）同公式：aspect 由素材宽高现算，不写死 2.4", () => {
    // 竖图 ar=.4167：容器 320×480 → kx=1 兜 50%；ky=480/(480×.4167)=1.6，
    // py=(.45−1.6×.37)/(1−1.6)=23.66…
    expect(coverPos(640, 1536, 320, 480, 0.68, 0.37, 0.7, 0.45)).toEqual({
      px: 50,
      py: 23.7,
    });
  });

  it("锚点够不到（焦点贴边）：钳 3/97——cover 档同款钳位", () => {
    // 竖高容器 kx=3.6：fx=1,ax=0 → (0−3.6)/(−2.6)=138.5→97；fx=0,ax=1 → −38.5→3
    expect(
      coverPos(BACK_SPEC.w, BACK_SPEC.h, 320, 480, 1, 0.37, 0, 0.45).px,
    ).toBe(97);
    expect(
      coverPos(BACK_SPEC.w, BACK_SPEC.h, 320, 480, 0, 0.37, 1, 0.45).px,
    ).toBe(3);
  });
});
