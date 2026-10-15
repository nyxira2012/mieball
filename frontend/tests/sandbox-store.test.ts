/* 沙盒 store 编排锁（2.7 批2）：模式进出/NPC 定时器清理/本地记分到分
   开窗/结算编排推进。真局 live store 不涉、零 API。每例全新 pinia + 假定时器。 */
import { afterAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import type { SandState } from "@/sandbox/engine";
import { ELO_PREVIEW } from "@/sandbox/data";

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
  it("enter('participate')：mode/state/stepIdx=0/步进表首句", async () => {
    const h = await load();
    h.enter("participate");
    expect(h.mode).toBe("participate");
    expect(h.state).not.toBeNull();
    expect(qNames(h.state!)).toEqual(["阿豪", "老周"]); // 幕一：阿豪老周在等
    expect(h.stepIdx).toBe(0);
    expect(h.step?.text).toBe("这局是示例——点『我到了』，你也进场");
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
  });

  it("重放：exit 再进=全新开局（步进指针回零、局面复位）", async () => {
    const h = await load();
    h.enter("participate");
    h.checkInMe();
    expect(h.stepIdx).toBe(1);
    h.exit();
    h.enter("participate");
    expect(h.stepIdx).toBe(0);
    expect(qNames(h.state!)).toEqual(["阿豪", "老周"]);
    expect(h.state!.players.find((p) => p.you)!.check).toBe("none"); // 你未签到（重放）
  });
});

describe("本地记分与结算编排（§4.2 幕三/幕四）", () => {
  it("到分开窗→confirmSettle：先上的先下（候场[阿豪,老周]）、关窗清账、步进按判据推进", async () => {
    const h = await load();
    h.enter("participate");
    h.checkInMe(); // 幕一：候场出现你 → 第 1 步翻面
    expect(h.stepIdx).toBe(1);
    vi.advanceTimersByTime(2000); // 球球到（第 4 人）自动开赛、你上场 → 亮码步等着
    expect(h.stepIdx).toBe(2);
    expect(h.step?.spot).toBe("qr-btn"); // v2.8 亮码收人步：光圈指顶条二维码钮
    expect(h.stepText).toContain("二维码亮码");
    h.qrShown(); // 点开示意浮层 → 亮码步翻面（判据只认点击事件，状态跳不了）
    expect(h.stepIdx).toBe(3);
    expect(
      h.state!.courts[0]!.b.map(
        (id) => h.state!.players.find((p) => p.id === id)!.name,
      ),
    ).toEqual(["你", "球球"]);
    h.point(1, "b"); // 你队记 1 分 → 第 4 步翻面；武装老金小鹿线索
    expect(h.stepIdx).toBe(4);
    vi.advanceTimersByTime(600); // 老金到
    vi.advanceTimersByTime(2000); // 小鹿随后到
    expect(qNames(h.state!)).toEqual(["老金", "小鹿"]);

    for (let i = 0; i < 11; i++) h.point(1, "b"); // 打到 11:0（净胜≥2）→ 自动开窗
    expect(h.settleWindow).toEqual({ courtNo: 1 });
    h.confirmSettle(1, "b", 11, 0);
    expect(h.settleWindow).toBeNull(); // 关窗
    expect(h.localScores[1]).toEqual({ sa: 0, sb: 0, history: [] }); // 清账，下一场 0:0
    expect(qNames(h.state!)).toEqual(["阿豪", "老周"]); // 第一场结算：老金小鹿顶坑
    expect(h.stepIdx).toBe(5); // 第 5 步翻面；第 6 步（设歇/第二场结算）等着
    expect(h.step?.text).toContain("先上的先下——你不下接着打");
  });

  it("undoPoint/clearScore 撤得动；窗没开 confirmSettle 不落（幂等闸同 live）", async () => {
    const h = await load();
    h.enter("participate");
    h.checkInMe();
    vi.advanceTimersByTime(2000);
    h.qrShown(); // 亮码步过（记分步前的一步）
    h.point(1, "b");
    h.point(1, "b");
    h.undoPoint(1);
    expect(h.localScores[1]).toEqual({ sa: 0, sb: 1, history: ["b"] });
    h.clearScore(1);
    expect(h.localScores[1]).toEqual({ sa: 0, sb: 0, history: [] });
    h.confirmSettle(1, "b", 11, 0); // 窗没开着：什么都不发生
    expect(h.state!.matches.length).toBe(0);
    expect(h.stepIdx).toBe(4); // 没有判据推进（记 1 分那面已翻过）
  });

  it("涨跌预览纯查表（§6 界面一个数不自算）：结算全链不碰 ELO_PREVIEW，改比分预览值不动", async () => {
    // 预览组装在 SandboxSettle 组件内按名查这张表——store 层锁得住的真源是
    // 「表纯」：记分/直录写回/确认结算全链走完，表不被改写、查表值逐字定格，
    // 涨跌预览就与比分无关（形状覆盖与量级另锁在 sandbox-engine.test.ts）
    const h = await load();
    h.enter("participate");
    h.checkInMe();
    vi.advanceTimersByTime(2000); // 球球到（第 4 人）自动开赛
    for (let i = 0; i < 11; i++) h.point(1, "b"); // 打到 11:0 自动开窗
    expect(h.settleWindow).toEqual({ courtNo: 1 });
    const frozen = JSON.parse(JSON.stringify(ELO_PREVIEW)); // 开窗时刻快照
    h.localScores[1] = { sa: 15, sb: 13, history: [] }; // 窗内直录改比分（writeBack 同路）
    h.confirmSettle(1, "b", 15, 13);
    expect(ELO_PREVIEW).toEqual(frozen); // 全链没碰表：涨跌与比分无关
    expect(ELO_PREVIEW["你"]).toEqual({ win: 21, lose: -13 }); // 查表值逐字定格
    expect(ELO_PREVIEW["朋友"]).toEqual({ win: 20, lose: -12 }); // 访客行也有展示值
  });
});

