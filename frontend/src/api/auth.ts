/* 账号域 API（1.1 基础 + 1.6 密码钥匙）—— 只做类型化取数与错误透传，业务态在 stores/session。
   响应里的 account 是后端"隐私出口"视图：本人视图含 phone/phone_tail。 */
import { request } from "./http";
import { CHIBI_PRESETS } from "./dict";
import type { CardBg, ChibiConfig } from "./types";

export type SmsPurpose =
  | "recovery"
  | "takeover"
  | "deactivate"
  | "set_password"
  | "reset_password"
  | "bind_phone"; // 1.8：快进号补绑手机号（判定反转：有账号当场拒，apiPhoneBindSend）

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
  wechat_bound?: boolean; // 微信登记位有无（1.8 批3）：我的页「微信已绑定」行两态唯一判定（仅本人视图给）
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

/** 名片草稿 → CardPayload（D5 显式旗标单一源）：SignupSheet 表单路与 login.vue
    微信回跳重建路共用——「明确填过的才置位」与预设下标映射只此一份，防两处漂移 */
export function cardPayloadOf(
  phone: string,
  nickname: string,
  picked: number | null,
): CardPayload {
  return {
    phone,
    nickname,
    nickname_set: !!nickname.trim(),
    chibi: picked != null ? CHIBI_PRESETS[picked].c : undefined,
    chibi_set: picked != null,
  };
}

export interface SessionPayload {
  token: string;
  account: AccountView;
  /** 1.7 微信绑定凭条生效标记：绑定真成了才回 true（没绑上绝不说——画面据此说「已绑上」） */
  wechat_bound?: boolean;
}

export function apiSignup(
  card: CardPayload,
  device: string,
  bindToken?: string,
): Promise<SessionPayload> {
  return request("POST", "/auth/signup", {
    device_marker: device,
    card,
    ...(bindToken ? { bind_token: bindToken } : {}),
  });
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
  bindToken?: string,
): Promise<SessionPayload> {
  return request("POST", "/auth/redeem", {
    phone,
    code,
    purpose,
    device_marker: device,
    card,
    ...(bindToken ? { bind_token: bindToken } : {}),
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
  bindToken?: string,
): Promise<SessionPayload> {
  return request("POST", "/auth/password/login", {
    phone,
    password,
    device_marker: device,
    ...(bindToken ? { bind_token: bindToken } : {}),
  });
}

/** 忘记密码重置（4.10）：换锁——后端作废全设备钥匙，只留本次登录的这台 */
export function apiPasswordReset(
  phone: string,
  code: string,
  password: string,
  device: string,
  bindToken?: string,
): Promise<SessionPayload> {
  return request("POST", "/auth/password/reset", {
    phone,
    code,
    password,
    device_marker: device,
    ...(bindToken ? { bind_token: bindToken } : {}),
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
  bindToken?: string,
): Promise<SessionPayload> {
  return request("POST", "/auth/password/redeem", {
    phone,
    password,
    device_marker: device,
    card,
    ...(bindToken ? { bind_token: bindToken } : {}),
  });
}

/* ---- 补绑手机号（1.8 §4.4 快进号随时补上）——须登录态；错误原样透传 ---- */

/** 补绑发码：号码已有账号 → 409 phone_taken_redirect（指路话术后端单一源，message 原样上抛） */
export function apiPhoneBindSend(phone: string): Promise<void> {
  return request("POST", "/auth/sms", { phone, purpose: "bind_phone" });
}

/** 补绑确认：核销后落号 + phone_verified，回最新本人视图（尾号/微信行立即翻真） */
export function apiPhoneBind(
  phone: string,
  code: string,
): Promise<{ account: AccountView }> {
  return request("POST", "/auth/phone/bind", { phone, code });
}

/* ---- 微信 JS-SDK 签名（分享卡登记用；与上面的登录钥匙非同族——无鉴权，页面打开即调） ---- */

/** 签名响应（线上 snake_case 直出，四键镜像后端 jsapi 签证处） */
export interface WechatJsapiSign {
  app_id: string;
  timestamp: number;
  nonce_str: string;
  signature: string;
}

/** 要一页的 JS-SDK 签名：url 是去掉 hash 的页面地址（SPA 全站同址，签一次全站能用） */
export function apiWechatJsapiSign(url: string): Promise<WechatJsapiSign> {
  return request("GET", `/wechat/jsapi_sign?url=${encodeURIComponent(url)}`);
}

/* ---- 微信钥匙（1.7）——请求字段逐字镜像 auth.py，规则全在 stores/session 与后端 ---- */

/** 要授权地址（A4：地址后端拼好，画面只管跳） */
export function apiWechatUrl(
  redirectUri: string,
  state: string,
): Promise<{ url: string }> {
  return request("POST", "/auth/wechat/url", {
    redirect_uri: redirectUri,
    state,
  });
}

/** 认人门回话：绑了直接进（钥匙在手），没绑发绑定凭条（转名片/验证时顺手绑）；
    1.8 快进支 created：fast=True 且微信没绑过 → 后端直接开号（微信生而正式绑，
    无凭条）——nickname_random=名字落到随机名（前端 toast 报名字的判据，4.1） */
export type WechatLoginResult =
  | { status: "ok"; token: string; account: AccountView; bind_token: string }
  | { status: "unbound"; bind_token: string }
  | {
      status: "created";
      token: string;
      account: AccountView;
      nickname_random: boolean;
    };

/** 认人门可带的快进卡字段（修订二「填了就算」）：api / session store / utils
 *  wechat 出发编排三层同形，共用这一份声明 */
export type WechatCardFields = {
  /** fast=false/不传同义（后端默认 False）=登录页微信键出发 → unbound 发凭条落卡（1.7 原路） */
  fast?: boolean;
  /** 卡上手填昵称（手填优先于微信昵称） */
  nickname?: string;
  /** 卡上手机号——没人用建带号账号、撞占用后端拒 phone_taken */
  phone?: string;
  /** 卡上选中的预设小人；不传=默认小人 */
  chibi?: ChibiConfig;
};

export function apiWechatLogin(
  code: string,
  device: string,
  opts?: WechatCardFields,
): Promise<WechatLoginResult> {
  return request("POST", "/auth/wechat/login", {
    code,
    device_marker: device,
    ...opts,
    chibi_set: opts?.chibi != null,
  });
}

/** 占卡「微信验证进入」（只认正式绑，接管级——文案与放行全由后端裁定） */
export function apiWechatRedeem(
  code: string,
  phone: string,
  device: string,
  card?: CardPayload,
): Promise<SessionPayload> {
  return request("POST", "/auth/wechat/redeem", {
    code,
    phone,
    device_marker: device,
    card,
  });
}
