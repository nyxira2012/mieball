/* 沙盒组织卡十步数字账全程锁（2.7 批4）——照规格 §7 A4 组织卡数字账经 store 编排
   逐条断言（组件动作全走 store：抽屉族/权限闸/编排动作单一真值在这，与真局抽屉同路
   ——engine 层的同一份账已锁在 sandbox-engine.test.ts，这里锁的是「组件动作 → store
   编排 → 步进翻面」全程）。另锁：权限随卡走（§4.4）、freeroam 快照与全功能（A2）。
   真局 live store 不涉、零 API——uni 全局 stub 掉（黑匣子测试同惯例），node 环境可跑。
   每例全新 pinia + 假定时器。 */
import { afterAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import type { SandState } from "@/sandbox/engine";
import { ORG_FINAL_BILL } from "@/sandbox/data";

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

const idOf = (s: SandState, name: string) =>
  s.players.find((p) => p.name === name)!.id;
const qNames = (s: SandState) =>
  s.queue.map((i) => s.players.find((p) => p.id === i)!.name);
const sideNames = (s: SandState, no: number, side: "a" | "b") =>
  s.courts
    .find((c) => c.no === no)!
    [side].map((i) => s.players.find((p) => p.id === i)!.name);

describe("组织卡十步全程（A4 数字账 × store 编排）", () => {
  it("开场→自动开赛→代办→带访客→改规→换人→封管理员→加片→两场直录→散场账单", async () => {
    const h = await load();
    h.enter("organize");
    expect(h.stepIdx).toBe(0);
    expect(h.isFull).toBe(true); // 组织卡=全权
    const s = h.state!;

    vi.advanceTimersByTime(2000 + 800); // 球球到（第 4 人）自动开赛、老金紧随
    expect(h.stepIdx).toBe(2); // 第 1、2 步判据同拍级联（开赛不用谁按）
    expect(sideNames(s, 1, "a")).toEqual(["老周", "小敏"]);
    expect(sideNames(s, 1, "b")).toEqual(["你", "球球"]);
    expect(s.feed[0]).toBe("人够 4 · 自动开赛");

    // 第三步：凯文迟到句滚出 → ＋到场开代办抽屉 → 【到场】签入队尾
    vi.advanceTimersByTime(1); // 凯文迟到句是 0 延时线索（下一拍滚出；假定时器 0 步进不触发）
    expect(s.feed[0]).toBe("凯文 · 迟到了");
    h.tapCheckin();
    expect(h.sheetKind).toBe("checkin");
    h.checkInRow(idOf(s, "凯文"));
    expect(h.stepIdx).toBe(3);
    expect(qNames(s)).toEqual(["老金", "凯文"]);

    // 第四步：同一抽屉「带访客」（预填「朋友」），徽章入候场
    h.bringGuest("朋友");
    expect(h.stepIdx).toBe(4);
    expect(h.sheetKind).toBe("checkin"); // 同一抽屉（§4.3 第四步）
    const guest = s.players.find((p) => p.guest)!;
    expect(guest.name).toBe("朋友");
    expect(qNames(s)).toEqual(["老金", "凯文", "朋友"]);
    h.closeSheet();

    // 第五步：规则抽屉改分制 15（提示句照真局）
    h.openRules();
    h.setScoring(15);
    expect(h.stepIdx).toBe(5);
    expect(s.scoring).toBe(15);
    expect(s.courts[0]!.scoring).toBe(11); // 在打片照旧（下一场起生效）
    h.closeSheet();

    // 第六步：点场上头像换人（球球 ↔ 老金），落子即关抽屉
    h.openPerson(idOf(s, "球球"));
    expect(h.sheetKind).toBe("person");
    h.setSwapMode(true);
    h.swapWith(idOf(s, "老金"));
    expect(h.sheetKind).toBeNull();
    expect(sideNames(s, 1, "b")).toEqual(["你", "老金"]);
    expect(h.stepIdx).toBe(6);

    // 第七步：点候场里的凯文封管理员（带徽章）；小鹿随后到
    h.openPerson(idOf(s, "凯文"));
    h.setAdmin(idOf(s, "凯文"));
    expect(s.players.find((p) => p.name === "凯文")!.admin).toBe(true);
    expect(h.stepIdx).toBe(7);
    vi.advanceTimersByTime(800); // admin-set 线索：小鹿到
    expect(qNames(s)).toEqual(["凯文", "朋友", "球球", "小鹿"]); // 攒到 4 人、无空片不开

    // 第八步：顶条场地格填 2 → 加片即自动开出第二片（含访客、15 分制）
    expect(h.spot).toBe("courts-cell"); // 步进表锚顶条场地格
    expect(h.courtsInput("2")).toBe(true);
    expect(s.courtsCount).toBe(2);
    expect(sideNames(s, 2, "a")).toEqual(["凯文", "朋友"]);
    expect(sideNames(s, 2, "b")).toEqual(["球球", "小鹿"]);
    expect(s.courts[1]!.scoring).toBe(15);
    expect(qNames(s)).toEqual([]);
    expect(h.stepIdx).toBe(8);

    // 第九步：两片各「本场完成＋直录」（15 分制）；无人候场=原班续场
    expect(h.spot).toBe("quick-settle");
    h.openSettle(1);
    expect(h.settleWindow).toEqual({ courtNo: 1 });
    h.confirmSettle(1, "a", 15, 9);
    expect(sideNames(s, 1, "a")).toEqual(["老周", "小敏"]); // 刚下的转身又顶回来
    expect(h.stepIdx).toBe(8); // 两片各一次才翻面
    h.openSettle(2);
    h.confirmSettle(2, "b", 7, 15);
    expect(h.stepIdx).toBe(9);
    expect(s.matches.length).toBe(2);
    expect(h.stepText).toBe("都打完了——散场收工，看看费用怎么摊");
    expect(h.spot).toBe("sweep-entry");

    // 第十条：散场——残局两场 0:0 续场，全部取消后二次确认放行
    h.openSweep();
    expect(h.sheetKind).toBe("sweep");
    expect(h.endGame()).toBe(false); // 残局不清完不放行
    h.sweepCancelAll();
    expect(qNames(s)).toEqual([
      "老周",
      "小敏",
      "你",
      "老金",
      "球球",
      "凯文",
      "小鹿",
      "朋友",
    ]); // 8 人=收工账单 heads
    expect(h.endGame()).toBe(true);
    expect(s.ended).toBe(true);
    expect(h.sheetKind).toBe("sweep"); // 账单亮相做在本抽屉的 ended 态
    expect(h.stepText).toBe("组织者的事就这些——去发个真局 ▸"); // 收尾句（4.3）
    expect(h.spot).toBeNull(); // 收尾出口是整行，光圈从散场钮上熄掉
    vi.advanceTimersByTime(5000); // 收尾几秒后收成小尾巴
    expect(h.step).toBeNull();

    // 账单写死数（§6 界面一个数不自算——组件只读这份）
    expect(ORG_FINAL_BILL).toMatchObject({
      feeTotal: 240,
      heads: 8,
      perHead: 30,
      myShare: 60,
    });
  });

  it("围栏：场地格只增不减、非数字回退；抽屉闸把访客封管理员与重复封挡住", async () => {
    const h = await load();
    h.enter("organize");
    vi.advanceTimersByTime(2000 + 800);
    const s = h.state!;
    expect(h.courtsInput("abc")).toBe(false); // 非数字：失败回退
    expect(h.courtsInput("0")).toBe(false); // 越界
    expect(h.courtsInput("9")).toBe(true); // 解析 1~9
    expect(s.courtsCount).toBe(9);
    expect(h.courtsInput("2")).toBe(false); // 只增不减（减片教学不教）

    // 带访客后再点人抽屉：访客无「设为管理员」的份（store 闸兜底）
    h.bringGuest("阿花");
    h.openPerson(idOf(s, "阿花"));
    h.setAdmin(idOf(s, "阿花"));
    expect(s.players.find((p) => p.name === "阿花")!.admin).toBe(false);
  });
});

describe("权限随卡走（§4.4）", () => {
  it("参与卡：给别人设歇被拦+提示、自己可歇；「本场完成」不开（全权本事）", async () => {
    const h = await load();
    const { useUiStore } = await import("@/stores/ui");
    const ui = useUiStore();
    h.enter("participate");
    h.checkInMe();
    vi.advanceTimersByTime(2000); // 自动开赛 阿豪·老周 vs 你·球球
    const s = h.state!;

    h.openPerson(idOf(s, "阿豪"));
    h.tempo(idOf(s, "阿豪"), "skip"); // 给别人：普通球员如实拦下
    expect(s.players.find((p) => p.name === "阿豪")!.skip).toBe(0);
    expect(ui.toastMsg).toBe("请找组织者或管理员");
    h.tempo(idOf(s, "你"), "skip"); // 自己：随时可（幕五的教学点）
    expect(s.players.find((p) => p.you)!.skip).toBe(1);
    h.openSettle(1); // 组件不渲染这颗钮，store 闸兜底
    expect(h.settleWindow).toBeNull();
    h.exit();

    h.enter("organize");
    vi.advanceTimersByTime(2000 + 800);
    vi.advanceTimersByTime(1); // 凯文迟到句（0 延时线索，0 步进不触发）
    const zh = h.state!.players.find((p) => p.name === "老周")!;
    h.openPerson(zh.id);
    h.tempo(zh.id, "skip"); // 组织卡全权：给别人可用
    expect(zh.skip).toBe(1);
    expect(h.stepIdx).toBe(2); // 无关动作不抢翻步进（第三步代办等着）
  });
});

describe("freeroam 随便逛逛（§4.5/A2）", () => {
  it("快照：第二场 7:5、老金小鹿 vs 你球球、阿豪老周候场；无引导；全功能照常轮转", async () => {
    const h = await load();
    const { useUiStore } = await import("@/stores/ui");
    const ui = useUiStore();
    h.enter("freeroam");
    const s = h.state!;
    expect(sideNames(s, 1, "a")).toEqual(["老金", "小鹿"]);
    expect(sideNames(s, 1, "b")).toEqual(["你", "球球"]);
    expect(qNames(s)).toEqual(["阿豪", "老周"]);
    expect(h.localScores[1]).toMatchObject({ sa: 7, sb: 5 });
    expect(h.step).toBeNull(); // 提示槽无步进（组件只画「重新来一遍 ▸」）

    h.tapCheckin(); // ＋到场：普通球员如实拦下
    expect(h.sheetKind).toBeNull();
    expect(ui.toastMsg).toBe("请找组织者或管理员");
    h.openRules(); // 规则抽屉照常可开（抽屉内只读）
    expect(h.sheetKind).toBe("rules");
    h.closeSheet();

    for (let i = 0; i < 6; i++) h.point(1, "b"); // 7:5 → 7:11 到分自动开窗（b=你球球）
    expect(h.settleWindow).toEqual({ courtNo: 1 });
    h.confirmSettle(1, "b", 7, 11);
    // 先上的先下：你球球连打两场下场入队尾，阿豪老周顶坑
    expect(sideNames(s, 1, "b")).toEqual(["阿豪", "老周"]);
    expect(qNames(s)).toEqual(["你", "球球"]);

    h.restart(); // 「重新来一遍 ▸」= 同快照重放
    expect(h.localScores[1]).toMatchObject({ sa: 7, sb: 5 });
    expect(sideNames(h.state!, 1, "a")).toEqual(["老金", "小鹿"]);
  });
});
