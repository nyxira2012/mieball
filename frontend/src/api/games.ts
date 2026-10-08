/* 球局/意向域 API（1.2）—— 线上 snake_case 形状逐字镜像（契约§1），只做类型化取数与错误透传。
   业务态在 stores/game（snake→camel 映射收在 store 单点）；错误统一抛 ApiError（http.ts），
   12 个 code 的合同表见 docs/开发日志.md 2026-10-06 收口条目（权威在 app/core/errors.py）。 */
import { request } from "./http";
import type {
  ChibiConfig,
  CourtMode,
  EditGameInput,
  GameStatus,
  PublishGameInput,
  Visibility,
} from "./types";

/** 报名行（entry_rows 镜像）：formal 在前按报名先后、候补按 seq 跟后 */
export interface EntryRowApi {
  account: { id: number; nickname: string; chibi: ChibiConfig };
  bring: number;
  standing: "formal" | "waitlist";
  wait_seq: number | null;
}

/** viewer 视角块（my_block 镜像）；匿名请求不带。能力旗与后端写窗同源（闸旗同源） */
export interface MyBlockApi {
  is_organizer: boolean;
  my_entry: {
    bring: number;
    standing: "formal" | "waitlist";
    wait_seq: number | null;
  } | null;
  invited: boolean;
  can_book: boolean;
  can_fill_fee: boolean;
  can_lock: boolean;
}

/** 已出账局的实摊定值块（game_view bill 镜像，1.3 批3；my_* 按 viewer，不在名单 → null） */
export interface GameBillApi {
  fee_total: number;
  per_head: number;
  heads: number;
  my_share: number | null;
  my_guest_count: number | null;
}

/** 补填确认步定值（fee-preview 响应，1.3 §4.5）：「将按人均 X 元向 N 人出账」 */
export interface FeePreviewApi {
  heads: number;
  per_head: number;
  organizer_share: number;
}

/** 局（game_view 镜像）。heads/slots_left/per_head/forced 是后端算好的定值（A4）；
    entries 仅详情与写动作出口带，my 仅登录 viewer 带。 */
export interface GameViewApi {
  id: number;
  name: string;
  organizer: { id: number; nickname: string; chibi: ChibiConfig };
  start_at: string; // ISO 8601 +08:00
  end_at: string;
  deadline_at: string;
  venue_name: string;
  venue_address: string | null;
  min_players: number;
  max_players: number;
  visibility: Visibility;
  scoring: number;
  rotation: CourtMode;
  score_rule: string;
  manual_lock: boolean;
  courts: string[] | null;
  fee_total: number | null;
  bill?: GameBillApi | null; // 实摊定值块（已出账的局非 null；1.3 批3）
  status: GameStatus;
  unlocked: boolean;
  joinable: boolean;
  live_opened: boolean; // 现场账已开（game_view 定值；2.5 批1）
  ended: boolean; // 散场确认过（流程锚；到点未散场 done 但 ended 假）
  heads: number;
  slots_left: number;
  per_head: number | null;
  forced: boolean;
  entries?: EntryRowApi[];
  my?: MyBlockApi;
}

/** 意向（intent_view 镜像）；known 由 routes 组合（列表=与 viewer 同局打过，mine 恒 false） */
export interface IntentViewApi {
  account: { id: number; nickname: string; chibi: ChibiConfig };
  slots: string[];
  frequency: number;
  note: string | null;
  updated_at: string;
  invited: boolean;
  known: boolean;
}

/* ---- 局簿 ---- */

export function apiPublishGame(input: PublishGameInput): Promise<GameViewApi> {
  return request("POST", "/games", input);
}

/** 找局打列表（可匿名；懒判定+三档过滤；含 done——前端列表自滤，见 meet 修订面裁决⑧） */
export function apiListGames(): Promise<GameViewApi[]> {
  return request("GET", "/games");
}

/** 我的局（Bearer）：组织者含 pending/恢复窗内 terminated，参加者含当日灰字行，被邀未加入也返回 */
export function apiMyGames(): Promise<GameViewApi[]> {
  return request("GET", "/games/mine");
}

/** 局详情（可匿名；链接即门票只拦 404；终态照常 200 带状态） */
export function apiGameDetail(id: number): Promise<GameViewApi> {
  return request("GET", `/games/${id}`);
}

/** 报名（整行进出；坑不够落候补也 200——看 my.my_entry.standing；重复 join 幂等） */
export function apiJoinGame(id: number, bring: number): Promise<GameViewApi> {
  return request("POST", `/games/${id}/join`, { bring });
}

/** 退局（截止锁退出、改约解锁窗可退；幂等——后端恒 {ok:true}） */
export function apiQuitGame(id: number): Promise<{ ok: true }> {
  return request("POST", `/games/${id}/quit`);
}

/** 改局（组织者；截止不在参数表=不可改；编辑类型层已挡 deadline_at） */
export function apiEditGame(
  id: number,
  input: EditGameInput,
): Promise<GameViewApi> {
  return request("POST", `/games/${id}/edit`, input);
}

/** 空锁必打（幂等） */
export function apiLockGame(id: number): Promise<GameViewApi> {
  return request("POST", `/games/${id}/lock`);
}

/** 订场登记（免费填 0） */
export function apiBookCourt(
  id: number,
  courts: string[],
  feeTotal: number,
): Promise<GameViewApi> {
  return request("POST", `/games/${id}/booking`, {
    courts,
    fee_total: feeTotal,
  });
}

/** 清空订场（手动锁保留；幂等） */
export function apiClearBooking(id: number): Promise<GameViewApi> {
  return request("POST", `/games/${id}/booking/clear`);
}

/** 补填确认步定值（组织者本人；纯现算不落库） */
export function apiGameFeePreview(
  id: number,
  amount: number,
): Promise<FeePreviewApi> {
  return request("GET", `/games/${id}/fee-preview?amount=${amount}`);
}

/** 补填总价（1.3 §4.5：>0 当场出账、=0 只定值不出账；价格就此定死）——响应直出局视图 */
export function apiGameFee(id: number, feeTotal: number): Promise<GameViewApi> {
  return request("POST", `/games/${id}/fee`, { fee_total: feeTotal });
}

/** 撤局（开打前；组织者 mine 不留痕） */
export function apiCancelGame(id: number): Promise<{ ok: true }> {
  return request("POST", `/games/${id}/cancel`);
}

/** 恢复（terminated 且开打前 → pending 待处置） */
export function apiRestoreGame(id: number): Promise<GameViewApi> {
  return request("POST", `/games/${id}/restore`);
}

/** 邀请（幂等；被邀不占坑） */
export function apiInviteUser(
  gameId: number,
  accountId: number,
): Promise<{ ok: true }> {
  return request("POST", `/games/${gameId}/invite`, { account_id: accountId });
}

/* ---- 意向簿 ---- */

/** 意向列表（可匿名，3.1 已定游客可翻；后端已排未邀在前） */
export function apiListIntents(): Promise<IntentViewApi[]> {
  return request("GET", "/intents");
}

export function apiMyIntent(): Promise<IntentViewApi | null> {
  return request("GET", "/intents/mine");
}

/** 留/改意向（改即清已邀标记；slots 空由后端 intent_slots_empty 拦，前端先拦省一跳） */
export function apiSaveIntent(
  slots: string[],
  frequency: number,
  note: string,
): Promise<IntentViewApi> {
  return request("POST", "/intents", { slots, frequency, note });
}

/** 删意向（幂等） */
export function apiDeleteIntent(): Promise<{ ok: true }> {
  return request("POST", "/intents/delete");
}
