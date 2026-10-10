import { describe, expect, it } from "vitest";
import { newPwdError } from "@/utils/validate";

/* newPwdError：1.6 设密/重置/改密共用的前端两遍守卫——6 位起步（前端先拦 5 位，
   后端 password_too_short 真闸兜底）、不限字符种类、两遍一致才放行。 */
describe("newPwdError 新密码两遍守卫（1.6）", () => {
  it("5 位被拦：密码至少 6 位", () => {
    expect(newPwdError("abc12", "abc12")).toBe("密码至少 6 位");
  });

  it("6 位纯数字放行：不限字符种类，返回 null", () => {
    expect(newPwdError("123456", "123456")).toBeNull();
  });

  it("两遍不一致被拦", () => {
    expect(newPwdError("123456", "123457")).toBe("两次输入的密码不一样");
  });
});
