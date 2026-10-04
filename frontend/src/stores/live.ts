/* 现场 store（alpha:1471-1530 startLive/avail/fillCourts/nextMatch · 1591-1648 setCheck · 1680-1728 point）
   2.1 打球页改版（批1 数据层）：终局从「到分自动落账 + WinPopup」改为 confirm-before-settle——
   point 到分只落 settling 快照，confirmSettle 才落账并自动排下一场；WinPopup/endMatch/newRound/toggleMine 退役。
   硬约束：不触碰任何 uni.*；发牌引擎在 utils/rotate.ts（纯函数，live 状态作参数）。
   roster 直接引用球员对象（alpha:1474）：结算落回的与 mock U / 战力榜是同一批对象，
   reactive 对同一原始目标返回同一代理 —— 战力页自动联动。 */
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { DEFAULT_MOCK_CHECKIN_COUNT, U } from '@/api';
import type { CheckStatus, CourtMode, LiveState, User } from '@/api/types';
import { settleElo } from '@/utils/elo';
import { DRESS_RANGES } from '@/utils/chibi';
import { fillCourts, nextMatch, pById } from '@/utils/rotate';
import { shouldEnd, undoScore } from '@/utils/score';
import { MODE_NAMES } from '@/utils/format';
import { useGameStore } from './game';
import { useUiStore } from './ui';

/** 访客 id 单调发号（批1 刺客：Math.random 撞号会让两位访客在 roster/swap 里互相串线） */
let guestSeq = 0;

/** 「算到场」谓词单一源（候场条状态文案与二维码浮层在场人数共用）：
    ok 正常 / late 迟到已到 / join 中途加入；absent 未到、left 早退不算 */
export const isArrived = (c?: CheckStatus): boolean => c === 'ok' || c === 'late' || c === 'join';

