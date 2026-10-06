/* 夜球场 · 类型定义（P2 数据层）
   1.2 接线重塑：局/意向按后端 game_view / intent_view 镜像成可读 camelCase（store/页面消费本文件）；
   线上 snake_case 形状镜像在 api/games.ts（GameViewApi/IntentViewApi），映射收在 stores/game.ts 单点。
   mock 隔离线（账单/登记/记录/现场演示）继续吃文末 MockGame 快照形状。 */

/** Q 版头像配置（alpha:719 chibi(c) 的参数对象；SVG 生成函数在 utils/chibi.ts，归 P1） */
export interface ChibiConfig {
  skin?: number;
  hair?: number;
  hc?: number;
  shirt?: number;
  face?: number;
  acc?: number;
}

/** 我的战力卡卡背（alpha:1844 bg-neon/gold/cyber/aurora） */
export type CardBg = "neon" | "gold" | "cyber" | "aurora";

/** 现场签到五态（alpha:1579） */
export type CheckStatus = "ok" | "late" | "left" | "absent" | "join";

/** 球员。U 里 13 人是同一份对象贯穿全局：名单/现场名册/榜单直接引用同一对象
    （alpha:1474「现场名单直接引用球员对象：Elo 变动实时落回战力榜」）。
    check/skip/fire 由 startLive 挂上（alpha:1482）。 */
export interface User {
  id: number;
  name: string;
  elo: number;
  play: number;
  win: number;
  month: number;
  last5?: ("W" | "L")[];
  liked?: boolean; // 喜欢：静默单向（alpha:1922 toggleLike）
  shadow?: boolean; // 随行访客 · 半权重不进榜（alpha:774 / 1703）
  chibi: ChibiConfig;
  cardBg?: CardBg;
  recentStats?: RecentStats;
  check?: CheckStatus;
  skip?: number; // 剩余歇轮数：歇两轮=2（2.1 文档+原型「候场区点人可设歇两轮」）。
  // 轮到发牌给他时递减 1（rotate.ts takeFromQueue），归 0 自动归队；0=不在歇
  fire?: boolean; // 连战：排到队首，与歇互斥（alpha:1631-1633）
  dropin?: boolean; // 空降进场：没报名扫码直入名册（§4.4 全场看得到的标记；线上名单/候补不动）
  arriveAt?: string; // ISO · 首次到场时刻（出勤底账，time.ts toIso 落/isoHm 显）
  leftAt?: string; // ISO · 早退离场时刻
  courtSeq?: number; // 现场态 · 上场先后序（LiveState.courtSeqNext 递增发放；2.4 资历并列时先上的先下）
  tenure?: number; // 现场态 · 连续在场场数（上场=0 起，每结束一场 +1，下场清 0——2.4 N人下按此排「待得最久」）
}

/** 出勤底账一行（§4.14 观察点：几点到/几点走/访客谁带的/移出留痕）。
    一人一行快照式、不引用 User——人被移出名册后行必须保留（removedAt 留痕），故复制字段。 */
export interface LedgerRow {
  id: number;
  name: string;
  shadow?: boolean; // 随行访客 · 半权重不进榜
  dropin?: boolean; // 空降进场
  guarantor?: string; // 担保人名（访客谁带的）
  arriveAt?: string; // ISO · 几点到（首次到场）
  leftAt?: string; // ISO · 几点走（早退）
  removedAt?: string; // ISO · 被移出名册时刻（行保留=留痕）
}

/** alpha:762 recentStats（我的页运动数据条） */
export interface RecentStats {
  win: number;
  loss: number;
  hours: number;
  kcal: number;
}

/** 报名条目（MockGame 遗留形状）：带的人也占坑（alpha:776 · heads 计入 bring） */
export interface GameEntry {
  u: User;
  bring?: number;
}

/** 时间桶（MockGame 遗留；真局列表筛选由页面从 startAt 现算） */
export type TimeBucket = "tonight" | "tomorrow" | "weekend" | "week";

/** 发牌模式（alpha:1404 winner 赢家留场 / rotate 纯粹轮转 / balance 均衡配对） */
export type CourtMode = "winner" | "rotate" | "balance";

/** 视图状态 7 态（单一源=后端 game_views.derive；派生态读时算：
    locked 随时刻翻 locked/live/done，pending 拖过开打=terminated） */
export type GameStatus =
  "open" | "locked" | "live" | "done" | "terminated" | "cancelled" | "pending";

