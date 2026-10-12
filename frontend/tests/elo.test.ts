import { describe, expect, it } from "vitest";
import { ELO_INIT, duprOf, duprParts, duprTier, fmtDupr1 } from "@/utils/elo";

/* settleElo 的公式用例已随 2026-10-08 收归后端退役（前端零公式零镜像）——数字
   守门移至后端 test_live_score.py 的 test_pending_elo_preview_two_branches_equal_
   settlement（预演双分支与落账 elo_rows 逐行相等）。本文件只剩展示位。
   1.4 §3 公式口径备忘（实现=backend/app/services/live.py _elo_settle）：
   双打按两队人均分算期望落到个人；delta=max(1,round(K*(1-exp)))、败方只扣涨分
   六成（loss=max(1,round(delta*0.6))）；访客按 1200 代入全额算、自己不落账；地板 800。 */
describe("elo 展示残留位（公式已收归后端唯一源）", () => {
  it("ELO_INIT=1200：名册无积分行的展示兜底（1.4 §3；真值在后端）", () => {
    expect(ELO_INIT).toBe(1200);
  });
});

describe("DUPR 展示（1.4 §1/§2：三位小数 + 段位档）", () => {
  it("duprParts 三位小数分段（主数字分层形态；2026-10-12 分层批，整串 fmtDupr 退役）", () => {
    expect(duprParts(3.52)).toEqual({ head: "3", tail: ".520" });
    expect(duprParts(3.5)).toEqual({ head: "3", tail: ".500" });
    expect(duprParts(4)).toEqual({ head: "4", tail: ".000" });
    expect(duprParts(2.875)).toEqual({ head: "2", tail: ".875" });
    // head+tail 拼回 = 三位小数整串（口径自洽）
    for (const d of [2.0, 2.5, 3.052, 4.4, 7.999]) {
      const { head, tail } = duprParts(d);
      expect(head + tail).toBe(d.toFixed(3));
    }
  });

  it("duprOf 兜底单一源：空值/缺行一律回访客标准分 2.5（1.4 §4；六文件 13 处收编）", () => {
    expect(duprOf({ dupr: 3.52 })).toBe(3.52);
    expect(duprOf({})).toBe(2.5);
    expect(duprOf({ dupr: null })).toBe(2.5);
    expect(duprOf(undefined)).toBe(2.5); // rotate 配对查无行
  });

  it("fmtDupr1 一位小数（现场小字）", () => {
    expect(fmtDupr1(3.52)).toBe("3.5");
    expect(fmtDupr1(3.48)).toBe("3.5");
    expect(fmtDupr1(2.44)).toBe("2.4");
    expect(fmtDupr1(4.04)).toBe("4.0");
  });

  it("duprTier 段位边界：2.5 / 3.0 / 3.5 / 4.0 各档左闭右开", () => {
    expect(duprTier(2.0)).toBe("2.0");
    expect(duprTier(2.499)).toBe("2.0");
    expect(duprTier(2.5)).toBe("2.5");
    expect(duprTier(2.999)).toBe("2.5");
    expect(duprTier(3.0)).toBe("3.0");
    expect(duprTier(3.499)).toBe("3.0");
    expect(duprTier(3.5)).toBe("3.5");
    expect(duprTier(3.999)).toBe("3.5");
    expect(duprTier(4.0)).toBe("4.0+");
    expect(duprTier(4.6)).toBe("4.0+");
  });
});
