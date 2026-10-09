/* 夜球场 · 类型定义（P2 数据层）
   1.2 接线重塑：局/意向按后端 game_view / intent_view 镜像成可读 camelCase（store/页面消费本文件）；
   线上 snake_case 形状镜像在 api/games.ts（GameViewApi/IntentViewApi），映射收在 stores/game.ts 单点。
   mock 隔离线快照形状已随演示世界退役（2026-10-10）：账单/登记/记录/现场全量吃真数据。 */

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

/** 球员（档案视图模型）：身份位（user store me）、真人档案缓存（people）、
    现场名册行（live store 落 check/skip/fire 等现场态）共用本形状。 */
export interface User {
  id: number;
  accountId?: number; // 账号 id（现场名册行：id=行靶位、accountId=账号空间；非名册行两者同值不重复存）
  name: string;
  elo: number;
  dupr?: number; // 1.4 双轨：DUPR 核心轨展示位；elo 继续 Elo 娱乐轨（弹窗±/撒花）
  provisional?: boolean; // DUPR 未定级（已结算 <5 场）
  duprGames?: number; // DUPR 已结算场数
  play: number;
  win: number;
  month: number;
  last5?: ("W" | "L")[];
  shadow?: boolean; // 随行访客 · 不计积分不进榜（对局按新人初始等级代入算分，2.3 修订②）
  chibi: ChibiConfig;
  cardBg?: CardBg;
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

/** 出勤底账一行（§4.14 观察点：几点到/几点走/访客谁带的）。
    一人一行快照式、不引用 User（applyLiveView 随视图 players 重建，故复制字段）。 */
export interface LedgerRow {
  id: number;
  name: string;
  shadow?: boolean; // 随行访客 · 不计积分不进榜
  dropin?: boolean; // 空降进场
  guarantor?: string; // 担保人名（访客谁带的）
  arriveAt?: string; // ISO · 几点到（首次到场）
  leftAt?: string; // ISO · 几点走（早退）
}

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
  /** 能力旗（闸旗同源）：组织者 × 写窗真值——钮显隐直读，不再拿 status 拼窗口 */
  canBook: boolean; // 订场/改价窗（散场确认前）
  canFillFee: boolean; // 补填窗（散场过且从未填价）
  canLock: boolean; // 空锁必打窗（开打前三态）
}

/** 已出账局的实摊定值块（game_view bill 镜像，1.3 批3）：fee_total/per_head/heads
    是引擎定格数；my_share/my_guest_count 按 viewer（不在摊钱名单 → null）。
    未出账 → 整块 null——前端以块有无区分「约（预估人均）」与实摊（A4） */
export interface GameBill {
  feeTotal: number;
  perHead: number;
  heads: number;
  myShare: number | null;
  myGuestCount: number | null;
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
  bill?: GameBill | null; // 实摊定值块（已出账的局非 null；1.3 批3）
  status: GameStatus;
  unlocked: boolean; // 改约解锁：锁定局改了时间/地点，开打前可退
  joinable: boolean; // 派生态 ∈ {open, locked, live}——加入按钮显隐直接读
  liveOpened: boolean; // 现场账已开（LiveState 行存在；2.5 §4.4：账一开卡片立显「进入现场」，不看时间）
  ended: boolean; // 散场确认过（流程锚，与派生显示态 done 不同——到点未散场 done 但 ended 假，2.3 §4.9）
  heads: number; // 人头（自己+带的人，后端定值）
  slotsLeft: number; // 剩几坑
  perHead: number | null; // 人均（half-up）；null=未定
  forced: boolean; // 必打 = 手动锁 ∨ 场上有号
  entries?: EntryRow[];
  my?: MyBlock;
}

