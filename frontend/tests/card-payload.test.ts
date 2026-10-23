/* 注册卡名片载荷（cardPayloadOf）单测：公共头像下标→编号映射与
   「明确填过的才置位」旗标——SignupSheet 表单路与 login.vue 草稿重建路
   共用这一份，两处漂移在此钉死。 */
import { describe, expect, it } from "vitest";
import { cardPayloadOf } from "@/api/auth";
import { PUBLIC_AVATARS } from "@/api/dict";

describe("cardPayloadOf（手填路/微信回跳重建路单一源）", () => {
  it("没挑头像：avatar 不带（后端兜默认第一款），昵称空不带旗标", () => {
    expect(cardPayloadOf("13800001111", "", null)).toEqual({
      phone: "13800001111",
      nickname: "",
      nickname_set: false,
      avatar: undefined,
    });
  });

  it("挑了第 3 款（下标 2）→ avatar=a-p3；昵称填了（空白不算）置位", () => {
    expect(cardPayloadOf("13800001111", "海淀反手王", 2)).toEqual({
      phone: "13800001111",
      nickname: "海淀反手王",
      nickname_set: true,
      avatar: "a-p3",
    });
    // 昵称只有空白 → 没填过
    expect(cardPayloadOf("13800001111", "   ", 0).nickname_set).toBe(false);
  });

  it("下标全域恰 6 款公共头像（与后端册子公共款同宽）", () => {
    const picked = PUBLIC_AVATARS.map(
      (_, i) => cardPayloadOf("p", "n", i).avatar,
    );
    expect(picked).toEqual(["a-p1", "a-p2", "a-p3", "a-p4", "a-p5", "a-p6"]);
  });

  it("注册卡六选一不含默认款（不挑才得默认）", () => {
    // 后端兜 DEFAULT_AVATAR=g-00（后端半边 test_cosmetics_catalog
    // 已锁），默认款不进注册卡编号组——挑与不挑语义分开，两侧不许悄悄并回
    expect(PUBLIC_AVATARS).not.toContain("g-00");
  });
});
