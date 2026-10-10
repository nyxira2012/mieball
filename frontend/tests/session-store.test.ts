/* session store（1.1 账号域前端深模块）单测：
   - 启动认人：有钥匙换档案 / 钥匙失效静默降级游客
   - 身份位（user store me）：真账号视图 applyAccount 原位换装（mock 退役后游客=零战绩占位）
   - 退出/注销回落游客占位；建号成功清草稿
   API 层整体 mock（@/api/auth），不触网。 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import * as authApi from "@/api/auth";
import type { AccountView } from "@/api/auth";
import * as http from "@/api/http";
import { GUEST_USER, useUserStore } from "@/stores/user";
import { useSessionStore } from "@/stores/session";
import { useUiStore } from "@/stores/ui";

vi.mock("@/api/auth", () => ({
  apiSignup: vi.fn(),
  apiMe: vi.fn(),
  apiUpdateProfile: vi.fn(),
  apiLogout: vi.fn(),
  apiSendCode: vi.fn(),
  apiRedeem: vi.fn(),
  apiDeactivate: vi.fn(),
  apiPasswordSet: vi.fn(),
  apiPasswordLogin: vi.fn(),
  apiPasswordReset: vi.fn(),
  apiPasswordChange: vi.fn(),
  apiPasswordRedeem: vi.fn(),
}));

const view: AccountView = {
  id: 42,
  name: "海淀反手王",
  chibi: { skin: 2, hair: 3, hc: 1, shirt: 4, face: 2, acc: 1 },
  card_bg: "gold",
  deactivated: false,
  has_password: false,
  phone: "13800001111",
  phone_tail: "1111",
};

/** 游客占位（恢复断言用——零战绩，非演示数字） */
const demo = {
  id: GUEST_USER.id,
  name: GUEST_USER.name,
  chibi: { ...GUEST_USER.chibi },
};

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
  vi.spyOn(http, "getToken").mockReturnValue(null);
  vi.spyOn(http, "setToken").mockImplementation(() => {});
  vi.spyOn(http, "clearCardDraft").mockImplementation(() => {});
});

describe("启动认人（4.3）", () => {
  it("本机有钥匙 → 换成后端档案，身份位 me 同步换新", async () => {
    vi.spyOn(http, "getToken").mockReturnValue("a-token");
    vi.mocked(authApi.apiMe).mockResolvedValue({ account: view });

    const session = useSessionStore();
    await session.init();

    expect(session.status).toBe("ready");
    expect(session.account?.id).toBe(42);
    const me = useUserStore().me;
    expect(me.id).toBe(42);
    expect(me.name).toBe("海淀反手王");
    expect(me.chibi).toEqual(view.chibi);
    expect(me.cardBg).toBe("gold");
  });

  it("钥匙已作废（被接管/注销）→ 静默降级游客，不报错", async () => {
    vi.spyOn(http, "getToken").mockReturnValue("dead-token");
    vi.mocked(authApi.apiMe).mockResolvedValue({ account: null });

    const session = useSessionStore();
    await session.init();

    expect(session.status).toBe("guest");
    expect(session.account).toBeNull();
  });

  it("没钥匙 → 直接游客", async () => {
    const session = useSessionStore();
    await session.init();
    expect(session.status).toBe("guest");
    expect(authApi.apiMe).not.toHaveBeenCalled();
  });

  it("网络失败 → 按游客进场，不拦启动", async () => {
    vi.spyOn(http, "getToken").mockReturnValue("t");
    vi.mocked(authApi.apiMe).mockRejectedValue(new Error("net"));
    const session = useSessionStore();
    await session.init();
    expect(session.status).toBe("guest");
  });
});