/** 留意向（intent_view 镜像）：时段词表在 api/dict.ts slots（后端只存 key 串不校验）；
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
  countdown?: string; // 开打倒计时灰字（2.5 §4.1：'还有 N 小时 N 分'；仅在办局且没到入场窗才派生）
  liveEnter?: boolean; // 「进入现场」入口（2.5 §4.2/4.4：账已开 ∨ 必开且进两小时窗；waitlist/游客永无）
  stackAvatars: ChibiConfig[];
  stackPlus: string; // 头像叠层溢出文案：'+' / '+N' / '+N · 含随行'
}

/* ─────────── 1.3 账单域（批4 读链切真） ───────────
   snake 线上形状（…Api 族）逐字镜像 backend/app/services/bills.py 的 view 输出
   （契约唯一真源；技术设计 §8b 签名照抄）；camel 业务形状（Bill/BillPayer 等，
   导出名沿 5.1 mock 期）由 stores/bill.ts 单点映射。 */

/** 账单行四态（5.1：待付/已付/应收/已收；状态由两时刻推导，后端同串直出） */
export type BillKind = "payable" | "paid" | "receivable" | "received";

/** 应收按人明细一行（§4.2：每个别人该摊多少、收没收到；组织者自己那份由
    my_share 承载，不进明细）。paid_at 有而 received_at 空 = 「已转 · 待收」灰字 */
export interface BillPayerApi {
  account_id: number;
  name: string;
  deactivated: boolean;
  amount: number;
  guest_count: number;
  paid_at: string | null;
  received_at: string | null;
}

/** 账单行（§4.1/§4.2）：payable/paid 是我欠的（payee=组织者）；receivable/received
    是我组织的（amount=未收合计，收讫翻全额；payer_rows 不含我自己那份） */
export interface BillRowApi {
  kind: BillKind;
  game_id: number;
  game_name: string;
  ended_day: string; // 'YYYY-MM-DD' 散场那天（补填出账的局也记散场日）
  amount: number;
  guest_count?: number; // >0 才带：「含带来的朋友 ×N」
  payee_name?: string; // payable/paid：欠谁
  payee_deactivated?: boolean;
  peer_received?: boolean; // 对方已点收而我未结算（灰字旗，不改三数）
  fee_total?: number; // receivable/received：明细末行「总价 · 我自己那份」
  my_share?: number | null;
  my_guest_count?: number;
  payer_rows?: BillPayerApi[];
}

/** 「谁还欠你」一行（跨场聚合，期间内散场的局） */
export interface BillDebtorApi {
  account_id: number;
  name: string;
  deactivated: boolean;
  total: number;
  games: number;
}

/** 费用未定提醒一条（仅组织者自己：散场过且从未填价） */
export interface BillUnfixedApi {
  game_id: number;
  game_name: string;
  ended_day: string;
}

/** 账单页全视图（GET /api/bills 响应镜像）：分权在服务层裁死——三数/逐笔/
    谁还欠你同随 period，SQL 只取 viewer 的行/viewer 组织的局 */
export interface BillsViewApi {
  period: "7d" | "30d" | "all";
  summary: { due: number; paid: number; receivable: number };
  rows: BillRowApi[];
  debtors: BillDebtorApi[];
  unfixed: BillUnfixedApi[];
}

/** 账单状态（=行四态；导出名沿 5.1 mock 期，定义体已切真形状） */
export type BillStatus = BillKind;

/** 应收按人明细一行（camel）：paidAt 有而 receivedAt 空 = 「已转 · 待收」 */
export interface BillPayer {
  accountId: number;
  name: string;
  deactivated: boolean;
  amount: number;
  guestCount: number;
  paidAt: string | null;
  receivedAt: string | null;
}

/** 账单行（camel，store 映射产物）：见 BillRowApi */
export interface Bill {
  kind: BillStatus;
  gameId: number;
  gameName: string;
  endedDay: string;
  amount: number;
  guestCount?: number;
  payeeName?: string;
  payeeDeactivated?: boolean;
  peerReceived?: boolean;
  feeTotal?: number;
  myShare?: number | null;
  myGuestCount?: number;
  payerRows?: BillPayer[];
}

/** 「谁还欠你」一行（camel） */
export interface BillDebtor {
  accountId: number;
  name: string;
  deactivated: boolean;
  total: number;
  games: number;
}

/** 费用未定提醒一条（camel） */
export interface BillUnfixed {
  gameId: number;
  gameName: string;
  endedDay: string;
}

