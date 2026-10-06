/* 现场 store（alpha:1471-1530 startLive/avail/fillCourts/nextMatch · 1591-1648 setCheck · 1680-1728 point）
   2.1 打球页改版（批1 数据层）：终局从「到分自动落账 + WinPopup」改为 confirm-before-settle——
   point 到分只落 settling 快照，confirmSettle 才落账并自动排下一场。
   2.2 批1（权限地基）：现场权限分级——isFullPower 单一源（组织者 ∨ 管理员）；store 是 mock 期
   总账，收权动作在入口把关（规格 B1：不指望手机端拦住），越权句式两读：「请找组织者或管理员」
   （全权动作）/「只有组织者能做」（封撤管理员）。
   硬约束：不触碰任何 uni.*；发牌引擎在 utils/rotate.ts（纯函数，live 状态作参数）。
   1.2 隔离线适配：startLive 吃重塑后的真局对象（Person→伪 User 名册 + mock 默认值补现场属性）；
   现场改规则/场地只落在 LiveState.g 浅克隆上，不回写 game store 的局（派生态归后端）。
   名册直接引用球员对象（alpha:1474）：mock U 同 id 者带出真实战绩对象（结算落回战力榜）。 */
import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { DEFAULT_MOCK_CHECKIN_COUNT, U } from "@/api";
import type {
  CheckStatus,
  CourtMode,
  Game,
  LiveState,
  Person,
  User,
} from "@/api/types";
import { settleElo } from "@/utils/elo";
import { DRESS_RANGES } from "@/utils/chibi";
import { fillCourts, nextMatch, pById, usedCourts } from "@/utils/rotate";
import { shouldEnd, undoScore } from "@/utils/score";
import { isOrg, MODE_NAMES } from "@/utils/format";
import { errText } from "@/api/http";
import { useGameStore } from "./game";
import { useUiStore } from "./ui";
import { useUserStore } from "./user";

/** 访客 id 单调发号（批1 刺客：Math.random 撞号会让两位访客在 roster/swap 里互相串线） */
let guestSeq = 0;

/** 「算到场」谓词单一源（候场条状态文案与二维码浮层在场人数共用）：
    ok 正常 / late 迟到已到 / join 中途加入；absent 未到、left 早退不算 */
export const isArrived = (c?: CheckStatus): boolean =>
  c === "ok" || c === "late" || c === "join";

