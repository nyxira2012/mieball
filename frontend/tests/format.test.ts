import { describe, expect, it, vi } from "vitest";
import type { Game, Person } from "@/api/types";
import {
  autoGameName,
  courtDisplayName,
  courtsShortLabel,
  deadRowKind,
  freqName,
  gameTapAction,
  isOrg,
  liveOngoing,
  newGameCard,
  slotBig,
  slotName,
} from "@/utils/format";
import { toIso } from "@/utils/time";

/* 卡面时间换算（isoDay/isoHm）按设备本地墙钟走；本项目时区口径=北京时间（契约§2），
   测试环境钉死 TZ，避免开发机时区不同导致断言漂移。 */
process.env.TZ = "Asia/Shanghai";

/* 1.2 接线重写：人头/剩坑/人均/forced 等本地公式退役（改读后端定值），
   本文件只测换下来的纯展示口径：状态文案表、卡面映射（真局/快照）、点卡分支、词表。 */

const ken: Person = { id: 11, nickname: "亮马河 Ken" };
const me: Person = { id: 0, nickname: "我" };

function mkGame(p: Partial<Game> = {}): Game {
  return {
    id: 1,
    name: "测试局",
    organizer: ken,
    startAt: "2026-10-10T10:00:00+08:00",
    endAt: "2026-10-10T12:00:00+08:00",
    deadlineAt: "2026-10-10T08:00:00+08:00",
    venueName: "亮马河 · 滨河球场",
    venueAddress: null,
    minPlayers: 4,
    maxPlayers: 8,
    visibility: "public",
    scoring: 11,
    rotation: "balance",
    scoreRule: "rally",
    manualLock: false,
    courts: null,
    feeTotal: null,
    status: "open",
    unlocked: false,
    joinable: true,
    liveOpened: false,
    ended: false,
    heads: 1,
    slotsLeft: 7,
    perHead: null,
    forced: false,
    ...p,
  };
}

describe("newGameCard（真局 → 卡面模型：定值直读，时间现场换算）", () => {
  it("时间/场馆/必打标/剩坑", () => {
    // 「今天」锚死北京 2026-10-04：远日字面断言才确定（isoDay 对 0-2 天出 今天/明天/后天）
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-04T12:00:00+08:00"));
    try {
      const start = new Date(2026, 9, 10, 10, 0); // 本地墙钟 2026-10-10 10:00，经 toIso 往返免 TZ 抖动
      const card = newGameCard(
        mkGame({
          startAt: toIso(start),
          courts: ["3号"],
          forced: true,
          slotsLeft: 3,
          heads: 5,
          entries: [
            { account: ken, bring: 0, standing: "formal", waitSeq: null },
            { account: me, bring: 1, standing: "formal", waitSeq: null },
            {
              account: { id: 2, nickname: "乙" },
              bring: 0,
              standing: "waitlist",
              waitSeq: 1,
            },
          ],
        }),
      );
      expect(card.hmText).toBe("10:00"); // ISO 现场换算
      expect(card.dayText).toBe("10.10 周六"); // 北京墙钟日段（dayToken 已退役，修复批 F2）
      expect(card.venueText).toBe("亮马河 · 滨河球场");
      expect(card.timeSub).toBe("3号场"); // 场上号进时间列固定槽（courtDisplayName 补号场），优先于空锁文案
      expect(card.slotsLeft).toBe(3);
      // 候补不进头像叠层；带的人不计入头像数
      expect(card.stackAvatarUrls).toHaveLength(2);
      expect(card.stackPlus).toBe("+");
    } finally {
      vi.useRealTimers();
    }
  });

  it("myRole 三态 + 空锁标", () => {
    expect(
      newGameCard(
        mkGame({ my: { isOrganizer: true, myEntry: null, invited: false } }),
      ).myRole,
    ).toBe("org");
    expect(
      newGameCard(
        mkGame({ my: { isOrganizer: false, myEntry: null, invited: true } }),
      ).myRole,
    ).toBe("inv");
    expect(
      newGameCard(
        mkGame({
          my: {
            isOrganizer: false,
            myEntry: { bring: 0, standing: "formal", waitSeq: null },
            invited: false,
          },
        }),
      ).myRole,
    ).toBe("joined");
    expect(
      newGameCard(mkGame({ manualLock: true, forced: true })).timeSub,
    ).toBe("必开"); // 仅手动锁（场上无号）亮「必开」
    expect(newGameCard(mkGame({ courts: ["16号", "17号"] })).timeSub).toBe(
      "16号场·17号场", // 多片逐个过 courtDisplayName 再 join「·」，卡片固定槽窄位显示
    );
    expect(newGameCard(mkGame()).timeSub).toBeUndefined();
  });

  it("orgBack 随组织者透传（1.9 A6 #6 局卡铺组织者卡背）；无卡背兜 null 素卡", () => {
    expect(
      newGameCard(mkGame({ organizer: { ...ken, back: "b-t35" } })).orgBack,
    ).toBe("b-t35");
    expect(newGameCard(mkGame()).orgBack).toBeNull(); // 旧形状 Person 无 back → 素卡不铺
  });
});