/** 账单页全视图（camel，store/页面消费）：三数/rows/debtors/unfixed 全是后端
    定值（A4：界面不自算），期间切换=重新 load */
export interface BillsView {
  period: "7d" | "30d" | "all";
  summary: { due: number; paid: number; receivable: number };
  rows: Bill[];
  debtors: BillDebtor[];
  unfixed: BillUnfixed[];
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

/** 一片场地（2.4 多片并行）：A/B 半边存玩家 id——
    每片各打各的（补满即打，无「待开」态）；playing/idle 由 A/B 是否空区分。
    id/name 归 store 建片，singles/streak 归并行引擎（记分族动作按 id 定位这片）；
    记分本地化（2026-10-09）后 sa/sb/last 是旧引擎记分板位：恒 0/空占位
    （fillCourt 归零兜旧格式），真值挂 store.localScores——留 0 兼 mock 树必填，
    删旧归 1.3。 */
export interface LiveCourt {
  A: number[];
  B: number[];
  id: number; // 片序 0..n-1（并行模型键，记分族动作按此定位）
  name: string; // 场地号（'3号'；未登记回退序号场）
  singles: boolean; // 本片当前对局格式（换单双打过渡期可 ≠ rules.singles，2.4 §4.7-3）
  sa: number; // 旧位恒 0 占位——真值挂 localScores，留 0 兼 mock 树必填（删旧归 1.3）
  sb: number; // 同 sa
  scoring?: number; // 片分制快照（视图缺行时本地补空片走 g.scoring 兜底，2.6）
  last?: "a" | "b"; // 旧位不再读——undoPoint 回退改吃 localScores.last（删旧归 1.3）
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
    各片自带记分板，回流补位真值在后端 live_rotation——视图落地即排好）。g 是真局对象的
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
  endedAt?: string; // 散场时刻（apiLiveEnd 落）：有值=现场封存转只读回看（§4.9/4.10）；live 态保留供回看与底账查
  ledger: LedgerRow[]; // 出勤底账（applyLiveView 随视图 players 重建：到/走/访客谁带的）
  rules: RotationRules; // 2.4 轮换四件套（startLive 起必挂：自选前 down 跟推荐走）
  courtSeqNext: number; // 上场先后序发号器（courtSeq 的源——资历并列的 tiebreak）
}

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
  | {
      type: "booking"; // 订场登记 / 锁定必打（3.2 三态锁：没锁→空锁→订场锁共用的面板）
      gameId: number;
      feeOnly?: boolean; // 补填形态（1.3 §4.5）：散场后从未填价的局，只让填总价
    }
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
      pendingIntent?: { slots: string[]; frequency: number; note: string };
    };
// 名片建号卡（1.1 A1）：游客点报名/建局/留意向/扫码签到时弹出；建号成功自动接着完成挂起的动作（D3 两步拆分）
// pendingCheckin（2.1·选项A）：扫码到场一律走名片建号，建号成功后自动「我到了」进候场区
// pendingIntent（1.2 4.13）：游客留意向同走先看后报——建号成功自动把意向落进意向簿

/** 结算 ±积分一行（2.1 打球页改版：终局结算弹窗 EndSettleModal 的预览行复用本形状） */
export interface WinChange {
  name: string;
  up: boolean;
  d: number;
}

/* ─────────── 2.3 现场总账读链（批4 阶段1·类型层） ───────────
   与上面的 mock 期现场族（LiveState/LiveCourt/MatchHistory）双树为稳态，删旧归 1.3。
   snake 线上形状（…Api 族）逐字镜像 backend/app/services/live.py 的 view 输出（契约唯一真源）；
   camel 业务形状由 api/live.ts 的 toLiveView 单点映射（沿 1.2 stores/game.ts toGame 先例）。 */

/** 半场标识：记分 side / 场上 court_side / 胜方 winner_side 共用同一枚 */
export type LiveSide = "a" | "b";

/** 片状态机（后端单一源）：idle 空闲 / playing 在打——pending 已随 2026-10-09
    记分本地化整体退役（服务端不记进行中比分，无窗可待确认） */
export type LiveCourtStatus = "idle" | "playing";

