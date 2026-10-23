/* 装扮页保存把关的派生纯函数面 —— 三族「还差 X」派生 + 保存按钮把关句。
   界面只显示不算（A4）：解锁状态与三类进度都是后端核算定值，这里只做
   前置提示文案的派生；能不能存的真值在服务端（POST /dress 把关，4.11），
   按钮变灰只是提示，不算判定。 */

import type { CosmeticItemApi, CosmeticsPageApi } from "@/api/cosmetics";

export type UnlockMap = CosmeticsPageApi["unlocks"];
export type DressProgress = CosmeticsPageApi["progress"];

/** 该件是否已解锁：unlocks 清单只收荣誉款与已授予定制款，册子里查无此件
    （公共款）即人人可穿，不在清单=不受限 */
export function isUnlocked(cid: string, unlocks: UnlockMap): boolean {
  return unlocks[cid]?.unlocked ?? true;
}

/** 分数差格式：台阶档 threshold 是×10 整数（35=3.5），进度 rating 是分数原值；
    一位小数、尾零收掉（0.3 分 / 1 分） */
function ratingGapText(threshold: number, rating: number): string | null {
  const d = Math.round(threshold - rating * 10) / 10;
  return d > 0 ? `还差 ${Number.isInteger(d) ? d : d.toFixed(1)} 分` : null;
}

/** 荣誉款「还差 X」派生：场数族按场、组局族按局、台阶族已定级才按分；
    未定级（台阶不算数）与已达标（不该再带锁）回 null——界面回落条件原文 */
export function honorGap(
  item: CosmeticItemApi,
  progress: DressProgress,
): string | null {
  if (item.tier !== "honor" || item.family == null || item.threshold == null)
    return null;
  switch (item.family) {
    case "matches": {
      const n = item.threshold - progress.matches;
      return n > 0 ? `还差 ${n} 场对局` : null;
    }
    case "organize": {
      const n = item.threshold - progress.organizes;
      return n > 0 ? `还差 ${n} 局` : null;
    }
    case "rating":
      return progress.rating_provisional
        ? null
        : ratingGapText(item.threshold, progress.rating);
  }
}

/** 保存把关：所选（头像/卡背）含未解锁荣誉款 → 报差什么的句子（可派生给
    「还差 X 解锁这件」、不可派生给册子条件原文）；全可保存回 null。
    'wechat' 不是册子编号——微信头像选项只在后端记下头像时才渲染，页面把门 */
export function dressBlock(
  page: CosmeticsPageApi,
  sel: { avatar: string; back: string },
): string | null {
  for (const cid of [sel.avatar, sel.back]) {
    if (cid === "wechat") continue;
    const item = page.items.find((i) => i.cid === cid);
    if (item && !isUnlocked(cid, page.unlocks)) {
      const gap = honorGap(item, page.progress);
      return gap ? `${gap}解锁这件` : (item.lock_text ?? "这件还没解锁");
    }
  }
  return null;
}