export const useLiveStore = defineStore("live", () => {
  const ui = useUiStore();
  /** alpha:805 let live=null —— 进行中的现场状态；TabBar 的 LIVE 红点（alpha:1487 #live-dot-nav） */
  const live = ref<LiveState | null>(null);
  const hasLive = computed(() => !!live.value);

  /** 终局结算待确认快照（2.1 §5）：非空 = EndSettleModal 开着；cur 保持不动 */
  const settling = ref<{ sa: number; sb: number } | null>(null);

  /** 现场权限单一源（2.2 §4.7）：组织者 ∨ 被封管理员 = 全权（同一套手柄）；
      球友只开放记分/撤分/换人/自己的报到早退与歇连 */
  const isFullPower = computed(() => {
    const L = live.value;
    return !!L && (isOrg(L.g) || L.admins.includes(U.me.id));
  });

  /** 越权拦截（规格 B1 总账把关）：收权动作入口统一走这里，UI 置灰只是前置 */
  function needFull(): boolean {
    if (isFullPower.value) return true;
    ui.toast("请找组织者或管理员");
    return false;
  }
  /** 组织者独占（§4.6 禁止：管理员自己也不能再封管理员） */
  function needOrg(): boolean {
    const L = live.value;
    if (L && isOrg(L.g)) return true;
    ui.toast("只有组织者能做");
    return false;
  }

  /** 战报 feed（unshift 新到旧）：句子在动作处拼好（含操作者），LiveTopbar 轮播消费 */
  function feedPush(sentence: string): void {
    live.value?.feed.unshift(sentence);
  }

  /** 我还有几轮上场（2.1 §3）：ceil((4*待开片数 + 我的队列位 + 1) / 4) */
  const myRound = computed<number | null>(() => {
    const L = live.value;
    if (!L) return null;
    const idx = L.queue.indexOf(U.me.id);
    if (idx < 0) return null;
    return Math.ceil((4 * L.courts.length + idx + 1) / 4);
  });

  /** 开始打球（alpha:1471-1490 口径）：吃真局对象——
    - 名册 = formal 报名行展开：成员卡（Person）优先借 mock U 同 id 者的完整属性对象
      （现场域仍吃 mock 属性；结算 Elo 落回战力榜），无则用 mock 默认值造伪 User；
    - 「带的人」展开成随行访客（随机 chibi · 半权重不进榜）；前 9 人 ok，其余 absent。 */
  function startLive(g: Game): string | null {
    const lg: Game = { ...g, courts: g.courts ? [...g.courts] : null }; // 现场改动不回写局（派生态归后端）
    const src: User[] = [];
    (g.entries ?? [])
      .filter((e) => e.standing === "formal")
      .forEach((e) => {
        src.push(mkPlayer(e.account));
        for (let i = 0; i < (e.bring || 0); i++) {
          src.push(mkGuest(e.account.nickname.slice(0, 2) + "的球友"));
        }
      });
    const roster = src.map((u, i) => {
      u.check = i < DEFAULT_MOCK_CHECKIN_COUNT ? "ok" : "absent";
      u.skip = 0;
      u.fire = false;
      return u;
    }); // alpha:1482
    const L: LiveState = {
      g: lg,
      roster,
      queue: roster.filter((p) => p.check === "ok").map((p) => p.id), // alpha:1483
      courts: [],
      history: [],
      round: 0,
      cur: null,
      lastWinners: null,
      admins: [], // 管理员现场封（不回写 g）
      feed: [`现场已点亮 · 组织者 ${lg.organizer.nickname}`], // 开场首句：轮播在无人动作时也有内容
    };
    live.value = L;
    settling.value = null; // 换局清残留结算窗（批1 刺客：上一局的快照不许漏进新局）
    fillCourts(L); // alpha:1485
    nextMatch(L); // alpha:1486
    const msg = "球局开始 · 现场已点亮";
    ui.toast(msg);
    return msg;
  }

  /** 成员卡 → 名册 User：mock U 同 id 者直接借对象（战绩联动）；否则 mock 默认值造伪 User */
  function mkPlayer(p: Person): User {
    const known = Object.values(useUserStore().users).find(
      (x) => x.id === p.id,
    );
    if (known) return known;
    return {
      id: p.id,
      name: p.nickname,
      elo: 1200,
      play: 0,
      win: 0,
      month: 0,
      chibi: { ...p.chibi },
    };
  }

  /** 确保现场开的是目标局（跳转/深链/扫码直达共用的守门口径）：
      列表缓存没有该局（或没带全量名单）就拉详情，找不到提示后不动现场。 */
  async function ensureLive(id: number): Promise<void> {
    if (live.value && live.value.g.id === id) return;
    const gs = useGameStore();
    let g = gs.findGame(id);
    if (!g || !g.entries?.length) {
      try {
        g = await gs.loadDetail(id);
      } catch {
        ui.toast("球局不存在或已结束");
        return;
      }
    }
    startLive(g);
  }

  /** 造一位随行访客（startLive 报名展开与组织者「带访客」addGuests 同法）：
      shadow · elo 1200 计入期望 · 随机 chibi 引用 chibi.ts 单一源 DRESS_RANGES */
  function mkGuest(name: string): User {
    return {
      id: 9000 + ++guestSeq,
      name,
      elo: 1200,
      play: 0,
      win: 0,
      month: 0,
      shadow: true,
      chibi: {
        skin: Math.floor(Math.random() * DRESS_RANGES.skin),
        hair: Math.floor(Math.random() * DRESS_RANGES.hair),
        hc: Math.floor(Math.random() * DRESS_RANGES.hc),
        shirt: Math.floor(Math.random() * DRESS_RANGES.shirt),
        face: Math.floor(Math.random() * DRESS_RANGES.face),
        acc: Math.floor(Math.random() * DRESS_RANGES.acc),
      },
    };
  }

  /** 到场四操作（alpha:1591-1605 setCheck）：迟到自动排队尾 / 早退清队列清场上 / 中途加入进队首。
      权限（§4.3）：代办他人收权；自己报到（扫码链路）/早退随时可 */
  function setCheck(id: number, st: CheckStatus): void {
    const L = live.value;
    const p = L ? pById(L, id) : undefined;
    if (!L || !p) return;
    if (id !== U.me.id && !needFull()) return;
    if (st === "late" && p.check !== "late") {
      p.check = "late";
      const i = L.queue.indexOf(id);
      if (i >= 0) L.queue.splice(i, 1);
      L.queue.push(id); // 迟到排队尾（toast 即此承诺）
      ui.toast(`${p.name} 迟到 · 自动排到队尾等一轮`);
    } else if (st === "left") {
      p.check = "left";
      L.queue = L.queue.filter((x) => x !== id);
      L.courts.forEach((c) => {
        c.A = c.A.filter((x) => x !== id);
        c.B = c.B.filter((x) => x !== id);
      });
      if (L.cur) {
        L.cur.A = L.cur.A.filter((x) => x !== id);
        L.cur.B = L.cur.B.filter((x) => x !== id);
      }
      ui.toast(`${p.name} 早退 · 名单已记录`);
    } else if (st === "join") {
      p.check = "join";
      if (!L.queue.includes(id)) L.queue.unshift(id);
      ui.toast(`${p.name} 中途加入 · 排进队首`);
    } else p.check = st;
  }

  /** 歇两轮 / 连战（alpha:1629-1636）：互斥；歇两轮=2；连战排到队首。给自己随时可、给他人需全权 */
  function togglePerson(id: number, k: "skip" | "fire"): void {
    const L = live.value;
    const p = L ? pById(L, id) : undefined;
    if (!L || !p) return;
    if (id !== U.me.id && !needFull()) return;
    if (k === "skip") {
      p.skip = p.skip ? 0 : 2; // 开=歇两轮，关=0
      if (p.skip) p.fire = false;
      ui.toast(p.skip ? "已歇两轮 · 发牌自动跳过" : "取消歇");
    } else {
      p.fire = !p.fire;
      if (p.fire) p.skip = 0;
      if (p.fire) {
        const i = L.queue.indexOf(id);
        if (i >= 0) {
          L.queue.splice(i, 1);
          L.queue.unshift(id);
        }
      }
      ui.toast(p.fire ? "连战 · 排到队首" : "取消连战");
    }
  }

  /** 封管理员（§4.6 仅组织者）：admins 存现场态不回写 g；「对方手机弹提示」mock 期降级为 feed+toast。
      边缘静默幂等：已封再封 / 人不在册都不动 */
  function setAdmin(id: number): void {
    if (!needOrg()) return;
    const L = live.value;
    const p = L ? pById(L, id) : undefined;
    if (!L || !p || L.admins.includes(id)) return;
    L.admins.push(id);
    feedPush(`组织者封 ${p.name} 为管理员`);
    ui.toast(`组织者封 ${p.name} 为管理员`);
  }

  /** 撤管理员（§4.6 仅组织者）：被撤者留痕 feed「组织者收回了 XX 的管理员身份」；不在册静默 */
  function unsetAdmin(id: number): void {
    if (!needOrg()) return;
    const L = live.value;
    const p = L ? pById(L, id) : undefined;
    if (!L || !p || !L.admins.includes(id)) return;
    L.admins = L.admins.filter((x) => x !== id);
    feedPush(`组织者收回了 ${p.name} 的管理员身份`);
    ui.toast(`组织者收回了 ${p.name} 的管理员身份`);
  }

  /** 扫码自签到（2.1·选项A）：名册没我（空降）→ 先报名进局再把人放进名册；
      然后标「中途加入」排进队首。现场没开或开的是别局 → 先切到目标局（扫码直达场景）。 */
  async function arriveMe(gameId: number): Promise<string | null> {
    await ensureLive(gameId);
    const L = live.value;
    if (!L || L.g.id !== gameId) return null; // ensureLive 已 toast 兜底
    const myId = U.me.id;
    let p = pById(L, myId);
    if (!p) {
      try {
        await useGameStore().joinGame(gameId, 0); // 空降：先成为报名球友（名片建号已在前一步完成）
      } catch (e) {
        ui.toast(errText(e));
        return null;
      }
      L.roster.push(
        mkPlayer({ id: myId, nickname: U.me.name, chibi: U.me.chibi }),
      ); // mkPlayer 借回 U.me 本体：战力/档案全局联动
      p = U.me;
    }
    if (p.check === "ok" || p.check === "join") {
      ui.toast("你已经在场了");
      return null;
    }
    setCheck(myId, "join"); // setCheck 内置 toast「中途加入 · 排进队首」
    return "已到场 · 进候场区";
  }

  /** 得分（alpha:1680-1687 point）：先到 N 且净胜 2 才收局——到分不落账，只开终局弹窗快照 */
  function point(side: "a" | "b"): void {
    if (settling.value) return; // 结算窗开着不许继续记分
    const L = live.value;
    const c = L?.cur;
    if (!L || !c) return;
    if (side === "a") c.sa++;
    else c.sb++;
    L.last = side;
    if (shouldEnd(c.sa, c.sb, L.g.scoring))
      settling.value = { sa: c.sa, sb: c.sb }; // cur 不动，等弹窗确认
  }

  /** 误记撤回一分（alpha:1676-1679 undoPoint） */
  function undoPoint(): void {
    if (settling.value) return;
    const L = live.value;
    const c = L?.cur;
    if (!L || !c) return;
    const r = undoScore(c.sa, c.sb, L.last);
    c.sa = r.sa;
    c.sb = r.sb;
  }

  /** 记分已清零 · 重开一盘（2.1 对局卡工具行；§4.8 收权——球友只能 ±1） */
  function clearScore(): void {
    const L = live.value;
    const c = L?.cur;
    if (!L || !c || !needFull()) return;
    c.sa = 0;
    c.sb = 0;
    L.last = undefined;
    settling.value = null;
    ui.toast("记分已清零 · 重开一盘");
  }

  /** 手动开终局结算：cur 存在才开，快照当前比分（§4.8 收权） */
  function openSettle(): void {
    const L = live.value;
    if (!L?.cur || !needFull()) return;
    settling.value = { sa: L.cur.sa, sb: L.cur.sb };
  }

  /** 关结算弹窗不落账：比分保留在 cur */
  function closeSettle(): void {
    settling.value = null;
  }

  /** 确认终局 · 排下一场（2.1 §5）：结算 = settleElo 落账 → 自动排下一场。撒花由页面层 watch。
      §4.8 收权：球友只能看结算窗（确认按钮置灰），绕过画面直调也在此拒 */
  function confirmSettle(winA: boolean, sa: number, sb: number): void {
    const L = live.value;
    const c = L?.cur;
    if (!L || !c || !needFull()) return;
    c.sa = sa;
    c.sb = sb;
    const winners = winA ? c.A : c.B;
    const losers = winA ? c.B : c.A;
    const byId = (id: number): User => pById(L, id)!;
    const results = settleElo(winners.map(byId), losers.map(byId));
    winners.concat(losers).forEach((id, i) => {
      const p = byId(id);
      const { up, d, elo } = results[i];
      p.elo = elo; // 地板 400 已在 settleElo 内处理
      p.month = (p.month || 0) + d; // alpha:1705
      p.play++; // alpha:1706
      if (up && !p.shadow) p.win++;
      if (p.id === U.me.id && p.last5)
        p.last5 = [...p.last5.slice(1), up ? "W" : "L"]; // alpha:1707 仅我滚动近5场
    });
    const wNm = winners.map((id) => byId(id).name).join(" & "); // alpha:1709
    L.history.unshift({ names: wNm, sa, sb });
    L.lastWinners = winners.filter((id) => !byId(id).shadow); // alpha:1711 随行不进胜者留场
    L.queue.push(...losers);
    if (L.g.rotation !== "winner" || L.courts.length > 0)
      L.queue.push(...winners);
    L.cur = null;
    L.round++;
    fillCourts(L);
    nextMatch(L);
    settling.value = null;
    ui.toast("积分落账 · 下一场已排好");
  }

  /** 取消对局（2.1 §2）：cur 的 A/B 全回队尾，cur=null、nextMatch 有待开片则顶上（收权动作） */
  function cancelMatch(): void {
    const L = live.value;
    const c = L?.cur;
    if (!L || !c || !needFull()) return;
    L.queue.push(...c.A, ...c.B);
    L.cur = null;
    settling.value = null;
    nextMatch(L);
    ui.toast("对局已取消 · 人回流候场 · 不计积分");
  }

  /** 换人（2.1 §4；2.2 §4.9 起球友开放）：cur 与待开片的 A/B 里 outId→inId */
  function swapPlayers(outId: number, inId: number): void {
    const L = live.value;
    if (!L) return;
    const swap = (arr: number[]): void => {
      const i = arr.indexOf(outId);
      if (i >= 0) arr[i] = inId;
    };
    if (L.cur) {
      swap(L.cur.A);
      swap(L.cur.B);
    }
    L.courts.forEach((c) => {
      swap(c.A);
      swap(c.B);
    });
    const j = L.queue.indexOf(inId);
    if (j >= 0) L.queue[j] = outId;
    ui.toast("已换人 · 对阵重排");
  }

  /** 带访客（2.1 §1 组织者代办 · 收权）：与 startLive 随行访客同法 */
  function addGuests(count: number, name: string, introducer: User): void {
    const L = live.value;
    if (!L || count <= 0 || !needFull()) return;
    for (let i = 0; i < count; i++) {
      const g = mkGuest(
        !name
          ? `${introducer.name.slice(0, 2)}的球友`
          : count > 1
            ? `${name}·${i + 2}`
            : name,
      );
      g.check = "join";
      L.roster.push(g);
      L.queue.push(g.id); // 队尾
    }
    ui.toast(`已带 ${count} 位访客 · 进候场区`);
  }

  /** 改分制（2.1 §3：当场生效——下一记分的收局判定即用新值；只落现场克隆，不回写局；收权动作） */
  function setRuleScore(v: number): void {
    const L = live.value;
    if (!L || !needFull()) return;
    L.g.scoring = v;
    ui.toast(`分制已改为 ${v} 分 · 当场生效`);
  }

  /** 改轮换模式（2.1 §3：下一场生效；收权动作） */
  function setRuleMode(m: CourtMode): void {
    const L = live.value;
    if (!L || !needFull()) return;
    L.g.rotation = m;
    ui.toast(`轮换模式已改为「${MODE_NAMES[m]}」· 下一场生效`);
  }

  /** 场地输入（2.1 顶条）：校验至少 1 片且 ≥ 已占片数；过 → 写 g.courts + fillCourts（收权动作） */
  function setCourtsInput(text: string): boolean {
    const L = live.value;
    if (!L || !needFull()) return false;
    const parts = text
      .split(/[、,，\s]+/)
      .map((s) => s.trim())
      .filter((s) => /^\d+号?$/.test(s))
      .map((s) => (s.endsWith("号") ? s : `${s}号`));
    const need = usedCourts(L);
    if (parts.length < 1) {
      ui.toast("至少要有 1 片场地");
      return false;
    }
    if (parts.length < need) {
      ui.toast("在打 + 待开的场地不能收");
      return false;
    }
    L.g.courts = parts;
    fillCourts(L);
    ui.toast(`场地已更新：${parts.join("、")}`);
    return true;
  }

  /** 自动排阵（2.1 §4）：fillCourts 发牌；没有在打场次则顶上一场（收权动作） */
  function autoDeal(): void {
    const L = live.value;
    if (!L || !needFull()) return;
    fillCourts(L);
    if (!L.cur) nextMatch(L);
    ui.toast("牌已发 · 按当前规则排好");
  }

  /** 名册按找（视图层 byId 的共享口径） */
  function byId(id: number): User {
    const L = live.value;
    return (
      (L ? pById(L, id) : undefined) ?? {
        id: -1,
        name: "—",
        elo: 0,
        play: 0,
        win: 0,
        month: 0,
        chibi: {},
      }
    );
  }

  return {
    live,
    hasLive,
    settling,
    myRound,
    isFullPower,
    needFull,
    byId,
    startLive,
    ensureLive,
    setCheck,
    arriveMe,
    addGuests,
    setAdmin,
    unsetAdmin,
    point,
    undoPoint,
    clearScore,
    openSettle,
    closeSettle,
    confirmSettle,
    cancelMatch,
    togglePerson,
    swapPlayers,
    setRuleScore,
    setRuleMode,
    setCourtsInput,
    autoDeal,
  };
});
