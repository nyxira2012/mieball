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
  fee: number;          // 预计费用总价
  note?: string;
  joined: GameEntry[];
  wait: GameEntry[];    // 候补栏：满员加入进这里，有人退出即刻递补
  status: GameStatus;
  score: number;        // 分制 target（先到 N 且净胜 2，alpha:1686）
  mode: CourtMode;
  lateRule: boolean;    // 迟到排队尾等一轮
  invitedMe?: boolean;  // 别人邀请我
  locked?: boolean;     // 已到截止锁定（参加者不能再退出）
  sure?: boolean;       // 必定开局（最少人数要求作废）
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

/** 账单（5.1 文档：哪局、多少钱、什么状态；垫付只属组织者，故 role=org 才有 receivable） */
export interface Bill { id: number; gameId: number; gname: string; date: string; amt: number; status: BillStatus; role: 'org' | 'member' }

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
  | { type: 'add-court'; gameId: number }
  | { type: 'invite-to-game'; gameId: number }   // 局详情翻意向列表拉人（alpha:1213）
  | { type: 'invite-to-slot'; userId: number }   // 球员档案选局邀请（alpha:1239）
  | { type: 'intent-form' }                      // 留/改意向（alpha:1266）
  | { type: 'launch'; gameId?: number }          // 组局表单：无 gid 新建（alpha:1301）
  | { type: 'logout-confirm' }                   // 退出账号确认（5.1 弹窗：只是这台设备登出，数据都在）
  | { type: 'delete-confirm' };                  // 注销账号确认（5.1 弹窗：后果说明 + 二次确认，两步都过才执行）

/** 胜利结算卡每人涨跌 */
export interface WinChange { name: string; up: boolean; d: number }

/** 胜利结算卡（alpha:1716-1724 WinPopup：胜者名/比分/每人涨跌；独立组件层级最高，不走 SheetHost） */
export interface WinData { names: string; sa: number; sb: number; chg: WinChange[] }

/** 组局表单提交值（publishGame/editGame 共用；fee 已由表单层解析为最终数字） */
export interface PublishInput {
  name: string;       // 可为空串 → 自动起名「时间 · 地点」（alpha:1383）
  time: string;       // '周六 10:00' 等（含自定义输入）
  dur: number;
  deadline: string;   // 编辑态定死不改（alpha:1388）
  venue: string;
  min: number;
  cap: number;
  fee: number;
  note: string;
}
