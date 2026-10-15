/* 两张卡步进表单一源（2.7 批1）——提示行文案+光圈锚+完成判据+自动步超时。
   文案逐字抄规格 §7 A3 步进表（含参与卡第 7 条双分支）；锚 key 是 steps→组件
   的私有协议（组件挂 :class="{ 'sb-glow': curSpot===锚 }"，目标不在自然不显示）。
   完成判据吃 SandState 快照，两类快照看不出的走 TutorEv：记 1 分（本地记分
   账不进 engine）、一次换人（状态无痕）。「约一拍自动进下一条」的停顿节奏归
   store 编排层（本表只记状态判据与两条定时步：第 7 条 4 秒、final 收尾 5 秒
   ——批3 定形：final 行的「几秒后收成尾巴」也走 autoAfterMs，store autoTimer
   推过末条即尾巴态，不另设机制）。 */
import type { SandState } from "./engine";
import { arrived, pOf } from "./engine";

/** 教学事件（store 编排层在动作/本地记分后喂给判据） */
export interface TutorEv {
  kind: "score" | "swap" | "qr";
  mine?: boolean; // score：是不是你队的数字
}

export interface TutorStep {
  text: string | ((s: SandState) => string); // 函数形=随状态换句（第 7 条歇没歇两句/组织卡收尾句）
  spot?: string | ((s: SandState) => string | null); // 光圈锚 key（缺省=无光圈；函数形=随状态熄——组织卡末条散场后整行是收尾出口，不再指散场钮）
  done?: (s: SandState, ev?: TutorEv) => boolean; // 缺省=不由状态推进（自动步/收尾行归 store）
  autoAfterMs?: number | ((s: SandState) => number | null); // 停 N 毫秒自动进下一条（函数形=条件自动步——组织卡末条要等散场收工完才收尾巴，进条时不计时）
  final?: boolean; // 收尾行：点击跳约球页、几秒后收成尾部小条
}

const youOf = (s: SandState) => s.players.find((p) => p.you)!;
const onCourt = (s: SandState, id: number) =>
  s.courts.some((c) => c.a.includes(id) || c.b.includes(id));
const arrivedP = (s: SandState, name: string) =>
  arrived(s.players.find((p) => p.name === name)!);
const inQueue = (s: SandState, name: string) =>
  s.queue.includes(s.players.find((p) => p.name === name)!.id);

/** 参与卡八条（规格 A3）——普通球员视角：签到→自动开赛→记分→两场结算→歇一轮 */
export const PARTICIPATE_STEPS: TutorStep[] = [
  {
    // 锚【我到了】钮（差人卡上）
    text: "这局是示例——点『我到了』，你也进场",
    spot: "me-checkin",
    done: (s) => s.queue.includes(youOf(s).id), // 候场出现「你」
  },
  {
    text: "凑够 4 人场就自动开——稍等大家一下",
    done: (s) => onCourt(s, youOf(s).id), // 球球到场自动开赛、你上场（NPC 定时器在 store）
  },
  {
    // 锚顶条二维码钮（v2.8 亮码升为一步，推翻「不占提示步」）：点开示意浮层即算
    // 完成——浮层里那句「已到场的人都能亮这张码收人」就是本步的正文。完成判据
    // 只认点击事件、状态恒不成立（NPC 定时器级联跳不了这步）；不模拟「朋友真扫
    // 码进场」——教学零联网，剧本加空降会打乱轮转数字账的确定性（§8 v2.8）
    text: "想拉朋友进来？点顶条的二维码亮码——朋友扫码填个称呼就能进场打球",
    spot: "qr-btn",
    done: (_s, ev) => ev?.kind === "qr", // 点开示意浮层
  },
  {
    // 锚你队的比分数字
    text: "轮到你了——点你们队的数字记分；点错了点冒号旁的撤回",
    spot: "my-score",
    done: (_s, ev) => ev?.kind === "score" && ev.mine === true, // 你记了 1 分（本地账）
  },
  {
    text: "把这场打到 11 分（净胜 2），走一次结算",
    spot: "my-score",
    done: (s) => s.matches.length >= 1, // 第一次结算确认
  },
  {
    // 锚你在场上的头像（点人抽屉入口）。第二场的引导要在本句里给足：不歇的
    // 用户第二场结算时本步与第 6 步同拍级联翻过，第 6 句没有显示的机会
    text: "先上的先下——你不下接着打，把第二场打到 11 分再走一次结算。打累了？点自己的头像，选『休息一轮』",
    spot: "my-avatar",
    done: (s) => youOf(s).skip > 0 || s.matches.length >= 2, // 设了歇，或第二场结算确认（不歇也放行）
  },
  {
    text: "把第二场打完，再走一次结算",
    spot: "my-score",
    done: (s) => s.matches.length >= 2,
  },
  {
    // 按歇没歇分两句（规格 A3 第 7 条）
    text: (s) =>
      youOf(s).skip > 0
        ? "你下场了，歇的那一轮也记上了——现场就是这么转起来的"
        : "下次累了可以先歇——点自己的头像就行。现场就是这么转起来的",
    autoAfterMs: 4000, // 停 4 秒自动进下一条
  },
  {
    text: "想打真的？去约球页找个真局 ▸",
    autoAfterMs: 5000, // 整行可点跳约球页；不点几秒后收成尾部小条（store autoTimer 推过末条=尾巴态）
    final: true, // 收尾行：点击跳约球页（真出口）
  },
];

