/* 现场 store（2.4 批2 起多片并行总账）：每片各打各的（LiveCourt 自带记分板/连庄/格式），
   轮换真值在 utils/rotate.ts 的 endMatch（纯函数，live 状态作参数）——store 只做
   guard + 编排 + toast + Elo/history/底账落账（沿用 store 头注释分工）。
   2.2 批1（权限地基）：isFullPower 单一源（组织者 ∨ 管理员）；收权动作入口把关
   （规格 B1：不指望手机端拦住），越权句式两读：「请找组织者或管理员」（全权动作）
   /「只有组织者能做」（封撤管理员）。
   2.2 批2（到场与名册）：名册成真账本——开场全员未到、到场驱动发牌；排队位统一队尾
   （迟到/中途加入/早退回来一律队尾）；空降扫码直入名册（不再 joinGame）；出勤底账
   ledger 当场落（touchLedger 单点）；移出名册对付扫码幽灵。
   2.4（轮换四件套）：rules 挂 LiveState——自选前「谁下」跟推荐走（syncRules 人数/片数
   变化时重算）、自选起冻结；记分族动作全部按片（courtId）；confirmSettle 幂等闸保证
   两端并发确认只落一次账（B2）；访客同规（2026-10-07 终裁，无 shadow 留场过滤）。
   硬约束：不触碰任何 uni.*；1.2 隔离线：startLive 吃真局对象（Person→伪 User 名册），
   现场改规则/场地只落在 LiveState.g 浅克隆上，不回写 game store 的局。
   名册直接引用球员对象：mock U 同 id 者带出真实战绩对象（结算落回战力榜）。 */
import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { U } from "@/api";
import type {
  CheckStatus,
  CourtMode,
  Game,
  LedgerRow,
  LiveCourt,
  LiveState,
  Person,
  RotationRules,
  User,
} from "@/api/types";
import { settleElo } from "@/utils/elo";
import { DRESS_RANGES } from "@/utils/chibi";
import {
  activePlayers,
  courtCount,
  courtSize,
  endMatch,
  fillAllCourts,
  fillCourt,
  pById,
  usedCourts,
} from "@/utils/rotate";
import { recommend } from "@/utils/recommend";
import { shouldEnd, undoScore } from "@/utils/score";
import { isOrg, MODE_NAMES } from "@/utils/format";
import { toIso } from "@/utils/time";
import { useGameStore } from "./game";
import { useUiStore } from "./ui";
import { useUserStore } from "./user";

/** 访客 id 单调发号（批1 刺客：Math.random 撞号会让两位访客在 roster/swap 里互相串线） */
let guestSeq = 0;

/** 「算到场」谓词单一源（候场条状态文案与二维码浮层在场人数共用）：
    ok 正常 / late 迟到已到 / join 中途加入；absent 未到、left 早退不算 */
export const isArrived = (c?: CheckStatus): boolean =>
  c === "ok" || c === "late" || c === "join";

/** 清场单点（2.2 批2：早退/移出两处 10 行块收敛；批3 替补/作废回流是可预见的下一个使用方）：
    把人从候场队和各片 A/B 同时清掉；在场资历一并注销（人已不在场上） */
function clearFromPlay(L: LiveState, id: number): void {
  L.queue = L.queue.filter((x) => x !== id);
  L.courts.forEach((c) => {
    c.A = c.A.filter((x) => x !== id);
    c.B = c.B.filter((x) => x !== id);
  });
  const p = pById(L, id);
  if (p) {
    p.tenure = 0;
    p.courtSeq = undefined;
  }
}

