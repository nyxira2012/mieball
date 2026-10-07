/* 账单域 API（1.3 批4）—— 线上 snake_case 形状镜像（类型在 types.ts 的 BillsViewApi 族），
   只做类型化取数与错误透传（沿 games.ts 范式）。写动作响应直出最新 BillsView：
   前端整树换新，「应收点一人少一笔、两处永远同一个数」由同一视图单点保证。 */
import { request } from "./http";
import type { BillsViewApi } from "./types";

export type BillPeriodName = "7d" | "30d" | "all";

/** 账单页全视图（登录者；period 按散场日过滤，缺省 all） */
export function apiBills(
  period: BillPeriodName = "all",
): Promise<BillsViewApi> {
  return request("GET", `/bills?period=${period}`);
}

/** 点「结算」（本人待付行，终态不可逆；重放幂等）——响应=当前档最新视图 */
export function apiBillSettle(
  gameId: number,
  period: BillPeriodName = "all",
): Promise<BillsViewApi> {
  return request("POST", `/bills/${gameId}/settle?period=${period}`);
}

/** 点「已收」（组织者本人，管理员 403；幂等）——响应=当前档最新视图 */
export function apiBillReceive(
  gameId: number,
  accountId: number,
  period: BillPeriodName = "all",
): Promise<BillsViewApi> {
  return request("POST", `/bills/${gameId}/receive?period=${period}`, {
    account_id: accountId,
  });
}
