/* 沙盒示例数据单一源（2.7 批1）——两张教学卡画面上出现的每个名字/数字/句子都
   从这里来，进卡瞬间可用、零联网（规格 §7 A4「数据从哪来」）。零框架 import：
   头像是公共款素材 URL（assetUrl 拼约定路径，渲染在 UI 层 AvatarBadge）。
   防误认红线（规格 §6）：假名+小头像、局名场馆带「示例」、已登录也统一「你」
   +默认头像。 */
import { DEFAULT_AVATAR_CID, assetUrl } from "@/utils/cardbg";

/** 名册种子行：check=进卡时的初始考勤（'ok' 开场已在候场 / 'none' 还没到，
    到场时机由 NPC 调度表或用户动作推进）。行序=名册序：资历并列时的先下判定
    按它稳定排序（engine byTenure），两张卡的剧本阵容靠行序锁定，别调换。 */
export interface SandSeed {
  name: string;
  /** 公共头像素材 URL（示例局人物指定公共款，不占个人衣柜）；assetUrl 单一源拼路径 */
  avatar: string;
  check: "ok" | "none";
  you?: boolean; // 示例局里的「你」（两卡各一粒，id 由 engine 按行序编）
  guest?: boolean; // 访客行：带访客时才签到进场（待签列表不显示它，走「带访客」表单）
  organizer?: boolean; // 组织者（参与卡=阿豪、组织卡=你；engine 落 organizerId）
}

/** 公共款轮换指派：假人各穿一款公共头像（同一人两卡同款）、你与访客吃默认
    第一款（防误认红线「默认形象」的真局同款口径） */
const AV = {
  def: assetUrl(DEFAULT_AVATAR_CID), // 你 / 访客「朋友」（跟全站默认款）
  hao: assetUrl("a-p2"),
  zhou: assetUrl("a-p3"),
  qiu: assetUrl("a-p4"),
  jin: assetUrl("a-p5"),
  lu: assetUrl("a-p6"),
  min: assetUrl("a-p2"), // 款少人多必有复用：小敏与阿豪分属两卡不撞面，老周/凯文同场同款 a-p3 属预期
  kevin: assetUrl("a-p3"),
} as const;

/** 假局信息（两卡共用）：分制 11 起步，组织卡第五步改 15；down/pairing 只作
    规则抽屉展示位——engine 的轮转口径固定 n2·按候场队序（教学局锁定，
    与推荐引擎给「6 人 1 片双打」的建议一致，规格 A4）。 */
export const SANDBOX_GAME = {
  name: "示例 · 新手体验局",
  venueName: "示例 · 球馆",
  doubles: true,
  scoring: 11,
  down: "n2" as const, // 规则抽屉词「2 人下」
  pairing: "queue" as const, // 签到顺序（展示名 PAIRING_NAMES，键不变）
};

/** 教学局每片人数单源：沙盒锁双打 4 人制（规格一片场双打；engine 发牌补片与
    组件候场预演同吃这份，别再写第二份 4） */
export const COURT_SIZE = 4;

/** 参与卡名册 6 人（含你；规格 A4）：阿豪=组织者、老周开场在等；你签到第三位；
    球球你签到约 2 秒后到（第 4 人、触发自动开赛）；老金小鹿随你打球时前后脚到。 */
export const PARTICIPATE_ROSTER: SandSeed[] = [
  {
    name: "阿豪",
    avatar: AV.hao,
    check: "ok",
    organizer: true,
  },
  {
    name: "老周",
    avatar: AV.zhou,
    check: "ok",
  },
  { name: "你", avatar: AV.def, check: "none", you: true }, // 默认头像（§8 裁决：防「我真在局里」错觉）
  {
    name: "球球",
    avatar: AV.qiu,
    check: "none",
  },
  {
    name: "老金",
    avatar: AV.jin,
    check: "none",
  },
  {
    name: "小鹿",
    avatar: AV.lu,
    check: "none",
  },
];

/** 组织卡名册 7 人+访客 1 位（规格 A4）：签到序老周→小敏→你（队头老周）；
    球球约 2 秒后到（第 4 人、触发自动开赛）、老金紧随；凯文第三步起待签迟到；
    访客「朋友」带访客时入册（称呼可改——store 签到前直接改行上的 name）。 */
export const ORGANIZE_ROSTER: SandSeed[] = [
  {
    name: "老周",
    avatar: AV.zhou,
    check: "ok",
  },
  {
    name: "小敏",
    avatar: AV.min,
    check: "ok",
  },
  { name: "你", avatar: AV.def, check: "ok", you: true, organizer: true },
  {
    name: "球球",
    avatar: AV.qiu,
    check: "none",
  },
  {
    name: "老金",
    avatar: AV.jin,
    check: "none",
  },
  {
    name: "凯文",
    avatar: AV.kevin,
    check: "none",
  },
  {
    name: "小鹿",
    avatar: AV.lu,
    check: "none",
  },
  { name: "朋友", avatar: AV.def, check: "none", guest: true }, // 访客无账号行→默认公共款头像（真码访客同款兜底）
];