/** 歇连动作（2.2 §4.10）：skip 叠一轮 / fire 连战（再按取消）/ unskip 清零 */
export type TempoAction = "skip" | "fire" | "unskip";

/** 报到可写四态（2.2 §4.2/4.3/4.5）；absent 只出不进——开账全员起笔态，不可报回 */
export type CheckInAction = "ok" | "late" | "join" | "left";

/** 名册行（view.players 元素镜像）。考勤分权（裁决 Q2）：arrive_at/left_at 只有
    组织者与本人见，其他人一律 null——拿到 null 不代表没到。 */
export interface LivePlayerApi {
  id: number; // 名册行 id——check/swap/tempo/封撤管理员写动作按它定靶
  account_id: number | null; // 访客 null
  name: string; // 开账定格名（注销者占位名；访客=担保人前两字+编号）
  chibi: ChibiConfig | null; // 开账时定格的账号小人（访客无账号行 → null）
  guest: boolean; // 随行访客：代入 1200 算分但不落积分账（1.4 §4）
  dupr: number; // DUPR 配平代位分（1.4 §6 修订：访客/无派分行统一 2.5、有派分行吃派生分）
  guarantor_account_id: number | null; // 访客挂谁名下（考勤底账「谁带的」）
  dropin: boolean; // 空降进场（没报名扫码直入名册）
  check: CheckStatus; // ok/late/join/left/absent 五态
  arrive_at: string | null; // ISO · 几点到（首次到场落账）
  left_at: string | null; // ISO · 几点走（早退原时刻，不覆写）
  court_no: number | null; // 在片上=片号；null=不在片
  court_side: LiveSide | null; // 'a'/'b'；null=候场/不在片
  skip: number; // 剩余歇轮数（轮到发牌给他时递减）
  fire: boolean; // 连战：排到队首，与歇互斥
  queue_pos: number | null; // 候场序（升序即队列序）；null=场上/不在队
}

/** 片行（view.courts 元素镜像）：进行中比分不进协议（记分本地化，2026-10-09）——
    各手机本地账自记，落账真值在 matches */
export interface LiveCourtApi {
  court_no: number; // 片号，1 起
  status: LiveCourtStatus;
  seq: number; // 该片今天第几场（开新场 +1）
  court_seq: number; // 片号版本：该片记分类写 +1（写动作带它作 base_court_seq）
  scoring: number; // 片分制快照（开赛定格 game.scoring，改分制下一场起生效——在打片照旧，2.6）
  elo_preview?: { a: EloRowApi[]; b: EloRowApi[] } | null; // 在打片 ±积分预演双分支（§4.11，后端 _elo_settle 同路=预演即落账；Elo 与比分无关故挂 playing 片，其余片 null）
}

/** 战报人员快照（winners/losers 元素镜像）：落账时定格，id 是名册行 id */
export interface MatchPersonApi {
  id: number;
  name: string;
  guest: boolean; // 访客标识：战报/预览「访客 · 不计积分」同款（§4.11）
}

/** 结算行（elo_rows 元素镜像）：每人一行、胜队在前；访客有 delta 展示值但不落账 */
export interface EloRowApi {
  account_id: number | null; // 访客 null（与 guest 同真值）
  name: string;
  guest: boolean;
  rating_before: number;
  rating_after: number; // 地板 800（1.4 §3）
  delta: number; // 胜 +delta / 败 -delta（败方只扣胜方涨分六成）
}

/** 战报行（view.matches 元素镜像）：确认落账即冻结不可改（积分可信的地基） */
export interface LiveMatchApi {
  court_no: number;
  seq: number; // 该片第几场
  winners: MatchPersonApi[];
  losers: MatchPersonApi[];
  score_a: number;
  score_b: number;
  winner_side: LiveSide;
  ended_at: string; // ISO
  elo_rows: EloRowApi[];
}

/** 战报事件句（view.feed 元素镜像，2.2 §4.6/§4.9 留痕）：结构化事件行、按发生序追加，
    句式拼装归前端（契约§2 后端不产中文文案） */
