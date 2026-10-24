/* 球局基础工具（alpha:881-892 · 意向卡 slotBig alpha:1023-1024）
   1.2 接线清账：人头/剩坑/人均/forced/名单谓词全改读后端定值（A4 画面不自算），
   本文件只剩文案表、卡面映射（newGameCard）与少量无数据可依的纯展示口径；
   mock 快照族的 isMe/mockGameCard 已随演示世界退役（isMe 归 user store）。 */
import type { DownMode, Game, GameCardModel, PairingMode } from "@/api/types";
import { slots } from "@/api/dict";
import { isoDay, isoHm, untilTxt } from "@/utils/time";

/** 得分规则名单一源：LaunchSheet 规则三件与 detail 规则牌共用 */
export const SCORE_RULE_NAMES: Record<"rally" | "serve", string> = {
  rally: "每球得分制",
  serve: "发球得分制",
};

/** 谁下五式名单一源（单打只有 all/loser；RulesSheet 谁下段与 LiveTopbar 赛制 chip 消费） */
export const DOWN_NAMES: Record<DownMode, string> = {
  all: "全上全下",
  loser: "输家下",
  n1: "1人下",
  n2: "2人下",
  n3: "3人下",
};

/** 配对规则名单一源（组局 LaunchSheet、详情页规则牌、现场 LiveTopbar 与 RulesSheet 共用） */
export const PAIRING_NAMES: Record<PairingMode, string> = {
  queue: "签到顺序", // 按签到先后排
  balance: "积分均衡", // 两边战力最接近
  partner: "轮换优先",
  even: "胜负均衡",
};

/** 配对规则分段选项单一源（从 PAIRING_NAMES 键序派生，LaunchSheet 与 RulesSheet 同吃一份） */
export const PAIRING_OPTS = (Object.keys(PAIRING_NAMES) as PairingMode[]).map(
  (p) => ({
    value: p,
    label: PAIRING_NAMES[p],
  }),
);

/** 局分分制三档单一源（原型 seg-score · 11 快节奏/15 标准局/21 马拉松，2.1 照旧保留）：
    真局 RulesSheet 与沙盒 SandboxSheets 规则抽屉同吃一份，改文案只动这里 */
export const SCORE_OPTS = [
  { value: 11, label: "11", sub: "快节奏" },
  { value: 15, label: "15", sub: "标准局" },
  { value: 21, label: "21", sub: "马拉松" },
];

/** 场地显示名单一源：不管库里存的是「16」「16号」还是「16号场」，一律显示「16号场」——
    各写入路径的场地名口径历史上不一致（订场原样存/顶条直填补号/直开场缺省带号），
    展示侧在此一刀收口，写入路径不必迁移。名字本就以「场」结尾的（如「中央场」）原样保留。
    打球页对局卡/空闲卡与终局结算弹窗 kicker 共用。
    原 courtLabel(courts, idx)（另含序号兜底语义）自诞生起零消费，随 2.4 批2 删除，「+场」语义收编至此。 */
export const courtDisplayName = (name: string): string =>
  name.endsWith("场")
    ? name
    : name.endsWith("号")
      ? `${name}场`
      : `${name}号场`;

/** 顶条「打球场地」短标签单一源：["16号","5号"] →「16、5号场」（共用尾缀只说一遍）。
    空数组回「—」（顶条格子无场可显的兜底）。 */
export const courtsShortLabel = (courts: string[]): string =>
  courts.length
    ? `${courts.map((c) => c.replace(/(?:号)?场?$/, "")).join("、")}号场`
    : "—";

/** 是否组织者（真局看 viewer 块定值；游客无 my 恒 false） */
export const isOrg = (g: Game): boolean => !!g.my?.isOrganizer;

/** 点局卡分支（alpha:907 单一源）：被邀请且未加入 → 先弹加入卡；其余 → 进详情页。
    meet 的 onGameTap 消费（导航留在页面层） */
export const gameTapAction = (g: Game): "join" | "detail" =>
  !!g.my?.invited && !g.my?.myEntry ? "join" : "detail";

/** 我的局里终局行的显示分派（meet 死局区三分，4.8/4.9/4.10）：
    pending=组织者待处置卡（锁必打/撤局两出口）；terminated=组织者未成局卡（恢复，4.9——terminated
    走恢复，撤局是待处置的出口）或参加者当日灰字行；cancelled=参加者灰字行（后端死亡当日返回、
    次日收走；组织者侧永不回——撤局不留痕，与 games.py mine 同口径）。
    「当日」口径在后端 mine（读时过滤、次日不返回），前端只管渲染不判日期。 */
export const deadRowKind = (g: Game): "pending" | "restore" | "gray" | null => {
  if (g.status === "pending") return isOrg(g) ? "pending" : null;
  if (g.status === "terminated") return isOrg(g) ? "restore" : "gray";
  if (g.status === "cancelled") return isOrg(g) ? null : "gray";
  return null;
};

/** 自动局名「昵称 · 场馆末段」单一源（不填名时的兜底名）：LaunchSheet 占位/发布共用，
    改规则只动这里，预览名与落库名不会劈叉；场馆空则单用昵称（2026-10-11 时间锚改人锚——
    日期卡面另有，名字里「谁组的局」辨识度更高） */
