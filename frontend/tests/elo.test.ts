import { describe, expect, it } from 'vitest';
import { ELO_K, fmtScore, ntrp, settleElo, tier } from '@/utils/elo';

/** 手工对照 alpha:1688-1714 公式的推演值：
    exp = 1/(1+10^((lAvg-wAvg)/400))，delta=max(1,round(24*(1-exp)))，loss=max(1,round(delta*0.6)) */
describe('elo settleElo（K=24 · 败方六成 · 地板 400 · 随行半权重 · 双打人均）', () => {
  it('同分 1500 vs 1500：涨 12 / 扣 7', () => {
    const r = settleElo([{ elo: 1500 }], [{ elo: 1500 }]);
    // exp=0.5 → delta=round(24*0.5)=12；loss=round(12*0.6)=round(7.2)=7
    expect(r[0]).toEqual({ up: true, d: 12, elo: 1512 });
    expect(r[1]).toEqual({ up: false, d: -7, elo: 1493 });
  });

  it('强者胜弱者：小涨（1600 胜 1400 → +6 / -4）', () => {
    const r = settleElo([{ elo: 1600 }], [{ elo: 1400 }]);
    // lAvg-wAvg=-200 → exp≈0.7597 → delta=round(5.767)=6 → loss=round(3.6)=4
    expect(r[0].d).toBe(6);
    expect(r[0].elo).toBe(1606);
    expect(r[1].d).toBe(-4);
    expect(r[1].elo).toBe(1396);
  });

  it('爆冷大涨（1400 胜 1600 → +18 / -11）', () => {
    const r = settleElo([{ elo: 1400 }], [{ elo: 1600 }]);
    // lAvg-wAvg=200 → exp≈0.2403 → delta=round(18.23)=18 → loss=round(10.8)=11
    expect(r[0].d).toBe(18);
    expect(r[0].elo).toBe(1418);
    expect(r[1].d).toBe(-11);
    expect(r[1].elo).toBe(1589);
  });

  it('随行访客：期望按 1200 计、涨跌半权重（涨 ceil / 跌 floor）', () => {
    const r = settleElo([{ elo: 1200, shadow: true }], [{ elo: 1500 }]);
    // rat(胜)=1200 → lAvg-wAvg=300 → exp=1/(1+10^0.75)≈0.15098 → delta=round(20.376)=20
    // 随行 d=ceil(20/2)=10；败方 loss=round(12)=12
    expect(r[0]).toEqual({ up: true, d: 10, elo: 1210 });
    expect(r[1]).toEqual({ up: false, d: -12, elo: 1488 });
  });

  it('地板 400：401 输 1 分也只到 400', () => {
    const r = settleElo([{ elo: 1500 }], [{ elo: 401 }]);
    // 碾压 → delta=max(1,0)=1 → loss=max(1,round(0.6))=1 → max(400, 400)=400
    expect(r[1].elo).toBe(400);
    expect(r[1].d).toBe(-1);
  });

  it('双打按两队人均分结算到个人', () => {
    const r = settleElo([{ elo: 1600 }, { elo: 1400 }], [{ elo: 1500 }, { elo: 1500 }]);
    // 两队人均都是 1500 → 每人同样涨跌：+12 / -7
    expect(r.map((x) => x.d)).toEqual([12, 12, -7, -7]);
    expect(r.map((x) => x.elo)).toEqual([1612, 1412, 1493, 1493]);
    expect(r.map((x) => x.up)).toEqual([true, true, false, false]);
  });

  it('K 常量 = 24（alpha:1697）', () => {
    expect(ELO_K).toBe(24);
  });
});

describe('ntrp / tier / fmtScore（alpha:851-863）', () => {
  it('ntrp 分级阈值', () => {
    expect(ntrp(1721)).toBe('4.5');
    expect(ntrp(1700)).toBe('4.5');
    expect(ntrp(1699)).toBe('4.0');
    expect(ntrp(1655)).toBe('4.0');
    expect(ntrp(1600)).toBe('4.0');
    expect(ntrp(1599)).toBe('3.5');
    expect(ntrp(1518)).toBe('3.5');
    expect(ntrp(1500)).toBe('3.5');
    expect(ntrp(1499)).toBe('3.0');
    expect(ntrp(1400)).toBe('3.0');
    expect(ntrp(1399)).toBe('2.5');
    expect(ntrp(1300)).toBe('2.5');
    expect(ntrp(1299)).toBe('2.0');
  });

  it('tier 段位', () => {
    expect(tier(1721)).toBe('SS');
    expect(tier(1688)).toBe('S');
    expect(tier(1602)).toBe('S');
    expect(tier(1574)).toBe('A');
    expect(tier(1498)).toBe('B');
    expect(tier(1380)).toBe('C');
  });

  it('fmtScore 双分制', () => {
    expect(fmtScore(1518, 'elo')).toBe(1518);
    expect(fmtScore(1518.6, 'elo')).toBe(1519);
    expect(fmtScore(1518, 'ntrp')).toBe('3.5');
    expect(fmtScore(1721, 'ntrp')).toBe('4.5');
  });
});
