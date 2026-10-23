/* 头像取景参数读取单一源：取景参数长在素材自己身上（webp 的 XMP 块），
   圆章渲染按参数逐图复现排版工具里的画面。跨模块契约（改一头必须改另一头）：
   - 写入方：scripts/picfit.html（把 JSON 包进 <m:fit> 标签写入 XMP 块，像素不动）
   - 读取方：本模块 parseWebpFit；消费方 AvatarBadge（按大小位分档取 bust/face）
   参数口径：k=窗内放大倍数（窗口显示画布中央 1/k 见方），x/y=位移（窗口边长
   的比例，正值右移/下移）。窗口显示的画布区域以 (0.5−x/k, 0.5−y/k) 为中心、
   边长 1/k——排版工具的画布渲染与此公式同源，所见即线上所得。 */

/** 单档取景：k 放大倍数（>0）、x/y 位移（窗口边长比例） */
export interface FrameFit {
  k: number;
  x: number;
  y: number;
}

/** 一张素材两档取景：bust 大位半身（≥40px 位）、face 小位脸特写（<40px 位） */
export interface AvatarFit {
  bust: FrameFit;
  face: FrameFit;
}

const FIT_TAG_RE = /<m:fit>([\s\S]*?)<\/m:fit>/;

function normFrame(raw: unknown): FrameFit | null {
  if (typeof raw !== "object" || raw === null) return null;
  const { k, x, y } = raw as Record<string, unknown>;
  if (
    typeof k !== "number" ||
    typeof x !== "number" ||
    typeof y !== "number" ||
    !Number.isFinite(k) ||
    !Number.isFinite(x) ||
    !Number.isFinite(y) ||
    k <= 0
  ) {
    return null;
  }
  return { k, x, y };
}

/** 从 webp 字节里解出取景参数：无 XMP 块 / 块里没有 <m:fit> / JSON 坏 /
    版本不认识 / 数值不合法，一律回 null（调用方回落无参数的默认摆放） */
export function parseWebpFit(buf: ArrayBuffer): AvatarFit | null {
  const b = new Uint8Array(buf);
  if (b.length < 12) return null;
  const dv = new DataView(buf);
  if (
    dv.getUint32(0, false) !== 0x52494646 || // 'RIFF'
    dv.getUint32(8, false) !== 0x57454250 // 'WEBP'
  ) {
    return null;
  }
  let xmp: string | null = null;
  let pos = 12;
  while (pos + 8 <= b.length) {
    const fourcc = dv.getUint32(pos, false);
    const size = dv.getUint32(pos + 4, true);
    if (pos + 8 + size > b.length) return null; // 尾块被截断，文件不完整
    if (fourcc === 0x584d5020) {
      // 'XMP '（四字符带尾空格）
      xmp = new TextDecoder().decode(b.subarray(pos + 8, pos + 8 + size));
      break; // 工具写入方保证唯一，取第一个即全部
    }
    pos += 8 + size + (size & 1); // 奇数长度块后有一个不计数的目的垫字节
  }
  if (xmp === null) return null;
  const tag = xmp.match(FIT_TAG_RE);
  if (!tag) return null;
  try {
    const raw = JSON.parse(tag[1]) as Record<string, unknown>;
    if (raw.v !== 1) return null; // 不认识的版本按无参数处理，回落默认摆放
    const bust = normFrame(raw.bust);
    const face = normFrame(raw.face);
    return bust && face ? { bust, face } : null;
  } catch {
    return null;
  }
}

/** 取景参数 → img 的 CSS transform（img 铺满窗口 object-fit:cover 后套用；
    百分比位移以 img 自身边长（=窗口边长）为基，与排版工具公式一一对应） */
export function frameTransform(f: FrameFit): string {
  return `translate(${(f.x * 100).toFixed(2)}%, ${(f.y * 100).toFixed(2)}%) scale(${f.k.toFixed(3)})`;
}

const fitCache = new Map<string, Promise<AvatarFit | null>>();

/** 取某 URL 素材的取景参数（按 URL 记忆，同图多枚圆章只取一次字节）。
    只认本站 /cosmetics/ 素材：微信头像等外链永不带参数，取一趟白费还涉跨域。
    取不到（请求失败/格式不认识）回 null，圆章回落默认摆放，不报错不拦渲染。 */
export function loadAvatarFit(url: string): Promise<AvatarFit | null> {
  if (!url.startsWith("/cosmetics/")) return Promise.resolve(null);
  let pending = fitCache.get(url);
  if (!pending) {
    pending = new Promise((resolve) => {
      uni.request({
        url,
        responseType: "arraybuffer",
        success: (r) => resolve(parseWebpFit(r.data as ArrayBuffer)),
        fail: () => resolve(null),
      });
    });
    fitCache.set(url, pending);
  }
  return pending;
}
