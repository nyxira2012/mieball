import { beforeEach, describe, expect, it, vi } from "vitest";
import { shareLink } from "@/utils/share";

/* shareLink（2.6/3.2 分享降级单一源）纯工具测试：clipboard 模块整体 mock
   （copyWithToast 内部走 uni，node 环境没有）；navigator 用 vi.stubGlobal 换装。 */
const clipboard = vi.hoisted(() => ({ copyWithToast: vi.fn() }));

vi.mock("@/utils/clipboard", () => clipboard);

beforeEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

const abortError = Object.assign(new Error("用户取消"), { name: "AbortError" });

describe("shareLink（分享分层：系统面板优先，复制兜底）", () => {
  it("navigator.share 在：直走系统面板，参数透传，不走复制", async () => {
    const share = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { share });
    await shareLink("https://x.y/recap?id=1", "周末球局战报", "下午 12 场");
    expect(share).toHaveBeenCalledTimes(1);
    expect(share).toHaveBeenCalledWith({
      title: "周末球局战报",
      text: "下午 12 场",
      url: "https://x.y/recap?id=1",
    });
    expect(clipboard.copyWithToast).not.toHaveBeenCalled();
  });

  it("text 缺省：share 只带 title/url", async () => {
    const share = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { share });
    await shareLink("https://x.y/detail?id=9", "球局详情");
    expect(share).toHaveBeenCalledWith({
      title: "球局详情",
      text: undefined,
      url: "https://x.y/detail?id=9",
    });
  });

  it("share 拒绝 AbortError：用户取消——静默收场，不走复制、不抛错", async () => {
    vi.stubGlobal("navigator", {
      share: vi.fn().mockRejectedValue(abortError),
    });
    await expect(shareLink("https://x.y/r?id=1", "t")).resolves.toBeUndefined();
    expect(clipboard.copyWithToast).not.toHaveBeenCalled();
  });

  it("share 拒绝非取消错误：降级复制链接（默认句带「访客可看」知情小字）", async () => {
    vi.stubGlobal("navigator", {
      share: vi.fn().mockRejectedValue(new TypeError("不在支持的环境")),
    });
    await shareLink("https://x.y/r?id=1", "t");
    expect(clipboard.copyWithToast).toHaveBeenCalledWith(
      "https://x.y/r?id=1",
      "链接已复制 · 访客可看",
    );
  });

  it("无 navigator.share：直接复制兜底（默认句同上）", async () => {
    vi.stubGlobal("navigator", {});
    await shareLink("https://x.y/r?id=1", "t");
    expect(clipboard.copyWithToast).toHaveBeenCalledTimes(1);
    expect(clipboard.copyWithToast).toHaveBeenCalledWith(
      "https://x.y/r?id=1",
      "链接已复制 · 访客可看",
    );
  });

  it("copyMsg 定制：仍可换兜底句（2026-10-12 三处统一后默认即知情句，定制口留存）", async () => {
    vi.stubGlobal("navigator", {});
    await shareLink(
      "https://x.y/detail?id=1",
      "球局详情",
      undefined,
      "链接已复制 · 去微信群里粘贴",
    );
    expect(clipboard.copyWithToast).toHaveBeenCalledWith(
      "https://x.y/detail?id=1",
      "链接已复制 · 去微信群里粘贴",
    );
  });
});
