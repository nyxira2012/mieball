/* 账号域 API（1.1 基础 + 1.6 密码钥匙）—— 只做类型化取数与错误透传，业务态在 stores/session。
   响应里的 account 是后端"隐私出口"视图：本人视图含 phone/phone_tail。 */
import { request } from "./http";
import type { CardBg, ChibiConfig } from "./types";

export type SmsPurpose =
  "recovery" | "takeover" | "deactivate" | "set_password" | "reset_password";

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
  has_password: boolean; // 密码钥匙已设（1.6）：设置页「设/改密」与占卡「用密码进入」的唯一判定依据
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

/* ---- 密码钥匙（1.6 §4.8~§4.11）——请求字段逐字镜像 auth.py 模型（snake_case 直出） ---- */

/** 首设密码（4.8）：code 可空——接管/找回刚验完短信的宽限窗内免再发码（后端认空串走窗） */
export function apiPasswordSet(
  code: string | null,
  password: string,
): Promise<void> {
  return request("POST", "/auth/password/set", { code: code ?? "", password });
}

export function apiPasswordLogin(
  phone: string,
  password: string,
  device: string,
): Promise<SessionPayload> {
  return request("POST", "/auth/password/login", {
    phone,
    password,
    device_marker: device,
  });
}

/** 忘记密码重置（4.10）：换锁——后端作废全设备钥匙，只留本次登录的这台 */
export function apiPasswordReset(
  phone: string,
  code: string,
  password: string,
  device: string,
): Promise<SessionPayload> {
  return request("POST", "/auth/password/reset", {
    phone,
    code,
    password,
    device_marker: device,
  });
}

export function apiPasswordChange(
  oldPwd: string,
  newPwd: string,
): Promise<void> {
  return request("POST", "/auth/password/change", { old: oldPwd, new: newPwd });
}

/** 占卡「用密码进入」（4.5 三出口之二）：密码接管，名片合并由后端 D5 处理 */
export function apiPasswordRedeem(
  phone: string,
  password: string,
  device: string,
  card?: CardPayload,
): Promise<SessionPayload> {
  return request("POST", "/auth/password/redeem", {
    phone,
    password,
    device_marker: device,
    card,
  });
}
