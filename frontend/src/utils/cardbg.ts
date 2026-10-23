/* 卡背取景引擎的纯函数面 —— 素材路径约定 + 焦点缺省 + 六档参数 + 定位公式，
   参数逐值迁自 temp/原型-背景卡组件.html 与 temp/原型-头像背景卡优化.html（对照面）。
   分工：公式归这里（可单测），DOM 量测归 CardBackdrop 组件——cover 档的溢出倍率
   依赖容器实际宽高，必须渲染后量测再喂给 coverPos。
   「一张图走全站」：每件卡背只有一份 1536×640 原图，铺哪个位置、取哪块全由六档
   承担；换图/加款只改册子，全站各档自动对齐。 */

/** 册子规格素材面（横幅 12:5 全深色）——占位图与正式素材同规格产出，
    cover 档公式按它算溢出倍率 */
export const BACK_SPEC = { w: 1536, h: 640 };

/** 首批全统一卡背焦点（素材管线就位后按图逐件登记：册子 fx/fy 下发覆盖，此处只兜缺省） */
export const DEFAULT_FOCUS = { x: 0.68, y: 0.37 };

/** 取景六档：r 行卡 · c 横卡 · f 全幅卡 · d 试穿 · h 头带 · p 名单格 */
export type CardMode = "r" | "c" | "f" | "d" | "h" | "p";

/** 切片档参数：k=窗内放大倍数（>1 才有焦点位移余量），sx/sy=甜点位（焦点要落的窗内位置） */
export interface SliceSpec {
  k: number;
  sx: number;
  sy: number;
}

/** cover 档参数：ax/ay=容器锚点（图焦点要吸到的宿主内位置） */
export interface CoverSpec {
  cover: true;
  ax: number;
  ay: number;
}

/* 档位一本账（原型 WIN 表逐值迁入）——调档只改这里一行，全站自动对齐 */
export const WIN: Record<CardMode, SliceSpec | CoverSpec> = {
  r: { k: 1.32, sx: 0.64, sy: 0.52 }, // 行卡档：名字与分数的夹缝偏右、垂直居中
  c: { k: 1.28, sx: 0.62, sy: 0.42 }, // 横卡档：右侧偏上开阔区（避底部地点行/foot）
  f: { cover: true, ax: 0.8, ay: 0.42 }, // 全幅卡档（战力卡/档案/名片）：锚=右侧舞台
  d: { cover: true, ax: 0.8, ay: 0.42 }, // 试穿档（装扮大预览）：同全幅锚、纱更轻
  h: { cover: true, ax: 0.7, ay: 0.45 }, // 头带档（点人抽屉头部）：锚偏中，底边羽化
  p: { cover: true, ax: 0.5, ay: 0.42 }, // 名单格档（局详情名单墙小格）：内容居中，锚取中
};

/** 卡背素材 URL：约定优于配置（H5 同域直引 /cosmetics/{cid}.webp，册子不存路径） */
export function backUrl(cid: string): string {
  return `/cosmetics/${cid}.webp`;
}

/** 头像素材 URL：同款约定单一源（/cosmetics/{cid}.png，与后端 asset_url 头像族
    同口径）——默认款兜底与注册卡头像组的路径拼接收口到这里，不再各处手写 */
export function avatarUrl(cid: string): string {
  return `/cosmetics/${cid}.png`;
}

/* 钳 3~97% 后取 0.1% 精度——原型的落点精度（--bpx: xx.x%）收进公式层，
   组件与测试拿到即定值，不在 DOM 边缘各写一遍 toFixed */
const clampPx = (v: number) => {
  const p = Math.min(97, Math.max(3, v * 100));
  return Math.round(p * 10) / 10;
};

/** 切片档定位（渲染期可算，无需量测）：px=(sx−k·fx)/(1−k) 钳 3~97%——
    出界即焦点吸到可达边缘，图在窗内两侧永远出血、零切线 */
export function slicePos(
  t: SliceSpec,
  fx: number,
  fy: number,
): { px: number; py: number } {
  return {
    px: clampPx((t.sx - t.k * fx) / (1 - t.k)),
    py: clampPx((t.sy - t.k * fy) / (1 - t.k)),
  };
}

/** cover 档定位（组件量测容器后调用）：素材宽高+容器宽高+图焦点+框锚点 →
    background-position 百分比。kx/ky=cover 在各轴的溢出倍率；k 贴着 1（该轴
    溢出不足 2%）时位移量不足 1px、定位空转，落 50% 不误导检视 */
export function coverPos(
  matW: number,
  matH: number,
  boxW: number,
  boxH: number,
  fx: number,
  fy: number,
  ax: number,
  ay: number,
): { px: number; py: number } {
  const ar = matW / matH;
  const kx = Math.max(1, (boxH * ar) / boxW);
  const ky = Math.max(1, boxW / (boxH * ar));
  const pxOf = (k: number, f: number, a: number) =>
    k < 1.02 ? 50 : clampPx((a - k * f) / (1 - k));
  return { px: pxOf(kx, fx, ax), py: pxOf(ky, fy, ay) };
}