export const autoGameName = (nickname: string, venue: string): string => {
  const tail = venue.split(" · ").pop()?.trim() ?? "";
  return tail ? `${nickname} · ${tail}` : nickname;
};

/** 卡片入场两字段派生（2.5 §4.1/4.2/4.4）：只对「我的局」（组织者 ∨ 正式报名；waitlist/被邀/
    游客永无入口）判定——
    账已开且未散场（liveOpened ∧ ¬ended）入口常在：组织者随时回去补散场确认，锚散场
    确认而非派生 done——到点未散场的局显示态已是 done 但流程没散场，收入口会把局挂死在
    「回不了现场、散不了场」的吸收态（2026-10-08 债清偿）；未开账的在办局（open/locked/live）
    里，必开局进两小时窗（含整点）放行（§4.2）；其余给倒计时灰字，纯展示无出口。
    导出给 detail.vue 复用——「进入现场」详情页与卡片同规矩同文案（2.5 附录A1），判定只此一份。 */
export function cardLiveEntry(g: Game): {
  countdown?: string;
  liveEnter?: boolean;
} {
  const mine = !!g.my?.isOrganizer || g.my?.myEntry?.standing === "formal";
  if (!mine) return {};
  if (g.liveOpened && !g.ended) return { liveEnter: true };
  if (g.status !== "open" && g.status !== "locked" && g.status !== "live")
    return {};
  // 必开与 backend/app/services/game_views.py is_forced（订场∨手动锁）同构：手动锁/订场后
  // 截止懒判定前簿 state 仍 open，开账闸已放行——口径不同构就漏亮入口（2.5 §4.2 锁了必打、
  // 订了场即必开；locked/live 时 forced 天然真，写全四条为可读）
  const forced =
    g.manualLock ||
    !!(g.courts && g.courts.length) ||
    g.status === "locked" ||
    g.status === "live";
  const start = new Date(g.startAt).getTime();
  if (forced && Date.now() >= start - 2 * 3600_000) return { liveEnter: true }; // 与 backend/app/services/live.py _start_gate timedelta(hours=2) 同源——2.5 §4.2 两小时窗两端各算
  const u = untilTxt(new Date(g.startAt));
  return u ? { countdown: `还有${u}` } : {};
}

/** 「这局的现场账开着还没散场」单一口径（2.5 §4.4 账开即现场）：status 已 live ∨
    liveOpened（提前开账时簿 state 仍 open/locked），且未散场。meet 远程散场横幅、
    detail「回到现场」、game store liveGame 三处同消费（2026-10-12 收编：原先三处
    各写一遍，meet 只写了 status 窄版，提前开账与到点未散场两类局横幅漏亮） */
export function liveOngoing(g: Game): boolean {
  return (g.status === "live" || g.liveOpened) && !g.ended;
}

/** 真局 → 卡面模型（meet 列表用）：时间/场馆/必打标都是纯展示换算，
    人头进度读后端定值 slotsLeft；角色与头像来自 entries+my */
export function newGameCard(g: Game): GameCardModel {
  const formal = g.entries?.filter((e) => e.standing === "formal") ?? [];
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
    timeSub: g.courts?.length
      ? g.courts.map((c) => courtDisplayName(c)).join("·")
      : g.manualLock
        ? "必开"
        : undefined,
    myRole: g.my?.isOrganizer
      ? "org"
      : g.my?.myEntry
        ? "joined"
        : g.my?.invited
          ? "inv"
          : null,
    stackAvatarUrls: formal.slice(0, 5).map((e) => e.account.avatarUrl ?? null),
    stackPlus: g.heads > 5 ? `+${g.heads - 5}` : "+",
    orgBack: g.organizer.back ?? null, // 局卡铺组织者卡背（无卡背素卡；旧形状 Person 缺键归一 null）
    ...cardLiveEntry(g),
  };
}

/** 名片显示名单一源（我的页与装扮页试穿框同吃）：游客态或占位名（「我」/
    「访客」）兜「访客」，登录后显示真实昵称——两页口径必须同源，改占位规则只动这里 */
export const displayMeName = (name: string, isGuest: boolean): string =>
  isGuest || name === "我" || name === "访客" ? "访客" : name;

/** 战绩行单一源（同上两页同吃）：N 场 · N 胜 · 胜率 N%（0 场人话守卫） */
export const meRecordText = (play: number, win: number): string =>
  play === 0
    ? "还没开张"
    : `${play} 场 · ${win} 胜 · 胜率 ${Math.round((win / play) * 100)}%`;

/** 时段名（alpha:890） */
export const slotName = (k: string): string =>
  slots.find((s) => s.k === k)?.n || k;

/** 频率名（alpha:891） */
export const freqName = (f: number): string =>
  f === 0 ? "随缘" : `每周 ${f} 打`;

/** 意向卡大字时段（alpha:1023-1024）：'工作日晚间' → ['晚间','工作日']，其余 → [名,''] */
export const slotBig = (k: string): [string, string] => {
  const n = slotName(k);
  return n.startsWith("工作日")
    ? [n.slice(3), "工作日"]
    : n.startsWith("周末")
      ? [n.slice(2), "周末"]
      : [n, ""];
};
