import { describe, expect, it } from "vitest";
import { RECAP_HINT, eloTotals } from "@/utils/recap";
import type { EloRow, MatchReport } from "@/api/types";

/* 2.6 门牌文案与名单积分合计抽纯函数为测（vitest 挂不了 .vue）；双钮 emit 与页面
   编排（收摊/返回/分享/约球）走浏览器走查覆盖。 */

const row = (accountId: number | null, delta: number): EloRow => ({
  accountId,
  name: "测试",
  guest: accountId == null,
  ratingBefore: 1200,
  ratingAfter: 1200 + delta,
  delta,
});

const m = (eloRows: EloRow[]): MatchReport => ({
  courtNo: 1,
  seq: 1,
  sideA: [],
  sideB: [],
  sa: 11,
  sb: 7,
  winA: true,
  endedAt: "2026-10-12T20:00:00+08:00",
  eloRows,
});

describe("RECAP_HINT（去向提示行：一句指路，条件显示归组件）", () => {
  it("只说去处，不带「球局已结束」前缀（kicker 已说一遍）", () => {
    expect(RECAP_HINT).toBe("赛后可在 我的-打球记录 翻看");
  });
});

describe("eloTotals（名单全场积分合计：落账行加总不重算）", () => {
  it("同人跨场累加、多人分账", () => {
    const t = eloTotals([m([row(1, 12), row(2, -7)]), m([row(1, -10)])]);
    expect(t.get(1)).toBe(2);
    expect(t.get(2)).toBe(-7);
  });

  it("访客（accountId null）不进汇总——同名会串且不落账", () => {
    expect(eloTotals([m([row(null, 12)])]).size).toBe(0);
  });

  it("没上过场的查无、零战报局空表", () => {
    expect(eloTotals([]).size).toBe(0);
    expect(eloTotals([m([])]).size).toBe(0);
  });
});