/* 2.5 批2 卡片三态（§4.1 倒计时 / §4.2 两小时窗入口 / §4.4 账开即入口）：
   时间相关例以 now 相对量构造 startAt，断言只看字段有无不看具体分钟文案（免时钟漂移）。 */
describe("newGameCard 三态（进入现场入口 / 倒计时 / 均无）", () => {
  const org = (p: Partial<Game> = {}) =>
    mkGame({ my: { isOrganizer: true, myEntry: null, invited: false }, ...p });
  const member =
    (standing: "formal" | "waitlist") =>
    (p: Partial<Game> = {}) =>
      mkGame({
        my: {
          isOrganizer: false,
          myEntry: {
            bring: 0,
            standing,
            waitSeq: standing === "waitlist" ? 1 : null,
          },
          invited: false,
        },
        ...p,
      });
  const hoursFromNow = (h: number): string =>
    toIso(new Date(Date.now() + h * 3600_000));

  it(">2h 未开账 open 局：只有倒计时，无入口（§4.2）", () => {
    const card = newGameCard(org({ startAt: hoursFromNow(3) }));
    expect(card.countdown).toMatch(/^还有\d/); // 紧凑口径：还有3时0分（2026-10-10 用户定）
    expect(card.dayText).toBe("今天"); // 相对日词照常上卡（2026-10-10 纠偏：删行指令已撤）
    expect(card.liveEnter).toBeUndefined();
  });

  it("报名中未锁定的局进两小时窗：也只有倒计时，无入口（§5）", () => {
    const card = newGameCard(org({ startAt: hoursFromNow(1.5) }));
    expect(card.countdown).toMatch(/^还有\d/);
    expect(card.liveEnter).toBeUndefined();
  });

  it("没报任何局的人（游客视角 my 缺省）：两字段均无（§5）", () => {
    const card = newGameCard(
      mkGame({ status: "locked", startAt: hoursFromNow(1.5) }),
    );
    expect(card.liveEnter).toBeUndefined();
    expect(card.countdown).toBeUndefined();
  });

  it("locked 局进两小时窗：入口亮、倒计时收（整点边界含）", () => {
    const inWin = newGameCard(
      org({ status: "locked", startAt: hoursFromNow(1.5) }),
    );
    expect(inWin.liveEnter).toBe(true);
    expect(inWin.countdown).toBeUndefined();
    const atEdge = newGameCard(
      org({ status: "locked", startAt: hoursFromNow(2) }),
    );
    expect(atEdge.liveEnter).toBe(true);
  });

  it("locked 局但 >2h 未开账：仍是倒计时", () => {
    const card = newGameCard(
      org({ status: "locked", startAt: hoursFromNow(3) }),
    );
    expect(card.countdown).toMatch(/^还有\d/);
    expect(card.liveEnter).toBeUndefined();
  });

  it("账已开（liveOpened）：不看时间立即入口（§4.4）", () => {
    const card = newGameCard(
      org({ liveOpened: true, startAt: hoursFromNow(3) }),
    );
    expect(card.liveEnter).toBe(true);
    expect(card.countdown).toBeUndefined();
  });

  it("waitlist 成员：窗内也两字段均无（候补不出现入口）", () => {
    const card = newGameCard(
      member("waitlist")({ status: "locked", startAt: hoursFromNow(1.5) }),
    );
    expect(card.liveEnter).toBeUndefined();
    expect(card.countdown).toBeUndefined();
  });

  it("真散场（ended）的 done 局：终态两字段均无（哪怕账开过）", () => {
    const card = newGameCard(
      org({ status: "done", liveOpened: true, ended: true }),
    );
    expect(card.liveEnter).toBeUndefined();
    expect(card.countdown).toBeUndefined();
  });

  /* 2026-10-08 债清偿回归：到点未散场的局派生已是 done 但 ended 仍假——入口必须
     常在（组织者要回去补散场确认），否则局挂死在「回不了现场、散不了场」的吸收态 */
  it("到点未散场（done ∧ ¬ended ∧ 账已开）：现场入口仍亮", () => {
    const card = newGameCard(
      org({ status: "done", liveOpened: true, ended: false }),
    );
    expect(card.liveEnter).toBe(true);
    // 成员同规矩：回现场看轮转/记分同一条路
    const mateCard = newGameCard(
      member("formal")({ status: "done", liveOpened: true, ended: false }),
    );
    expect(mateCard.liveEnter).toBe(true);
  });

  it("正式报名成员与组织者同规矩：窗内 locked 局入口亮", () => {
    const card = newGameCard(
      member("formal")({ status: "locked", startAt: hoursFromNow(1.5) }),
    );
    expect(card.liveEnter).toBe(true);
  });

  /* 批1 闸裂缝回归：手动锁/订场后、截止懒判定前簿 state 仍 open——必开口径必须与
     backend is_forced（订场∨手动锁）同构，否则此窗内后端放行开账、前端不亮入口 */
  it("open+manualLock 局进两小时窗：入口亮（必开）", () => {
    const card = newGameCard(
      org({ manualLock: true, startAt: hoursFromNow(1.5) }),
    );
    expect(card.liveEnter).toBe(true);
    expect(card.countdown).toBeUndefined();
  });

  it("open+courts 局进两小时窗：入口亮（订场即必开）", () => {
    const card = newGameCard(
      org({ courts: ["3号"], startAt: hoursFromNow(1.5) }),
    );
    expect(card.liveEnter).toBe(true);
    expect(card.countdown).toBeUndefined();
  });

  it("open+manualLock 局窗外：仍只是倒计时（必开也要等两小时窗）", () => {
    const card = newGameCard(
      org({ manualLock: true, startAt: hoursFromNow(3) }),
    );
    expect(card.liveEnter).toBeUndefined();
    expect(card.countdown).toMatch(/^还有\d/);
  });
});