export const useLiveStore = defineStore('live', () => {
  /** alpha:805 let live=null —— 进行中的现场状态；TabBar 的 LIVE 红点（alpha:1487 #live-dot-nav） */
  const live = ref<LiveState | null>(null);
  const hasLive = computed(() => !!live.value);

  /** 终局结算待确认快照（2.1 §5：到分弹结算窗，点胜方/改比分/预览±积分，确认才落账）。
      非空 = EndSettleModal 开着；cur 保持不动（比分还在记分板上，closeSettle 可回来重打） */
  const settling = ref<{ sa: number; sb: number } | null>(null);

  /** 我还有几轮上场（2.1 §3 候场区「还有 N 轮到我」）：ceil((4*待开片数 + 我的队列位 + 1) / 4)。
      待开片的人排我前面要计入；cur 的人结算后回队尾、不挡我；不在队列（在打/不在场）→ null */
  const myRound = computed<number | null>(() => {
    const L = live.value;
    if (!L) return null;
    const idx = L.queue.indexOf(U.me.id);
    if (idx < 0) return null;
    return Math.ceil((4 * L.courts.length + idx + 1) / 4);
  });

  /** 开始打球（alpha:1471-1490 逐字口径）：
    - 现场名单直接引用球员对象：Elo 变动实时落回战力榜（5.1 同一份）；
    - 报名里「带的人」在此展开成随行访客（随机 chibi、费用照常 · Elo 半权重不进榜）；
    - 前 9 人 ok，其余 absent。 */
  function startLive(id: number): string | null {
    const g = useGameStore().games.find((x) => x.id === id);
    if (!g) return null;
    g.status = 'live';
    const src: User[] = [];
    g.joined.forEach((e) => {
      src.push(e.u);
      for (let i = 0; i < (e.bring || 0); i++) {
        src.push(mkGuest(e.u.name.slice(0, 2) + '的球友'));
      }
    });
    const roster = src.map((u, i) => { u.check = i < DEFAULT_MOCK_CHECKIN_COUNT ? 'ok' : 'absent'; u.skip = 0; u.fire = false; return u; }); // alpha:1482（skip 随 2.1 改 number：0=不在歇）
    const L: LiveState = {
      g, roster,
      queue: roster.filter((p) => p.check === 'ok').map((p) => p.id), // alpha:1483
      courts: [], history: [], round: 0, cur: null, lastWinners: null,
    };
    live.value = L;
    settling.value = null; // 换局清残留结算窗（批1 刺客 Blocker：上一局的快照不许漏进新局）
    fillCourts(L);   // alpha:1485
    nextMatch(L);    // alpha:1486
    const msg = '球局开始 · 现场已点亮';
    useUiStore().toast(msg);
    return msg;
  }

  /** 造一位随行访客（startLive 报名展开与组织者「带访客」addGuests 同法）：
      shadow · elo 1200 计入期望 · 随机 chibi 引用 chibi.ts 单一源 DRESS_RANGES */
  function mkGuest(name: string): User {
    return {
      id: 9000 + ++guestSeq,
      name,
      elo: 1200, play: 0, win: 0, month: 0, shadow: true,
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

  /** 到场四操作（alpha:1591-1605 setCheck）：迟到自动排队尾 / 早退清队列清场上 / 中途加入进队首 */
  function setCheck(id: number, st: CheckStatus): void {
    const L = live.value;
    const p = L ? pById(L, id) : undefined;
    if (!L || !p) return;
    if (st === 'late' && p.check !== 'late') {
      p.check = 'late';
      const i = L.queue.indexOf(id);
      if (i >= 0) L.queue.splice(i, 1);
      L.queue.push(id); // 迟到排队尾（toast 即此承诺）；缺席者原本不在队里，到场也从队尾进——下一轮发牌即可上场（avail 放行 late）
      useUiStore().toast(`${p.name} 迟到 · 自动排到队尾等一轮`);
    } else if (st === 'left') {
      p.check = 'left';
      L.queue = L.queue.filter((x) => x !== id);
      L.courts.forEach((c) => { c.A = c.A.filter((x) => x !== id); c.B = c.B.filter((x) => x !== id); });
      if (L.cur) { L.cur.A = L.cur.A.filter((x) => x !== id); L.cur.B = L.cur.B.filter((x) => x !== id); }
      useUiStore().toast(`${p.name} 早退 · 名单已记录`);
    } else if (st === 'join') {
      p.check = 'join'; if (!L.queue.includes(id)) L.queue.unshift(id);
      useUiStore().toast(`${p.name} 中途加入 · 排进队首`);
    } else p.check = st;
  }

  /** 歇两轮 / 连战（alpha:1629-1636 toggleMine 的泛化，2.1 §3 候场区点人可设）：
      互斥；歇两轮=2（发牌递减、归 0 归队，见 rotate.ts avail）；连战排到队首。任意人可设（组织者兜底 + 自己） */
  function togglePerson(id: number, k: 'skip' | 'fire'): void {
    const L = live.value;
    const p = L ? pById(L, id) : undefined;
    if (!L || !p) return;
    if (k === 'skip') {
      p.skip = p.skip ? 0 : 2;        // 开=歇两轮，关=0
      if (p.skip) p.fire = false;
      useUiStore().toast(p.skip ? '已歇两轮 · 发牌自动跳过' : '取消歇');
    } else {
      p.fire = !p.fire;
      if (p.fire) p.skip = 0;
      if (p.fire) { const i = L.queue.indexOf(id); if (i >= 0) { L.queue.splice(i, 1); L.queue.unshift(id); } }
      useUiStore().toast(p.fire ? '连战 · 排到队首' : '取消连战');
    }
  }

  /** 扫码自签到（2.1·选项A：到场一律是注册球友，无访客通道）。
      名册没我（空降）→ 先报名进局再把人放进名册；然后标「中途加入」排进队首。
      现场没开或开的是别局 → 先切到目标局（扫码直达场景）。 */
  function arriveMe(gameId: number): string | null {
    const g = useGameStore().games.find((x) => x.id === gameId);
    if (!g) {
      useUiStore().toast('球局不存在或已结束');
      return null;
    }
    if (!live.value || live.value.g.id !== gameId) startLive(gameId);
    const L = live.value!;
    const myId = U.me.id;
    let p = pById(L, myId);
    if (!p) {
      useGameStore().joinGame(gameId, 0); // 空降：先成为报名球友（名片建号已在前一步完成）
      L.roster.push(U.me);                // 名册直接引用「我」对象：战力/档案全局联动（alpha:1474 同法）
      p = U.me;
    }
    if (p.check === 'ok' || p.check === 'join') {
      useUiStore().toast('你已经在场了');
      return null;
    }
    setCheck(myId, 'join'); // setCheck 内置 toast「中途加入 · 排进队首」
    return '已到场 · 进候场区';
  }

  /** 得分（alpha:1680-1687 point）：先到 N 且净胜 2 才收局——到分不落账，只开终局弹窗快照（2.1 §5） */
  function point(side: 'a' | 'b'): void {
    if (settling.value) return; // 结算窗开着不许继续记分（批1 刺客：快照与记分板会劈叉）
    const L = live.value;
    const c = L?.cur;
    if (!L || !c) return;
    if (side === 'a') c.sa++; else c.sb++;
    L.last = side;
    if (shouldEnd(c.sa, c.sb, L.g.score)) settling.value = { sa: c.sa, sb: c.sb }; // cur 不动，等弹窗确认
  }

  /** 误记撤回一分（alpha:1676-1679 undoPoint）：按最后得分方回退（score.ts 保留 alpha 的 else-if quirk） */
  function undoPoint(): void {
    if (settling.value) return; // 结算窗开着不撤分（与 point 的拦截对称，防快照与记分板劈叉）
    const L = live.value;
    const c = L?.cur;
    if (!L || !c) return;
    const r = undoScore(c.sa, c.sb, L.last);
    c.sa = r.sa;
    c.sb = r.sb;
  }

  /** 记分已清零 · 重开一盘（2.1 对局卡工具行）：比分与最后得分方一起清，结算窗随比分一并作废 */
  function clearScore(): void {
    const L = live.value;
    const c = L?.cur;
    if (!L || !c) return;
    c.sa = 0; c.sb = 0;
    L.last = undefined;
    settling.value = null; // 快照对着旧比分，重开一盘后不再有效
    useUiStore().toast('记分已清零 · 重开一盘');
  }

  /** 手动开终局结算（对局卡「终局结算」钮）：cur 存在才开，快照当前比分 */
  function openSettle(): void {
    const L = live.value;
    if (!L?.cur) return;
    settling.value = { sa: L.cur.sa, sb: L.cur.sb };
  }

  /** 关结算弹窗不落账：比分保留在 cur，可回来重打/重计 */
  function closeSettle(): void {
    settling.value = null;
  }

  /** 确认终局 · 排下一场（2.1 §5，旧 endMatch 口径 + 自动排场）：
      winA/sa/sb 由弹窗传入（胜方可改、比分可改），不只看 sa>sb；
      结算 = settleElo 落账（roster 与 mock U 同一批对象 → 战力页联动）、
      month/play/win/last5、history.unshift、lastWinners、败者回队尾 + 非 winner 模式胜者也回队；
      然后 round++ + fillCourts + nextMatch 排下一场。撒花由页面层 watch history 做（store 不管）。 */
  function confirmSettle(winA: boolean, sa: number, sb: number): void {
    const L = live.value;
    const c = L?.cur;
    if (!L || !c) return;
    c.sa = sa; c.sb = sb;                        // 弹窗改过的比分写回记分板（history 同源）
    const winners = winA ? c.A : c.B;
    const losers = winA ? c.B : c.A;
    const byId = (id: number): User => pById(L, id)!;
    const results = settleElo(winners.map(byId), losers.map(byId));
    winners.concat(losers).forEach((id, i) => {
      const p = byId(id);
      const { up, d, elo } = results[i];
      p.elo = elo;                                // 地板 400 已在 settleElo 内处理
      p.month = (p.month || 0) + d;               // alpha:1705
      p.play++;                                   // alpha:1706
      if (up && !p.shadow) p.win++;
      if (p.id === U.me.id && p.last5) p.last5 = [...p.last5.slice(1), up ? 'W' : 'L']; // alpha:1707 仅我滚动近5场（alpha 原样）
      // ±积分预览行（WinChange 形状）由 EndSettleModal 弹窗侧自调 settleElo 组装，落账不走它
    });
    const wNm = winners.map((id) => byId(id).name).join(' & '); // alpha:1709
    L.history.unshift({ names: wNm, sa, sb });
    L.lastWinners = winners.filter((id) => !byId(id).shadow);   // alpha:1711 随行不进胜者留场
    // 队列：败者回队尾；胜者仅在头片空缺时留场，否则同样回队（alpha:1712-1714）
    L.queue.push(...losers);
    if (L.g.mode !== 'winner' || L.courts.length > 0) L.queue.push(...winners);
    L.cur = null;
    L.round++;                    // 排下一场（确认即自动，不再有「开下一轮」钮）
    fillCourts(L);
    nextMatch(L);
    settling.value = null;
    useUiStore().toast('积分落账 · 下一场已排好');
  }

  /** 取消对局（2.1 §2「也留取消对局——人回流候场、不计积分」）：cur 的 A/B 全回队尾，
      cur=null、nextMatch 有待开片则顶上；结算弹窗随对局一并关（无 cur 可结） */
  function cancelMatch(): void {
    const L = live.value;
    const c = L?.cur;
    if (!L || !c) return;
    L.queue.push(...c.A, ...c.B);
    L.cur = null;
    settling.value = null;
    nextMatch(L);
    useUiStore().toast('对局已取消 · 人回流候场 · 不计积分');
  }

  /** 换人（2.1 §4 组织者兜底：场上↔候场互换）：cur 与待开片的 A/B 里 outId→inId；
      候场侧 inId 的坑由 outId 顶（位置互换，队列次序不乱） */
  function swapPlayers(outId: number, inId: number): void {
    const L = live.value;
    if (!L) return;
    const swap = (arr: number[]): void => { const i = arr.indexOf(outId); if (i >= 0) arr[i] = inId; };
    if (L.cur) { swap(L.cur.A); swap(L.cur.B); }
    L.courts.forEach((c) => { swap(c.A); swap(c.B); });
    const j = L.queue.indexOf(inId);
    if (j >= 0) L.queue[j] = outId;
    useUiStore().toast('已换人 · 对阵重排');
  }

  /** 带访客（2.1 §1 组织者代办：代人带客，访客直接进候场区）：
      与 startLive 随行访客同法（shadow · 半权重不进榜 · 随机 chibi）。
      命名：空名 → 「介绍人前两字+的球友」；非空且多位 → name·2、name·3 依次（第一位带序号起排）；
      check='join' 但排队尾（setCheck 的 join 才排队首——访客不该插熟人的队），发牌随 avail 放行 join */
  function addGuests(count: number, name: string, introducer: User): void {
    const L = live.value;
    if (!L || count <= 0) return;
    for (let i = 0; i < count; i++) {
      const g = mkGuest(!name ? `${introducer.name.slice(0, 2)}的球友` : count > 1 ? `${name}·${i + 2}` : name);
      g.check = 'join';
      L.roster.push(g);
      L.queue.push(g.id); // 队尾
    }
    useUiStore().toast(`已带 ${count} 位访客 · 进候场区`);
  }

  /** 改分制（2.1 §3 辅助·规则修改：当场生效——下一记分的收局判定即用新值） */
  function setRuleScore(v: number): void {
    const L = live.value;
    if (!L) return;
    L.g.score = v;
    useUiStore().toast(`分制已改为 ${v} 分 · 当场生效`);
  }

  /** 改轮换模式（2.1 §3：下一场生效——只影响之后的 fillCourts 发牌，在场对局不动） */
  function setRuleMode(m: CourtMode): void {
    const L = live.value;
    if (!L) return;
    L.g.mode = m;
    useUiStore().toast(`轮换模式已改为「${MODE_NAMES[m]}」· 下一场生效`);
  }

  /** 场地输入（2.1 顶条：『3、4 / 3,4 / 3 4 / 3号、4号』→ ['3号','4号']，无「号」补上）。
      校验：至少 1 片，且 ≥ 在打(cur)+待开(courts)——在打和待开的场地不能收。
      过 → 写 g.booked + fillCourts（按新片数补片）→ true；不过 → toast 提示 → false */
  function setCourtsInput(text: string): boolean {
    const L = live.value;
    if (!L) return false;
    const parts = text
      .split(/[、,，\s]+/)
      .map((s) => s.trim())
      .filter((s) => /^\d+号?$/.test(s))          // 只认「N / N号」形，其余 token 丢弃
      .map((s) => (s.endsWith('号') ? s : `${s}号`));
    const need = (L.cur ? 1 : 0) + L.courts.length;
    if (parts.length < 1) {
      useUiStore().toast('至少要有 1 片场地');
      return false;
    }
    if (parts.length < need) {
      useUiStore().toast('在打 + 待开的场地不能收');
      return false;
    }
    L.g.booked = parts;
    fillCourts(L);
    useUiStore().toast(`场地已更新：${parts.join('、')}`);
    return true;
  }

  /** 自动排阵（2.1 §4：空闲卡「一键派四人下场」）：fillCourts 发牌；没有在打场次则顶上一场 */
  function autoDeal(): void {
    const L = live.value;
    if (!L) return;
    fillCourts(L);
    if (!L.cur) nextMatch(L);
    useUiStore().toast('牌已发 · 按当前规则排好');
  }

  /** 名册按找（roster 查不到兜底「—」占位：视图层 byId 的共享口径——
      原 CourtCard/Scoreboard 各自的兜底副本随 2.1 改版收敛于此，打球页组件统一走这里） */
  function byId(id: number): User {
    const L = live.value;
    return (L ? pById(L, id) : undefined) ?? { id: -1, name: '—', elo: 0, play: 0, win: 0, month: 0, chibi: {} };
  }

  return {
    live, hasLive, settling, myRound,
    byId,
    startLive, setCheck, arriveMe, addGuests,
    point, undoPoint, clearScore,
    openSettle, closeSettle, confirmSettle, cancelMatch,
    togglePerson, swapPlayers,
    setRuleScore, setRuleMode, setCourtsInput, autoDeal,
  };
});
