/* 沙盒引擎数字账逐条锁（2.7 批1）——照规格 §7 A4 两段数字账推演全程断言，
   轮转语义与后端 live_rotation 同口径（剧本两场下场者与真码一致）；歇轮/
   连战/胜负不改谁下各自成锁。跑马灯句逐字断言（含示例局自造句）。 */
import { describe, expect, it } from "vitest";
import {
  addCourt,
  checkIn,
  endGame,
  initOrganize,
  initParticipate,
  pOf,
  pushFeed,
  setAdmin,
  setScoring,
  settle,
  swap,
  sweepCancelAll,
  tempo,
  type SandState,
} from "@/sandbox/engine";
import {
  ELO_PREVIEW,
  ORG_FINAL_BILL,
  ORGANIZE_CUES,
  ORGANIZE_ROSTER,
  PARTICIPATE_ROSTER,
} from "@/sandbox/data";
import { ORGANIZE_STEPS, PARTICIPATE_STEPS } from "@/sandbox/steps";

const idOf = (s: SandState, name: string) =>
  s.players.find((p) => p.name === name)!.id;
const qNames = (s: SandState) => s.queue.map((i) => pOf(s, i).name);
const court = (s: SandState, no: number) => s.courts.find((c) => c.no === no)!;
const sideNames = (s: SandState, no: number, side: "a" | "b") =>
  court(s, no)[side].map((i) => pOf(s, i).name);

describe("参与卡数字账（A4：先上的先下·候场首补位）", () => {
  const s = initParticipate();

  it("开场：阿豪老周在等、1 片空场、你未签到", () => {
    expect(qNames(s)).toEqual(["阿豪", "老周"]);
    expect(s.courtsCount).toBe(1);
    expect(sideNames(s, 1, "a")).toEqual([]);
    expect(s.organizerId).toBe(idOf(s, "阿豪"));
  });

  it("你签到→候场 3 人仍不开；球球到（第 4 人）自动开赛 阿豪·老周 vs 你·球球", () => {
    checkIn(s, idOf(s, "你"));
    expect(qNames(s)).toEqual(["阿豪", "老周", "你"]);
    expect(sideNames(s, 1, "a")).toEqual([]); // 还差 1 人，差人卡仍在
    checkIn(s, idOf(s, "球球"));
    expect(sideNames(s, 1, "a")).toEqual(["阿豪", "老周"]);
    expect(sideNames(s, 1, "b")).toEqual(["你", "球球"]);
    expect(s.queue).toEqual([]);
    expect(s.feed[0]).toBe("人够 4 · 自动开赛"); // 起头句（真码无此事件，示例局自造）
  });

  it("老金小鹿随你打球前后脚到，候场 [老金, 小鹿]", () => {
    checkIn(s, idOf(s, "老金"));
    checkIn(s, idOf(s, "小鹿"));
    expect(qNames(s)).toEqual(["老金", "小鹿"]);
  });

  it("第一场结算：阿豪老周下、老金小鹿顶坑、你球球留场，候场 [阿豪, 老周]", () => {
    settle(s, 1, "a", 11, 9);
    expect(sideNames(s, 1, "a")).toEqual(["老金", "小鹿"]);
    expect(sideNames(s, 1, "b")).toEqual(["你", "球球"]);
    expect(qNames(s)).toEqual(["阿豪", "老周"]);
    expect(s.matches).toEqual([
      { courtNo: 1, winners: ["阿豪", "老周"], sa: 11, sb: 9 },
    ]);
    expect(s.feed[0]).toBe("阿豪 & 老周 11:9 拿下");
  });

  it("幕五设歇+第二场结算：你球球（连打两场）下、阿豪老周顶上，候场 [你, 球球]", () => {
    tempo(s, idOf(s, "你"), "skip");
    expect(pOf(s, idOf(s, "你")).skip).toBe(1); // 状态记名下，不是马上离场
    settle(s, 1, "b", 9, 11);
    expect(sideNames(s, 1, "a")).toEqual(["老金", "小鹿"]); // 留场的保住半边
    expect(sideNames(s, 1, "b")).toEqual(["阿豪", "老周"]);
    expect(qNames(s)).toEqual(["你", "球球"]);
    expect(s.matches.length).toBe(2);
    expect(s.matches[1]).toEqual({
      courtNo: 1,
      winners: ["你", "球球"],
      sa: 9,
      sb: 11,
    });
  });

  it("歇轮语义：发牌轮到队首的你时跳过、消耗一次、保位留队（没被轮到的不消耗）", () => {
    // 第三场：先上的是老金小鹿（第二老的上场章）→ 他俩下；补位从队首取，
    // 你被跳过（skip 1→0 仍队首），球球与回流的老金补上 a 半边
    settle(s, 1, "a", 11, 5);
    expect(pOf(s, idOf(s, "你")).skip).toBe(0);
    expect(qNames(s)).toEqual(["你", "小鹿"]); // 位置不动=仍是队首
    expect(sideNames(s, 1, "a")).toEqual(["球球", "老金"]);
    expect(sideNames(s, 1, "b")).toEqual(["阿豪", "老周"]);
  });
});

