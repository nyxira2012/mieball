/* 夜球场 · 类型定义（P2 数据层）
   字段名与 mock/data.ts（alpha:760-830 原样移植）一一对应。 */

/** Q 版头像配置（alpha:719 chibi(c) 的参数对象；SVG 生成函数在 utils/chibi.ts，归 P1） */
export interface ChibiConfig {
  skin?: number;
  hair?: number;
  hc?: number;
  shirt?: number;
  face?: number;
  acc?: number;
}

/** alpha:762 recentStats（我的页运动数据条） */
export interface RecentStats { win: number; loss: number; hours: number; kcal: number }

/** 我的战力卡卡背（alpha:1844 bg-neon/gold/cyber/aurora） */
export type CardBg = 'neon' | 'gold' | 'cyber' | 'aurora';

/** 现场签到五态（alpha:1579） */
export type CheckStatus = 'ok' | 'late' | 'left' | 'absent' | 'join';

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
  last5?: ('W' | 'L')[];
  liked?: boolean;       // 喜欢：静默单向（alpha:1922 toggleLike）
  shadow?: boolean;      // 随行访客 · 半权重不进榜（alpha:774 / 1703）
  chibi: ChibiConfig;
  cardBg?: CardBg;
  recentStats?: RecentStats;
  check?: CheckStatus;
  skip?: boolean;        // 歇一轮：消耗型徽章（alpha:1496）
  fire?: boolean;        // 连战：排到队首，与歇互斥（alpha:1631-1633）
}

/** 报名条目：带的人也占坑（alpha:776 · heads 计入 bring） */
export interface GameEntry { u: User; bring?: number }

/** 时间桶（约球页筛选，alpha:776） */
export type TimeBucket = 'tonight' | 'tomorrow' | 'weekend' | 'week';

/** 发牌模式（alpha:1404 winner 赢家留场 / rotate 纯粹轮转 / balance 均衡配对） */
export type CourtMode = 'winner' | 'rotate' | 'balance';

/** done=已结束局（5.1）：作为一等球局留在 games[]，换取局卡/详情/摊账弹层整链复用 */
export type GameStatus = 'open' | 'ready' | 'live' | 'done';

/** 球局。alpha:776-780 的口径注释是权威语义（mock/data.ts 原样保留） */
export interface Game {
  id: number;
  organizer: User;
  t: string;            // '今晚 19:00'（utils/time.ts gameTime 解析）
  d: string;            // 展示用日期（'今天' / '10.07'）
  tb: TimeBucket;
  area: string;         // 地区（找局打筛选用）
  dur: number;          // 打多久（小时）
  deadline: string;     // 组局截止：到点锁名单，定死不改
  loc: string;
  name: string;
  min: number;          // 最少人数（截止时判成不成）
  cap: number;          // 最多人数（满员线，进度只讲剩几坑）
  fee: number | null;   // 预计费用总价；null=费用未定（2026-10-04 定：发局表单去掉费用，新局为 null，旧局保留数字）
  note?: string;
  joined: GameEntry[];
  wait: GameEntry[];    // 候补栏：满员加入进这里，有人退出即刻递补
  status: GameStatus;
  score: number;        // 分制 target（先到 N 且净胜 2，alpha:1686）
  scoreRule?: 'rally' | 'serve'; // 得分规则：rally=每球得分 / serve=发球得分（3.3 表单直选；旧局无此字段不显示）
  mode: CourtMode;
  lateRule: boolean;    // 迟到排队尾等一轮（3.3 起退出组局表单，仅存量局/现场逻辑保留）
  invitedMe?: boolean;  // 别人邀请我
  locked?: boolean;     // 已到截止锁定（参加者不能再退出）
  sure?: boolean;       // 必打 · 手动锁（点「锁定必打」不带场地；锁上不撤，与订场锁并存于 isForced 口径）
  booked?: string[];    // 订场登记的场地号（如 ['3号','5号']，片数=个数；订场发生在 app 外，这里只登记结果）。
                        // 场上有号即必打（utils/format isForced），fee 随登记落定为总价；清空后 fee 回 null
  dead?: boolean;       // 未成局（自动终止 · 组织者可恢复）
  result?: { sa: number; sb: number; myWin: boolean }; // 已结束局的最终比分（5.1 局卡 done 分支 / 记录页看比分）
  myLog?: { checkIn: string; checkOut?: string };      // 我的到场底账：签到/早退时刻（5.1 登记页「签到 19:02 · 早退 21:30」）
}

/** 留意向（alpha:807：大概什么时段想打、多久打一次 —— 组局的人翻列表看中谁就邀请谁） */
export interface Intent {
  u: User;
  slots: string[];
  freq: number;         // 0=随缘 / 1 / 2
  note?: string;
  done?: boolean;       // 被邀请后标记（alpha:1257）
}

/** 时段定义。match=同波段人数（alpha:826 启动时算一次，后续改意向不重算 —— alpha 原样） */
export interface Slot { k: string; n: string; desc: string; match: number }

export interface MyIntent { slots: string[]; freq: number }

/** 账单状态四态（5.1 文档：待付/已付/该收/已收） */
export type BillStatus = 'due' | 'paid' | 'receivable' | 'received';

