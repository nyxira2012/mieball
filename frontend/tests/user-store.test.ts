/* user store 身份换装单测：accountToUser 装扮三键透传（snake→camel 单点在
   user store，经 applyAccount 入口测——登录/改名片/补绑四路共用它换装）与
   退出回落不残留上一具身份的形象。API 不触（applyAccount 是纯换装动作）。 */
import { beforeEach, describe, expect, it } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import type { AccountView } from "@/api/auth";
import { useUserStore } from "@/stores/user";

const dressedView: AccountView = {
  id: 42,
  name: "海淀反手王",
  avatar: "a-p3",
  avatar_url: "/cosmetics/a-p3.png",
  back: "b-t45",
  deactivated: false,
  has_password: false,
};

beforeEach(() => {
  setActivePinia(createPinia());
});

describe("applyAccount 装扮三键透传（登录换装全站读 me）", () => {
  it("册子编号头像：avatar/avatarUrl/back 三键原样落 me（snake→camel 单点）", () => {
    const user = useUserStore();
    user.applyAccount(dressedView);
    expect(user.me.avatar).toBe("a-p3");
    expect(user.me.avatarUrl).toBe("/cosmetics/a-p3.png");
    expect(user.me.back).toBe("b-t45");
  });

  it("微信头像：穿戴值与解析图（授权时记下的原图）如数透传", () => {
    const user = useUserStore();
    user.applyAccount({
      ...dressedView,
      avatar: "wechat",
      avatar_url: "https://wx.example/head.jpg",
    });
    expect(user.me.avatar).toBe("wechat");
    expect(user.me.avatarUrl).toBe("https://wx.example/head.jpg");
  });
});

describe("resetGuest 回落不残留（退出/注销后不当访客穿着旧形象）", () => {
  it("退出后装扮三键清空：头像位回落默认公共款、卡背素卡", () => {
    const user = useUserStore();
    user.applyAccount(dressedView);
    user.resetGuest();
    expect(user.me.avatar).toBeUndefined();
    expect(user.me.avatarUrl).toBeUndefined();
    expect(user.me.back).toBeUndefined();
    expect(user.me.id).toBe(0); // 同回落游客占位
  });
});