describe("胜负不影响谁下（验收「轮换可预期」：胜方点给不同队，下场者不变）", () => {
  it("两次结算胜方互换重推，下场者与参与卡数字账完全一致", () => {
    const s = initParticipate();
    checkIn(s, idOf(s, "你"));
    checkIn(s, idOf(s, "球球"));
    checkIn(s, idOf(s, "老金"));
    checkIn(s, idOf(s, "小鹿"));
    settle(s, 1, "b", 9, 11); // 第一场点你球球赢
    expect(qNames(s)).toEqual(["阿豪", "老周"]); // 下的还是先上的阿豪老周
    expect(sideNames(s, 1, "a")).toEqual(["老金", "小鹿"]);
    expect(s.matches[0]!.winners).toEqual(["你", "球球"]);
    settle(s, 1, "a", 11, 9); // 第二场点阿豪老周赢
    expect(sideNames(s, 1, "b")).toEqual(["阿豪", "老周"]); // 下的还是连打两场的你球球
    expect(qNames(s)).toEqual(["你", "球球"]);
  });
});

describe("组织卡数字账（A4：自动开赛→代办带访客→加片即开→原班续场→散场）", () => {
  const s = initOrganize();

  it("开场：签到序老周→小敏→你、你是组织者、无人任管理员、1 片空场", () => {
    expect(qNames(s)).toEqual(["老周", "小敏", "你"]);
    expect(s.organizerId).toBe(idOf(s, "你"));
    expect(s.players.some((p) => p.admin)).toBe(false);
    expect(sideNames(s, 1, "a")).toEqual([]);
  });

  it("球球到（第 4 人）自动开赛 老周·小敏 vs 你·球球；老金紧随候场 [老金]", () => {
    checkIn(s, idOf(s, "球球"));
    expect(sideNames(s, 1, "a")).toEqual(["老周", "小敏"]);
    expect(sideNames(s, 1, "b")).toEqual(["你", "球球"]);
    expect(s.feed[0]).toBe("人够 4 · 自动开赛");
    checkIn(s, idOf(s, "老金"));
    expect(qNames(s)).toEqual(["老金"]);
  });

  it("凯文迟到代办+访客带上，先后入队尾 [老金, 凯文, 朋友]", () => {
    checkIn(s, idOf(s, "凯文"), "late");
    const kevinCue = ORGANIZE_CUES.find((c) => c.feed);
    pushFeed(s, kevinCue!.feed!); // store 批2 按 NPC 调度表滚这句
    expect(s.feed[0]).toBe("凯文 · 迟到了");
    checkIn(s, idOf(s, "朋友")); // 带访客出口（访客行进卡即在册，签到进场）
    expect(qNames(s)).toEqual(["老金", "凯文", "朋友"]);
  });

  it("改分制 15：全局生效、在打片快照照旧（下一场起生效）", () => {
    setScoring(s, 15);
    expect(s.scoring).toBe(15);
    expect(court(s, 1).scoring).toBe(11);
  });

  it("换人：老金原位顶球球的坑、球球回队尾；封凯文当管理员", () => {
    swap(s, idOf(s, "球球"), idOf(s, "老金"));
    expect(sideNames(s, 1, "b")).toEqual(["你", "老金"]);
    expect(qNames(s)).toEqual(["凯文", "朋友", "球球"]);
    expect(s.feed[0]).toBe("你 把 球球 换下 · 老金 上");
    setAdmin(s, idOf(s, "凯文"));
    expect(pOf(s, idOf(s, "凯文")).admin).toBe(true);
    expect(s.feed[0]).toBe("组织者封 凯文 为管理员");
  });

  it("小鹿到候场攒到 4 人，但 1 片在打无空片→不开；加片即自动开出第二片（15 分制）", () => {
    checkIn(s, idOf(s, "小鹿"));
    expect(qNames(s)).toEqual(["凯文", "朋友", "球球", "小鹿"]);
    expect(s.courts.length).toBe(1); // 没有空片可自动上
    addCourt(s);
    expect(s.courtsCount).toBe(2);
    expect(sideNames(s, 2, "a")).toEqual(["凯文", "朋友"]); // 访客也照上
    expect(sideNames(s, 2, "b")).toEqual(["球球", "小鹿"]);
    expect(court(s, 2).scoring).toBe(15); // 新片用新制
    expect(s.feed[0]).toBe("人够 4 · 自动开赛");
    expect(s.queue).toEqual([]);
  });

  it("两片各结算一次：无人候场=原班四人接着打；1 号片续场刷新 15 分制", () => {
    settle(s, 1, "a", 15, 9); // 直录按 15 分制填
    expect(sideNames(s, 1, "a")).toEqual(["老周", "小敏"]); // 刚下的转身又顶回来
    expect(sideNames(s, 1, "b")).toEqual(["你", "老金"]);
    expect(court(s, 1).scoring).toBe(15);
    expect(s.queue).toEqual([]);
    expect(s.matches[0]).toEqual({
      courtNo: 1,
      winners: ["老周", "小敏"],
      sa: 15,
      sb: 9,
    });
    settle(s, 2, "b", 7, 15);
    expect([...sideNames(s, 2, "a"), ...sideNames(s, 2, "b")].sort()).toEqual(
      ["凯文", "小鹿", "球球", "朋友"].sort(),
    ); // 原班续场（半边内顺序无关紧要）
    expect(s.matches.length).toBe(2);
  });

  it("散场链：残局不清完不放行→未完对局全部取消（回流队首保行序）→确认散场", () => {
    expect(endGame(s)).toBe(false); // 两片 0:0 续场还在打
    sweepCancelAll(s);
    expect(s.courts.every((c) => !c.a.length && !c.b.length)).toBe(true);
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
    expect(endGame(s)).toBe(true);
    expect(s.ended).toBe(true);
  });
});

