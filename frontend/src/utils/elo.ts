/* 5.1 分数体系：Elo 引擎 (1500 起步) + NTRP 分级展示（alpha:849-865, 1688-1714） */
import type { ScoreMode } from '@/api/types';

export type Tier = 'SS' | 'S' | 'A' | 'B' | 'C';

/** NTRP 分级阈值（alpha:851-858 逐字对齐） */
export function ntrp(e: number): string {
  if (e >= 1700) return '4.5';
  if (e >= 1600) return '4.0';
  if (e >= 1500) return '3.5';
  if (e >= 1400) return '3.0';
  if (e >= 1300) return '2.5';
  return '2.0';
}

/** 分制展示（alpha:859；mode 来自 ui store 的 scoreMode） */
export function fmtScore(e: number, mode: ScoreMode = 'elo'): number | string {
  return mode === 'elo' ? Math.round(e) : ntrp(e);
}

/** 段位（alpha:860） */
export function tier(e: number): Tier {
  return e >= 1700 ? 'SS' : e >= 1600 ? 'S' : e >= 1500 ? 'A' : e >= 1400 ? 'B' : 'C';
}

/** 段位徽章配色（alpha:861-862 值原样；TierBadge 组件消费） */
export const TIER_BG: Record<Tier, string> = {
  SS: 'rgba(255,90,54,.2)', S: 'rgba(255,212,0,.18)', A: 'rgba(111,231,255,.16)',
  B: 'rgba(184,169,255,.16)', C: 'rgba(245,241,232,.1)',
};
export const TIER_FG: Record<Tier, string> = {
  SS: 'var(--coral)', S: 'var(--lemon)', A: 'var(--ice)', B: 'var(--lilac)', C: 'var(--dim)',
};

export const ELO_K = 24;      // alpha:1697 K=24：赢强者涨得多
export const ELO_FLOOR = 400; // alpha:1704 地板 400
const SHADOW_RATING = 1200;   // alpha:1693 随行访客按 1200 计入期望

export interface EloPlayer { elo: number; shadow?: boolean }

/** 结算结果（按「胜队在前、败队在后」的顺序返回每人一项） */
export interface EloOutcome { up: boolean; d: number; elo: number }

/** K=24 结算（alpha:1688-1714 公式逐条对齐）：
    - 双打按两队人均分算期望、落到个人（alpha:1692 唯一算得平的办法）；
    - delta = max(1, round(K*(1-exp)))，loss = max(1, round(delta*0.6))（败方只扣胜方涨分的六成）；
    - 随行访客半权重（涨取 ceil、跌取 floor，不进榜）；地板 400。
    输入只需每人的 elo 与 shadow，不产生副作用（落账由 live store 的 endMatch 做）。 */
export function settleElo(winners: EloPlayer[], losers: EloPlayer[]): EloOutcome[] {
  const rat = (p: EloPlayer): number => (p.shadow ? SHADOW_RATING : p.elo); // alpha:1693
  const wAvg = winners.map(rat).reduce((a, b) => a + b, 0) / winners.length;   // alpha:1694
  const lAvg = losers.map(rat).reduce((a, b) => a + b, 0) / losers.length;     // alpha:1695
  const exp = 1 / (1 + Math.pow(10, (lAvg - wAvg) / 400));                     // alpha:1696
  const delta = Math.max(1, Math.round(ELO_K * (1 - exp)));                    // alpha:1697
  const loss = Math.max(1, Math.round(delta * 0.6));                           // alpha:1698 败方只扣胜方涨分的六成
  return winners.concat(losers).map((p, i) => {
    const up = i < winners.length;
    let d = up ? delta : -loss;
    if (p.shadow) d = d > 0 ? Math.ceil(d / 2) : Math.floor(d / 2); // alpha:1703 访客半权重（不进榜）
    return { up, d, elo: Math.max(ELO_FLOOR, p.elo + d) };          // alpha:1704 地板 400
  });
}