/** 谁能翻到（可见档；enum 真值=后端模型，档位只管列表翻不翻得到、不管链接进出） */
export type Visibility = "played" | "public" | "invite_only";

/** 名单里的一人（后端 person_view 镜像）：对外只显昵称+小人（1.1 隐私口径） */
export interface Person {
  id: number;
  nickname: string;
  chibi: ChibiConfig;
}

/** 报名行：formal 按报名先后在前、候补按 seq 跟后（后端 entry_rows 保序，前端不再排序） */
export interface EntryRow {
  account: Person;
  bring: number;
  standing: "formal" | "waitlist";
  waitSeq: number | null;
}

/** viewer 视角块（my_block 镜像）；匿名请求不带 my */
export interface MyBlock {
  isOrganizer: boolean;
  myEntry: {
    bring: number;
    standing: "formal" | "waitlist";
    waitSeq: number | null;
  } | null;
  invited: boolean;
}

/** 球局（game_view 镜像）。人头/剩坑/人均/forced 是后端算好的定值（A4：画面不自算）；
    entries 仅详情与写动作出口带（列表简版没有），my 仅登录 viewer 带。 */
export interface Game {
  id: number;
  name: string;
  organizer: Person;
  startAt: string; // ISO 8601 +08:00（契约§2：相对表达只许待在输入框）
  endAt: string;
  deadlineAt: string; // 截止发布即定死（不变承诺3）
  venueName: string;
  venueAddress: string | null;
  minPlayers: number; // 最少人数（截止时判成不成）
  maxPlayers: number; // 最多人数（满员线，进度只讲剩几坑）
  visibility: Visibility;
  scoring: number; // 分制 target（先到 N 且净胜 2）
  rotation: CourtMode;
  scoreRule: string; // 后端 str 原样；非 rally/serve 的值不显示得分规则段（旧局容错）
  manualLock: boolean; // 必打手动锁（锁上不撤）
  courts: string[] | null; // 订场登记的场地号；场上有号即必打；null=未登记
  feeTotal: number | null; // 总价（整数元）；null=费用未定
  status: GameStatus;
  unlocked: boolean; // 改约解锁：锁定局改了时间/地点，开打前可退
  joinable: boolean; // 派生态 ∈ {open, locked, live}——加入按钮显隐直接读
  heads: number; // 人头（自己+带的人，后端定值）
  slotsLeft: number; // 剩几坑
  perHead: number | null; // 人均（half-up）；null=未定
  forced: boolean; // 必打 = 手动锁 ∨ 场上有号
  entries?: EntryRow[];
  my?: MyBlock;
}

/** 留意向（intent_view 镜像）：时段词表沿用 mock/data slots（后端只存 key 串不校验）；
    invited=被我邀过、known=与 viewer 同局打过（都是后端定值） */
export interface Intent {
  account: Person;
  slots: string[];
  frequency: number; // 0=随缘 / 1 / 2
  note: string | null;
  updatedAt: string;
  invited: boolean;
  known: boolean;
}

/** 我的一份意向 */
export interface MyIntent {
  slots: string[];
  frequency: number;
  note: string | null;
}

/** 时段定义（前端词表单一源，后端不校验词表——防两真值） */
export interface Slot {
  k: string;
  n: string;
  desc: string;
}

/** 局卡展示模型（批4 裁决①：GameCard props 收窄为卡面原子，组件与数据源解耦——
    meet 传真局映射 newGameCard，登记/记录页传 mock 映射 mockGameCard） */
export interface GameCardModel {
  id: number;
  name: string;
  dayText: string; // 时间位小字：'今晚' / '10.06 周一'
  hmText: string; // 时间位大字：'19:00'
  venueText: string;
  status: GameStatus;
  minPlayers: number;
  maxPlayers: number;
  slotsLeft: number;
  forcedLabel?: string; // '已订场 · 必开' / '必开'；未锁定则缺省
  result?: { sa: number; sb: number; myWin: boolean }; // done 战报（mock 快照域）
  myRole?: "org" | "inv" | "joined" | null;
  stackAvatars: ChibiConfig[];
  stackPlus: string; // 头像叠层溢出文案：'+' / '+N' / '+N · 含随行'
}

/** 账单状态四态（5.1 文档：待付/已付/该收/已收） */
export type BillStatus = "due" | "paid" | "receivable" | "received";