describe("参与卡七幕串联（§4.2：幕四老金小鹿条件触发→幕七收尾 final 行）", () => {
  /** 从进卡推到「第一次结算确认完」（幕五完）：返回 store 与「你」的行 */
  async function toFirstSettle() {
    const h = await load();
    h.enter("participate");
    h.checkInMe(); // 幕一：候场出现你
    vi.advanceTimersByTime(2000); // 幕二：球球到（第 4 人）自动开赛、你上场
    h.qrShown(); // 幕三：点开二维码示意浮层（亮码收人）
    h.point(1, "b"); // 幕四：你记 1 分（武装老金小鹿条件线索）
    vi.advanceTimersByTime(600 + 2000); // 老金、小鹿前后脚到
    expect(qNames(h.state!)).toEqual(["老金", "小鹿"]); // 不弹提示、不打断
    for (let i = 0; i < 11; i++) h.point(1, "b"); // 幕四：打到 11:0 自动开窗
    h.confirmSettle(1, "b", 11, 0);
    return { h, you: h.state!.players.find((p) => p.you)! };
  }

  it("幕五歇轮+幕六第二场：你不下→设歇翻面→第二场结算你下场、歇了句、4 秒进 final、5 秒收尾巴", async () => {
    const { h, you } = await toFirstSettle();
    expect(h.stepIdx).toBe(5); // 幕五完：先上的先下——你不下（第 6 步等着）
    expect(h.state!.courts[0]!.b).toContain(you.id); // 你留场接着打

    h.openPerson(you.id); // 幕五入口：点自己头像开点人抽屉
    h.tempo(you.id, "skip"); // 幕五「休息一轮」——办完抽屉即关（规格幕五验收「设歇后抽屉关上」）
    expect(h.sheetKind).toBeNull(); // 抽屉关上——提示行是引导本体，不能压在抽屉底下
    expect(h.stepIdx).toBe(6); // 设了歇即翻面
    expect(you.skip).toBe(1); // 歇记在名下——不是马上离场

    for (let i = 0; i < 11; i++) h.point(1, "b"); // 幕六：第二场打到 11
    h.confirmSettle(1, "b", 11, 0);
    expect(qNames(h.state!)).toEqual(["你", "球球"]); // 连打两场的你球球下场排队
    expect(
      h.state!.courts[0]!.b.map(
        (i) => h.state!.players.find((p) => p.id === i)!.name,
      ),
    ).toEqual(["阿豪", "老周"]); // 阿豪老周顶上
    expect(h.stepIdx).toBe(7); // 幕六/幕七两步判据同拍级联翻完
    expect(h.stepText).toBe(
      "你下场了，歇的那一轮也记上了——现场就是这么转起来的",
    );
    vi.advanceTimersByTime(4000); // 第 7 条停 4 秒自动进
    expect(h.step?.final).toBe(true);
    expect(h.stepText).toBe("想打真的？去约球页找个真局 ▸");
    vi.advanceTimersByTime(5000); // final 行几秒后收成尾部小条
    expect(h.step).toBeNull(); // 提示槽收窄成尾巴（✓ 教学走完了），不消失
  });

  it("幕五不歇也放行：第二场结算直接连翻，第 7 条换「先歇」句（A3 双分支另一边）", async () => {
    const { h } = await toFirstSettle();
    for (let i = 0; i < 11; i++) h.point(1, "b");
    h.confirmSettle(1, "b", 11, 0);
    expect(h.stepIdx).toBe(7); // 不歇：两步判据同拍翻完，一样放行
    expect(h.stepText).toBe(
      "下次累了可以先歇——点自己的头像就行。现场就是这么转起来的",
    );
  });
});

describe("抽屉族与权限闸（2.7 批4：参与卡=普通球员）", () => {
  it("参与卡改分制不动、规则抽屉照常可开（只读）；退出清抽屉状态（局面散）", async () => {
    const h = await load();
    h.enter("participate");
    h.checkInMe();
    vi.advanceTimersByTime(2000); // 自动开赛
    h.setScoring(15); // 普通球员：不动（真局 needFull 同闸；抽屉内罩层点不动是第一层）
    expect(h.state!.scoring).toBe(11);
    h.openRules(); // 抽屉照常可开（§4.4 规格原话「规则抽屉照常可开但改不了」）
    expect(h.sheetKind).toBe("rules");
    h.openPerson(h.state!.players.find((p) => p.you)!.id); // 点自己头像（幕五入口）
    expect(h.sheetKind).toBe("person");
    expect(h.personId).toBe(h.state!.players.find((p) => p.you)!.id);
    h.exit();
    expect(h.sheetKind).toBeNull(); // 退出即散（§4.5：本机不落任何东西）
    expect(h.personId).toBe(0);
  });
});
