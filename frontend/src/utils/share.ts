/* 分享链接（三处分享共用件：详情页 / 战报子页 / 现场散场门牌，2026-10-12 统一
   都发详情链接）：微信内复制+指路右上角（微信里没有系统分享面板，也不给网页
   代发的口子——定制卡只能靠右上角「···」转出，复制出去的成不了卡）；
   微信外系统分享面板优先（Web Share API），复制链接兜底。
   uni 全局调用不 import——utils 不碰框架的例外适配位，同 nav.ts/clipboard.ts 先例。 */
import { copyWithToast } from "./clipboard";
import { isWeChatBrowser } from "./wechat";

/** 微信内复制提示语：保住「访客可看」知情小字，后半句指路卡片出口（复制≠卡片）。
    仅模块内消费——测试刻意钉字面量，不 import 这里 */
const WECHAT_COPY_MSG = "链接已复制 · 访客可看 · 发卡片点右上角 ···";

/** 分享链接：navigator.share 优先（AbortError=用户取消，静默）→ 复制链接兜底，
    其余分流细节不外泄。兜底提示带「访客可看」知情小字（2.6 §6；详情链接
    未登录也能开，不传 copyMsg 即用这句——三处统一，不再各带各的） */
export async function shareLink(
  url: string,
  title: string,
  text?: string,
  copyMsg?: string,
): Promise<void> {
  // 微信内先于 navigator.share 分流：微信的面板/代发口子都不存在，硬走系统面板
  // 只会报错，直接落到复制+指路
  if (isWeChatBrowser()) {
    copyWithToast(url, copyMsg ?? WECHAT_COPY_MSG);
    return;
  }
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