export type FeedEventApi =
  | { kind: "swap"; actor: string; out: string; in: string; at: string }
  | {
      /** auto_admin（2.5）：账开张后第一位签到的球友自动暂管现场（后端批1 落的事件，
          actor=target=获授人） */
      kind: "set_admin" | "unset_admin" | "auto_admin";
      actor: string;
      target: string;
      at: string;
    };

/** 规则块（view.rules 镜像）：全场统一；scoring 复用局列（裁决 Q1，不另存第二份） */
export interface LiveRulesApi {
  scoring: number; // 分制 target（先到 N 且净胜 2）
  doubles: boolean; // true=双打
  down: DownMode; // 谁下（枚举沿用 2.4 定稿）
  pairing: PairingMode; // 怎么配
  streak_max: number; // 连庄上限
}

/** 费用亮数块（view.fee 镜像，1.3 批1 散场确认页）：total=订场登记总价（null=未定）；
    heads=账单口径摊钱人头（正式/空降行每人 1 + 名下访客行数，后端定值）；
    per_head=floor(total/heads)，未定时 null 但 heads 照给（亮「总价未定 · N 人」用） */
export interface LiveFeeApi {
  total: number | null;
  heads: number;
  per_head: number | null;
}

/** 总账读视图（GET /games/{id}/live 响应镜像）：进行中与散场后同一形状（散场=只读回看） */
export interface LiveViewApi {
  game_id: number;
  started_at: string; // ISO · 开账时刻
  ended: boolean; // 已散场（games.ended_at 有值）
  ended_at: string | null; // ISO · 散场时刻
  fee?: LiveFeeApi | null; // 费用亮数块（散场确认页吃它，1.3 批1）
  total_seq: number; // 全场总号：任何现场写 +1（轮询对表与写动作 base_total_seq 的基准）
  round: number; // 全场第几场（散场时收口定总数）
  admins: number[]; // 管理员 account_id 表（组织者 ∨ 本表 = 全权）
  is_organizer: boolean; // viewer 是组织者（身份块，2026-10-08 修订起随视图直读）
  is_full_power: boolean; // 组织者 ∨ 管理员（收权动作入口把关；游客恒 false）
  organizer_account_id: number; // 组织者账号（前端代收判定找其名册行）
  feed: FeedEventApi[];
  courts_count: number; // 场地片数真值（缩片先撤空闲片）
  rules: LiveRulesApi;
  players: LivePlayerApi[];
  queue: number[]; // 候场队名册行 id（队首在前，发牌从这里取）
  courts: LiveCourtApi[];
  matches: LiveMatchApi[]; // 战报（按结束时刻序）
}

/** 名册行（camel）：LivePlayerApi 的映射产物 */
export interface LivePlayer {
  id: number;
  accountId: number | null;
  name: string;
  chibi: ChibiConfig | undefined; // 开账定格小人（访客 undefined → 缺省形象）
  guest: boolean;
  dupr: number;
  guarantorAccountId: number | null;
  dropin: boolean;
  check: CheckStatus;
  arriveAt: string | null;
  leftAt: string | null;
  courtNo: number | null;
  courtSide: LiveSide | null;
  skip: number;
  fire: boolean;
  queuePos: number | null;
}

/** 片行（camel；不叫 LiveCourt 是避让上面 mock 期的旧类型，阶段2 删旧后不复名） */
export interface LiveCourtView {
  courtNo: number;
  status: LiveCourtStatus;
  seq: number;
  courtSeq: number;
  scoring: number; // 片分制快照（在打片定格开赛分制，改分制只影响新开片——2.6）
  eloPreview: { a: EloRow[]; b: EloRow[] } | null; // 在打片 ±积分预演双分支（结算窗点胜方切换消费；其余片 null）
}

/** 战报人员快照（camel）：键与线上同形，不另建映射 */
export interface MatchPerson extends MatchPersonApi {}

/** 结算行（camel） */
export interface EloRow {
  accountId: number | null;
  name: string;
  guest: boolean;
  ratingBefore: number;
  ratingAfter: number;
  delta: number;
}

/** 战报事件句（camel）：键与值都是后端短词，与 FeedEventApi 同形 */
export type FeedEvent = FeedEventApi;

