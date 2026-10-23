/* ==========================================================
   二维码 SVG 生成（qrcode-generator 矩阵编码 + 自拼 SVG 串）。
   真码前端直接做：编码的是明文深链、无私密信息（2026-10-10
   用户定稿，推翻旧「真码后端接」口径）。纯函数零 vue/uni 依赖
   （I3.2 解耦，自拼 SVG 串模式），供 QrOverlay 消费。
   ========================================================== */
import qrcode from "qrcode-generator";

/** 文本 → 二维码 SVG：viewBox 0 0 N N（1 格 = 1 单位，静区由容器留白负责），
    暗格 fill=currentColor——码色随外层 color 走。
    注意：库默认按单字节编码（charCodeAt & 0xff），只喂 ASCII 深链——
    内容一旦混入中文须另配 stringToBytes，否则码编错。 */
export const qrSvg = (text: string): string => {
  const qr = qrcode(0, "M"); // typeNumber 0=按内容自动选版、纠错 M
  qr.addData(text);
  qr.make();
  const n = qr.getModuleCount();
  let rects = "";
  for (let r = 0; r < n; r++) {
    for (let c = 0; c < n; c++) {
      if (qr.isDark(r, c))
        rects += `<rect x="${c}" y="${r}" width="1" height="1" fill="currentColor"/>`;
    }
  }
  return `<svg viewBox="0 0 ${n} ${n}" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">${rects}</svg>`;
};