describe("gameTapAction（alpha:907 点局卡分支）：被邀请未加入 → join", () => {
  it("三态", () => {
    expect(
      gameTapAction(
        mkGame({ my: { isOrganizer: false, myEntry: null, invited: true } }),
      ),
    ).toBe("join");
    expect(
      gameTapAction(
        mkGame({
          my: {
            isOrganizer: false,
            myEntry: { bring: 0, standing: "formal", waitSeq: null },
            invited: true,
          },
        }),
      ),
    ).toBe("detail"); // 已加入的邀请不算
    expect(gameTapAction(mkGame())).toBe("detail");
  });
});

describe("liveOngoing（「账开着还没散场」单一口径：meet 横幅/detail 回现场/liveGame 同消费）", () => {
  it("status=live 在办、liveOpened 提前开账（簿仍 open/locked）也在办", () => {
    expect(liveOngoing(mkGame({ status: "live" }))).toBe(true);
    expect(liveOngoing(mkGame({ status: "open", liveOpened: true }))).toBe(
      true,
    );
    expect(liveOngoing(mkGame({ status: "locked", liveOpened: true }))).toBe(
      true,
    );
  });
  it("已散场（ended）不算在办；没开账的 open/locked 也不算", () => {
    expect(
      liveOngoing(mkGame({ status: "done", liveOpened: true, ended: true })),
    ).toBe(false);
    expect(liveOngoing(mkGame({ status: "open" }))).toBe(false);
    expect(liveOngoing(mkGame({ status: "locked" }))).toBe(false);
  });
});