/* ───────── NPC 剧本调度表（store 批2 消费：按 when 挂定时器，到点调
   engine.checkIn / engine.pushFeed）─────────
   when 词汇：'enter'=进卡那一刻；'me-checked-in'=你点了【我到了】；
   'me-scored'=你记了第 1 分（本地记分事件）；'admin-set'=封了管理员；
   'arrive'=某人到场之后（who）；'step'=步进指针进入第 N 条（1 起）。
   凯文不进调度表——他的到场是用户代办签到的教学点，只有跑马灯句定时滚。 */
export interface NpcCue {
  when:
    "enter" | "me-checked-in" | "me-scored" | "admin-set" | "arrive" | "step";
  delayMs: number; // 触发条件成立后再等多久（规格口径：球球约 2 秒、其余一拍）
  who?: string; // when='arrive'：在谁到场之后
  step?: number; // when='step'：第几步（1 起）
  arrive?: string; // 到场者名（engine.checkIn）
  feed?: string; // 跑马灯句（engine.pushFeed）
}

export const PARTICIPATE_CUES: NpcCue[] = [
  { when: "me-checked-in", delayMs: 2000, arrive: "球球" }, // 第 4 人一到即自动开赛（幕二）
  { when: "me-scored", delayMs: 600, arrive: "老金" }, // 幕三：你打着分，前后脚到、不弹提示
  { when: "arrive", who: "老金", delayMs: 2000, arrive: "小鹿" },
];

export const ORGANIZE_CUES: NpcCue[] = [
  { when: "enter", delayMs: 2000, arrive: "球球" }, // 第二步：人够 4 自动开赛
  { when: "arrive", who: "球球", delayMs: 800, arrive: "老金" }, // 紧随着到
  { when: "step", step: 3, delayMs: 0, feed: "凯文 · 迟到了" }, // 第三步起待签迟到
  { when: "admin-set", delayMs: 800, arrive: "小鹿" }, // 第七步封完管理员，第八步的因
];

/* ───────── 写死数值（规格 A4/§6 降级：界面一个数都不自算）───────── */

/** 结算窗积分涨跌小表：每人 {win:+X, lose:−Y}，量级照真局 Elo（1200 上下、
    K=24 档：胜 +12~24、败按胜方六成扣）编的示例数，胜败与比分无关。 */
export const ELO_PREVIEW: Record<string, { win: number; lose: number }> = {
  阿豪: { win: 18, lose: -11 },
  老周: { win: 16, lose: -10 },
  你: { win: 21, lose: -13 },
  球球: { win: 24, lose: -14 },
  老金: { win: 15, lose: -9 },
  小鹿: { win: 12, lose: -8 },
  小敏: { win: 19, lose: -12 },
  凯文: { win: 14, lose: -9 },
  朋友: { win: 20, lose: -12 }, // 访客有展示值不落账（真码 EloRow.guest 同口径）
};

/** 组织卡收工账单（写死）：场地费 240 · 8 人 · 每人 30；访客「朋友」份额归
    担保人你——你付 60（你的 30 + 朋友的 30）。 */
export const ORG_FINAL_BILL = {
  feeTotal: 240,
  heads: 8,
  perHead: 30,
  myShare: 60,
  tail: "真局的账单在『我的-账单』随时翻",
};

/* ───────── 示例句常量（规格 4.1/4.4/收尾逐字）───────── */

/** 教学态常驻横幅两档：访客带转化出口，已登录讲空态事实 */
export const BANNER_GUEST = "示例局 · 登录后这里就是你的现场";
export const BANNER_GUEST_ACTION = "登录 ▸";
export const BANNER_LOGGED_IN = "你还没有进行中的球局 · 下面是示例";

/** 两张体验卡的题+副句单一源：2.1 空态的两张虚拟卡（SandboxCards）与真局
    live.vue teach-ov 浮层两屏同貌同吃——改文案只动这里，两处不会劈叉 */
export const CARD_TITLES = {
  participate: { title: "参与打球指引", sub: "第一次来？跟着打一遍" },
  organize: { title: "组织打球指引", sub: "想自己组局？跟着当一遍组织者" },
};

/** 真局「新手教学」浮层的 kicker 题（同示例局的防误认口径） */
export const TEACH_OV_TITLE = "示例局 · 不记账不联网";

/** 二维码示意浮层说明句（占位码下的一句，不出真码） */
export const QR_DEMO_NOTE =
  "真局里，已到场的人都能亮这张码收人——朋友扫了填个称呼就能进场打球";

/** 顶条剩余时间：定格的假数，不走表（规格 A4） */
export const TIME_LEFT_FROZEN = "1:28:00";

/** 教学走完的常驻尾巴（两卡同款） */
export const TUTOR_TAIL = "✓ 教学走完了";
