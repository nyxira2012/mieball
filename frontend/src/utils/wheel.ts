/* 开打拨盘的网格常量与换算（LaunchSheet 消费，测试直盖本文件）。
   拨盘是全项目唯一「多列滚动、一次上报整组下标」的输入件，列的拆装换算收在
   这里单一源——父层拆列容易漏（2026-10-16 修复：结束列下标从未被消费，拨了
   不进值、保存回旧值）。 */

/** 时刻步进（分钟）——2026-10-04 定：30 分钟一格 */
export const STEP = 30;
/** 24h × 2 格（00:00–23:30） */
export const GRID_N = 48;
/** 网格最后一格 23:30 */
export const GRID_MAX = 23 * 60 + 30;
/** 00:00–23:30 逐格文案 */
export const GRID_LABELS: string[] = Array.from(
  { length: GRID_N },
  (_, i) =>
    `${String(Math.floor(i / 2)).padStart(2, "0")}:${String((i % 2) * 30).padStart(2, "0")}`,
);

/** 分钟 ↔ 网格下标（夹取） */
export const m2g = (m: number): number =>
  Math.max(0, Math.min(Math.round(m / STEP), GRID_N - 1));

const clamp = (v: number, lo: number, hi: number): number =>
  Math.max(lo, Math.min(v, hi));

/** 结束列可拨窗：开始后 30 分钟 ~ 6 小时（且不越过 23:30） */
const endWindow = (startMin: number): { lo: number; hi: number } => ({
  lo: startMin + STEP,
  hi: Math.min(startMin + 360, GRID_MAX),
});

/** 开打拨盘 change 的结束分钟换算。picked 是 picker 上报的结束行号，prevEndRow
    是换算前（旧开始口径）的结束行——两者不等 = 结束列被拨，按行号重算绝对分钟；
    相等 = 只动了日期/开始列，保持旧结束分钟（结束绝对时刻不变，时长随窗伸缩）。
    prevEndRow 必须在改 startMin 之前取：picker 上报的行号对照的是旧 value 的选中位。 */
export function playEndMin(
  picked: number,
  prevEndRow: number,
  prevEndMin: number,
  startMin: number,
): number {
  const { lo, hi } = endWindow(startMin);
  return picked !== prevEndRow
    ? clamp(startMin + STEP + picked * STEP, lo, hi)
    : clamp(prevEndMin, lo, hi);
}

/** 结束列文案（建列单一源）：可拨窗下沿逐格到上沿。LaunchSheet 的列组装、
    行号反推、编辑回填夹取三处同吃——窗口规则（30 分钟起、6 小时上限、封顶
    23:30）改 endWindow 一处，行号↔分钟换算跟着同式，不再复现「行号错位」。 */
export function endLabels(startMin: number): string[] {
  const { lo, hi } = endWindow(startMin);
  const out: string[] = [];
  for (let m = lo; m <= hi; m += STEP) out.push(GRID_LABELS[m2g(m)]);
  return out;
}

/** 分钟 → 结束列行号（endLabels 的逆换算，同窗夹取） */
export function endRowOf(startMin: number, endMin: number): number {
  return clamp(
    Math.round((endMin - (startMin + STEP)) / STEP),
    0,
    Math.max(0, endLabels(startMin).length - 1),
  );
}

/** 结束分钟收进可拨窗（编辑回填/保存校验同式） */
export function clampEnd(startMin: number, endMin: number): number {
  const { lo, hi } = endWindow(startMin);
  return clamp(endMin, lo, hi);
}
