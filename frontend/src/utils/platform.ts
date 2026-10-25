/* 平台旗子单一源：编译期条件编译各写一支，构建产物里是定值（非运行时探测——
   小程序逻辑层无 UA 可测）。isWeChatBrowser 的语义钉死「H5 微信内浏览器」：
   JS-SDK 登记门（registerWechatShare）靠它在小程序端为 false——小程序分享走
   onShareAppMessage 不走 JS-SDK；小程序端的环境门（如微信键 WechatButton）
   一律改认 IS_MP，不往 isWeChatBrowser 里扩义。脚本里拿不到条件编译位的
   分支用 IS_MP，能写 #ifdef 处直接写 #ifdef。 */
let mp = false;
// #ifdef MP-WEIXIN
mp = true;
// #endif
export const IS_MP: boolean = mp;
