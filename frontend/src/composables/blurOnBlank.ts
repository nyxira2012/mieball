/* 点空白收键盘——表单页通用底垫（login/dress 消费）：点击落在输入组件之外时把聚焦的
   输入框失焦，软键盘随之收起。移动端浏览器大多原生如此，个别 webview 不收——这里补齐。
   H5/webview 是真实 DOM 事件面；无 document 的端（app-vue 逻辑层）静默跳过。
   绑定走原生 addEventListener 而非模板 @click：uni 内建 view 的 @click 在「slot 根节点」
   这一挂载位上不落地（同款 vnode props 的深层节点可点、根节点不触发，走查实证，
   uni 事件桥内部差异未深挖）——原生监听不依赖其事件桥。 */
export function blurOnBlank(ev: Event): void {
  if (typeof document === "undefined") return;
  const target = ev.target as { closest?: (sel: string) => unknown } | null;
  if (typeof target?.closest !== "function") return;
  if (target.closest("input, textarea, uni-input")) return; // 点的就是输入框本体
  const active = document.activeElement as HTMLElement | null;
  if (active && active !== document.body && typeof active.blur === "function") {
    active.blur();
  }
}

/** 挂/摘到包裹层元素上（uni-view 的模板 ref 可能是组件实例也可能是元素，两种都接） */
function tapEl(v: unknown): Element | null {
  if (typeof document === "undefined") return null;
  return v instanceof Element
    ? v
    : ((v as { $el?: Element } | null)?.$el ?? null);
}
export function bindBlurOnBlank(el: unknown): void {
  tapEl(el)?.addEventListener("click", blurOnBlank);
}
export function unbindBlurOnBlank(el: unknown): void {
  tapEl(el)?.removeEventListener("click", blurOnBlank);
}
