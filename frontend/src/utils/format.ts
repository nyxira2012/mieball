/* 球局基础工具（alpha:881-892 · 意向卡 slotBig alpha:1023-1024） */
import type { CourtMode, Game, GameEntry, User } from '@/api/types';
import { U, games, slots } from '@/mock/data';

/** 发牌模式名单一源（原 live.vue/detail.vue 内联 MODE_NAMES 挪出：live 页顶条/规则抽屉与
    live store 的 setRuleMode toast、detail 规则牌、LaunchSheet 规则三件共用一份） */
export const MODE_NAMES: Record<CourtMode, string> = { winner: '赢家留场', rotate: '纯粹轮转', balance: '均衡配对' };

/** 场馆词（loc「望京 · 花家地球馆 · 2 片」取第二段，无则空串）——
    打球页顶条 brand 高亮词与二维码浮层标题共用 */
export const venueOf = (g: Game): string => g.loc.split(' · ')[1] ?? '';

/** 场地显示名（booked 存量「3号」→「3号场」；无登记回退序号场）——
    打球页对局卡/空闲卡与终局结算弹窗 kicker 共用 */
export const courtLabel = (booked: string[] | undefined, idx: number): string => {
  const n = booked?.[idx] ?? `${idx + 1}号`;
  return n.endsWith('场') ? n : `${n}场`;
};

/** 是否当前登录用户（运行时读 U.me.id：真账号接管「我」位后 id 非 0，快照常量会认错人） */
export const isMe = (id?: number): boolean => id === U.me.id;

/** 带的人也占坑（alpha:882） */
export const heads = (g: Game): number => g.joined.reduce((s, e) => s + 1 + (e.bring || 0), 0);

/** 剩几坑（满员线口径，alpha:883） */
export const needOf = (g: Game): number => Math.max(0, g.cap - heads(g));

/** 必打判定（3.2 订场改版公共口径）：手动锁（sure）OR 场上有号（booked 非空）。
    截止是否自动终止、人均是否作废最少保底、卡面/详情的必打标识，全走这一个判定。 */
export const isForced = (g: Game): boolean => !!(g.sure || g.booked?.length);

/** 3.2 人均摊法口径（alpha:884 延伸）：
    不足最少按最少摊 / 够最少按当前人数摊 / 必打（手动锁或已订场）后最少作废按当前人数摊。
    fee=null（费用未定局）→ 0，调用方按 fee 判断显隐 */
export const perHead = (g: Game): number =>
  g.fee == null ? 0 : Math.round(g.fee / Math.max(isForced(g) ? 0 : g.min || 1, heads(g)));

/** 我的报名条目（alpha:885） */
export const myEntry = (g: Game): GameEntry | undefined => g.joined.find((e) => isMe(e.u.id));

/** 是否组织者（alpha:886） */
export const isOrg = (g: Game): boolean => !!(g.organizer && isMe(g.organizer.id));

/** 我的局：组织 / 已加入 / 被邀请（alpha:887） */
export const isMine = (g: Game): boolean => isOrg(g) || !!myEntry(g) || !!g.invitedMe;

/** 同局打过 = 熟人（alpha:888，启动时算一次的静态集合 —— alpha 原样，后续新建的局不并入） */
const knownIds = new Set<number>(games.filter(isMine).flatMap((g) => g.joined.map((e) => e.u.id)));

/** 喜欢过的 或 同局打过（alpha:889） */
export const known = (u: User): boolean => !!(u.liked || knownIds.has(u.id));

/** 时段名（alpha:890） */
export const slotName = (k: string): string => (slots.find((s) => s.k === k)?.n) || k;

/** 频率名（alpha:891） */
export const freqName = (f: number): string => (f === 0 ? '随缘' : `每周 ${f} 打`);

/** 意向卡大字时段（alpha:1023-1024）：'工作日晚间' → ['晚间','工作日']，其余 → [名,''] */
export const slotBig = (k: string): [string, string] => {
  const n = slotName(k);
  return n.startsWith('工作日') ? [n.slice(3), '工作日'] : n.startsWith('周末') ? [n.slice(2), '周末'] : [n, ''];
};