describe("tempo 连战（真码 tempo 镜像：连战排队首、与歇互斥、再按取消）", () => {
  it("fire 排到队首清歇；取消连战队列不动", () => {
    const s = initParticipate();
    checkIn(s, idOf(s, "你"));
    checkIn(s, idOf(s, "球球"));
    checkIn(s, idOf(s, "老金"));
    checkIn(s, idOf(s, "小鹿"));
    settle(s, 1, "a", 11, 9);
    settle(s, 1, "b", 9, 11); // 走到候场 [你, 球球]
    tempo(s, idOf(s, "球球"), "skip"); // 先设歇再连战——互斥清零
    expect(pOf(s, idOf(s, "球球")).skip).toBe(1);
    tempo(s, idOf(s, "球球"), "fire");
    expect(pOf(s, idOf(s, "球球"))).toMatchObject({ fire: true, skip: 0 });
    expect(qNames(s)).toEqual(["球球", "你"]); // 候场里排到队首
    tempo(s, idOf(s, "球球"), "fire"); // 再按一次=取消，队列不动
    expect(pOf(s, idOf(s, "球球")).fire).toBe(false);
    expect(qNames(s)).toEqual(["球球", "你"]);
  });
});

describe("写死数值与步进表（界面不自算·A3 条数）", () => {
  it("收工账单：场地费 240 · 8 人 · 每人 30 · 访客份额归担保人你付 60", () => {
    expect(ORG_FINAL_BILL).toEqual({
      feeTotal: 240,
      heads: 8,
      perHead: 30,
      myShare: 60,
      tail: "真局的账单在『我的-账单』随时翻",
    });
  });

  it("eloPreview 覆盖两卡全部名册，量级 Elo 1200 上下 ±24 内", () => {
    for (const r of [...PARTICIPATE_ROSTER, ...ORGANIZE_ROSTER]) {
      const e = ELO_PREVIEW[r.name];
      expect(e, r.name).toBeDefined();
      expect(e!.win).toBeGreaterThan(0);
      expect(e!.win).toBeLessThanOrEqual(24);
      expect(e!.lose).toBeLessThan(0);
      expect(e!.lose).toBeGreaterThanOrEqual(-24);
    }
  });

  it("步进表：参与卡 9 条、组织卡 10 条，首尾句逐字", () => {
    expect(PARTICIPATE_STEPS.length).toBe(9);
    expect(ORGANIZE_STEPS.length).toBe(10);
    expect(PARTICIPATE_STEPS[0]!.text).toBe(
      "这局是示例——点『我到了』，你也进场",
    );
    expect(PARTICIPATE_STEPS[2]).toMatchObject({
      spot: "qr-btn", // v2.8 亮码收人步：光圈指顶条二维码钮
    });
    expect(PARTICIPATE_STEPS[8]).toMatchObject({
      text: "想打真的？去约球页找个真局 ▸",
      final: true,
    });
    const orgLast = ORGANIZE_STEPS[9]!.text as (s: SandState) => string;
    expect(orgLast(initOrganize())).toBe("都打完了——散场收工，看看费用怎么摊");
    const done = initOrganize();
    done.ended = true;
    expect(orgLast(done)).toBe("组织者的事就这些——去发个真局 ▸"); // 收尾句（4.3）
  });

  it("步进判据随剧本翻面（engine↔steps 契约）", () => {
    const s = initParticipate();
    const step = (i: number) => PARTICIPATE_STEPS[i]!.done!;
    expect(step(0)(s)).toBe(false);
    checkIn(s, idOf(s, "你"));
    expect(step(0)(s)).toBe(true); // 候场出现你
    expect(step(1)(s)).toBe(false);
    checkIn(s, idOf(s, "球球"));
    expect(step(1)(s)).toBe(true); // 你上场
    expect(step(2)(s)).toBe(false); // 亮码步：状态恒不成立（NPC 定时器跳不了）
    expect(step(2)(s, { kind: "score", mine: true })).toBe(false); // 也不吃记分事件
    expect(step(2)(s, { kind: "qr" })).toBe(true); // 只认点开示意浮层
    expect(step(3)(s, { kind: "score", mine: false })).toBe(false);
    expect(step(3)(s, { kind: "score", mine: true })).toBe(true); // 你记了 1 分
    expect(step(4)(s)).toBe(false);
    checkIn(s, idOf(s, "老金"));
    checkIn(s, idOf(s, "小鹿"));
    settle(s, 1, "a", 11, 9);
    expect(step(4)(s)).toBe(true); // 第一次结算确认
    expect(step(5)(s)).toBe(false);
    tempo(s, idOf(s, "你"), "skip");
    expect(step(5)(s)).toBe(true); // 设了歇
    expect(step(6)(s)).toBe(false);
    settle(s, 1, "b", 9, 11);
    expect(step(6)(s)).toBe(true); // 第二次结算确认
  });

  it("组织卡第七步判据：封了任一人即翻面（文案「点一个人」，不锁凯文）", () => {
    const s = initOrganize();
    const step7 = ORGANIZE_STEPS[6]!.done!;
    expect(step7(s)).toBe(false); // 无人被封
    setAdmin(s, idOf(s, "球球")); // 照文案封了别人（用户实测踩中的卡点）
    expect(step7(s)).toBe(true);
  });
});
