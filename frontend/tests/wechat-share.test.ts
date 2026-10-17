/* 微信分享卡（2.10 §5 验收/附录 A4）单测：cardDesc 六态锁句 + buildShareCard
   + registerWechatShare 登记。jweixin 注入零真网络——document/location/wx 全用
   vi.stubGlobal 假装（wechat.test.ts 先例）；api/auth 整体 mock。
   register 的模块级缓存（jweixin/config promise）按测试隔离：vi.resetModules
   + 动态 import 拿干净实例。 */
import { beforeEach, describe, expect, it, vi } from "vitest";

const authApi = vi.hoisted(() => ({ apiWechatJsapiSign: vi.fn() }));

vi.mock("@/api/auth", () => authApi);

import { buildShareCard, cardDesc } from "@/utils/wechatShare";

/* 远期日期：isoDay 走「M.DD 周X」支，不吃今天/明天相对支（那是 time.ts 自己的测试面） */
const FAR_ISO = "2099-06-15T19:30:00+08:00";

beforeEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("cardDesc（A4 六态文案）", () => {
  it("open/locked/live：日期 钟点 · 场地名 · 已报 N 人（与详情页画面同款格式）", () => {
    for (const status of ["open", "locked", "live"] as const) {
      expect(
        cardDesc({
          name: "夜球局",
          status,
          startAt: FAR_ISO,
          venueName: "某某球馆",
          heads: 6,
        }),
      ).toMatch(/^6\.15 周. 19:30 · 某某球馆 · 已报 6 人$/);
    }
  });
  it("场地名空：整段省掉，不留悬空隔点", () => {
    expect(
      cardDesc({
        name: "夜球局",
        status: "open",
        startAt: FAR_ISO,
        venueName: "",
        heads: 6,
      }),
    ).toMatch(/^6\.15 周. 19:30 · 已报 6 人$/);
  });
  it("heads 0 也照说「已报 0 人」，不另造句", () => {
    expect(
      cardDesc({
        name: "夜球局",
        status: "locked",
        startAt: FAR_ISO,
        venueName: "v",
        heads: 0,
      }),
    ).toMatch(/已报 0 人$/);
  });
  it("done 有场数：N 场对局 · 看看谁赢了", () => {
    expect(cardDesc({ name: "n", status: "done", matchCount: 3 })).toBe(
      "3 场对局 · 看看谁赢了",
    );
  });
  it("done 一场没打：只说已散场，不出「0 场对局」", () => {
    expect(cardDesc({ name: "n", status: "done", matchCount: 0 })).toBe(
      "已散场",
    );
  });
  it("done 拿不到场数：兜底句「已散场 · 看看谁赢了」", () => {
    expect(cardDesc({ name: "n", status: "done", matchCount: null })).toBe(
      "已散场 · 看看谁赢了",
    );
  });
  it("terminated/pending 同句「这局已终止」；cancelled「这局已撤销」", () => {
    expect(cardDesc({ name: "n", status: "terminated" })).toBe("这局已终止");
    expect(cardDesc({ name: "n", status: "pending" })).toBe("这局已终止");
    expect(cardDesc({ name: "n", status: "cancelled" })).toBe("这局已撤销");
  });
});

describe("buildShareCard（卡片四件）", () => {
  it("title=局名 · imgUrl=origin+/share-card.png · desc 由 cardDesc 拼 · link 透传", () => {
    vi.stubGlobal("location", {
      href: "https://x.y/#/pages/detail/detail?id=5",
      origin: "https://x.y",
    });
    const src = {
      name: "周六夜球",
      status: "open" as const,
      startAt: FAR_ISO,
      venueName: "某某球馆",
      heads: 6,
    };
    expect(
      buildShareCard(src, "https://x.y/#/pages/detail/detail?id=5"),
    ).toEqual({
      title: "周六夜球",
      desc: cardDesc(src),
      link: "https://x.y/#/pages/detail/detail?id=5",
      imgUrl: "https://x.y/share-card.png",
    });
  });
});

