/* mpAuth（1.10 小程序微信钥匙编排）单测：静默换 code → mp 通道认人 → 三态就地消费。
   session store 与 pendingResume 用模块 mock（不落库不触网），ui store 走真实 pinia
   （signupThen/signupOccupiedPhone 的落位语义要真状态才测得出）；uni.login /
   getCurrentPages stub 换装（node 环境没有——mpAuth 整文件 #ifdef 在 vitest 里是活码）。 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";

const sessionMock = vi.hoisted(() => ({
  wechatLogin: vi.fn(),
  wechatRedeem: vi.fn(),
  account: null as { name: string } | null,
}));
const resumeMock = vi.hoisted(() => ({ runPendingResume: vi.fn() }));
const navMock = vi.hoisted(() => ({
  LOGIN_PATH: "/sub/mine/login",
  goMeet: vi.fn(),
}));

vi.mock("@/stores/session", () => ({
  useSessionStore: () => sessionMock,
}));
vi.mock("@/composables/pendingResume", () => resumeMock);
vi.mock("@/utils/nav", () => navMock);

import { ApiError } from "@/api/http";
import { TOAST_VISIBLE_MS, useUiStore } from "@/stores/ui";
import { mpLogin } from "@/utils/mpAuth";

/** 页面栈（landInPlace 宿主判定用）：let 可换装 */
let stack: Array<{ route?: string }> = [{ route: "pages/meet/meet" }];

const uniMock = {
  login: vi.fn(),
  navigateBack: vi.fn(),
  switchTab: vi.fn(),
  getStorageSync: vi.fn(() => ""),
};

const PENDING = { pendingJoin: { gameId: 9, bring: 0 } };

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
  stack = [{ route: "pages/meet/meet" }];
  sessionMock.account = null;
  uniMock.login.mockImplementation(
    (o: { success: (r: { code: string }) => void }) =>
      o.success({ code: "mp-code-1" }),
  );
  vi.stubGlobal("uni", uniMock);
  vi.stubGlobal("getCurrentPages", () => stack);
});

