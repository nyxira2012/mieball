import { describe, expect, it } from 'vitest';
import type { Game, LiveState, User } from '@/api/types';
import { avail, fillCourts, nextMatch, pById } from '@/utils/rotate';

let seq = 0;
function mkP(elo: number, extra: Partial<User> = {}): User {
  seq += 1;
  return { id: seq, name: `P${seq}`, elo, play: 1, win: 0, month: 0, chibi: {}, check: 'ok', skip: false, fire: false, ...extra };
}
function mkLive(mode: Game['mode'], players: User[], opts: Partial<LiveState> = {}): LiveState {
  return {
    g: {
      id: 1, organizer: players[0] ?? mkP(1500), t: '今晚 19:00', d: '今天', tb: 'tonight', area: '工体', dur: 2,
      deadline: '今天 17:00', loc: 'x', name: 't', min: 4, cap: 8, fee: 100,
      joined: [], wait: [], status: 'live', score: 11, mode, lateRule: false,
    },
    roster: players,
    queue: players.map((p) => p.id),
    courts: [], history: [], round: 0, cur: null, lastWinners: null,
    ...opts,
  };
}

describe('avail：skip 消耗型徽章、排除非 ok（alpha:1492-1500）', () => {
  it('歇一轮本轮跳过且徽章被消耗；迟到/早退/未到不进池', () => {
    const a = mkP(1500, { skip: true });
    const b = mkP(1600, { check: 'late' });
    const c = mkP(1400);
    const d = mkP(1300);
    const live = mkLive('rotate', [a, b, c, d]);
    expect(avail(live)).toEqual([c.id, d.id]);
    expect(a.skip).toBe(false); // 徽章消耗
    // 再发一轮：a 恢复可上场
    expect(avail(live)).toEqual([a.id, c.id, d.id]);
  });
});

describe('fillCourts（alpha:1501-1523）', () => {
  it('balance 蛇形按分降序：A=[首,末] B=[二,三]', () => {
    const ps = [1800, 1700, 1600, 1500, 1400, 1300, 1200, 1100].map((e) => mkP(e));
    const live = mkLive('balance', ps);
    live.g.cap = 8; // <12 → 两片
    fillCourts(live);
    expect(live.courts.map((c) => c.A)).toEqual([[ps[0].id, ps[3].id], [ps[4].id, ps[7].id]]);
    expect(live.courts.map((c) => c.B)).toEqual([[ps[1].id, ps[2].id], [ps[5].id, ps[6].id]]);
    expect(live.queue).toEqual([]); // 全部上场
  });

  it('rotate 顺序发牌：A=[一二] B=[三四]', () => {
    const ps = [1500, 1510, 1520, 1530, 1540, 1550, 1560, 1570].map((e) => mkP(e));
    const live = mkLive('rotate', ps);
    fillCourts(live);
    expect(live.courts[0]).toEqual({ A: [ps[0].id, ps[1].id], B: [ps[2].id, ps[3].id] });
    expect(live.courts[1]).toEqual({ A: [ps[4].id, ps[5].id], B: [ps[6].id, ps[7].id] });
  });

  it('winner 模式：胜者留场仅头片空缺时生效，挑战者是池子里前两位', () => {
    const w1 = mkP(1700), w2 = mkP(1600); // 上轮胜者（不在队列）
    const ps = [1500, 1490, 1480, 1470, 1460, 1450, 1440, 1430].map((e) => mkP(e));
    const live = mkLive('winner', ps, { lastWinners: [w1.id, w2.id] });
    fillCourts(live);
    expect(live.courts[0]).toEqual({ A: [w1.id, w2.id], B: [ps[0].id, ps[1].id] });
    expect(live.courts[1]).toEqual({ A: [ps[2].id, ps[3].id], B: [ps[4].id, ps[5].id] }); // 头片已补，胜者规则不再触发
  });

  it('winner 模式：场上还有待打片（头片非空）→ 胜者不适用，按序补片', () => {
    const w1 = mkP(1700), w2 = mkP(1600);
    const ps = [1500, 1490, 1480, 1470, 1460, 1450, 1440, 1430].map((e) => mkP(e));
    const live = mkLive('winner', ps, { lastWinners: [w1.id, w2.id], courts: [{ A: [9001, 9002], B: [9003, 9004] }] });
    fillCourts(live);
    expect(live.courts[1]).toEqual({ A: [ps[0].id, ps[1].id], B: [ps[2].id, ps[3].id] });
  });

  it('cap≥12 → 最多三片（12 人恰好 3 满片）', () => {
    const ps = Array.from({ length: 12 }, (_, i) => mkP(1600 - i));
    const live = mkLive('rotate', ps);
    live.g.cap = 12;
    fillCourts(live);
    expect(live.courts).toHaveLength(3);
    expect(live.queue).toEqual([]);
  });

  it('未上场的余量留在队列，且 fire（连战）优先回队', () => {
    const ps = Array.from({ length: 10 }, (_, i) => mkP(1600 - i));
    const live = mkLive('rotate', ps);
    live.g.cap = 12;
    fillCourts(live);
    expect(live.courts).toHaveLength(2);                    // 8 人上场
    expect(live.queue).toEqual([ps[8].id, ps[9].id]);       // 余 2 人候场
    ps[9].fire = true;
    fillCourts(live);
    expect(live.queue).toEqual([ps[9].id, ps[8].id]);       // 连战排到队首
  });
});

describe('nextMatch（alpha:1524-1529）', () => {
  it('取头片上记分板，比分清零', () => {
    const ps = [1500, 1510, 1520, 1530].map((e) => mkP(e));
    const live = mkLive('rotate', ps);
    fillCourts(live);
    nextMatch(live);
    expect(live.courts).toHaveLength(0);
    expect(live.cur).toEqual({ A: [ps[0].id, ps[1].id], B: [ps[2].id, ps[3].id], sa: 0, sb: 0 });
  });
  it('无片可开 → cur 为 null', () => {
    const live = mkLive('rotate', []);
    nextMatch(live);
    expect(live.cur).toBeNull();
  });
  it('pById 按找 roster', () => {
    const ps = [1500].map((e) => mkP(e));
    const live = mkLive('rotate', ps);
    expect(pById(live, ps[0].id)?.name).toBe(ps[0].name);
    expect(pById(live, 99999)).toBeUndefined();
  });
});
