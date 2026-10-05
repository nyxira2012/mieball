/* 提交前的即时校验小工具。手机号规则的权威在后端 services/accounts.py 的 PHONE_RE；
   这里只做同样的形状判断用于发请求前给快提示，不构成第二真值。 */

/** 中国大陆手机号：1[3-9] 开头 11 位（与后端 PHONE_RE 同规则） */
export const isValidPhone = (p: string): boolean => /^1[3-9]\d{9}$/.test(p.trim());