describe("名片建号与退出（4.2 / A3）", () => {
  it("建号成功：落钥匙、接过渡位、清草稿", async () => {
    vi.mocked(authApi.apiSignup).mockResolvedValue({
      token: "t1",
      account: view,
    });
    const session = useSessionStore();
    await session.signupWithCard({
      phone: "13800001111",
      nickname: "海淀反手王",
      nickname_set: true,
    });

    expect(http.setToken).toHaveBeenCalledWith("t1");
    expect(session.status).toBe("ready");
    expect(http.clearCardDraft).toHaveBeenCalled();
    expect(useUserStore().me.id).toBe(42);
  });

  it("手机号被占：phone_taken 原样抛给弹层接", async () => {
    vi.mocked(authApi.apiSignup).mockRejectedValue(
      Object.assign(new Error("占用"), { code: "phone_taken", status: 409 }),
    );
    const session = useSessionStore();
    await expect(
      session.signupWithCard({ phone: "13800001111" }),
    ).rejects.toMatchObject({ code: "phone_taken" });
    expect(session.status).not.toBe("ready");
  });

  it("退出：服务端作废失败也不拦，本机回落游客占位", async () => {
    vi.mocked(authApi.apiLogout).mockRejectedValue(new Error("net"));
    const session = useSessionStore();
    session.$patch({ status: "ready", account: view });
    useUserStore().applyAccount(view);

    await session.logout();

    expect(session.status).toBe("guest");
    expect(session.account).toBeNull();
    expect(http.setToken).toHaveBeenCalledWith(null);
    const me = useUserStore().me;
    expect(me.id).toBe(demo.id);
    expect(me.name).toBe(demo.name);
    expect(me.chibi).toEqual(demo.chibi);
  });
});

describe("注销（4.6）", () => {
  it("验证通过后：清钥匙、回落游客占位", async () => {
    vi.mocked(authApi.apiDeactivate).mockResolvedValue();
    const session = useSessionStore();
    session.$patch({ status: "ready", account: view });

    await session.deactivateAccount("13800001111", "123456");

    expect(session.status).toBe("guest");
    expect(useUserStore().me.name).toBe(demo.name);
  });

  it("验证码错：错误上抛，不降级身份", async () => {
    vi.mocked(authApi.apiDeactivate).mockRejectedValue(
      Object.assign(new Error("码不对"), { code: "sms_bad_code", status: 400 }),
    );
    const session = useSessionStore();
    session.$patch({ status: "ready", account: view });

    await expect(
      session.deactivateAccount("13800001111", "000000"),
    ).rejects.toMatchObject({ code: "sms_bad_code" });
    expect(session.status).toBe("ready");
  });
});

