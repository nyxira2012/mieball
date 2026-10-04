/* 现场 store（alpha:1471-1530 startLive/avail/fillCourts/nextMatch · 1591-1648 setCheck/toggleMine/newRound · 1680-1728 point/endMatch）
   硬约束：不触碰任何 uni.*；发牌引擎在 utils/rotate.ts（纯函数，live 状态作参数）。
   roster 直接引用球员对象（alpha:1474）：结算落回的与 mock U / 战力榜是同一批对象，
   reactive 对同一原始目标返回同一代理 —— 战力页自动联动。 */
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import type { CheckStatus, LiveState, User, WinChange } from '@/api/types';
import { settleElo } from '@/utils/elo';
import { fillCourts, nextMatch, pById } from '@/utils/rotate';
import { shouldEnd, undoScore } from '@/utils/score';
import { useGameStore } from './game';
import { useUiStore } from './ui';

export const useLiveStore = defineStore('live', () => {
  /** alpha:805 let live=null —— 进行中的现场状态；TabBar 的 LIVE 红点（alpha:1487 #live-dot-nav） */
  const live = ref<LiveState | null>(null);
  const hasLive = computed(() => !!live.value);

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
        src.push({
          id: 9000 + Math.floor(Math.random() * 999),
          name: `${e.u.name.slice(0, 2)}的球友`,
          elo: 1200, play: 0, win: 0, month: 0, shadow: true,
          /* 随机值域 = user.ts DRESS_RANGES（skin4/hair6/hc6/shirt8/face4/acc3），同步改 —— 值域扩了这里会越界出图 */
          chibi: {
            skin: Math.floor(Math.random() * 4), hair: Math.floor(Math.random() * 6), hc: Math.floor(Math.random() * 6),
            shirt: Math.floor(Math.random() * 8), face: Math.floor(Math.random() * 4), acc: Math.floor(Math.random() * 3),
          },
        });
      }
    });
    const roster = src.map((u, i) => { u.check = i < 9 ? 'ok' : 'absent'; u.skip = false; u.fire = false; return u; }); // alpha:1482
    const L: LiveState = {
      g, roster,
      queue: roster.filter((p) => p.check === 'ok').map((p) => p.id), // alpha:1483
      courts: [], history: [], round: 0, cur: null, lastWinners: null,
    };
    live.value = L;
    fillCourts(L);   // alpha:1485
    nextMatch(L);    // alpha:1486
    const msg = '球局开始 · 现场已点亮';
    useUiStore().toast(msg);
    return msg;
  }

  /** 到场四操作（alpha:1591-1605 setCheck）：迟到自动排队尾 / 早退清队列清场上 / 中途加入进队首 */
  function setCheck(id: number, st: CheckStatus): void {
    const L = live.value;
    const p = L ? pById(L, id) : undefined;
    if (!L || !p) return;
    if (st === 'late' && p.check !== 'late') {
      p.check = 'late';
      const i = L.queue.indexOf(id); if (i >= 0) { L.queue.splice(i, 1); L.queue.push(id); } // 迟到排队尾
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

  /** 歇一轮 / 连战（alpha:1629-1636 toggleMine）：互斥；连战排到队首 */
  function toggleMine(k: 'skip' | 'fire'): void {
    const L = live.value;
    const m = L ? pById(L, 0) : undefined;
    if (!L || !m) return;
    if (k === 'skip') { m.skip = !m.skip; if (m.skip) m.fire = false; }
    else {
      m.fire = !m.fire; if (m.fire) m.skip = false;
      if (m.fire) { const i = L.queue.indexOf(0); if (i >= 0) { L.queue.splice(i, 1); L.queue.unshift(0); } }
    }
    useUiStore().toast(k === 'skip' ? (m.skip ? '已标记歇一轮 · 下轮跳过你' : '取消歇一轮') : (m.fire ? '连战模式 · 排到队首' : '取消连战'));
  }

  /** 开下一轮（alpha:1637-1648 newRound）：未打完场次退回重排（人回队尾）。撒花由页面层 Confetti 做。 */
  function newRound(): void {
    const L = live.value;
    if (!L) return;
    L.round++;
    if (L.cur) L.queue.push(...L.cur.A, ...L.cur.B); // 未打完就开下一轮：这片退回待打，人回队尾重排
    L.cur = null;
    fillCourts(L);
    nextMatch(L);
    useUiStore().toast(`第 ${L.round + 1} 轮 · 牌已发`);
  }

  /** 得分（alpha:1680-1687 point）：先到 N 且净胜 2 才收局 */
  function point(side: 'a' | 'b'): void {
    const L = live.value;
    const c = L?.cur;
    if (!L || !c) return;
    if (side === 'a') c.sa++; else c.sb++;
    L.last = side;
    if (shouldEnd(c.sa, c.sb, L.g.score)) endMatch(); // alpha:1686
  }

  /** 误记撤回一分（alpha:1676-1679 undoPoint）：按最后得分方回退（score.ts 保留 alpha 的 else-if quirk） */
  function undoPoint(): void {
    const L = live.value;
    const c = L?.cur;
    if (!L || !c) return;
    const r = undoScore(c.sa, c.sb, L.last);
    c.sa = r.sa;
    c.sb = r.sb;
  }

  /** 收局结算（alpha:1688-1728 endMatch）：调 utils/elo 的 settleElo，把 delta/新分落回 roster。
    roster 与 mock U 是同一批对象 → 战力页（榜单/档案/我的）联动；
    随行访客不在 U 里、只存在于现场（半权重、不进榜）。 */
  function endMatch(): void {
    const L = live.value;
    const c = L?.cur;
    if (!L || !c) return;
    const winA = c.sa > c.sb;
    const winners = winA ? c.A : c.B;
    const losers = winA ? c.B : c.A;
    const byId = (id: number): User => pById(L, id)!;
    const results = settleElo(winners.map(byId), losers.map(byId));
    const chg: WinChange[] = [];
    winners.concat(losers).forEach((id, i) => {
      const p = byId(id);
      const { up, d, elo } = results[i];
      p.elo = elo;                                // 地板 400 已在 settleElo 内处理
      p.month = (p.month || 0) + d;               // alpha:1705
      p.play++;                                   // alpha:1706
      if (up && !p.shadow) p.win++;
      if (p.id === 0 && p.last5) p.last5 = [...p.last5.slice(1), up ? 'W' : 'L']; // alpha:1707 仅我滚动近5场（alpha 原样）
      chg.push({ name: p.name, up, d });
    });
    const wNm = winners.map((id) => byId(id).name).join(' & '); // alpha:1709
    L.history.unshift({ names: wNm, sa: c.sa, sb: c.sb });
    L.lastWinners = winners.filter((id) => !byId(id).shadow);   // alpha:1711 随行不进胜者留场
    // 队列：败者回队尾；胜者仅在头片空缺时留场，否则同样回队（alpha:1712-1714）
    L.queue.push(...losers);
    if (L.g.mode !== 'winner' || L.courts.length > 0) L.queue.push(...winners);
    L.cur = null;
    useUiStore().showWin({ names: wNm, sa: c.sa, sb: c.sb, chg }); // WinPopup 消费（alpha:1716-1725）
  }

  return { live, hasLive, startLive, setCheck, toggleMine, newRound, point, undoPoint, endMatch };
});
