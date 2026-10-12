/* 分享链接（三处分享共用件：详情页 / 战报子页 / 现场散场门牌，2026-10-12 统一
   都发详情链接）：系统分享面板优先（Web Share API），复制链接兜底；微信自定义
   卡片维持挂起（待服务号资质，2.6 §6）。
   uni 全局调用不 import——utils 不碰框架的例外适配位，同 nav.ts/clipboard.ts 先例。 */
import { copyWithToast } from "./clipboard";

/** 分享链接：navigator.share 优先（AbortError=用户取消，静默）→ 复制链接兜底，
    其余分流细节不外泄。兜底提示带「访客可看」知情小字（2.6 §6；详情链接
    未登录也能开，不传 copyMsg 即用这句——三处统一，不再各带各的） */
export async function shareLink(
  url: string,
  title: string,
  text?: string,
  copyMsg?: string,
): Promise<void> {
  if (typeof navigator !== "undefined" && navigator.share) {
    try {
      await navigator.share({ title, text, url });
      return;
    } catch (e) {
      if ((e as DOMException)?.name === "AbortError") return; // 用户取消分享，静默
    }
  }
  copyWithToast(url, copyMsg ?? "链接已复制 · 访客可看");
}