export const useLiveStore = defineStore("live", () => {
  const ui = useUiStore();
  /** alpha:805 let live=null —— 进行中的现场状态；TabBar 的 LIVE 红点（alpha:1487 #live-dot-nav） */
  const live = ref<LiveState | null>(null);
  const hasLive = computed(() => !!live.value);

  /** 终局结算待确认快照（2.1 §5 · 2.4 按片）：非空 = 该片 EndSettleModal 开着；
      courtId 同时是 confirmSettle 的幂等闸——两端并发确认同一场只落一次账（B2） */
  const settling = ref<{ courtId: number; sa: number; sb: number } | null>(null);

  /** 管理员谓词单一源（id ∈ L.admins）：PersonSheet/CheckinSheet/QueueSheet 徽章与全权判定共用 */
  function isAdmin(id: number): boolean {
    const L = live.value;
    return !!L && L.admins.includes(id);
  }

  /** 现场权限单一源（2.2 §4.7）：组织者 ∨ 被封管理员 = 全权（同一套手柄）；
      球友只开放记分/撤分/换人/自己的报到早退与歇连 */
  const isFullPower = computed(() => {
    const L = live.value;
    return !!L && (isOrg(L.g) || isAdmin(U.me.id));
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

  /** 推荐快照（2.4 §4.2：总账算好随时可取，非强制不替切；批3 RulesSheet 消费） */
  const advice = computed(() => {
    const L = live.value;
    return L
      ? recommend(L.rules.singles, activePlayers(L), courtCount(L))
      : null;
  });

  /** 我还有几轮上场（2.1 §3 · 2.4 size-aware）：
      ceil((每片人数 × 空片数 + 我的队列位 + 1) / 每片人数) */
  const myRound = computed<number | null>(() => {
    const L = live.value;
    if (!L) return null;
    const idx = L.queue.indexOf(U.me.id);
    if (idx < 0) return null;
    const size = courtSize(L.rules.singles);
    const empty = L.courts.filter((c) => !c.A.length && !c.B.length).length;
    return Math.ceil((size * empty + idx + 1) / size);
  });

  /** 按片找（记分族动作的定位口径） */
  function courtOf(courtId: number): LiveCourt | undefined {
    return live.value?.courts.find((c) => c.id === courtId);
  }

  /** 建一片空片（差人卡呈现；格式跟当前规则） */
  function mkCourt(L: LiveState, idx: number): LiveCourt {
    return {
      id: idx,
      name: L.g.courts?.[idx] ?? `${idx + 1}号`,
      singles: L.rules.singles,
      A: [],
      B: [],
      sa: 0,
      sb: 0,
      streakA: 0,
      streakB: 0,
    };
  }

  /** 片数与场地号对齐（startLive 建片 / setCourtsInput 改场地）：
      非空片（在打）按序保留——收片校验已保证新片数 ≥ 非空片数；空片补齐到片数上限 */
  function syncCourts(L: LiveState): void {
    const n = courtCount(L);
    L.courts = L.courts.filter((c) => c.A.length || c.B.length);
    L.courts.forEach((c, i) => {
      c.id = i;
      c.name = L.g.courts?.[i] ?? `${i + 1}号`;
    });
    while (L.courts.length < n) L.courts.push(mkCourt(L, L.courts.length));
  }

  /** 推荐跟随（2.4 §4.2）：人数/片数变化的动作尾部调——未自选（!downChosen）时
      「谁下」重算成最新推荐，不荐挂「全上全下」占位；自选起冻结（推荐只亮标签） */
  function syncRules(): void {
    const L = live.value;
    if (!L || L.rules.downChosen) return;
    const adv = recommend(L.rules.singles, activePlayers(L), courtCount(L));
    L.rules.down = adv.kind === "down" ? adv.down : "all";
  }

  /** 开始打球（alpha:1471-1490 口径 · 2.2 批2§4.1 开场点亮 · 2.4 批2 并行建片）：吃真局对象——
    - 名册 = formal 报名行展开：成员卡（Person）优先借 mock U 同 id 者的完整属性对象
      （现场域仍吃 mock 属性；结算 Elo 落回战力榜），无则用 mock 默认值造伪 User；
    - 「带的人」展开成随行访客（编号从 ·1 起，如「小李的球友·1」）；
    - 全员先记「未到」谁报到谁亮；候场空——够一片的人数是「到场」攒出来的
      （setCheck 到场支线自动补片）；片按 courtCount 建空片（差人卡呈现，4.3 空状态）；
    - rules 四件套起笔：双打/队序/连庄上限 3；「谁下」跟推荐走（无人时挂 all 占位）；
    - ledger=出勤底账起笔（正式一人一行、随行行挂 guarantor），startedAt=点亮时刻。 */
  function startLive(g: Game): string | null {
    const lg: Game = { ...g, courts: g.courts ? [...g.courts] : null }; // 现场改动不回写局（派生态归后端）
    const src: User[] = [];
    const ledger: LedgerRow[] = [];
    (g.entries ?? [])
      .filter((e) => e.standing === "formal")
      .forEach((e) => {
        const m = mkPlayer(e.account);
        src.push(m);
        ledger.push({ id: m.id, name: m.name, shadow: m.shadow });
        for (let i = 0; i < (e.bring || 0); i++) {
          const gu = mkGuest(
            `${e.account.nickname.slice(0, 2)}的球友·${i + 1}`,
          );
          src.push(gu);
          ledger.push({
            id: gu.id,
            name: gu.name,
            shadow: true,
            guarantor: e.account.nickname,
          });
        }
      });
    const roster = src.map((u) => {
      u.check = "absent";
      u.skip = 0;
      u.fire = false;
      u.courtSeq = undefined;
      u.tenure = 0;
      return u;
    }); // 全员「未到」开场（§4.1 每人先记未到、谁报到谁亮）
    const L: LiveState = {
      g: lg,
      roster,
      queue: [], // 候场区空：报到的人按先后排进（到场驱动，开场不发牌不报错）
      courts: [],
      history: [],
      round: 0,
      admins: [], // 管理员现场封（不回写 g）
      feed: [`现场已点亮 · 组织者 ${lg.organizer.nickname}`], // 开场首句：轮播在无人动作时也有内容
      startedAt: toIso(new Date()),
      ledger,
      rules: {
        singles: false,
        down: "all", // 占位：syncRules 立刻按推荐重算（无人时推荐「不荐」→ 挂 all）
        downChosen: false,
        pairing: "queue",
        champCap: 3,
      },
      courtSeqNext: 0,
    };
    live.value = L;
    settling.value = null; // 换局清残留结算窗（批1 刺客：上一局的快照不许漏进新局）
    syncCourts(L); // 按片数建空片（差人卡）
    syncRules();
    fillAllCourts(L); // 开场若已够人（不会有）——保持到场驱动同一条路
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
      列表缓存没有该局（或没带全量名单）就拉详情，找不到提示后不动现场；
      已结束的局（done/terminated/cancelled 终态）扫码禁入——散场后二维码不能用（§4.2 本批拦截）。 */
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
    if (["done", "terminated", "cancelled"].includes(g.status)) {
      ui.toast("球局不存在或已结束");
      return;
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

  /** 出勤底账单点补笔（2.2 批2）：只按 id 合并 patch；人已移出（行被保留留痕）时不再复活字段 */
  function touchLedger(id: number, patch: Partial<LedgerRow>): void {
    const row = live.value?.ledger.find((r) => r.id === id);
    if (row) Object.assign(row, patch);
  }

  /** 到场四操作（alpha:1591-1605 setCheck · 2.2 批2§4.2/4.5 口径单一源）：
    - 「到场」请求一律传 'ok'，未到首报且已过开球时刻（局 startAt，ISO）归一成 'late'；
    - 排队位统一队尾（修订④）：迟到排队尾、中途加入排队尾（不再插队首）、早退回来也队尾；
    - 早退=候场队和场上同时清掉 + 落离场时刻（片上缺人打短维持现状，补人归手动换人）；
    - 三种时刻当场落出勤底账；
    - 落坑后自动补片（fillAllCourts：够一片补一片，多片同时要人按片号先后）。
    权限（§4.3）：代办他人收权；自己报到（扫码链路）/早退随时可 */
  function setCheck(id: number, st: CheckStatus): void {
    const L = live.value;
    const p = L ? pById(L, id) : undefined;
    if (!L || !p) return;
    if (id !== U.me.id && !needFull()) return;
    const was = p.check; // 发牌只由「新到场」驱动：已在场的人重报（迟到再点/重复扫）不重发
    if (st === "ok" || st === "late") {
      // 「回来也是队尾」：早退者再到场走中途加入口径（§4.5 禁止回来排队首）
      if (p.check === "left") st = "join";
      else if (
        st === "ok" &&
        p.check === "absent" &&
        Date.now() > new Date(L.g.startAt).getTime()
      )
        st = "late"; // 迟到口径：未到首报且已过开球时刻
    }
    if (st === "late") {
      p.check = "late";
      const i = L.queue.indexOf(id);
      if (i >= 0) L.queue.splice(i, 1);
      L.queue.push(id); // 迟到排队尾（toast 即此承诺）
      ui.toast(`${p.name} 迟到 · 自动排到队尾等一轮`);
    } else if (st === "left") {
      p.check = "left";
      clearFromPlay(L, id);
      ui.toast(`${p.name} 早退 · 已记离场时刻`);
    } else if (st === "join") {
      p.check = "join";
      if (!L.queue.includes(id)) L.queue.push(id); // 修订④：中途加入排到队尾
      ui.toast(`${p.name} 中途加入 · 排到队尾`);
    } else {
      const first = !isArrived(p.check); // 'ok' 只在首报时进队（在场上/队里的人重报不重排）
      p.check = st;
      if (st === "ok") {
        if (first && !L.queue.includes(id)) L.queue.push(id); // 按先后排进候场队=队尾
        ui.toast(`${p.name} 已到场 · 排进候场队`);
      }
    }
    if (st === "left") {
      if (!p.leftAt) p.leftAt = toIso(new Date());
      touchLedger(id, { leftAt: p.leftAt });
      feedPush(`${p.name} 早退 · 已记离场时刻`);
    } else if (st !== "absent" && !p.arriveAt) {
      p.arriveAt = toIso(new Date()); // 几点到：首次到场落账（底账随行补笔）
      touchLedger(id, { arriveAt: p.arriveAt });
    }
    if ((st === "ok" || st === "late" || st === "join") && !isArrived(was)) {
      fillAllCourts(L); // 到场驱动发牌：够一片的人数就自动上片（重复报到不触发）
    }
    syncRules();
  }

  /** 移出名册（2.2 批2§4.3 新动作，收权）：人从名册消失（对付远程扫码幽灵）——
      候场/各片全清，底账行保留只落 removedAt（留痕）；与早退的区别：早退还留在名册 */
  function removeFromRoster(id: number): void {
    if (!needFull()) return;
    const L = live.value;
    const p = L ? pById(L, id) : undefined;
    if (!L || !p) return;
    L.roster = L.roster.filter((x) => x.id !== id);
    clearFromPlay(L, id);
    touchLedger(id, { removedAt: toIso(new Date()) });
    feedPush(`${p.name} 被移出名册`);
    ui.toast(`${p.name} 被移出名册`);
    syncRules();
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

  /** 扫码自签到（2.1·选项A · 2.2 批2§4.4 空降改造）：
      名册没我（空降）→ 直入名册（不再 joinGame——线上满员和候补都不拦、线上名单与候补原样
      不动，名册可超线上上限），带「空降」标记+底账加行+feed 留痕；已在场幂等提示；
      然后统一走 setCheck 到场支线（空降=中途加入排队尾；已报名者按开球时刻归一 ok/late）。
      现场没开或开的是别局 → 先切到目标局；已结束的局被 ensureLive 拦下。 */
  async function arriveMe(gameId: number): Promise<string | null> {
    await ensureLive(gameId);
    const L = live.value;
    if (!L || L.g.id !== gameId) return null; // ensureLive 已 toast 兜底
    const myId = U.me.id;
    let p = pById(L, myId);
    if (!p) {
      p = mkPlayer({ id: myId, nickname: U.me.name, chibi: U.me.chibi }); // 借回 U.me 本体：战力/档案全局联动
      p.check = undefined; // mkPlayer 可能借回共享对象、残留移出前的 check——入册前先重置，防幂等闸误拦（§4.3 对手方：移出后重扫要能回候场）
      p.dropin = true; // 空降标记全场看得到（§4.4）
      L.roster.push(p);
      if (!L.ledger.some((r) => r.id === myId))
        L.ledger.push({ id: myId, name: p.name, dropin: true }); // 同一人一行：移出→重进复用原行，不累积重复行
      feedPush(`${p.name} 空降 · 排到队尾`);
    }
    if (isArrived(p.check)) {
      ui.toast("你已经在场了");
      return null;
    }
    setCheck(myId, p.dropin ? "join" : "ok"); // 到场口径（含迟到归一/队尾/自动发牌/toast）在 setCheck 单点
    return "已到场 · 进候场区";
  }

  /** 得分（alpha:1680-1687 point · 2.4 按片）：先到 N 且净胜 2 才收局——到分不落账，
      只开该片终局弹窗快照；结算窗只拦同片记分，别片照打（4.3 各打各的） */
  function point(courtId: number, side: "a" | "b"): void {
    if (settling.value?.courtId === courtId) return;
    const L = live.value;
    const c = courtOf(courtId);
    if (!L || !c || (!c.A.length && !c.B.length)) return;
    if (side === "a") c.sa++;
    else c.sb++;
    c.last = side;
    if (shouldEnd(c.sa, c.sb, L.g.scoring))
      settling.value = { courtId, sa: c.sa, sb: c.sb }; // 片不动，等弹窗确认
  }

  /** 误记撤回一分（alpha:1676-1679 undoPoint · 按片回退该片最后得分方） */
  function undoPoint(courtId: number): void {
    if (settling.value?.courtId === courtId) return;
    const c = courtOf(courtId);
    if (!c) return;
    const r = undoScore(c.sa, c.sb, c.last);
    c.sa = r.sa;
    c.sb = r.sb;
  }

  /** 记分已清零 · 重开一盘（2.1 对局卡工具行 · 按片；§4.8 收权——球友只能 ±1） */
  function clearScore(courtId: number): void {
    const c = courtOf(courtId);
    if (!c || !needFull()) return;
    c.sa = 0;
    c.sb = 0;
    c.last = undefined;
    if (settling.value?.courtId === courtId) settling.value = null;
    ui.toast("记分已清零 · 重开一盘");
  }

  /** 手动开终局结算（按片；§4.8 收权）：该片在打才开，快照当前比分 */
  function openSettle(courtId: number): void {
    const c = courtOf(courtId);
    if (!c || (!c.A.length && !c.B.length) || !needFull()) return;
    settling.value = { courtId, sa: c.sa, sb: c.sb };
  }

  /** 关结算弹窗不落账：比分保留在该片 */
  function closeSettle(): void {
    settling.value = null;
  }

  /** 确认终局 · 排下一场（2.1 §5 · 2.4 各片各排各的）：
      幂等闸先行（settling.courtId 对不上直接 return——两端并发确认同一场只落一次账、不双排，
      B2）；结算 = settleElo 落账（访客同规，无 shadow 留场过滤）→ endMatch 接管轮换
      （谁下/连庄/资历真值在引擎）→ history/feed 留痕 → 推荐跟随。
      §4.8 收权：球友只能看结算窗（确认按钮置灰），绕过画面直调也在此拒。撒花由页面层 watch。 */
  function confirmSettle(
    courtId: number,
    winA: boolean,
    sa: number,
    sb: number,
  ): void {
    if (settling.value?.courtId !== courtId) return; // 幂等闸：只落一次账
    const L = live.value;
    const c = courtOf(courtId);
    if (!L || !c || !needFull()) return;
    c.sa = sa;
    c.sb = sb;
    c.last = undefined;
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
    feedPush(`${wNm} 拿下 ${sa}:${sb}`);
    L.round++;
    endMatch(L, courtId, winA ? "A" : "B"); // 轮换真值：谁下/连庄/资历/补坑全在引擎
    syncRules();
    settling.value = null;
    ui.toast("积分落账 · 下一场已排好");
  }

  /** 取消对局（2.1 §2 · 按片，收权）：该片 A/B 全回队尾（现行回流语义）、片清空，
      fillCourt 立刻按候场首重发这片（无人可补则差人卡）——不计积分 */
  function cancelMatch(courtId: number): void {
    const L = live.value;
    const c = courtOf(courtId);
    if (!L || !c || (!c.A.length && !c.B.length) || !needFull()) return;
    L.queue.push(...c.A, ...c.B);
    for (const id of [...c.A, ...c.B]) {
      const p = pById(L, id);
      if (p) {
        p.tenure = 0;
        p.courtSeq = undefined;
      }
    }
    c.A = [];
    c.B = [];
    c.sa = 0;
    c.sb = 0;
    c.last = undefined;
    c.streakA = 0;
    c.streakB = 0;
    if (settling.value?.courtId === courtId) settling.value = null;
    fillCourt(L, c);
    syncRules();
    ui.toast("对局已取消 · 人回流候场 · 不计积分");
  }

  /** 换人（2.1 §4 · 2.2 §4.9 球友开放 · 2.4 §4.9 真值）：场上 outId 原位顶坑给候场 inId——
      换下者排队尾、资历注销；换上者 courtSeq 新发、资历从换上起算；该半边连庄不动。
      这片下一场照常自动发牌，不推翻手动阵容（endMatch 按资历算，不重排留下的半边）。 */
  function swapPlayers(outId: number, inId: number): void {
    const L = live.value;
    if (!L) return;
    const court = L.courts.find((c) => c.A.includes(outId) || c.B.includes(outId));
    if (!court) return; // out 不在场上：无坑可换
    const side = court.A.includes(outId) ? "A" : "B";
    court[side][court[side].indexOf(outId)] = inId; // 原位顶坑
    const j = L.queue.indexOf(inId);
    if (j >= 0) L.queue.splice(j, 1);
    L.queue.push(outId); // 换下排队尾（§0.2 裁定）
    const outP = pById(L, outId);
    if (outP) {
      outP.tenure = 0;
      outP.courtSeq = undefined;
    }
    const inP = pById(L, inId);
    if (inP) {
      L.courtSeqNext += 1;
      inP.courtSeq = L.courtSeqNext;
      inP.tenure = 0;
    }
    syncRules();
    ui.toast("已换人 · 对阵重排");
  }

  /** 带访客（2.1 §1 组织者代办 · 收权）：与 startLive 随行访客同法；编号从 ·1 起；
      底账加行挂担保人（§4.14 访客谁带的） */
  function addGuests(count: number, name: string, introducer: User): void {
    const L = live.value;
    if (!L || count <= 0 || !needFull()) return;
    for (let i = 0; i < count; i++) {
      const g = mkGuest(
        !name
          ? `${introducer.name.slice(0, 2)}的球友`
          : count > 1
            ? `${name}·${i + 1}`
            : name,
      );
      g.check = "join";
      L.roster.push(g);
      L.queue.push(g.id); // 队尾
      L.ledger.push({
        id: g.id,
        name: g.name,
        shadow: true,
        guarantor: introducer.name,
      });
    }
    syncRules();
    ui.toast(`已带 ${count} 位访客 · 进候场区`);
  }

  /** 改分制（2.1 §3：当场生效——下一记分的收局判定即用新值；只落现场克隆，不回写局；收权动作） */
  function setRuleScore(v: number): void {
    const L = live.value;
    if (!L || !needFull()) return;
    L.g.scoring = v;
    ui.toast(`分制已改为 ${v} 分 · 当场生效`);
  }

  /** 改轮换四件套（2.4 §4.1/4.7，收权）：点选即生效；在打对局照旧打完，下一场起按新规。
      - 组合回落：单打×1/2/3人下不合法 → down 自动落回全上全下（如实显示；自动回落不算自选）；
      - 切到输家下：全片连庄清零重算（场上的人不是赢上来的，4.7-2）；
      - 自选「谁下」即冻结推荐跟随（downChosen=true，此后推荐只亮标签）；
      - 连庄上限改动即时生效（到点判定在 endMatch 读现值）；
      - 换单双打：空片当场转新格式并补满开赛（在打片照旧打完，过渡在 endMatch ③）。 */
  function setRules(patch: Partial<RotationRules>): void {
    const L = live.value;
    if (!L || !needFull()) return;
    const prevDown = L.rules.down;
    Object.assign(L.rules, patch);
    if (L.rules.singles && ["n1", "n2", "n3"].includes(L.rules.down)) {
      L.rules.down = "all"; // 组合回落（4.7-4，含两人各改一项并发拼出来的）
    }
    if (patch.down !== undefined && patch.down === L.rules.down)
      L.rules.downChosen = true; // 自选冻结；回落后的 all ≠ 所选 → 不算自选
    if (prevDown !== "loser" && L.rules.down === "loser")
      L.courts.forEach((c) => {
        c.streakA = 0;
        c.streakB = 0;
      });
    if (patch.singles !== undefined) {
      // 空片格式传导（§5 边界：双打空片差人时改单打 → 2 人即开赛）：差人卡按 rules.singles
      // 显示，但 fillCourt 按 court.singles 取人——不传导会静默 no-op；在打片不动（过渡在 endMatch ③）
      for (const c of L.courts) if (!c.A.length && !c.B.length) c.singles = L.rules.singles;
      fillAllCourts(L);
    }
    syncRules();
    ui.toast("规则已更新 · 下一场起按新规");
  }

  /** 旧三模式过渡桥（2.4 §0.4 映射，批2 保留旧 RulesSheet 可用、批3 随新抽屉删）：
      赢家留场=输家下+队序 / 纯粹轮转=全上全下 / 均衡配对=全上全下+均衡分边 */
  function setRuleMode(m: CourtMode): void {
    const L = live.value;
    if (!L || !needFull()) return;
    L.g.rotation = m; // 旧抽屉 seg 显示位（g.rotation 契约不动，3.2 修订时废）
    const patch: Partial<RotationRules> =
      m === "winner"
        ? { down: "loser", pairing: "queue" }
        : m === "balance"
          ? { down: "all", pairing: "balance" }
          : { down: "all" };
    setRules(patch); // toast/冻结/连庄清零都在 setRules 单点
  }

  /** 场地输入（2.1 顶条 · 2.4 并行口径）：校验至少 1 片且 ≥ 非空片数（在打的片不能收）；
      过 → 写 g.courts + syncCourts（补空片/删空片/重挂场地名）+ 补满（收权动作） */
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
    syncCourts(L);
    fillAllCourts(L);
    syncRules();
    ui.toast(`场地已更新：${parts.join("、")}`);
    return true;
  }

  /** 自动排阵（2.1 §4 · 2.4 按片）：fillAllCourts 补所有空片（多片同时要人按片号先后）（收权动作） */
  function autoDeal(): void {
    const L = live.value;
    if (!L || !needFull()) return;
    fillAllCourts(L);
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
    advice,
    myRound,
    isFullPower,
    isAdmin,
    needFull,
    byId,
    startLive,
    ensureLive,
    setCheck,
    arriveMe,
    addGuests,
    removeFromRoster,
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
    setRules,
    setRuleMode,
    setCourtsInput,
    autoDeal,
  };
});
