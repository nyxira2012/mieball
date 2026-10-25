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

/* 素材地址单一源，两层分开（跨模块契约，改一头必须改另一头）：
   - assetUrl 出约定路径 /cosmetics/{cid}.webp——与后端 asset_url 同名同义的
     契约层，册子不存路径、不带平台与缓存信息；
   - resolveAssetUrl 把约定路径变取图真地址（补基地址+版本号），只在渲染宿主
     （AvatarBadge/CardBackdrop）各解析一次——后端下发的 avatar_url 入站地址
     与前端自拼地址同走这一口，微信头像等外链原样放行 */
/** 素材基地址：H5 两环境（dev 中间件/生产 nginx）都同域直引，空串即根相对；
    小程序无同源概念，编译期注入绝对域名。两分支各读各的键——MP 专属键带 MP
    前缀（.env 建档不碰 H5 读法）；单声明双赋值是条件编译与 vue-tsc 共存所需 */
let ASSET_BASE: string;
// #ifdef MP-WEIXIN
ASSET_BASE = import.meta.env.VITE_MP_ASSET_BASE ?? "";
// #endif
// #ifndef MP-WEIXIN
ASSET_BASE = import.meta.env.VITE_ASSET_BASE ?? "";
// #endif
/** 素材修订号：/cosmetics/ 按 immutable 永久缓存，换新全靠它——同名替换
    （改图/改取景参数）批次 +1 并随 fe 发版；上新新编号不必动 */
export const ASSET_REV = 1;

export function assetUrl(cid: string): string {
  return `/cosmetics/${cid}.webp`;
}

/** 约定路径 → 取图真地址；非约定路径（微信外链等）原样返回，已带查询串不重复拼 */
export function resolveAssetUrl(url: string): string {
  if (!url.startsWith("/cosmetics/") || url.includes("?")) return url;
  return `${ASSET_BASE}${url}?v=${ASSET_REV}`;
}

/** 认不认作本站素材（avatarfit 据此决定要不要拉字节读取景参数）——
    解析前的约定路径与解析后带基地址/版本号的真地址两种形态都认 */
export function isCosmeticUrl(url: string): boolean {
  return (
    url.startsWith("/cosmetics/") || url.startsWith(`${ASSET_BASE}/cosmetics/`)
  );
}

/* 卡背预载共享缓存：CSS 背景没有 onload，CardBackdrop 靠预载翻 shown——
   而列表页每行一个实例（榜单/约球页/名单墙），同一 URL 逐实例 new Image
   重复解码纯属浪费（多数人穿同一默认款）；按 URL 记一份 Promise，
   首个实例暖图、其余实例即点即显。失败也记账：坏编号整会话兜素卡不反复试 */
const preloadCache = new Map<string, Promise<boolean>>();
export function preloadAsset(url: string): Promise<boolean> {
  /* 无 Image 构造器的端（小程序逻辑层——new 即 ReferenceError）预载退位：
     CSS 背景由渲染层自载、失败不渲染（背景图没有裂图概念），直亮真值放行
     shown 闸——素底先出、图到即覆盖 */
  if (typeof Image === "undefined") return Promise.resolve(true);
  let p = preloadCache.get(url);
  if (!p) {
    p = new Promise<boolean>((resolve) => {
      const img = new Image();
      img.onload = () => resolve(true);
      img.onerror = () => resolve(false);
      img.src = url;
    });
    preloadCache.set(url, p);
  }
  return p;
}

/** 后端册子 cosmetics.py DEFAULT_AVATAR 的前端镜像（访客/无图兜底圆章吃它；
    卡背默认款前端无处消费不镜像——穿戴真值由装扮页 GET 的 wearing 直出。
    默认脸换编号时与后端同步改，cardbg.test 锁值 */
export const DEFAULT_AVATAR_CID = "g-00";

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