/** 该收按人明细一行——数据侧算好的每个人该摊多少、结没结，界面不自算（5.1 修订） */
export interface BillPayer { u: User; amt: number; settled: boolean }

/** 账单（5.1 文档：哪局、多少钱、什么状态；垫付只属组织者，故 role=org 才有 receivable。
    member 行 amt=人均摊费、payee=该局组织者（欠谁）；org 行 amt=别人摊费合计（我那份自己出了，
    刺客合议 #2 的「org 行=垫付总价」随 5.1 修订作废）、payers=数据侧给好的按人明细） */
export interface Bill {
  id: number; gameId: number; gname: string; date: string; amt: number; status: BillStatus; role: 'org' | 'member';
  payee?: User;         // 欠谁——member 行＝该局组织者；org 行无此字段
  payers?: BillPayer[]; // 该收按人明细，org 行才有；不含我自己
}

/** 场上待打的一片：A/B 两队（存玩家 id） */
export interface LiveCourt { A: number[]; B: number[] }

/** 进行中的一场（live.cur 记分板） */
export interface LiveMatch { A: number[]; B: number[]; sa: number; sb: number }

/** 已完成场次（alpha:1710）。alpha 的 txt 为含高亮的 HTML 字符串，这里存纯文本胜者名，
    页面渲染时拼「names 胜」（v-html 仅允许 ChibiAvatar 使用）。 */
export interface MatchHistory { names: string; sa: number; sb: number }

/** 现场状态（alpha:1483-1485 live） */
export interface LiveState {
  g: Game;
  roster: User[];
  queue: number[];
  courts: LiveCourt[];
  history: MatchHistory[];
  round: number;
  cur: LiveMatch | null;
  lastWinners: number[] | null;
  last?: 'a' | 'b';     // 最后得分方（undoPoint 回退用，alpha:1677/1682）
}

/** 分制（alpha:850 scoreMode 默认 elo） */
export type ScoreMode = 'elo' | 'ntrp';

/** 全局单例弹层 payload（§2.2：P2 全量预定义，后续阶段只消费不改） */
export type SheetPayload =
  | { type: 'profile'; userId: number }
  | { type: 'join'; gameId: number }
  | { type: 'quit-confirm'; gameId: number }
  | { type: 'cancel-confirm'; gameId: number }
  | { type: 'booking'; gameId: number }          // 订场登记 / 锁定必打（3.2 三态锁：没锁→空锁→订场锁共用的面板）
  | { type: 'invite-to-game'; gameId: number }   // 局详情翻意向列表拉人（alpha:1213）
  | { type: 'invite-to-slot'; userId: number }   // 球员档案选局邀请（alpha:1239）
  | { type: 'intent-form' }                      // 留/改意向（alpha:1266）
  | { type: 'launch'; gameId?: number }          // 组局表单：无 gid 新建（alpha:1301）
  | { type: 'logout-confirm' }                   // 退出账号确认（5.1 弹窗：只是这台设备登出，数据都在）
  | { type: 'delete-confirm' }                   // 注销账号确认（5.1 弹窗：后果说明 + 二次确认，两步都过才执行）
  | { type: 'signup-card'; pendingJoin?: { gameId: number; bring: number }; pendingLaunch?: PublishInput; pendingCheckin?: { gameId: number } };
  // 名片建号卡（1.1 A1）：游客点报名/建局/扫码签到时弹出；建号成功自动接着完成挂起的动作（D3 两步拆分）
  // pendingCheckin（2.1·选项A）：扫码到场一律走名片建号，建号成功后自动「我到了」进候场区

/** 胜利结算卡每人涨跌 */
export interface WinChange { name: string; up: boolean; d: number }

/** 胜利结算卡（alpha:1716-1724 WinPopup：胜者名/比分/每人涨跌；独立组件层级最高，不走 SheetHost） */
export interface WinData { names: string; sa: number; sb: number; chg: WinChange[] }

/** 组局表单提交值（publishGame/editGame 共用；2026-10-04 定：费用从表单去掉，改局不动原局的 fee；
    说明字段去掉，改选规则三件——分制/轮转/迟到规则，直接落 Game 的 score/mode/lateRule）
    time/deadline 为组局拨盘产物：日段（今天/明天/后天/M.DD 周X）+ HH:mm，由 utils/time.ts gameTime 解析。 */
export interface PublishInput {
  name: string;       // 可为空串 → 自动起名「日段 · 地点」
  time: string;       // '后天 19:00' / '10.06 周一 19:00' 等
  dur: number;        // 打多久（小时）——由拨盘起止时刻算出，不再单独选
  deadline: string;   // '后天 17:00' 等绝对时刻；编辑态定死不改（alpha:1388）
  venue: string;
  min: number;
  cap: number;
  score: number;      // 分制 target（先到 N 且净胜 2）
  mode: CourtMode;    // 轮转方式（赢家留场/纯粹轮转/均衡配对）
  scoreRule: 'rally' | 'serve'; // 得分规则（每球得分制/发球得分制；2026-10-04 替代表单里的迟到规则）
}
