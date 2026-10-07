/* 5.1 分数体系：Elo 娱乐轨引擎（1.4 §3：初始 1200/地板 800，只担弹窗±等情绪反馈）+
   DUPR 展示函数（1.4 §1/§2） */

export const ELO_K = 24; // alpha:1697 K=24：赢强者涨得多（1.4 §3：K 不动）
export const ELO_INIT = 1200; // 1.4 §3：初始 1200（推翻 2.3 的 1500）；访客/新人代入
export const ELO_FLOOR = 800; // 1.4 §3：地板 800（娱乐轨收窄波动区间；推翻 2.3 的 400）

/* ───────── DUPR 展示（1.4 §1：2.0-8.0 三位小数；消费方批4v1 接线）───────── */

/** 访客/查无者 DUPR 标准分（1.4 §4 恒 3.0 = 自评默认档；对齐后端 dupr.py GUEST_DUPR）。
    rankOf/live 兜底/mock zhao 三处消费 */
export const GUEST_DUPR = 3.0;

/** DUPR 主数字：三位小数（1.4 §1 形态，如 3.52 → "3.520"） */
export function fmtDupr(d: number): string {
  return d.toFixed(3);
}

/** DUPR 小字：一位小数（现场候场条/卡片小字用） */
export function fmtDupr1(d: number): string {
  return d.toFixed(1);
}

/** DUPR 段位档名（1.4 §2 段位口径：按 2.5/3.0/3.5/4.0+ 档映射；<2.5 归 "2.0"） */
export function duprTier(d: number): string {
  if (d >= 4.0) return "4.0+";
  if (d >= 3.5) return "3.5";
  if (d >= 3.0) return "3.0";
  if (d >= 2.5) return "2.5";
  return "2.0";
}

/** DUPR 段位徽章配色（按档名给，TierBadge 消费）：4.0+ 最高档珊瑚、3.5 柠檬、
    3.0 电青、2.5 丁香、2.0 入门近中性；档名单一源在 duprTier，键不会 miss */
export const DUPR_TIER_BG: Record<string, string> = {
  "4.0+": "rgba(255,90,54,.2)",
  "3.5": "rgba(255,212,0,.18)",
  "3.0": "rgba(111,231,255,.16)",
  "2.5": "rgba(184,169,255,.16)",
  "2.0": "rgba(245,241,232,.1)",
};
export const DUPR_TIER_FG: Record<string, string> = {
  "4.0+": "var(--coral)",
  "3.5": "var(--lemon)",
  "3.0": "var(--ice)",
  "2.5": "var(--lilac)",
  "2.0": "var(--dim)",
};

export interface EloPlayer {
  elo: number;
}

/** 结算结果（按「胜队在前、败队在后」的顺序返回每人一项） */
export interface EloOutcome {
  up: boolean;
  d: number;
  elo: number;
}

/** K=24 结算（alpha:1688-1714 公式逐条对齐）：
    - 双打按两队人均分算期望、落到个人（alpha:1692 唯一算得平的办法）；
    - delta = max(1, round(K*(1-exp)))，loss = max(1, round(delta*0.6))（败方只扣胜方涨分的六成）；
    - 地板 800（1.4 §3）。
    随行访客没有「另册」：调用方按初始等级 1200 代入（1.4 §4 访客 Elo 恒 1200——
    不计积分不进榜，代入值与正式球友同公式全额算），本函数不认访客身份。
    输入只需每人的 elo，不产生副作用（终局弹窗的 ±积分预览调它；落账真值在后端镜像）。 */
export function settleElo(
  winners: EloPlayer[],
  losers: EloPlayer[],
): EloOutcome[] {
  const wAvg = winners.reduce((a, b) => a + b.elo, 0) / winners.length; // alpha:1694
  const lAvg = losers.reduce((a, b) => a + b.elo, 0) / losers.length; // alpha:1695
  const exp = 1 / (1 + Math.pow(10, (lAvg - wAvg) / 400)); // alpha:1696
  const delta = Math.max(1, Math.round(ELO_K * (1 - exp))); // alpha:1697
  const loss = Math.max(1, Math.round(delta * 0.6)); // alpha:1698 败方只扣胜方涨分的六成
  return winners.concat(losers).map((p, i) => {
    const up = i < winners.length;
    const d = up ? delta : -loss;
    return { up, d, elo: Math.max(ELO_FLOOR, p.elo + d) }; // 地板 800（1.4 §3）
  });
}
