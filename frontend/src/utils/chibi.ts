/* ==========================================================
   一头身 Q 版球员生成器（参数化 SVG）—— alpha.html:715-758 逐字移植
   配色常量与 SVG 拼接逻辑完全保留原文；仅供 components/ui/ChibiAvatar.vue
   消费（全库唯一 chibi SVG 出口）。
   ========================================================== */

/** chibi 配置：部件均传索引，越界自动取模（与 alpha 行为一致） */
export interface ChibiConfig {
  skin?: number
  hair?: number
  hc?: number
  shirt?: number
  face?: number
  acc?: number
}

export const SKIN = ['#FFE3C8', '#F3C79E', '#D89B6A', '#9C6238']
export const HAIRC = ['#2A2430', '#5B4632', '#C8562E', '#B8A9FF', '#E8D6A8', '#8A8F98']
export const SHIRT = ['#FFD400', '#FF5A36', '#B8A9FF', '#6FE7FF', '#F5F1E8', '#FF8FB2', '#2A2430', '#F2A93B']

/** alpha.html:719-757 的 chibi(c, s) 原样移植（唯一改动：TS 类型标注） */
export const chibi = (c?: ChibiConfig | null, s = 56): string => {
  const { skin = 0, hair = 0, hc = 0, shirt = 5, face = 0, acc = 0 } = c || {}
  const sk = SKIN[skin % 4], hh = HAIRC[hc % 6], st = SHIRT[shirt % 8]
  let hairSvg = ''
  if (hair % 6 === 0) hairSvg = `<path d="M20 46 Q20 12 50 12 Q80 12 80 46 Q66 36 50 36 Q34 36 20 46Z" fill="${hh}"/>` // 碗盖刘海
  if (hair % 6 === 1) hairSvg = `<path d="M20 46 Q20 12 50 12 Q80 12 80 46 Q66 36 50 36 Q34 36 20 46Z" fill="${hh}"/>
    <circle cx="50" cy="9" r="8" fill="${hh}"/>` // 丸子头
  if (hair % 6 === 2) hairSvg = `<path d="M19 42 Q26 10 50 10 Q74 10 81 42 L74 40 Q70 26 58 24 L60 38 L52 22 L46 38 L42 24 Q30 26 26 40Z" fill="${hh}"/>` // 刺头
  if (hair % 6 === 3) hairSvg = `<path d="M22 40 Q28 12 50 12 Q72 12 78 40 Q66 32 50 32 Q34 32 22 40Z" fill="${hh}"/>
    <rect x="16" y="36" width="8" height="26" rx="4" fill="${hh}"/><rect x="76" y="36" width="8" height="26" rx="4" fill="${hh}"/>` // 长发
  if (hair % 6 === 4) hairSvg = `<circle cx="30" cy="24" r="12" fill="${hh}"/><circle cx="50" cy="18" r="13" fill="${hh}"/>
    <circle cx="70" cy="24" r="12" fill="${hh}"/><path d="M22 42 Q26 24 50 22 Q74 24 78 42 Q60 34 50 34 Q40 34 22 42Z" fill="${hh}"/>` // 卷毛
  if (hair % 6 === 5) hairSvg = `<path d="M21 38 Q24 10 50 10 Q76 10 79 38 L79 44 L21 44Z" fill="${st === '#FFD400' ? '#2A2430' : st}"/>
    <ellipse cx="68" cy="40" rx="16" ry="4.5" fill="${st === '#FFD400' ? '#2A2430' : st}"/>` // 棒球帽
  let faceSvg = ''
  if (face % 4 === 0) faceSvg = `<circle cx="39" cy="46" r="3.2" fill="#2A2430"/><circle cx="61" cy="46" r="3.2" fill="#2A2430"/>
    <path d="M44 56 Q50 61 56 56" stroke="#2A2430" stroke-width="2.4" fill="none" stroke-linecap="round"/>` // 平静微笑
  if (face % 4 === 1) faceSvg = `<path d="M35 46 q4 -5 8 0 M57 46 q4 -5 8 0" stroke="#2A2430" stroke-width="2.6" fill="none" stroke-linecap="round"/>
    <path d="M43 55 Q50 63 57 55Z" fill="#2A2430"/>` // 开心
  if (face % 4 === 2) faceSvg = `<rect x="31" y="41" width="16" height="10" rx="4" fill="#2A2430"/><rect x="53" y="41" width="16" height="10" rx="4" fill="#2A2430"/>
    <rect x="46" y="44" width="8" height="3" fill="#2A2430"/><path d="M45 57 Q50 60 55 57" stroke="#2A2430" stroke-width="2.4" fill="none" stroke-linecap="round"/>` // 墨镜
  if (face % 4 === 3) faceSvg = `<circle cx="39" cy="46" r="3" fill="#2A2430"/><circle cx="61" cy="46" r="3" fill="#2A2430"/>
    <path d="M35 39 l8 2 M65 39 l-8 2" stroke="#2A2430" stroke-width="2" stroke-linecap="round"/>
    <path d="M45 57 h10" stroke="#2A2430" stroke-width="2.4" stroke-linecap="round"/>` // 专注
  let accSvg = ''
  if (acc % 3 === 1) accSvg = `<path d="M33 52 a8 7 0 0 1 14 0 M53 52 a8 7 0 0 1 14 0" stroke="#2A2430" stroke-width="2" fill="none"/>
    <line x1="47" y1="52" x2="53" y2="52" stroke="#2A2430" stroke-width="2"/>` // 眼镜
  if (acc % 3 === 2) accSvg = `<rect x="20" y="36" width="60" height="7" rx="3.5" fill="${st === '#F5F1E8' ? '#FF5A36' : '#F5F1E8'}"/>` // 发带
  return `<svg viewBox="0 0 100 100" width="${s}" height="${s}" aria-hidden="true">
    <ellipse cx="50" cy="95" rx="24" ry="4" fill="rgba(0,0,0,.25)"/>
    <rect x="30" y="64" width="40" height="30" rx="14" fill="${st}"/>
    <rect x="38" y="72" width="24" height="14" rx="7" fill="rgba(255,255,255,.16)"/>
    <circle cx="50" cy="42" r="29" fill="${sk}"/>
    ${hairSvg}
    <ellipse cx="33" cy="53" rx="5" ry="3.4" fill="rgba(255,90,54,.4)"/>
    <ellipse cx="67" cy="53" rx="5" ry="3.4" fill="rgba(255,90,54,.4)"/>
    ${faceSvg}${accSvg}
  </svg>`
}
