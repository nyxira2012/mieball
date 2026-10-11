import { describe, expect, it, vi } from "vitest";
import { MEME_FALLBACK, MEMES, pickMeme } from "@/utils/memes";

/* 梗句封面单一配置（utils/memes）：单人梗填一名，返回 text+name 供名字上色；
   随机性用性质断言，确定性用 mock 锁 */

const POOL = ["老周", "小雨", "板鸭"];

describe("pickMeme（随机单人梗：填一个名，name 供染色）", () => {
  it("性质：name 出自名单且在 text 里，text 无残留槽位", () => {
    for (let i = 0; i < 80; i++) {
      const r = pickMeme(POOL);
      expect(r.text).not.toContain("{a}");
      expect(POOL).toContain(r.name);
      expect(r.text).toContain(r.name!);
    }
  });

  it("mock 随机锁确定性：首模板+首名", () => {
    const rnd = vi.spyOn(Math, "random").mockReturnValue(0);
    try {
      expect(pickMeme(POOL)).toEqual({
        text: "真是一场酣畅淋漓的战斗呢，老周大人",
        name: "老周",
      });
    } finally {
      rnd.mockRestore();
    }
  });

  it("空名单/全空白名：兜底句 name=null；重名去重不影响", () => {
    expect(pickMeme([])).toEqual({ text: MEME_FALLBACK, name: null });
    expect(pickMeme(["", "  "])).toEqual({ text: MEME_FALLBACK, name: null });
    expect(pickMeme(["老周", "老周"]).name).toBe("老周");
  });

  it("模板表形状：每条恰一个 {a} 槽位", () => {
    for (const t of MEMES) expect(t.match(/\{a\}/g)).toHaveLength(1);
  });
});