describe("isOrg（viewer 块定值）", () => {
  it("my 缺省（游客）恒 false", () => {
    expect(
      isOrg(
        mkGame({ my: { isOrganizer: true, myEntry: null, invited: false } }),
      ),
    ).toBe(true);
    expect(isOrg(mkGame())).toBe(false);
  });
});

describe("deadRowKind（我的局终局行分派：4.8/4.9/4.10）", () => {
  const org = (p: Partial<Game> = {}) =>
    mkGame({ my: { isOrganizer: true, myEntry: null, invited: false }, ...p });
  const joiner = (p: Partial<Game> = {}) =>
    mkGame({
      my: {
        isOrganizer: false,
        myEntry: { bring: 0, standing: "formal", waitSeq: null },
        invited: false,
      },
      ...p,
    });

  it("组织者：pending→待处置卡、terminated→未成局卡、cancelled 不留痕", () => {
    expect(deadRowKind(org({ status: "pending" }))).toBe("pending");
    expect(deadRowKind(org({ status: "terminated" }))).toBe("restore");
    expect(deadRowKind(org({ status: "cancelled" }))).toBeNull(); // 撤局不留痕（4.10）
  });

  it("参加者：terminated/cancelled→当日灰字行；在办局与 pending 不进死局区", () => {
    expect(deadRowKind(joiner({ status: "terminated" }))).toBe("gray");
    expect(deadRowKind(joiner({ status: "cancelled" }))).toBe("gray");
    expect(deadRowKind(joiner({ status: "open" }))).toBeNull();
    // pending 后端只发给组织者（球友打开也不触发判死，4.9）；防御面不亮任何处置入口
    expect(deadRowKind(joiner({ status: "pending" }))).toBeNull();
  });
});

describe("slotName / freqName / slotBig（alpha:890-891, 1023-1024）", () => {
  it("时段名与兜底", () => {
    expect(slotName("wd")).toBe("工作日晚间");
    expect(slotName("we-n")).toBe("周末晚上");
    expect(slotName("nope")).toBe("nope");
  });
  it("频率名", () => {
    expect(freqName(0)).toBe("随缘");
    expect(freqName(1)).toBe("每周 1 打");
    expect(freqName(2)).toBe("每周 2 打");
  });
  it("意向卡大字时段（大字=时段 / 小字=天）", () => {
    expect(slotBig("wd")).toEqual(["晚间", "工作日"]);
    expect(slotBig("ln")).toEqual(["午休", "工作日"]);
    expect(slotBig("we-d")).toEqual(["白天", "周末"]);
    expect(slotBig("we-n")).toEqual(["晚上", "周末"]);
  });
});

describe("autoGameName（自动局名「昵称 · 场馆末段」，2026-10-11 时间锚改人锚）", () => {
  it("昵称+场馆；复合场馆取末段；空场馆单用昵称", () => {
    expect(autoGameName("亮马河 Ken", "亮马河 · 滨河球场")).toBe(
      "亮马河 Ken · 滨河球场",
    );
    expect(autoGameName("老王", "朝阳馆")).toBe("老王 · 朝阳馆");
    expect(autoGameName("老王", "")).toBe("老王");
  });
});

describe("courtDisplayName（场地显示名单一源：对局卡/空闲卡/终局弹窗 kicker）", () => {
  it("各写入路径的存量口径统一显示「N号场」；本就以「场」结尾的名字原样保留", () => {
    expect(courtDisplayName("3号")).toBe("3号场");
    expect(courtDisplayName("5号")).toBe("5号场");
    expect(courtDisplayName("16")).toBe("16号场"); // 订场/直开原样存的裸号
    expect(courtDisplayName("16号场")).toBe("16号场"); // 种子口径（号场齐备）
    expect(courtDisplayName("中央场")).toBe("中央场"); // 非「N号场」形状的本名不动
  });
});

describe("courtsShortLabel（顶条打球场地短标签单一源）", () => {
  it("共用尾缀只说一遍；空数组兜底", () => {
    expect(courtsShortLabel(["16号", "5号"])).toBe("16、5号场");
    expect(courtsShortLabel(["16", "5号场"])).toBe("16、5号场"); // 存量口径混着也归一
    expect(courtsShortLabel(["1号"])).toBe("1号场");
    expect(courtsShortLabel([])).toBe("—");
  });
});
