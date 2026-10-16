/* 本机记分账纯代数（live 与 sandbox 两域同构）：per-court 账的形状与
   懒建/记分/撤分/清零口径单一源——改账面形状或撤分语义只动这里，
   两个 store 各持 reactive 容器、只共享这套代数。 */

/** 一片的本机账：sa/sb 大比分 + 得分流水栈（undo 撤回到底基准，后进先出） */
export interface LocalScore {
  sa: number;
  sb: number;
  history: ("a" | "b")[];
}

export type LocalScoreBook = Record<number, LocalScore>;

/** 空账（懒建与清零同形——散落各处的字面量收此一处） */
export const emptyLocal = (): LocalScore => ({ sa: 0, sb: 0, history: [] });

/** 记一分：账面加一并留流水痕 */
export function applyPoint(acc: LocalScore, side: "a" | "b"): void {
  acc[side === "a" ? "sa" : "sb"]++;
  acc.history.push(side);
}

/** 误记撤回：流水倒退一分（支持撤回到底；空账/没账不动） */
export function undoPointIn(acc: LocalScore | undefined): void {
  const side = acc?.history.pop();
  if (side === "a") acc!.sa--;
  else if (side === "b") acc!.sb--;
}

/** 记分清零：这笔账归 0:0 重开一盘（没开过账不动） */
export function clearLocal(acc: LocalScore | undefined): void {
  if (!acc) return;
  acc.sa = acc.sb = 0;
  acc.history = [];
}
