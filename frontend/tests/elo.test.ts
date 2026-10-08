import { describe, expect, it } from "vitest";
import { ELO_INIT, duprTier, fmtDupr, fmtDupr1 } from "@/utils/elo";

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
  it("fmtDupr 三位小数（主数字形态）", () => {
    expect(fmtDupr(3.52)).toBe("3.520");
    expect(fmtDupr(3.5)).toBe("3.500");
    expect(fmtDupr(4)).toBe("4.000");
    expect(fmtDupr(2.875)).toBe("2.875");
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