/** 该收按人明细一行——数据侧算好的每个人该摊多少、结没结，界面不自算（5.1 修订） */
export interface BillPayer {
  u: User;
  amt: number;
  settled: boolean;
}

/** 账单（5.1 文档：哪局、多少钱、什么状态；垫付只属组织者，故 role=org 才有 receivable。
    member 行 amt=人均摊费、payee=该局组织者（欠谁）；org 行 amt=别人摊费合计、payers=按人明细） */
export interface Bill {
  id: number;
  gameId: number;
  gname: string;
  date: string;
  amt: number;
  status: BillStatus;
  role: "org" | "member";
  payee?: User; // 欠谁——member 行＝该局组织者；org 行无此字段
  payers?: BillPayer[]; // 该收按人明细，org 行才有；不含我自己
}

/** 谁下（2.4 §4.1 四件套之二）：全上全下 / 输家下 / 1、2、3人下（单打只有 all/loser） */
export type DownMode = "all" | "loser" | "n1" | "n2" | "n3";

/** 怎么配（仅双打）：按候场队序 / 均衡配对（2.4 §4.5） */
export type PairingMode = "queue" | "balance";

/** 现场轮换四件套（2.4 §4.1）：谁能改=全权者（2.2 已定），点选即生效、在打对局照旧打完 */
export interface RotationRules {
  singles: boolean; // 全场统一单双打（true=单打）；默认双打
  down: DownMode; // 谁下；未自选时跟推荐走，「不荐」时挂 'all' 占位
  downChosen: boolean; // 组织者自选过「谁下」即 true，此后推荐只亮标签不替改
  pairing: PairingMode; // 怎么配；默认按候场队序
  champCap: number; // 连庄上限（仅输家下显示/生效）；默认 3，0=不限
}

/** 一片场地（2.4 多片并行）：A/B 半边存玩家 id，sa/sb 是本片自己的记分板——
    每片各打各的（补满即打，无「待开」态）；playing/idle 由 A/B 是否空区分。
    id/name 归 store 建片，singles/sa/sb/streak 归并行引擎（endMatch 按 id 定位这片）。 */
export interface LiveCourt {
  A: number[];
  B: number[];
  id: number; // 片序 0..n-1（并行模型键，endMatch/记分族动作按此定位）
  name: string; // 场地号（'3号'；未登记回退序号场）
  singles: boolean; // 本片当前对局格式（换单双打过渡期可 ≠ rules.singles，2.4 §4.7-3）
  sa: number;
  sb: number;
  last?: "a" | "b"; // 本片最后得分方（undoPoint 回退用——多片各记各的）
  streakA: number; // 连庄数——跟半边不跟人（手动换人不动连庄，2.4 §4.9）
  streakB: number;
}

/** 已完成场次（alpha:1710）。alpha 的 txt 为含高亮的 HTML 字符串，这里存纯文本胜者名，
    页面渲染时拼「names 胜」（v-html 仅允许 ChibiAvatar 使用）。 */
export interface MatchHistory {
  names: string;
  sa: number;
  sb: number;
}

/** 现场状态（alpha:1483-1485 live · 2.4 批2 起多片并行总账：无 cur/lastWinners——
    各片自带记分板，轮换由 utils/rotate.ts 的 endMatch 按 courtId 接管）。g 是真局对象的
    浅克隆：现场改规则/场地只落在克隆上，不回写 game store 的局（派生态归后端）。 */
export interface LiveState {
  g: Game;
  roster: User[];
  queue: number[];
  courts: LiveCourt[];
  history: MatchHistory[];
  round: number;
  admins: number[]; // 被封管理员 id（现场态，不回写 g；isFullPower = org ∨ 本表）
  feed: string[]; // 战报事件句（unshift 新到旧；句子在动作处拼好、含操作者，LiveTopbar 轮播消费）
  startedAt: string; // 现场点亮时刻（startLive 落 ISO；批4 底账定格/散场消费）
  endedAt?: string; // 散场时刻（endLive 落 ISO）：有值=现场封存、二维码失效（§4.14）；live 态保留供底账查
  ledger: LedgerRow[]; // 出勤底账（动作处同步写：touchLedger 单点；移出/空降行留痕）
  rules: RotationRules; // 2.4 轮换四件套（startLive 起必挂：自选前 down 跟推荐走）
  courtSeqNext: number; // 上场先后序发号器（courtSeq 的源——资历并列的 tiebreak）
}

/** 分制（alpha:850 scoreMode 默认 elo） */
export type ScoreMode = "elo" | "ntrp";