describe("registerWechatShare（登记编排）", () => {
  /** 模块级缓存按测试隔离：resetModules 后动态 import 拿干净实例 */
  async function fresh() {
    vi.resetModules();
    return import("@/utils/wechatShare");
  }

  /** 微信环境四件套：UA + 页面地址 + 假 document（appendChild 即触发 onload）+ 假 wx */
  function stubWechatEnv(wx: unknown): void {
    vi.stubGlobal("navigator", { userAgent: "MicroMessenger/8.0.49" });
    vi.stubGlobal("location", {
      href: "https://x.y/#/pages/detail/detail?id=5",
      origin: "https://x.y",
    });
    vi.stubGlobal("wx", wx);
    vi.stubGlobal("document", {
      createElement: () => ({ src: "", onload: null, onerror: null }),
      head: {
        appendChild: (s: { onload?: (() => void) | null }) => s.onload?.(),
      },
    });
  }

  const CARD = { title: "t", desc: "d", link: "l", imgUrl: "i" };

  it("非微信：直接返回——不注入 script、不发签名请求", async () => {
    vi.stubGlobal("navigator", { userAgent: "Mozilla/5.0 Chrome/129" });
    const createElement = vi.fn();
    vi.stubGlobal("document", {
      createElement,
      head: { appendChild: vi.fn() },
    });
    const { registerWechatShare } = await fresh();
    await registerWechatShare(() => CARD);
    expect(authApi.apiWechatJsapiSign).not.toHaveBeenCalled();
    expect(createElement).not.toHaveBeenCalled();
  });

  it("非微信：make 根本不执行（done 局微信外不白拉战报视图等原料）", async () => {
    vi.stubGlobal("navigator", { userAgent: "Mozilla/5.0 Chrome/129" });
    const { registerWechatShare } = await fresh();
    const make = vi.fn(() => CARD);
    await registerWechatShare(make);
    expect(make).not.toHaveBeenCalled();
  });

  it("微信内：注入 → 签名（href 去 hash）→ config → ready → 两个 update 全调到", async () => {
    const wx = {
      config: vi.fn(),
      ready: vi.fn((fn: () => void) => fn()),
      error: vi.fn(),
      updateAppMessageShareData: vi.fn(),
      updateTimelineShareData: vi.fn(),
    };
    stubWechatEnv(wx);
    authApi.apiWechatJsapiSign.mockResolvedValue({
      app_id: "wx1",
      timestamp: 123,
      nonce_str: "n",
      signature: "sig",
    });
    const { registerWechatShare } = await fresh();
    await registerWechatShare(() => CARD);
    expect(authApi.apiWechatJsapiSign).toHaveBeenCalledWith("https://x.y/");
    expect(wx.config).toHaveBeenCalledWith({
      appId: "wx1",
      timestamp: 123,
      nonceStr: "n",
      signature: "sig",
      jsApiList: ["updateAppMessageShareData", "updateTimelineShareData"],
    });
    expect(wx.updateAppMessageShareData).toHaveBeenCalledWith(CARD);
    // 朋友圈卡只带三件（朋友圈没有描述行，微信的规矩）
    expect(wx.updateTimelineShareData).toHaveBeenCalledWith({
      title: "t",
      link: "l",
      imgUrl: "i",
    });
  });

  it("签名接口抛错：静默收场不炸（卡退微信默认样），两 update 不调；失败不记指纹，修好后同卡照常重试", async () => {
    const wx = {
      config: vi.fn(),
      ready: vi.fn((fn: () => void) => fn()),
      error: vi.fn(),
      updateAppMessageShareData: vi.fn(),
      updateTimelineShareData: vi.fn(),
    };
    stubWechatEnv(wx);
    authApi.apiWechatJsapiSign.mockRejectedValue(new Error("wechat_off"));
    const { registerWechatShare } = await fresh();
    await expect(registerWechatShare(() => CARD)).resolves.toBeUndefined();
    expect(wx.updateAppMessageShareData).not.toHaveBeenCalled();
    expect(wx.updateTimelineShareData).not.toHaveBeenCalled();
    authApi.apiWechatJsapiSign.mockResolvedValue({
      app_id: "wx1",
      timestamp: 123,
      nonce_str: "n",
      signature: "sig",
    });
    await registerWechatShare(() => CARD);
    expect(wx.updateAppMessageShareData).toHaveBeenCalledTimes(1);
  });

  it("同一地址只签一次：换卡重登吃 config 缓存，签名零新请求、update 照常", async () => {
    const wx = {
      config: vi.fn(),
      ready: vi.fn((fn: () => void) => fn()),
      error: vi.fn(),
      updateAppMessageShareData: vi.fn(),
      updateTimelineShareData: vi.fn(),
    };
    stubWechatEnv(wx);
    authApi.apiWechatJsapiSign.mockResolvedValue({
      app_id: "wx1",
      timestamp: 123,
      nonce_str: "n",
      signature: "sig",
    });
    const { registerWechatShare } = await fresh();
    await registerWechatShare(() => CARD);
    await registerWechatShare(async () => ({ ...CARD, title: "t2" }));
    expect(authApi.apiWechatJsapiSign).toHaveBeenCalledTimes(1);
    expect(wx.updateAppMessageShareData).toHaveBeenCalledTimes(2);
  });

  it("同卡连登两次只登记一次；内容变了再登记（详情页双拉/现场页轮询不再重复打 SDK）", async () => {
    const wx = {
      config: vi.fn(),
      ready: vi.fn((fn: () => void) => fn()),
      error: vi.fn(),
      updateAppMessageShareData: vi.fn(),
      updateTimelineShareData: vi.fn(),
    };
    stubWechatEnv(wx);
    authApi.apiWechatJsapiSign.mockResolvedValue({
      app_id: "wx1",
      timestamp: 123,
      nonce_str: "n",
      signature: "sig",
    });
    const { registerWechatShare } = await fresh();
    await registerWechatShare(() => CARD);
    await registerWechatShare(() => CARD);
    expect(wx.updateAppMessageShareData).toHaveBeenCalledTimes(1);
    expect(wx.updateTimelineShareData).toHaveBeenCalledTimes(1);
    await registerWechatShare(async () => ({ ...CARD, desc: "换了卡面" }));
    expect(wx.updateAppMessageShareData).toHaveBeenCalledTimes(2);
  });

  it("旧意图慢回不盖新意图：先领号的卡 A 后回作废，只写卡 B；指纹记 B（再登 B 去重挡住、再登 A 能写入）", async () => {
    const wx = {
      config: vi.fn(),
      ready: vi.fn((fn: () => void) => fn()),
      error: vi.fn(),
      updateAppMessageShareData: vi.fn(),
      updateTimelineShareData: vi.fn(),
    };
    stubWechatEnv(wx);
    authApi.apiWechatJsapiSign.mockResolvedValue({
      app_id: "wx1",
      timestamp: 123,
      nonce_str: "n",
      signature: "sig",
    });
    const { registerWechatShare } = await fresh();
    const CARD_A = { ...CARD, title: "A" }; // 旧意图的卡（比如失败落兜底句的那次）
    const CARD_B = { ...CARD, title: "B" }; // 新意图的卡（成功拉到真句的那次）
    let releaseA!: (c: typeof CARD) => void;
    const slowA = new Promise<typeof CARD>((res) => {
      releaseA = res;
    });
    const p1 = registerWechatShare(() => slowA); // 先飞的：卡 A 慢回
    const p2 = registerWechatShare(async () => CARD_B); // 后到的：卡 B 即回
    await p2;
    releaseA(CARD_A); // 旧的那次这才后回
    await p1;
    expect(wx.updateAppMessageShareData).toHaveBeenCalledTimes(1);
    expect(wx.updateAppMessageShareData).toHaveBeenCalledWith(CARD_B);
    // 指纹账本记的是 B：B 再登被同内容去重挡住，A 再登要能正常写入
    await registerWechatShare(async () => CARD_B);
    expect(wx.updateAppMessageShareData).toHaveBeenCalledTimes(1);
    await registerWechatShare(async () => CARD_A);
    expect(wx.updateAppMessageShareData).toHaveBeenCalledTimes(2);
    expect(wx.updateAppMessageShareData).toHaveBeenLastCalledWith(CARD_A);
  });

  it("wx 全局被占成别的对象（无 config，uni-app H5 的 uni 别名情形）且无 jWeixin：静默不炸", async () => {
    stubWechatEnv({ uniAlias: true });
    const { registerWechatShare } = await fresh();
    await expect(registerWechatShare(() => CARD)).resolves.toBeUndefined();
    expect(authApi.apiWechatJsapiSign).not.toHaveBeenCalled();
  });

  it("wx 被占成 uni 别名（无 config）时优先取 jWeixin：照常登记", async () => {
    const jw = {
      config: vi.fn(),
      ready: vi.fn((fn: () => void) => fn()),
      error: vi.fn(),
      updateAppMessageShareData: vi.fn(),
      updateTimelineShareData: vi.fn(),
    };
    vi.stubGlobal("navigator", { userAgent: "MicroMessenger/8.0.49" });
    vi.stubGlobal("location", {
      href: "https://x.y/#/pages/detail/detail?id=5",
      origin: "https://x.y",
    });
    vi.stubGlobal("wx", { uniAlias: true });
    vi.stubGlobal("jWeixin", jw);
    vi.stubGlobal("document", {
      createElement: () => ({ src: "", onload: null, onerror: null }),
      head: {
        appendChild: (s: { onload?: (() => void) | null }) => s.onload?.(),
      },
    });
    authApi.apiWechatJsapiSign.mockResolvedValue({
      app_id: "wx1",
      timestamp: 123,
      nonce_str: "n",
      signature: "sig",
    });
    const { registerWechatShare } = await fresh();
    await registerWechatShare(() => CARD);
    expect(jw.updateAppMessageShareData).toHaveBeenCalledWith(CARD);
  });
});
