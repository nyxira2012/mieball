/** 复制到剪贴板 + toast 反馈的单一源（mine 复制诊断日志 / detail 复制分享链接共用）。
    uni 全局调用不 import——utils 不碰框架的例外适配位，同 nav.ts 先例。 */
import { useUiStore } from "@/stores/ui";

/** 成功 toast 按调用方口径，失败文案全站单一：重试指引比报错细节有用 */
export function copyWithToast(data: string, okMsg: string): void {
  const ui = useUiStore(); // 函数内取：避免模块顶层 Pinia 未装
  uni.setClipboardData({
    data,
    success: () => ui.toast(okMsg),
    fail: () => ui.toast("复制没成功，再试一次"),
  });
}
