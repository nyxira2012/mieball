/* 战报域文案与名单积分汇总单一源（2.6 §4.1/§4.3，2026-10-12 UI 修订）——抽纯函数
   为可测（vitest 无 @vue/test-utils 挂不了 .vue）；消费点 LiveRecap 单一。 */
import type { MatchReport } from "@/api/types";

/** 去向提示行（recapHint 两分支退役：路人中性句与子页语境都是绕圈话；显不显示归组件 door+is_my_game） */
export const RECAP_HINT = "赛后可在 我的-打球记录 翻看";

/* 分享复制兜底提示随三处分享统一（2026-10-12）移居 utils/share 默认句，
   RECAP_COPY_MSG 退役——战报/详情/现场门牌同一句「链接已复制 · 访客可看」 */

/** 链接死局统一句（§4.6 链接场景不说「已结束」——散场恰是翻得回战报的状态）：四表面共用 */
export const DEAD_LINK_MSG = "找不到这个球局，可能已被撤销";

/** 名单行全场积分合计：只加总落账 eloRows 不重算（A4 不破口）。访客 accountId null
    同名会串且本就不落账——不进汇总，名单行维持「访客 · 不计积分」标识 */
export function eloTotals(matches: MatchReport[]): Map<number, number> {
  const totals = new Map<number, number>();
  for (const m of matches)
    for (const r of m.eloRows)
      if (r.accountId != null)
        totals.set(r.accountId, (totals.get(r.accountId) ?? 0) + r.delta);
  return totals;
}
