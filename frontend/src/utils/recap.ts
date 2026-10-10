/* 战报页提示行文案（2.6 §4.1/4.3）：按「我是不是这局的人」（后端 live view 的
   is_my_game 定值，前端不自判）两分支——是 → 指路 我的-打球记录（赛后回看入口）；
   否（路人/未登录一律）→ 中性句，不指一条走不通的路。抽纯函数为可测
   （vitest 无 @vue/test-utils 挂不了 .vue）；消费点 LiveRecap 单一。 */
export const recapHint = (isMyGame: boolean): string =>
  isMyGame
    ? "球局已结束 · 赛后可在 我的-打球记录 翻看"
    : "球局已结束 · 战报仅供回看";

/** 链接死局统一句（2.6 §4.6：链接场景不说「已结束」——散场恰是翻得回战报的状态，
    404 只发生在真没有/已撤销）：单源常量防四处表面各写各的漂移——现场页死链态、
    战报子页死链态、详情页失效说明、live store 死链 toast 共用。 */
export const DEAD_LINK_MSG = "找不到这个球局，可能已被撤销";
