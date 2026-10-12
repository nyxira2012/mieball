/* 5.1 分数体系：Elo 展示残留位 + DUPR 展示函数（1.4 §1/§2）。
   Elo 公式与常量已收归后端唯一源（2026-10-08：backend/app/services/live.py 的
   _ELO_K/_ELO_FLOOR/RATING_INIT 与 _elo_settle；确认窗 ±预演由视图 elo_preview
   双分支下发，预演=落账）——前端零公式零镜像，调参只改后端一处。
   本文件只剩 ELO_INIT 展示兜底与 DUPR 展示族 */

export const ELO_INIT = 1200; // 展示兜底位：名册无积分行的默认显示（公式与真值在后端）

/* ───────── DUPR 展示（1.4 §1：2.0-8.0 三位小数；消费方批4v1 接线）───────── */

/** 访客/查无者 DUPR 标准分（1.4 §4+§5 修订：与新号起步同源 2.5——自评废除；
    对齐后端 dupr.py GUEST_DUPR）。rankOf/live 兜底/mock zhao 三处消费 */
export const GUEST_DUPR = 2.5;

/** DUPR 主数字分段：head=整数位（原字号原色）、tail=小数位含点（".520"）
    由消费方缩淡——整数给档位重心、小数留精度的通行分层。唯一消费口
    ui/DuprScore 组件（整串 fmtDupr 已随分层退役：三位小数口径由本函数钉） */
export function duprParts(d: number): { head: string; tail: string } {
  const s = d.toFixed(3);
  const i = s.indexOf(".");
  return { head: s.slice(0, i), tail: s.slice(i) };
}

/** DUPR 展示取数：空值（未定级/访客缺数/查无此人）按访客标准分兜底（1.4 §4）——
    兜底动作单一源（2026-10-12 收编：原先六文件 13 处各拼一遍 ?? GUEST_DUPR），
    改兜底口径只动这里；入参可空（rotate 配对查无行时 p 为 undefined） */
export function duprOf(u?: { dupr?: number | null } | null): number {
  return u?.dupr ?? GUEST_DUPR;
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

/* ───────── 以下为 1.4 §3 的公式口径备忘（settleElo 已随 2026-10-08 收归后端
   退役，实现见 backend/app/services/live.py _elo_settle）：
   - 双打按两队人均分算期望、落到个人；
   - delta = max(1, round(K*(1-exp)))，loss = max(1, round(delta*0.6))（败方只扣胜方涨分六成）；
   - 访客按初始 1200 代入当正常玩家全额算，自己不落账不进榜（1.4 §4）；
   - 地板 800。调参与改公式都在后端一处完成。 ───────── */
