/* 记分（alpha:1650-1687）：先到 N 且净胜 2 才算赢 */

/** 收局判定（alpha:1686 `(c.sa>=T||c.sb>=T)&&Math.abs(c.sa-c.sb)>=2` 逐字对齐） */
export function shouldEnd(sa: number, sb: number, target: number): boolean {
  return (sa >= target || sb >= target) && Math.abs(sa - sb) >= 2;
}

/** undoPoint 语义辅助（alpha:1676-1679）：按最后得分方回退。
    注意 alpha 原样 quirk 保留：last==='a' 但 sa===0 时落到 else-if 会去减 sb。 */
export function undoScore(sa: number, sb: number, last: 'a' | 'b' | undefined): { sa: number; sb: number } {
  if (last === 'a' && sa > 0) return { sa: sa - 1, sb };
  else if (sb > 0) return { sa, sb: sb - 1 };
  return { sa, sb };
}
