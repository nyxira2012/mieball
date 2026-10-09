/* 6.1 批2【错误号】前端锁：500 错误体带 error_id → ApiError(internal_error) 且报号话术带号、
   errText 原样透出；业务错误（有 code 无号）、无 error 体、断网三分支不带号零改动（6.1 §4.1 禁止项）。
   stub 掉 uni 全局、喂 uni.request 的 success/fail 回调，不触网。 */
import { afterAll, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, errText, request } from "@/api/http";

const uniMock = vi.hoisted(() => ({ request: vi.fn() }));

vi.stubGlobal("uni", {
  request: (opts: { success?: (r: unknown) => void; fail?: () => void }) =>
    uniMock.request(opts),
  getStorageSync: () => "",
  setStorageSync: () => {},
  removeStorageSync: () => {},
});

afterAll(() => vi.unstubAllGlobals());

/** 喂一次 uni.request 成功回调：statusCode+data 原样进 http 层 */
function respond(statusCode: number, data: unknown) {
  uniMock.request.mockImplementationOnce(
    (opts: { success?: (r: unknown) => void }) =>
      opts.success?.({ statusCode, data }),
  );
}

/** 拿 request 抛出的 ApiError（本文件用例全部走错误分支） */
function errOf(method: "GET" | "POST", path: string): Promise<ApiError> {
  return request(method, path).then(
    () => {
      throw new Error("这一用例应当抛错");
    },
    (e) => e,
  );
}

beforeEach(() => {
  uniMock.request.mockReset();
});

describe("意外错误带号（6.1 §4.1 / 契约总则 §3）", () => {
  it("500 错误体带 error_id → code=internal_error、message 换报号话术、errText 原样透出", async () => {
    respond(500, {
      error: {
        code: "internal_error",
        message: "出错了，请稍后再试",
        error_id: "ERR-1a2b3c",
      },
    });
    const e = await errOf("GET", "/anything");
    expect(e).toBeInstanceOf(ApiError);
    expect(e.code).toBe("internal_error");
    expect(e.errorId).toBe("ERR-1a2b3c");
    expect(e.message).toBe("出错了，请把编号 ERR-1a2b3c 发到反馈群或告诉群主");
    expect(e.status).toBe(500);
    expect(errText(e)).toBe("出错了，请把编号 ERR-1a2b3c 发到反馈群或告诉群主");
  });

  it("业务错误（有 code 无 error_id）→ 后端 message 原样透传，不带号", async () => {
    respond(409, {
      error: { code: "phone_taken", message: "这个手机号已经有人用了" },
    });
    const e = await errOf("POST", "/auth/signup");
    expect(e).toBeInstanceOf(ApiError);
    expect(e.code).toBe("phone_taken");
    expect(e.message).toBe("这个手机号已经有人用了");
    expect(e.errorId).toBeUndefined();
  });

  it("≥400 无 error 体（网关错页等）→ http_error 兜底文案，不带号", async () => {
    respond(502, { detail: "Bad Gateway" });
    const e = await errOf("GET", "/anything");
    expect(e).toBeInstanceOf(ApiError);
    expect(e.code).toBe("http_error");
    expect(e.message).toBe("出错了，请稍后再试");
    expect(e.errorId).toBeUndefined();
  });

  it("断网（uni.request fail 回调）→ network 文案，不带号", async () => {
    uniMock.request.mockImplementationOnce((opts: { fail?: () => void }) =>
      opts.fail?.(),
    );
    const e = await errOf("POST", "/anything");
    expect(e).toBeInstanceOf(ApiError);
    expect(e.code).toBe("network");
    expect(e.message).toBe("网络不给力，请稍后再试");
    expect(e.errorId).toBeUndefined();
  });
});
