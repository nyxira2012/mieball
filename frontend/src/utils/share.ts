/* 分享链接（2.6 战报/3.2 详情共用件）：系统分享面板优先（Web Share API），
   复制链接兜底；微信自定义卡片维持挂起（待服务号资质，2.6 §6）。
   uni 全局调用不 import——utils 不碰框架的例外适配位，同 nav.ts/clipboard.ts 先例。 */
import { copyWithToast } from "./clipboard";

/** 分享链接：navigator.share 优先（AbortError=用户取消，静默）；无 share /
    调用失败 → 复制链接兜底（copyWithToast，成功 toast 文案全站单一）。调用方只给
    链接与文案，其余分流细节不外泄 */
export async function shareLink(
  url: string,
  title: string,
  text?: string,
): Promise<void> {
  if (typeof navigator !== "undefined" && navigator.share) {
    try {
      await navigator.share({ title, text, url });
      return;
    } catch (e) {
      if ((e as DOMException)?.name === "AbortError") return; // 用户取消分享，静默
    }
  }
  copyWithToast(url, "链接已复制 · 去微信群里粘贴");
}
