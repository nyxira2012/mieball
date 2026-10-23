/* 装扮域 API —— 线上 snake_case 形状逐字镜像（games.ts 就地定义范式），
   只做类型化取数与错误透传。GET 打开即顺手核算（解锁/新标/进度全由后端定值，
   界面只显示不算）；POST /dress 的把关真值在服务端（cosmetic_not_found /
   cosmetic_not_unlocked / wechat_avatar_missing 抛 ApiError），界面变灰只是前置提示。 */
import { request } from "./http";

/** 册子条目（后端 CATALOG 镜像）：family/threshold 是前端派生「还差 X」的原料，
    lock_text 只给条件原文（界面一字不改）；fx/fy 是卡背主体焦点（头像恒 0） */
export interface CosmeticItemApi {
  cid: string;
  kind: "avatar" | "back";
  tier: "common" | "honor" | "custom";
  name: string;
  family: "matches" | "rating" | "organize" | null;
  threshold: number | null;
  lock_text: string | null;
  fx: number;
  fy: number;
  /** 素材约定路径，直出即用（卡背缩略/试穿直接吃它，不必 backUrl 自拼重复口径；
      asset 由后端按 kind 出扩展名：头像 .png / 卡背 .webp） */
  asset: string;
}

/** 装扮页全视图（GET /api/cosmetics 镜像）：unlocks 只含荣誉款与已授予定制款
    （未授予者连定制款条目的存在都看不见）；progress 三口径为核算定值 */
export interface CosmeticsPageApi {
  items: CosmeticItemApi[];
  unlocks: Record<string, { unlocked: boolean; is_new: boolean }>;
  wearing: { avatar: string; back: string };
  progress: {
    matches: number;
    rating: number;
    rating_provisional: boolean;
    organizes: number;
  };
  wechat_avatar_available: boolean;
  /** 本人微信头像原图（有记录直出 URL、没记录 null）——试穿预览真图来源，
      有选项（available）必有值；接口旧响应可缺省 */
  wechat_avatar_url?: string | null;
}

/** 保存穿戴响应（后端 dress_fields 兜底后的穿戴三键：avatar='wechat' 时
    avatar_url 是授权时刻记下的微信头像原图） */
export interface DressingApi {
  avatar: string;
  avatar_url: string;
  back: string;
}

/** 打开装扮页：后端顺手核算三类进度（失败不拦路，按上次清单照常开门） */
export function apiCosmeticsPage(): Promise<CosmeticsPageApi> {
  return request("GET", "/cosmetics");
}

/** 保存穿戴（未传的栏不改动——穿戴永远「最后保存的赢」；错误统一抛 ApiError） */
export function apiCosmeticsDress(body: {
  avatar?: string;
  back?: string;
}): Promise<DressingApi> {
  return request("POST", "/cosmetics/dress", body);
}
