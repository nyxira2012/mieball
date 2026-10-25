/* SVG 字符串 → <image> 可吃的 data URL：小程序端 v-html 出口（TabBar 图标 /
   BrawlStage 球拍 / QrOverlay 兜底码图）的替身渲染通道——<image> 把内容当
   独立 SVG 文档加载，页面 CSS 进不了图内，颜色靠 svg 里的 currentColor 占位
   由 color 参数现换成实色；线型等其余属性由调用方烤进 svg 本体（data-URL 里的
   svg 按 XML 解析，重属性即坏图，拼装方须自防重复）。纯函数，两端可共用。 */
export function svgDataUrl(svg: string, color?: string): string {
  const body = color ? svg.replaceAll("currentColor", color) : svg;
  return "data:image/svg+xml;charset=utf-8," + encodeURIComponent(body);
}
