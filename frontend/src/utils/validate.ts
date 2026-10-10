/* 提交前的即时校验小工具。手机号规则的权威在后端 services/accounts.py 的 PHONE_RE；
   这里只做同样的形状判断用于发请求前给快提示，不构成第二真值。 */

/** 中国大陆手机号：1[3-9] 开头 11 位（与后端 PHONE_RE 同规则） */
export const isValidPhone = (p: string): boolean =>
  /^1[3-9]\d{9}$/.test(p.trim());

/** 新密码两遍守卫（1.6 设密/重置/改密三处共用）：6 位起步（前端先拦 5 位，
    后端 password_too_short 真闸兜底）；不限字符种类，纯数字放行。通过返回 null */
export const newPwdError = (p1: string, p2: string): string | null => {
  if (p1.length < 6) return "密码至少 6 位";
  if (p1 !== p2) return "两次输入的密码不一样";
  return null;
};
