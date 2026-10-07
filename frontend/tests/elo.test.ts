import { describe, expect, it } from "vitest";
import {
  ELO_FLOOR,
  ELO_INIT,
  ELO_K,
  duprTier,
  fmtDupr,
  fmtDupr1,
  fmtScore,
  ntrp,
  settleElo,
  tier,
} from "@/utils/elo";

/** 手工对照 alpha:1688-1714 公式的推演值：
    exp = 1/(1+10^((lAvg-wAvg)/400))，delta=max(1,round(24*(1-exp)))，loss=max(1,round(delta*0.6)) */
describe("elo settleElo（K=24 · 败方六成 · 地板 800 · 访客 1200 全额 · 双打人均）", () => {
  it("常量：初始 1200 / 地板 800 / K=24（1.4 §3 参数迁移）", () => {
    expect(ELO_INIT).toBe(1200);
    expect(ELO_FLOOR).toBe(800);
    expect(ELO_K).toBe(24);
  });

  it("同分 1200 vs 1200：涨 12 / 扣 7", () => {
    const r = settleElo([{ elo: 1200 }], [{ elo: 1200 }]);
    // exp=0.5 → delta=round(24*0.5)=12；loss=round(12*0.6)=round(7.2)=7
    expect(r[0]).toEqual({ up: true, d: 12, elo: 1212 });
    expect(r[1]).toEqual({ up: false, d: -7, elo: 1193 });
  });

  it("强者胜弱者：小涨（1600 胜 1400 → +6 / -4）", () => {
    const r = settleElo([{ elo: 1600 }], [{ elo: 1400 }]);
    // lAvg-wAvg=-200 → exp≈0.7597 → delta=round(5.767)=6 → loss=round(3.6)=4
    expect(r[0].d).toBe(6);
    expect(r[0].elo).toBe(1606);
    expect(r[1].d).toBe(-4);
    expect(r[1].elo).toBe(1396);
  });

  it("爆冷大涨（1400 胜 1600 → +18 / -11）", () => {
    const r = settleElo([{ elo: 1400 }], [{ elo: 1600 }]);
    // lAvg-wAvg=200 → exp≈0.2403 → delta=round(18.23)=18 → loss=round(10.8)=11
    expect(r[0].d).toBe(18);
    expect(r[0].elo).toBe(1418);
    expect(r[1].d).toBe(-11);
    expect(r[1].elo).toBe(1589);
  });

  it("访客按初始 1200 代入、同公式全额（1.4 §4：访客 Elo 恒 1200，自己不落账）", () => {
    // 访客代入 1200 打 1400 正式球友并赢：lAvg-wAvg=200 → exp≈0.2403 → delta=round(18.23)=18
    // → loss=round(10.8)=11；无半折无另册——代入值当正常玩家算
    const r = settleElo([{ elo: 1200 }], [{ elo: 1400 }]);
    expect(r[0]).toEqual({ up: true, d: 18, elo: 1218 });
    expect(r[1]).toEqual({ up: false, d: -11, elo: 1389 });
  });

  it("地板 800：801 输 1 分也只到 800", () => {
    const r = settleElo([{ elo: 1200 }], [{ elo: 801 }]);
    // 碾压 → exp≈0.909 → delta=round(2.19)=2 → loss=round(1.2)=1 → max(800, 800)=800
    expect(r[1].elo).toBe(800);
    expect(r[1].d).toBe(-1);
  });

  it("双打按两队人均分结算到个人", () => {
    const r = settleElo(
      [{ elo: 1600 }, { elo: 1400 }],
      [{ elo: 1500 }, { elo: 1500 }],
    );
    // 两队人均都是 1500 → 每人同样涨跌：+12 / -7
    expect(r.map((x) => x.d)).toEqual([12, 12, -7, -7]);
    expect(r.map((x) => x.elo)).toEqual([1612, 1412, 1493, 1493]);
    expect(r.map((x) => x.up)).toEqual([true, true, false, false]);
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

describe("ntrp / tier / fmtScore（alpha:851-863）", () => {
  it("ntrp 分级阈值", () => {
    expect(ntrp(1721)).toBe("4.5");
    expect(ntrp(1700)).toBe("4.5");
    expect(ntrp(1699)).toBe("4.0");
    expect(ntrp(1655)).toBe("4.0");
    expect(ntrp(1600)).toBe("4.0");
    expect(ntrp(1599)).toBe("3.5");
    expect(ntrp(1518)).toBe("3.5");
    expect(ntrp(1500)).toBe("3.5");
    expect(ntrp(1499)).toBe("3.0");
    expect(ntrp(1400)).toBe("3.0");
    expect(ntrp(1399)).toBe("2.5");
    expect(ntrp(1300)).toBe("2.5");
    expect(ntrp(1299)).toBe("2.0");
  });

  it("tier 段位", () => {
    expect(tier(1721)).toBe("SS");
    expect(tier(1688)).toBe("S");
    expect(tier(1602)).toBe("S");
    expect(tier(1574)).toBe("A");
    expect(tier(1498)).toBe("B");
    expect(tier(1380)).toBe("C");
  });

  it("fmtScore 双分制", () => {
    expect(fmtScore(1518, "elo")).toBe(1518);
    expect(fmtScore(1518.6, "elo")).toBe(1519);
    expect(fmtScore(1518, "ntrp")).toBe("3.5");
    expect(fmtScore(1721, "ntrp")).toBe("4.5");
  });
});
