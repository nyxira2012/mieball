/* 常用打球地点管理与候选匹配（3.3 组局表单地点交互单一源）。
   - 本地记忆：成功发局后记录场地，LRU 置顶去重，最多存 10 个；
   - 常用按钮：常驻前 3 馆（不足时由 dict.ts venueSuggestions 补齐）；
   - 模糊匹配：输入打字时从候选池过滤，内联胶囊快速填入。 */
import { venueSuggestions } from "@/api/dict";

export const VENUE_RECENT_KEY = "mieball_recent_venues";

/** 读取最近常用场地列表（本地持久化；空则兜底返回系统推荐） */
export function getRecentVenues(): string[] {
  try {
    const raw = uni.getStorageSync(VENUE_RECENT_KEY);
    if (typeof raw === "string" && raw.trim()) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed.filter(
          (v): v is string => typeof v === "string" && !!v.trim(),
        );
      }
    }
  } catch {
    // 格式损坏静默走兜底
  }
  return [...venueSuggestions];
}

/** 记录一次最终选用的场地（发局/改局成功后调用，LRU 置顶） */
export function recordVenue(name: string): void {
  const clean = name.trim();
  if (!clean) return;
  const current = getRecentVenues();
  const next = [clean, ...current.filter((v) => v !== clean)].slice(0, 10);
  try {
    uni.setStorageSync(VENUE_RECENT_KEY, JSON.stringify(next));
  } catch {
    // 存储满或无环境静默跳过
  }
}

/** 获取排在最前的 N 个常用按钮（默认 3 个，不足由推荐补齐并去重） */
export function getTopVenues(limit = 3): string[] {
  const recents = getRecentVenues();
  const combined = Array.from(new Set([...recents, ...venueSuggestions]));
  return combined.slice(0, limit);
}

/** 模糊匹配候选球馆（不区分大小写，包含关键字，排除与当前输入完全相同的值） */
export function matchVenues(query: string, max = 3): string[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const pool = Array.from(new Set([...getRecentVenues(), ...venueSuggestions]));
  return pool
    .filter((v) => {
      const lower = v.toLowerCase();
      return lower.includes(q) && lower !== q;
    })
    .slice(0, max);
}