describe("mpLogin（小程序静默认人）", () => {
  it("ok 态：mp 通道认人、续办挂起动作、关弹层，不动页面栈", async () => {
    sessionMock.wechatLogin.mockResolvedValue({
      status: "ok",
      randomName: false,
    });
    const ui = useUiStore();
    const closeSpy = vi.spyOn(ui, "closeSheet");
    await mpLogin({ pending: PENDING });
    expect(sessionMock.wechatLogin).toHaveBeenCalledWith(
      "mp-code-1",
      expect.objectContaining({ source: "mp" }),
    );
    expect(resumeMock.runPendingResume).toHaveBeenCalledWith(PENDING);
    expect(closeSpy).toHaveBeenCalled();
    expect(uniMock.navigateBack).not.toHaveBeenCalled(); // 宿主非登录页：原地不动
  });

  it("created+随机名（无挂起动作）：立即报名字句，续办空快照", async () => {
    sessionMock.wechatLogin.mockResolvedValue({
      status: "created",
      randomName: true,
    });
    sessionMock.account = { name: "球友8421" };
    await mpLogin({ fast: true });
    expect(useUiStore().toastMsg).toBe("名单里你叫『球友8421』，随时可改");
    expect(resumeMock.runPendingResume).toHaveBeenCalledWith({});
  });

  it("created+随机名（有挂起动作）：名字句排队——动作句展示完再补报", async () => {
    vi.useFakeTimers();
    sessionMock.wechatLogin.mockResolvedValue({
      status: "created",
      randomName: true,
    });
    sessionMock.account = { name: "球友8421" };
    await mpLogin({ fast: true, pending: PENDING });
    expect(useUiStore().toastMsg).toBe(""); // 先让动作句说
    vi.advanceTimersByTime(TOAST_VISIBLE_MS + 200);
    expect(useUiStore().toastMsg).toBe("名单里你叫『球友8421』，随时可改");
    vi.useRealTimers();
  });

  it("unbound：落普通新人卡（from=action 非 wechat-return，4.4 裁决），不续办不关卡", async () => {
    sessionMock.wechatLogin.mockResolvedValue({
      status: "unbound",
      randomName: false,
    });
    const ui = useUiStore();
    await mpLogin({ pending: PENDING });
    expect(ui.signupCardFrom).toBe("action");
    expect(ui.sheet).toMatchObject({ ...PENDING, type: "signup-card" });
    expect(resumeMock.runPendingResume).not.toHaveBeenCalled();
  });

  it("wechat_off：toast 原句 + 降级信号落位（名片卡撤快进钮、落手填确定——退建号老路，4.11）", async () => {
    sessionMock.wechatLogin.mockRejectedValue(
      new ApiError("wechat_off", "微信登录即将开通 · 资质到位后点亮", 503),
    );
    const ui = useUiStore();
    await mpLogin({});
    expect(useUiStore().toastMsg).toBe("微信登录即将开通 · 资质到位后点亮");
    expect(ui.mpWechatOff).toBe(true);
  });

  it("phone_taken：重开卡直落占卡三出口——signupThen 之后落占卡信号（openSheet 会清）", async () => {
    sessionMock.wechatLogin.mockRejectedValue(
      new ApiError("phone_taken", "这个手机号已经有人用了", 409),
    );
    const ui = useUiStore();
    await mpLogin({ fast: true, phone: "13800001234", pending: PENDING });
    expect(ui.signupCardFrom).toBe("action");
    expect(ui.signupOccupiedPhone).toBe("13800001234");
    expect(ui.sheet).toMatchObject({ ...PENDING, type: "signup-card" });
  });

  it("in-flight 防连点（A2）：识别途中二次调用静默 return，只认第一次", async () => {
    let held: (r: { code: string }) => void = () => {};
    uniMock.login.mockImplementation(
      (o: { success: (r: { code: string }) => void }) => {
        held = o.success;
      },
    );
    sessionMock.wechatLogin.mockResolvedValue({
      status: "ok",
      randomName: false,
    });
    const first = mpLogin({ fast: true });
    await mpLogin({ fast: true }); // in-flight：立即返回不另发
    held({ code: "mp-code-1" });
    await first;
    expect(sessionMock.wechatLogin).toHaveBeenCalledTimes(1);
  });

  it("redeemPhone 支：走 wechatRedeem 占卡接管路（source=mp、草稿重建卡）、续办收尾", async () => {
    sessionMock.wechatRedeem.mockResolvedValue({ id: 7, name: "dave" });
    await mpLogin({ redeemPhone: "13800001111", pending: PENDING });
    expect(sessionMock.wechatRedeem).toHaveBeenCalledWith(
      "mp-code-1",
      "13800001111",
      undefined, // 本机无草稿 → 不带卡（明确填过的才覆盖，D5 同规）
      "mp",
    );
    expect(sessionMock.wechatLogin).not.toHaveBeenCalled();
    expect(useUiStore().toastMsg).toBe("已进入你的账号");
    expect(resumeMock.runPendingResume).toHaveBeenCalledWith(PENDING);
  });

  it("uni.login 失败：toast 重试句，不触认人门", async () => {
    uniMock.login.mockImplementation((o: { fail: () => void }) => o.fail());
    await mpLogin({});
    expect(useUiStore().toastMsg).toBe("微信登录没成功，再试一次");
    expect(sessionMock.wechatLogin).not.toHaveBeenCalled();
  });
});

describe("mpLogin 宿主收尾（宿主是登录页时回上一页）", () => {
  it("ok 态宿主登录页：navigateBack 回带来者（4.2 直进画面）", async () => {
    stack = [{ route: "pages/meet/meet" }, { route: "sub/mine/login" }];
    sessionMock.wechatLogin.mockResolvedValue({
      status: "ok",
      randomName: false,
    });
    await mpLogin({});
    expect(uniMock.navigateBack).toHaveBeenCalledTimes(1);
  });

  it("深链冷开登录页（栈无底）：兜约球页", async () => {
    stack = [{ route: "sub/mine/login" }];
    sessionMock.wechatLogin.mockResolvedValue({
      status: "ok",
      randomName: false,
    });
    await mpLogin({});
    expect(navMock.goMeet).toHaveBeenCalled();
    expect(uniMock.navigateBack).not.toHaveBeenCalled();
  });
});
