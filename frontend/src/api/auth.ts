/* 账号域 API（1.1）—— 只做类型化取数与错误透传，业务态在 stores/session。
   响应里的 account 是后端"隐私出口"视图：本人视图含 phone/phone_tail。 */
import { request } from "./http";
import type { CardBg, ChibiConfig } from "./types";

export type SmsPurpose = "recovery" | "takeover" | "deactivate";

/** 本人视图（GET /me、signup/redeem/profile 的返回） */
export interface AccountView {
  id: number;
  name: string;
  chibi: ChibiConfig;
  card_bg: CardBg | null;
  dupr_rating: number; // 1.4 DUPR 核心轨派生分（未定级=起步分，访客档语义 3.0）
  dupr_provisional: boolean; // 未定级（已结算 <5 场）
  dupr_games: number; // 已结算场数
  dupr_wins: number; // 已结算胜场数
  dupr_last5?: string[]; // 近 5 场胜负（时间正序）
  dupr_month_net?: number; // 本月净胜场
  deactivated: boolean;
  phone?: string;
  phone_tail?: string;
}

/** 名片三行。*_set 是"用户确实填了这一项"的显式标志（接管合并 D5 用，不做值推断） */
export interface CardPayload {
  phone: string;
  nickname?: string;
  nickname_set?: boolean;
  chibi?: ChibiConfig;
  chibi_set?: boolean;
}

export interface SessionPayload {
  token: string;
  account: AccountView;
}

export function apiSignup(
  card: CardPayload,
  device: string,
): Promise<SessionPayload> {
  return request("POST", "/auth/signup", { device_marker: device, card });
}

export function apiMe(): Promise<{ account: AccountView | null }> {
  return request("GET", "/auth/me");
}

export function apiUpdateProfile(patch: {
  nickname?: string;
  chibi?: ChibiConfig;
  card_bg?: CardBg;
}): Promise<{ account: AccountView }> {
  // POST 而非 PATCH：uni.request（尤其小程序端）不支持 PATCH 方法
  return request("POST", "/auth/profile", patch);
}

export function apiLogout(): Promise<void> {
  return request("POST", "/auth/logout");
}

export function apiSendCode(phone: string, purpose: SmsPurpose): Promise<void> {
  return request("POST", "/auth/sms", { phone, purpose });
}

export function apiRedeem(
  phone: string,
  code: string,
  purpose: "recovery" | "takeover",
  device: string,
  card?: CardPayload,
): Promise<SessionPayload> {
  return request("POST", "/auth/redeem", {
    phone,
    code,
    purpose,
    device_marker: device,
    card,
  });
}

export function apiDeactivate(phone: string, code: string): Promise<void> {
  return request("POST", "/auth/deactivate", { phone, code });
}
