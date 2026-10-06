/* 球局基础工具（alpha:881-892 · 意向卡 slotBig alpha:1023-1024）
   1.2 接线清账：人头/剩坑/人均/forced/名单谓词全改读后端定值（A4 画面不自算），
   本文件只剩文案表、卡面映射（newGameCard/mockGameCard）与少量无数据可依的纯展示口径。 */
import type { ChibiConfig, CourtMode, DownMode, Game, GameCardModel, GameStatus, MockGame, PairingMode } from '@/api/types';
import { U, slots } from '@/mock/data';
import { isoDay, isoHm, splitGameTime } from '@/utils/time';

/** 发牌模式名单一源（原 live.vue/detail.vue 内联 MODE_NAMES 挪出：live 页顶条/规则抽屉与
    live store 的 setRuleMode toast、detail 规则牌、LaunchSheet 规则三件共用一份） */
export const MODE_NAMES: Record<CourtMode, string> = { winner: '赢家留场', rotate: '纯粹轮转', balance: '均衡配对' };

/** 得分规则名单一源（MODE_NAMES 同族）：LaunchSheet 规则三件与 detail 规则牌共用 */
export const SCORE_RULE_NAMES: Record<'rally' | 'serve', string> = { rally: '每球得分制', serve: '发球得分制' };

/** 谁下五式名单一源（2.4 §4.1 四件套之二；单打只有 all/loser）。
    与 MODE_NAMES 并列新表、不并入——3.2 面仍消费 MODE_NAMES，批3 旧抽屉删后再清账 */
export const DOWN_NAMES: Record<DownMode, string> = {
  all: '全上全下',
  loser: '输家下',
  n1: '1人下',
  n2: '2人下',
  n3: '3人下',
};

/** 怎么配名单一源（仅双打显示，2.4 §4.5） */
export const PAIRING_NAMES: Record<PairingMode, string> = { queue: '按候场队序', balance: '均衡配对' };

/** 视图 7 态 ↔ 文案（单一源=后端 derive；先例 MODE_NAMES/BILL_STATUS_NAMES） */
export const GAME_STATUS_NAMES: Record<GameStatus, string> = {
  open: '报名中', locked: '已锁定', live: '进行中', done: '已结束',
  terminated: '已终止', cancelled: '已取消', pending: '待处置',
};

/** 场地显示名（登记的「3号」→「3号场」；无登记回退序号场）——
    打球页对局卡/空闲卡与终局结算弹窗 kicker 共用 */
export const courtLabel = (courts: string[] | null | undefined, idx: number): string => {
  const n = courts?.[idx] ?? `${idx + 1}号`;
  return n.endsWith('场') ? n : `${n}场`;
};

/** 是否当前登录用户（运行时读 U.me.id：真账号接管「我」位后 id 非 0，快照常量会认错人） */
export const isMe = (id?: number): boolean => id === U.me.id;

/** 是否组织者（真局看 viewer 块定值；游客无 my 恒 false） */
export const isOrg = (g: Game): boolean => !!g.my?.isOrganizer;

/** 点局卡分支（alpha:907 单一源）：被邀请且未加入 → 先弹加入卡；其余 → 进详情页。
    meet 的 onGameTap 消费（导航留在页面层） */
export const gameTapAction = (g: Game): 'join' | 'detail' =>
  !!g.my?.invited && !g.my?.myEntry ? 'join' : 'detail';

/** 我的局里终局行的显示分派（meet 死局区三分，4.8/4.9/4.10）：
    pending=组织者待处置卡（锁必打/撤局两出口）；terminated=组织者未成局卡（恢复/撤局）或
    参加者当日灰字行；cancelled=参加者灰字行（组织者撤局不留痕，后端本就不回，防御）。
    「当日」口径在后端 mine（读时过滤、次日不返回），前端只管渲染不判日期。 */
export const deadRowKind = (g: Game): 'pending' | 'restore' | 'gray' | null => {
  if (g.status === 'pending') return isOrg(g) ? 'pending' : null;
  if (g.status === 'terminated') return isOrg(g) ? 'restore' : 'gray';
  if (g.status === 'cancelled') return isOrg(g) ? null : 'gray';
  return null;
};

/** 自动局名「日段 · 场馆末段」单一源（不填名时的兜底名）：LaunchSheet 占位/发布共用，
    改规则只动这里，预览名与落库名不会劈叉 */
export const autoGameName = (time: string, venue: string): string =>
  `${time.split(' ')[0]} · ${venue.split(' · ').pop()}`;

/** 真局 → 卡面模型（meet 列表用）：时间/场馆/必打标都是纯展示换算，
    人头进度读后端定值 slotsLeft；角色与头像来自 entries+my */
export function newGameCard(g: Game): GameCardModel {
  const formal = g.entries?.filter((e) => e.standing === 'formal') ?? [];
  return {
    id: g.id,
    name: g.name,
    dayText: isoDay(g.startAt),
    hmText: isoHm(g.startAt),
    venueText: g.venueName,
    status: g.status,
    minPlayers: g.minPlayers,
    maxPlayers: g.maxPlayers,
    slotsLeft: g.slotsLeft,
    forcedLabel: g.courts?.length ? '已订场 · 必开' : g.manualLock ? '必开' : undefined,
    myRole: g.my?.isOrganizer
      ? 'org'
      : g.my?.myEntry
        ? 'joined'
        : g.my?.invited
          ? 'inv'
          : null,
    stackAvatars: formal.slice(0, 5).map((e) => e.account.chibi),
    stackPlus: `+${g.heads - 5 > 0 ? g.heads - 5 : ''}`,
  };
}

/** mock 快照局 → 卡面模型（登记/记录页隔离线用；口径逐字保持 5.1 的 GameCard 行为） */
export function mockGameCard(g: MockGame): GameCardModel {
  const hs = g.joined.reduce((s, e) => s + 1 + (e.bring || 0), 0);
  const joinedMe = g.joined.some((e) => isMe(e.u.id));
  return {
    id: g.id,
    name: g.name,
    dayText: splitGameTime(g.t).day,
    hmText: splitGameTime(g.t).hm,
    venueText: g.loc,
    status: g.status,
    minPlayers: g.min,
    maxPlayers: g.cap,
    slotsLeft: Math.max(0, g.cap - hs),
    forcedLabel: g.booked?.length ? '已订场 · 必开' : g.sure ? '必开' : undefined,
    myRole: isMe(g.organizer.id) ? 'org' : joinedMe ? 'joined' : g.invitedMe ? 'inv' : null,
    stackAvatars: g.joined.slice(0, 5).map((e) => e.u.chibi),
    stackPlus: `+${hs - 5 > 0 ? hs - 5 : ''}${g.joined.some((e) => e.u.shadow) ? ' ·含随行' : ''}`,
    result: g.result,
  };
}

/** 时段名（alpha:890） */
export const slotName = (k: string): string => (slots.find((s) => s.k === k)?.n) || k;

/** 频率名（alpha:891） */
export const freqName = (f: number): string => (f === 0 ? '随缘' : `每周 ${f} 打`);

/** 意向卡大字时段（alpha:1023-1024）：'工作日晚间' → ['晚间','工作日']，其余 → [名,''] */
export const slotBig = (k: string): [string, string] => {
  const n = slotName(k);
  return n.startsWith('工作日') ? [n.slice(3), '工作日'] : n.startsWith('周末') ? [n.slice(2), '周末'] : [n, ''];
};
