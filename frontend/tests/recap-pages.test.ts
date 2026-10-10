import { describe, expect, it } from "vitest";
import { recapHint } from "@/utils/recap";

/* 2.6 门牌页面层（§4.1/4.3）：提示行按「我是不是这局的人」两分支（判定=后端 live view
   的 is_my_game 定值，前端不自判）。LiveRecap.vue 是纯渲染组件，vitest 无 @vue/test-utils
   挂不了 .vue——文案分支抽成 utils/recap 纯函数为测；双钮 emit 与页面编排层
   （收摊/返回/分享）同样吃这个退化，走浏览器走查覆盖。 */
describe("recapHint（战报提示行：isMyGame 两分支，文案单一源）", () => {
  it("这局的人：指路 我的-打球记录（赛后回看入口）", () => {
    expect(recapHint(true)).toBe("球局已结束 · 赛后可在 我的-打球记录 翻看");
  });

  it("路人/未登录一律：中性句，不指一条走不通的路", () => {
    expect(recapHint(false)).toBe("球局已结束 · 战报仅供回看");
  });
});