describe("密码钥匙（4.8~4.11）", () => {
  beforeEach(() => {
    vi.spyOn(http, "deviceMarker").mockReturnValue("dev-9");
  });

  it("密码登录成功：落钥匙换装，has_password 随视图落位，名片草稿保留", async () => {
    vi.mocked(authApi.apiPasswordLogin).mockResolvedValue({
      token: "tp",
      account: { ...view, has_password: true },
    });
    const session = useSessionStore();
    const got = await session.passwordLogin("13800001111", "pw123456");

    expect(authApi.apiPasswordLogin).toHaveBeenCalledWith(
      "13800001111",
      "pw123456",
      "dev-9",
    );
    expect(http.setToken).toHaveBeenCalledWith("tp");
    expect(session.status).toBe("ready");
    expect(got.has_password).toBe(true); // 设置页「设/改密」判定读这个位（1.6）
    expect(session.account?.has_password).toBe(true);
    expect(useUserStore().me.id).toBe(42);
    // 登录路不清草稿：挂起的报名/建局续办要用（A1 已填内容不丢）
    expect(http.clearCardDraft).not.toHaveBeenCalled();
  });

  it("忘记密码重置成功（4.10）：换锁进新钥匙，同样不清草稿", async () => {
    vi.mocked(authApi.apiPasswordReset).mockResolvedValue({
      token: "tr",
      account: view,
    });
    const session = useSessionStore();
    await session.passwordReset("13800001111", "654321", "new-pass");

    expect(authApi.apiPasswordReset).toHaveBeenCalledWith(
      "13800001111",
      "654321",
      "new-pass",
      "dev-9",
    );
    expect(http.setToken).toHaveBeenCalledWith("tr");
    expect(useUserStore().me.id).toBe(42);
    expect(http.clearCardDraft).not.toHaveBeenCalled();
  });

  it("占卡密码接管成功（4.5）：名片已并入账号，与 redeemCode 同款清草稿", async () => {
    vi.mocked(authApi.apiPasswordRedeem).mockResolvedValue({
      token: "td",
      account: view,
    });
    const session = useSessionStore();
    const card = {
      phone: "13800001111",
      nickname: "海淀反手王",
      nickname_set: true,
    };
    await session.passwordRedeem("13800001111", "pw123456", card);

    expect(authApi.apiPasswordRedeem).toHaveBeenCalledWith(
      "13800001111",
      "pw123456",
      "dev-9",
      card,
    );
    expect(http.setToken).toHaveBeenCalledWith("td");
    expect(session.status).toBe("ready");
    expect(http.clearCardDraft).toHaveBeenCalled();
  });

  it("密码错：ApiError 原样上抛，身份态不被污染", async () => {
    vi.mocked(authApi.apiPasswordLogin).mockRejectedValue(
      Object.assign(new Error("密码不对，还可试 4 次"), {
        code: "password_wrong",
        status: 400,
      }),
    );
    const session = useSessionStore();
    await expect(
      session.passwordLogin("13800001111", "bad"),
    ).rejects.toMatchObject({ code: "password_wrong" });

    expect(session.status).not.toBe("ready");
    expect(session.account).toBeNull();
    expect(http.setToken).not.toHaveBeenCalled();
  });

  it("首设密码（4.8）：code/password 原样透传 + 成功 toast 单一源", async () => {
    const session = useSessionStore();
    await session.setPassword("123456", "pw123456");

    expect(authApi.apiPasswordSet).toHaveBeenCalledWith("123456", "pw123456");
    expect(useUiStore().toastMsg).toBe("密码已设置 · 以后可用密码登录");
  });

  it("修改密码（4.11）：old/new 逐字镜像后端字段，toast 带其他设备口径", async () => {
    const session = useSessionStore();
    await session.changePassword("old-pass", "new-pass");

    expect(authApi.apiPasswordChange).toHaveBeenCalledWith(
      "old-pass",
      "new-pass",
    );
    expect(useUiStore().toastMsg).toContain("其他设备不用重新登录");
  });
});

describe("改名片（A3）", () => {
  it("登录态走云端并回接视图", async () => {
    const updated = { ...view, name: "亮马河快攻" };
    vi.mocked(authApi.apiUpdateProfile).mockResolvedValue({ account: updated });
    const session = useSessionStore();
    session.$patch({ status: "ready", account: view });

    await session.saveProfile({
      nickname: " 亮马河快攻 ",
      chibi: view.chibi,
      card_bg: "gold",
    });

    expect(authApi.apiUpdateProfile).toHaveBeenCalledWith(
      expect.objectContaining({ nickname: "亮马河快攻" }), // 去首尾空格
    );
    expect(useUserStore().me.name).toBe("亮马河快攻");
  });

  it("昵称为空：本地拦截，不发请求", async () => {
    const session = useSessionStore();
    session.$patch({ status: "ready", account: view });
    await session.saveProfile({ nickname: "   " });
    expect(authApi.apiUpdateProfile).not.toHaveBeenCalled();
  });

  it("游客态：本地演示保存，不触网", async () => {
    const session = useSessionStore();
    await session.saveProfile({ nickname: "路人甲" });
    expect(authApi.apiUpdateProfile).not.toHaveBeenCalled();
    expect(useUserStore().me.name).toBe("路人甲");
    // 还原游客名，避免影响其他用例
    useUserStore().me.name = demo.name;
  });
});