/** 组织卡十条（规格 A3）——组织者全权视角：自动开赛观演→代办→带访客→改规→
    换人→封管理员→加片→快速结算→散场收工；ended 后换收尾句跳发局 */
export const ORGANIZE_STEPS: TutorStep[] = [
  {
    // 球球到=第 4 人签到即自动开赛的那一刻翻面——文案与开赛画面同拍；若等老金
    // （晚 800ms）才翻，开赛已发生在本句展示期间，文案时序与画面错位
    text: "你是这局的组织者——人够就开赛",
    done: (s) => arrivedP(s, "球球"),
  },
  {
    // 观演步停一拍（规格 A3「约一拍自动进下一条」）：判据版会在老金到场时被
    // 同拍级联直接跳过——「开赛不用谁按」这句就永远显示不出来，故纯定时
    text: "人够 4 个局就自己开——开赛不用谁按",
    autoAfterMs: 2000,
  },
  {
    // 锚【＋到场】钮（候场条上，全权亮）
    text: "凯文迟到了——点【＋到场】给他签到",
    spot: "checkin-btn",
    done: (s) => inQueue(s, "凯文"), // 凯文入候场队尾
  },
  {
    // 锚签到抽屉里的「带访客」
    text: "朋友没注册也能来——同一抽屉『带访客』",
    spot: "bring-guest",
    done: (s) => s.players.some((p) => p.guest && arrived(p)), // 访客入候场（带徽章）
  },
  {
    // 锚顶条赛制模式入口
    text: "规矩你说了算——改改分制试试",
    spot: "rules-entry",
    done: (s) => s.scoring === 15, // 分制改成 15（下一场起生效）
  },
  {
    // 锚场上任一头像。点名换入对象（v2.13）：球球↔老金是剧本正路——若把凯文
    // 换上场，第七步「封凯文」的主线就断了（场上的候场者没有设管理员钮），
    // 所以文案直接指到人；换谁都照样翻面（判据吃事件宽容）
    text: "排得不顺眼？点场上【球球】的头像，把他换成【老金】",
    spot: "court-avatar",
    done: (_s, ev) => ev?.kind === "swap", // 一次换人落位（状态无痕，吃事件）
  },
  {
    // 锚候场里的凯文（整排亮）。点名自适应（v2.13）：凯文还候场就点名凯文；
    // 被第六步自由操作换上了场，就改点名候场里第一个可封的人（非访客未封）
    // ——点名指主线，谁候场封谁，什么换法都保得住
    text: (s) => {
      const k = s.players.find((p) => p.name === "凯文")!;
      const first = s.queue
        .map((id) => pOf(s, id))
        .find((p) => !p.guest && !p.admin);
      const name = s.queue.includes(k.id) ? k.name : (first?.name ?? "球友");
      return `临时不在场？点候场里的【${name}】，封他当管理员`;
    },
    spot: "queue-kevin",
    // 判据=封了任一人：文案点名凯文为主线，照点别人也放行（v2.9 用户实测教训
    // 的另一半——文案与判据同一口径：指名是引导，宽容是出口）
    done: (s) => s.players.some((p) => p.admin),
  },
  {
    // 锚顶条场地格（直填出口）
    text: "人多起来了——顶条场地格填『2』加一片",
    spot: "courts-cell",
    done: (s) =>
      s.courts.some((c) => c.no === 2 && c.a.length + c.b.length > 0), // 第二片自动开出、四人上场（填完即开，无按钮）
  },
  {
    // 锚对局卡上的【本场完成】钮（全权专属）。两片各结一次——光圈一次只亮该结的
    // 那片（在打且未结算过的最靠前片，锚带片号），结完一颗换下一颗（用户裁决：
    // 两颗同闪分不清先结哪场）。用户跳过锚先结另一片也照算（判据只数场数）
    text: "打完不用一分一分点——点『本场完成』，把比分直接填进去",
    spot: (s) => {
      const settled = new Set(s.matches.map((m) => m.courtNo));
      const c = s.courts.find(
        (cc) => (cc.a.length || cc.b.length) && !settled.has(cc.no),
      );
      return c ? `quick-settle-${c.no}` : null;
    },
    done: (s) => s.matches.length >= 2, // 两片各结算一次
  },
  {
    // 散场进行中锚散场入口；ended 后换收尾句（规格 4.3 收尾，点击跳发局）、
    // 光圈熄（出口已不是散场钮）、几秒后收尾巴（「之后同参与卡」——从收尾句起算）
    text: (s) =>
      s.ended
        ? "组织者的事就这些——去发个真局 ▸"
        : "都打完了——散场收工，看看费用怎么摊",
    spot: (s) => (s.ended ? null : "sweep-entry"),
    autoAfterMs: (s) => (s.ended ? 5000 : null),
    final: true,
  },
];
