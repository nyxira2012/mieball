/* 沙盒 store 编排锁（2.7 批2）：模式进出/卡标记两粒/NPC 定时器清理/本地记分到分
   开窗/结算编排推进。真局 live store 不涉、零 API——storage 用内存 Map stub 掉
   uni 全局（黑匣子测试同惯例），node 环境可跑。每例全新 pinia + 假定时器。 */
import { afterAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import type { SandState } from "@/sandbox/engine";

const storage = new Map<string, unknown>();
vi.stubGlobal("uni", {
  getStorageSync: (k: string) => (storage.has(k) ? storage.get(k) : ""),
  setStorageSync: (k: string, v: unknown) => void storage.set(k, v),
});

afterAll(() => vi.unstubAllGlobals());

beforeEach(() => {
  vi.resetModules();
  setActivePinia(createPinia());
  storage.clear();
  vi.useFakeTimers();
});

async function load() {
  const mod = await import("@/stores/sandbox");
  return mod.useSandboxStore();
}

/** 候场队名（按队序） */
const qNames = (s: SandState) =>
  s.queue.map((id) => s.players.find((p) => p.id === id)!.name);

describe("进卡/退出/重放（§4.1/§4.5）", () => {
  it("enter('participate')：mode/state/stepIdx=0/步进表首句/卡标记即落", async () => {
    const h = await load();
    h.enter("participate");
    expect(h.mode).toBe("participate");
    expect(h.state).not.toBeNull();
    expect(qNames(h.state!)).toEqual(["阿豪", "老周"]); // 幕一：阿豪老周在等
    expect(h.stepIdx).toBe(0);
    expect(h.step?.text).toBe("这局是示例——点『我到了』，你也进场");
    expect(h.doneCards).toEqual({ participate: true, organize: false }); // 进过即落
  });

  it("exit：mode 回 pick、局面散、定时器清光（NPC 线索不再触发）", async () => {
    const h = await load();
    h.enter("organize"); // enter 线索：球球 +2000ms
    expect(vi.getTimerCount()).toBeGreaterThan(0);
    h.exit();
    expect(h.mode).toBe("pick");
    expect(h.state).toBeNull();
    expect(vi.getTimerCount()).toBe(0);
    expect(() => vi.advanceTimersByTime(5000)).not.toThrow(); // 散场后到点的旧定时器无局可落
    expect(h.state).toBeNull();
    expect(h.doneCards.organize).toBe(true); // 退出不撤销卡标记（进过即落）
  });

  it("重放：exit 再进=全新开局（步进指针回零、局面复位）；随便逛逛不落卡标记", async () => {
    const h = await load();
    h.enter("participate");
    h.checkInMe();
    expect(h.stepIdx).toBe(1);
    h.exit();
    h.enter("participate");
    expect(h.stepIdx).toBe(0);
    expect(qNames(h.state!)).toEqual(["阿豪", "老周"]);
    expect(h.state!.players.find((p) => p.you)!.check).toBe("none"); // 你未签到（重放）

    h.enter("freeroam"); // 随便逛逛（§4.5）：不带引导
    expect(h.step).toBeNull();
    expect(h.doneCards).toEqual({ participate: true, organize: false }); // 本机只落两粒
  });
});

describe("本地记分与结算编排（§4.2 幕三/幕四）", () => {
  it("到分开窗→confirmSettle：先上的先下（候场[阿豪,老周]）、关窗清账、步进按判据推进", async () => {
    const h = await load();
    h.enter("participate");
    h.checkInMe(); // 幕一：候场出现你 → 第 1 步翻面
    expect(h.stepIdx).toBe(1);
    vi.advanceTimersByTime(2000); // 球球到（第 4 人）自动开赛、你上场 → 第 2 步翻面
    expect(h.stepIdx).toBe(2);
    expect(
      h.state!.courts[0]!.b.map(
        (id) => h.state!.players.find((p) => p.id === id)!.name,
      ),
    ).toEqual(["你", "球球"]);
    h.point(1, "b"); // 你队记 1 分 → 第 3 步翻面；武装老金小鹿线索
    expect(h.stepIdx).toBe(3);
    vi.advanceTimersByTime(600); // 老金到
    vi.advanceTimersByTime(2000); // 小鹿随后到
    expect(qNames(h.state!)).toEqual(["老金", "小鹿"]);

    for (let i = 0; i < 11; i++) h.point(1, "b"); // 打到 11:0（净胜≥2）→ 自动开窗
    expect(h.settleWindow).toEqual({ courtNo: 1 });
    h.confirmSettle(1, "b", 11, 0);
    expect(h.settleWindow).toBeNull(); // 关窗
    expect(h.localScores[1]).toEqual({ sa: 0, sb: 0, history: [] }); // 清账，下一场 0:0
    expect(qNames(h.state!)).toEqual(["阿豪", "老周"]); // 第一场结算：老金小鹿顶坑
    expect(h.stepIdx).toBe(4); // 第 4 步翻面；第 5 步（设歇/第二场结算）等着
    expect(h.step?.text).toContain("先上的先下——你不下接着打");
  });

  it("undoPoint/clearScore 撤得动；窗没开 confirmSettle 不落（幂等闸同 live）", async () => {
    const h = await load();
    h.enter("participate");
    h.checkInMe();
    vi.advanceTimersByTime(2000);
    h.point(1, "b");
    h.point(1, "b");
    h.undoPoint(1);
    expect(h.localScores[1]).toEqual({ sa: 0, sb: 1, history: ["b"] });
    h.clearScore(1);
    expect(h.localScores[1]).toEqual({ sa: 0, sb: 0, history: [] });
    h.confirmSettle(1, "b", 11, 0); // 窗没开着：什么都不发生
    expect(h.state!.matches.length).toBe(0);
    expect(h.stepIdx).toBe(3); // 没有判据推进（记 1 分那面已翻过）
  });
});