/** 规则块（camel） */
export interface LiveRules {
  scoring: number;
  doubles: boolean;
  down: DownMode;
  pairing: PairingMode;
  streakMax: number;
}

/** 费用亮数块（camel）：LiveFeeApi 的映射产物 */
export interface LiveFee {
  total: number | null;
  heads: number;
  perHead: number | null;
}

/** 战报新结构（2.3）：片号/第几场/双方名单快照/比分/胜方是否 A/时刻/结算行。
    与旧 MatchHistory 双树为稳态，删旧归 1.3；sa/sb/winA 沿旧树短名。 */
export interface MatchReport {
  courtNo: number;
  seq: number;
  winners: MatchPerson[];
  losers: MatchPerson[];
  sa: number;
  sb: number;
  winA: boolean; // winner_side === 'a'
  endedAt: string;
  eloRows: EloRow[];
}

/** 总账读视图（camel，store/页面消费）：toLiveView 映射产物，画面一个字不自算（A4）。
    身份块（isOrganizer/isFullPower/organizerAccountId）视图直读（2026-10-08 修订，
    翻批4a 的「视图不带身份块」——本地拼 viewer 在深链冷启动依赖异步身份）。 */
export interface LiveView {
  gameId: number;
  startedAt: string;
  ended: boolean;
  endedAt: string | null;
  fee?: LiveFee | null; // 费用亮数块（散场确认页吃它，1.3 批1）
  totalSeq: number; // 轮询对表基准：变了才换画面（§4.8 几秒内全场同步）
  round: number;
  admins: number[];
  feed: FeedEvent[];
  courtsCount: number;
  rules: LiveRules;
  players: LivePlayer[];
  queue: number[]; // 候场队（名册行 id，队首在前）
  courts: LiveCourtView[];
  courtSeqs: Record<number, number>; // 片号→court_seq（片级写的 base_court_seq 直取处）
  matches: MatchReport[];
  isOrganizer: boolean; // viewer 是组织者（视图身份块直读）
  isFullPower: boolean; // 组织者 ∨ 管理员：收权动作入口把关（沿 2.2 越权前置拦截）
  organizerAccountId: number; // 组织者账号（canEndLive 代收分支找组织者名册行）
}

/* ---- 写动作载荷（镜像 routes/live.py 请求模型，camel 参数形；snake 线上体在 api/live.ts 逐端点内联） ---- */

/** 排阵上报的一片（DealCourtIn 镜像）：a/b 是名册行 id，发牌算法在前端（rotate.ts） */
export interface DealCourt {
  courtNo: number; // 片号，1 起
  a: number[]; // 非空（A 半边）
  b: number[];
}

/** 确认结束（SettleConfirmIn 镜像）：窗内可能调过比分——最终比分与胜方由确认窗定死送来 */
export interface SettleConfirmInput {
  courtNo: number;
  winnerSide: LiveSide; // 必须分高方（平分双方均可）
  scoreA: number;
  scoreB: number;
  noRedeal?: boolean; // 散场清扫态：回流定格、不排下一场不补位（§4.9-1）
  baseTotalSeq: number;
  baseCourtSeq: number;
}

/** 改分重落（SettleOverwriteIn 镜像，全权）：下一场落账前把该片最新一场按新分重落
    （战报/Elo/DUPR 重写，轮转物理不动）——胜方/比分全吃入参，无 noRedeal（不重排） */
export interface SettleOverwriteInput {
  courtNo: number;
  winnerSide: LiveSide; // 必须分高方（平分双方均可）
  scoreA: number;
  scoreB: number;
  baseTotalSeq: number;
  baseCourtSeq: number;
}

/** 规则四件套+片数+分制（RulesIn 镜像）：全可选，只动显式给的字段（undefined 不进 JSON 体） */
export interface LiveRulesInput {
  doubles?: boolean;
  down?: DownMode;
  pairing?: PairingMode;
  streakMax?: number;
  courtsCount?: number; // 不得少于在用片数（缩片先撤空闲片）
  scoring?: number; // 分制 target（写局列，全局当前生效；在打片照旧、新开片用新制——2.6）
}