/** 组局表单提交值（线上形状 snake_case，POST /games 请求体镜像；契约§1）。
    拨盘串→ISO 的换算归 LaunchSheet（utils/time.ts toIso）。 */
export interface PublishGameInput {
  name: string; // LaunchSheet 自动起名后提交（契约§2 后端不产中文），提交时非空
  start_at: string; // ISO +08:00
  end_at: string;
  deadline_at: string; // 默认开打前 2h；手动拨过即固定
  venue_name: string;
  venue_address: string | null;
  min_players: number;
  max_players: number;
  visibility: Visibility; // 默认 'played'（熟人优先裁决）
  scoring: number;
  rotation: CourtMode;
  score_rule: string;
}

/** 改局输入：十参全可选；deadline_at 在类型层就挡死（不变承诺3：发布即定死不改） */
export type EditGameInput = Partial<Omit<PublishGameInput, "deadline_at">> & {
  deadline_at?: never;
};

/** 全局单例弹层 payload（§2.2：P2 全量预定义，后续阶段只消费不改） */
export type SheetPayload =
  | { type: "profile"; userId: number }
  | { type: "join"; gameId: number }
  | { type: "quit-confirm"; gameId: number }
  | { type: "cancel-confirm"; gameId: number }
  | { type: "booking"; gameId: number } // 订场登记 / 锁定必打（3.2 三态锁：没锁→空锁→订场锁共用的面板）
  | { type: "invite-to-game"; gameId: number } // 局详情翻意向列表拉人（alpha:1213）
  | { type: "invite-to-slot"; userId: number } // 球员档案选局邀请（alpha:1239）
  | { type: "intent-form" } // 留/改意向（alpha:1266）
  | { type: "launch"; gameId?: number } // 组局表单：无 gid 新建（alpha:1301）
  | { type: "logout-confirm" } // 退出账号确认（5.1 弹窗：只是这台设备登出，数据都在）
  | { type: "delete-confirm" } // 注销账号确认（5.1 弹窗：后果说明 + 二次确认，两步都过才执行）
  | {
      type: "signup-card";
      pendingJoin?: { gameId: number; bring: number };
      pendingLaunch?: PublishGameInput;
      pendingCheckin?: { gameId: number };
    };
// 名片建号卡（1.1 A1）：游客点报名/建局/扫码签到时弹出；建号成功自动接着完成挂起的动作（D3 两步拆分）
// pendingCheckin（2.1·选项A）：扫码到场一律走名片建号，建号成功后自动「我到了」进候场区

/** 结算 ±积分一行（2.1 打球页改版：终局结算弹窗 EndSettleModal 的预览行复用本形状） */
export interface WinChange {
  name: string;
  up: boolean;
  d: number;
}

/** ─────────── mock 隔离线快照形状（1.2 起冻结：字段不再生长） ───────────
    账单/登记/记录/现场演示继续吃 mock/data.ts 种子（5.1 快照域）；
    1.2 真局一律走上面的 Game。谁引用 t/d/tb/result 等旧字段，类型上必须经过 MockGame——
    type-check 借此画出隔离边界。 */
export interface MockGame {
  id: number;
  organizer: User;
  t: string; // '今晚 19:00'（utils/time.ts gameTime 解析）
  d: string; // 展示用日期（'今天' / '10.07'）
  tb: TimeBucket;
  area: string; // 地区（找局打筛选用）
  dur: number; // 打多久（小时）
  deadline: string; // 组局截止：到点锁名单，定死不改
  loc: string;
  name: string;
  min: number; // 最少人数（截止时判成不成）
  cap: number; // 最多人数（满员线，进度只讲剩几坑）
  fee: number | null; // 预计费用总价；null=费用未定
  note?: string;
  joined: GameEntry[];
  wait: GameEntry[]; // 候补栏：满员加入进这里，有人退出即刻递补
  status: GameStatus;
  score: number; // 分制 target
  scoreRule?: "rally" | "serve";
  mode: CourtMode;
  lateRule: boolean;
  invitedMe?: boolean;
  locked?: boolean;
  sure?: boolean; // 必打手动锁
  booked?: string[]; // 订场登记的场地号
  dead?: boolean; // 未成局（自动终止）
  result?: { sa: number; sb: number; myWin: boolean }; // 已结束局的最终比分
  myLog?: { checkIn: string; checkOut?: string }; // 我的到场底账
}
