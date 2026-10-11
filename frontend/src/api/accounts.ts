/* 账号读接口（users/stats 域的匿名读面）：他人档案 + 战力榜。
   形状原样镜像线上 snake（契约总则 §1）；camel 映射收在 user store 单点。 */
import { request } from "./http";
import type { AccountView } from "./auth";
import type { CardBg } from "./types";

/** 榜单行 = 账号身份四件 + DUPR 名片六件 + Elo 一件（与 AccountView 的 dupr
    字段同名同义，少 phone/phone_tail/deactivated——榜单是公开面，不漏号不列注销；
    elo_rating 是 Elo 娱乐轨只读值，战力页 DUPR/Elo 切换的娱乐视图用） */
export interface LeaderboardRowApi {
  id: number;
  name: string;
  chibi: Record<string, number>;
  card_bg: CardBg | null;
  dupr_rating: number;
  dupr_provisional: boolean;
  dupr_games: number;
  dupr_wins: number;
  dupr_last5: string[];
  dupr_month_net: number;
  elo_rating: number;
}

/** 他人档案（可匿名）：隐私口径在后端（尾号只给同局打过的人，前端不补） */
export function apiAccountView(id: number): Promise<{ account: AccountView }> {
  return request("GET", `/users/${id}`);
}

/** 战力榜全量（可匿名）：DUPR 降序、同分 id 升序；0 场新号在列（provisional=true） */
export function apiLeaderboard(): Promise<LeaderboardRowApi[]> {
  return request("GET", "/stats/leaderboard");
}
