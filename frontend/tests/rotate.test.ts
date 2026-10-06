import { describe, expect, it } from 'vitest';
import type { Game, LiveCourt, LiveState, RotationRules, User } from '@/api/types';
import {
  activePlayers,
  courtCount,
  courtSize,
  endMatch,
  fillAllCourts,
  fillCourt,
  pById,
  RANK_INIT,
  rankOf,
  splitSides,
  takeFromQueue,
  usedCourts,
} from '@/utils/rotate';

let seq = 0;
function mkP(elo: number, extra: Partial<User> = {}): User {
  seq += 1;
  return { id: seq, name: `P${seq}`, elo, play: 1, win: 0, month: 0, chibi: {}, check: 'ok', skip: 0, fire: false, ...extra };
}
const R0 = (): RotationRules => ({ singles: false, down: 'all', downChosen: true, pairing: 'queue', champCap: 3 });
function mkLive(mode: Game['rotation'], players: User[], opts: Partial<LiveState> = {}): LiveState {
  return {
    g: {
      id: 1, name: 't', organizer: { id: players[0]?.id ?? 99, nickname: players[0]?.name ?? 'P0', chibi: {} },
      startAt: '2026-10-06T19:00:00+08:00', endAt: '2026-10-06T21:00:00+08:00', deadlineAt: '2026-10-06T17:00:00+08:00',
      venueName: 'x', venueAddress: null, minPlayers: 4, maxPlayers: 8, visibility: 'public',
      scoring: 11, rotation: mode, scoreRule: 'rally',
      manualLock: false, courts: null, feeTotal: 100,
      status: 'live', unlocked: false, joinable: true, heads: 0, slotsLeft: 8, perHead: null, forced: false,
    },
    roster: players,
    queue: players.map((p) => p.id),
    courts: [], history: [], round: 0,
    rules: R0(), courtSeqNext: 0,
    ...opts,
  };
}

describe('pById / usedCourts（长期保留导出）', () => {
  it('pById 按找 roster', () => {
    const ps = [1500].map((e) => mkP(e));
    const live = mkLive('rotate', ps);
    expect(pById(live, ps[0].id)?.name).toBe(ps[0].name);
    expect(pById(live, 99999)).toBeUndefined();
  });

  it('usedCourts（2.4 批2 改口径）：数非空片——空片（差人卡）不算已占', () => {
    const ps = Array.from({ length: 8 }, (_, i) => mkP(1600 - i));
    const full = { id: 0, name: '1号', singles: false, A: [ps[0].id, ps[1].id], B: [ps[2].id, ps[3].id], sa: 0, sb: 0, streakA: 0, streakB: 0 };
    const idle = { id: 1, name: '2号', singles: false, A: [], B: [], sa: 0, sb: 0, streakA: 0, streakB: 0 };
    const live = mkLive('rotate', ps, { courts: [full, idle] });
    expect(usedCourts(live)).toBe(1);
    live.courts[1]!.A = [ps[4].id]; // 半边有人即在打
    expect(usedCourts(live)).toBe(2);
  });
});

/* ───────── 2.4 引擎用例（旧串行引擎段已随批2 删除）───────── */

const R = (over: Partial<RotationRules> = {}): RotationRules => ({
  singles: false, down: 'all', downChosen: true, pairing: 'queue', champCap: 3, ...over,
});
const mkCourt = (a: User[], b: User[], over: Partial<LiveCourt> = {}): LiveCourt => ({
  A: a.map((p) => p.id), B: b.map((p) => p.id), id: 0, singles: false, sa: 0, sb: 0, streakA: 0, streakB: 0, ...over,
});
/** 片上现役：按参数序发 courtSeq（先上=号小），tenure 统一指定 */
const vets = (players: User[], tenure: number, startSeq: number): User[] =>
  players.map((p, i) => { p.courtSeq = startSeq + i; p.tenure = tenure; return p; });

describe('takeFromQueue（2.4 §4.8：跳轮消耗+保位+坑由下位顶）', () => {
  it('轮到歇轮者：跳过这一轮、消耗一次，坑由下一位顶上；取完保位回队', () => {
    const a = mkP(1500, { skip: 2 });
    const b = mkP(1500), c = mkP(1500), d = mkP(1500);
    const live = mkLive('rotate', [a, b, c, d]);
    expect(takeFromQueue(live, 2)).toEqual([b.id, c.id]); // a 让位，b/c 顶坑
    expect(a.skip).toBe(1);                               // 消耗一次
    expect(live.queue).toEqual([a.id, d.id]);             // a 保位在 d 前
  });

  it('取满即停：没轮到的歇轮不消耗（轮到才算）', () => {
    const b = mkP(1500);
    const a = mkP(1500, { skip: 1 }); // 排 b 后面，本轮没轮到
    const live = mkLive('rotate', [b, a]);
    expect(takeFromQueue(live, 1)).toEqual([b.id]);
    expect(a.skip).toBe(1);
    expect(live.queue).toEqual([a.id]);
  });

  it('absent/left 不可发但留在队里；连战（fire）优先收——下次发牌排最前', () => {
    const gone = mkP(1500, { check: 'absent' });
    const left = mkP(1500, { check: 'left' });
    const hot = mkP(1500, { fire: true });
    const b = mkP(1500), c = mkP(1500);
    const live = mkLive('rotate', [gone, left, b, hot, c]);
    expect(takeFromQueue(live, 2)).toEqual([hot.id, b.id]);
    expect(live.queue).toEqual([gone.id, left.id, c.id]);
  });

  it('余额不足：能取多少取多少，队里不剩已取者', () => {
    const b = mkP(1500), c = mkP(1500);
    const live = mkLive('rotate', [b, c]);
    expect(takeFromQueue(live, 3)).toEqual([b.id, c.id]);
    expect(live.queue).toEqual([]);
  });
});

describe('splitSides（2.4 §4.5 分边真值）', () => {
  it('按候场队序：第 1、2 位一队，第 3、4 位一队', () => {
    const ps = [1600, 1500, 1400, 1300].map((e) => mkP(e));
    const live = mkLive('rotate', ps);
    expect(splitSides(live, ps.map((p) => p.id), 'queue')).toEqual({
      A: [ps[0].id, ps[1].id], B: [ps[2].id, ps[3].id],
    });
  });

  it('均衡配对：最强+最弱 vs 二三（积分强到弱，防两个高手挤同边）', () => {
    const ps = [1600, 1800, 1700, 1500].map((e) => mkP(e)); // 队序与强弱错开
    const live = mkLive('rotate', ps);
    expect(splitSides(live, ps.map((p) => p.id), 'balance')).toEqual({
      A: [ps[1].id, ps[3].id], B: [ps[2].id, ps[0].id], // 1800+1500 vs 1700+1600
    });
  });

  it('均衡同分：按候场队先后 tiebreak（不掷骰子，现场可复述）', () => {
    const ps = [1500, 1800, 1500, 1800].map((e) => mkP(e));
    const live = mkLive('rotate', ps);
    expect(splitSides(live, ps.map((p) => p.id), 'balance')).toEqual({
      A: [ps[1].id, ps[2].id], B: [ps[3].id, ps[0].id], // 两个 1800 里队序前的 ps[1] 排头
    });
  });

  it('没打过的人按初始分 1500 参与排序（2.4 §8 定值）', () => {
    expect(rankOf(mkP(999, { play: 0 }))).toBe(RANK_INIT);
    expect(rankOf(mkP(1700, { play: 3 }))).toBe(1700);
    const ps = [mkP(1800), mkP(999, { play: 0 }), mkP(1700), mkP(1600)];
    const live = mkLive('rotate', ps); // 新人按 1500 排：低于 1600/1700，垫底与最强一队
    expect(splitSides(live, ps.map((p) => p.id), 'balance')).toEqual({
      A: [ps[0].id, ps[1].id], B: [ps[2].id, ps[3].id], // 1800+新人(1500) vs 1700+1600
    });
  });

  it('单打没有分队：一左一右（怎么配都不分）', () => {
    const ps = [1800, 1500].map((e) => mkP(e));
    const live = mkLive('rotate', ps);
    expect(splitSides(live, ps.map((p) => p.id), 'balance')).toEqual({ A: [ps[0].id], B: [ps[1].id] });
  });
});

describe('fillCourt / fillAllCourts（2.4 §4.3 补满即打）', () => {
  it('空片补满：按怎么公分边、比分清零、新队连庄清零、courtSeq/tenure 起算', () => {
    const ps = Array.from({ length: 8 }, (_, i) => mkP(1600 - i));
    const court = mkCourt([], [], { id: 0, streakA: 5, streakB: 2, sa: 11, sb: 7 });
    const live = mkLive('rotate', ps, { rules: R({ down: 'loser' }), courtSeqNext: 4, courts: [court] });
    fillCourt(live, court);
    expect(court).toMatchObject({ A: [ps[0].id, ps[1].id], B: [ps[2].id, ps[3].id], sa: 0, sb: 0, streakA: 0, streakB: 0 });
    expect(ps[0].courtSeq).toBe(5);   // 新发上场序
    expect(ps[0].tenure).toBe(0);     // 资历从 0 起算
    expect(live.queue).toEqual(ps.slice(4).map((p) => p.id));
  });

  it('补不满留空（差人卡呈现）：不动队列、不消耗歇轮', () => {
    const a = mkP(1500, { skip: 1 });
    const b = mkP(1500), c = mkP(1500);
    const court = mkCourt([], [], { id: 0 });
    const live = mkLive('rotate', [a, b, c], { rules: R(), courtSeqNext: 0, courts: [court] });
    fillCourt(live, court);
    expect(court.A).toEqual([]);      // 留空
    expect(court.B).toEqual([]);
    expect(live.queue).toEqual([a.id, b.id, c.id]);
    expect(a.skip).toBe(1);           // 没发牌不消耗
  });

  it('片格式说了算（过渡期 court.singles 可 ≠ rules.singles）：单打片只取 2 人', () => {
    const ps = Array.from({ length: 4 }, (_, i) => mkP(1600 - i));
    const court = mkCourt([], [], { id: 0, singles: true });
    const live = mkLive('rotate', ps, { rules: R(), courtSeqNext: 0, courts: [court] });
    fillCourt(live, court);
    expect(court.A).toEqual([ps[0].id]);
    expect(court.B).toEqual([ps[1].id]);
  });

  it('fillAllCourts 按片号先后补空片；最后一片补不满留空', () => {
    const ps = Array.from({ length: 11 }, (_, i) => mkP(1600 - i));
    const c0 = mkCourt([], [], { id: 0 });
    const c1 = mkCourt([], [], { id: 1 });
    const c2 = mkCourt([], [], { id: 2 });
    ps[0].fire = true; // 连战者必进首片
    const live = mkLive('rotate', ps, { rules: R(), courtSeqNext: 0, courts: [c0, c1, c2] });
    live.g.maxPlayers = 12;
    fillAllCourts(live);
    expect(c0.A).toEqual([ps[0].id, ps[1].id]); // 片 0 先取：连战 ps[0] + 队首 ps[1]
    expect(c0.B).toEqual([ps[2].id, ps[3].id]);
    expect(c1.A).toEqual([ps[4].id, ps[5].id]); // 片 1 随后
    expect(c1.B).toEqual([ps[6].id, ps[7].id]);
    expect(c2.A).toEqual([]);                   // 只剩 3 人 <4：留空差人卡
    expect(live.queue).toEqual(ps.slice(8).map((p) => p.id));
  });
});

describe('endMatch 五式真值（2.4 §4.4-4.7）', () => {
  const setup = (rules: RotationRules, courtPlayers: User[], queue: User[], over: Partial<LiveCourt> = {}) => {
    const court = mkCourt(courtPlayers.slice(0, courtPlayers.length / 2), courtPlayers.slice(courtPlayers.length / 2), { id: 0, sa: 11, sb: 5, ...over });
    const live = mkLive('rotate', [...courtPlayers, ...queue], {
      rules, courtSeqNext: 4, courts: [court], queue: queue.map((p) => p.id),
    });
    return { live, court };
  };

  it('全上全下：场上全部按资历序排队尾，候场首 4 人补全新一队', () => {
    const a = mkP(1500), b = mkP(1500), c = mkP(1500), d = mkP(1500);
    const e = mkP(1500), f = mkP(1500), g = mkP(1500), h = mkP(1500);
    vets([a], 3, 1); vets([b], 2, 2); vets([c], 2, 3); vets([d], 1, 4); // 资历 a>b(并列c 先上)>c>d
    const { live, court } = setup(R({ down: 'all' }), [a, b, c, d], [e, f, g, h]);
    endMatch(live, 0, 'A');
    expect(court.A).toEqual([e.id, f.id]);       // 全新一队按队序分边
    expect(court.B).toEqual([g.id, h.id]);
    expect(live.queue).toEqual([a.id, b.id, c.id, d.id]); // 按资历序排队尾（先下的排前面）
    expect(court.streakA).toBe(0);
    expect(a.tenure).toBe(0);                    // 下场资历清零
    expect(a.courtSeq).toBeUndefined();          // 先后序注销
    expect(e.courtSeq).toBe(5);                  // 上场者发新序
    expect(e.tenure).toBe(0);
    expect(court.sa).toBe(0);                    // 比分清零开新场
  });

  it('输家下未到点：赢家留场连庄+1，输家排队尾，候场首补空边成一队不重配', () => {
    const a = mkP(1500), b = mkP(1500), c = mkP(1500), d = mkP(1500);
    const e = mkP(1500), f = mkP(1500), g = mkP(1500);
    vets([a, b, c, d], 1, 1);
    const { live, court } = setup(R({ down: 'loser', champCap: 3 }), [a, b, c, d], [e, f, g], { streakA: 1 });
    endMatch(live, 0, 'A');
    expect(court.streakA).toBe(2);               // 连庄 +1
    expect(court.A).toEqual([a.id, b.id]);       // 赢家原位留场
    expect(court.B).toEqual([e.id, f.id]);       // 候场首 2 人成一队挑战
    expect(court.streakB).toBe(0);               // 新挑战者连庄从零
    expect(live.queue).toEqual([g.id, c.id, d.id]); // 输家排队尾
    expect(c.tenure).toBe(0);                    // 下场清零
    expect(c.courtSeq).toBeUndefined();
    expect(e.tenure).toBe(0);                    // 中途上从换上起算
    expect(e.courtSeq).toBe(5);
  });

  it('输家下到点：赢家整队也下、候场首补全新一队（怎么配生效），下者按资历序排队尾', () => {
    const a = mkP(1500), b = mkP(1500), c = mkP(1500), d = mkP(1500);
    const e = mkP(1800), f = mkP(1700), g = mkP(1600), h = mkP(1500);
    vets([a], 5, 1); vets([b, c, d], 1, 2);      // 赢家 a 资历最深：到点下时排队首的是 a（资历序，非输家优先）
    const { live, court } = setup(R({ down: 'loser', champCap: 3, pairing: 'balance' }), [a, b, c, d], [e, f, g, h], { streakA: 2 });
    endMatch(live, 0, 'A');                      // streakA 2+1=3 到点
    expect(court.A).toEqual([e.id, h.id]);       // 均衡：最强+最弱 vs 二三
    expect(court.B).toEqual([f.id, g.id]);
    expect(court.streakA).toBe(0);               // 全新一队连庄清零
    expect(live.queue).toEqual([a.id, b.id, c.id, d.id]); // 全场按资历序下
  });

  it('连庄上限 0=不限：赢 10 场也照留；上限改小立即生效（读现值判定）', () => {
    const a = mkP(1500), b = mkP(1500), c = mkP(1500), d = mkP(1500);
    const e = mkP(1500), f = mkP(1500), g = mkP(1500), h = mkP(1500);
    vets([a, b, c, d], 1, 1);
    const free = setup(R({ down: 'loser', champCap: 0 }), [a, b, c, d], [e, f, g, h], { streakA: 9 });
    endMatch(free.live, 0, 'A');
    expect(free.court.streakA).toBe(10);         // 不限：照留场
    expect(free.court.A).toEqual([a.id, b.id]);
    expect(free.court.B).toEqual([e.id, f.id]);
    const tight = setup(R({ down: 'loser', champCap: 2 }), [a, b, c, d], [e, f, g, h], { streakA: 1 });
    endMatch(tight.live, 0, 'A');                // 1+1=2 到新上限：这场打完就下
    expect(tight.court.A).toEqual([e.id, f.id]); // 整队下、补全新一队
    expect(tight.court.B).toEqual([g.id, h.id]);
  });

  it('2人下：资历最久的 2 人下，候场首逐个原位顶坑（谁下补谁的坑、留下的保住半边）', () => {
    const a = mkP(1500), b = mkP(1500), c = mkP(1500), d = mkP(1500);
    const e = mkP(1500), f = mkP(1500), g = mkP(1500);
    vets([a], 3, 1); vets([b], 1, 2); vets([c], 2, 3); vets([d], 1, 4); // 资历序 a>c>b>d
    const { live, court } = setup(R({ down: 'n2' }), [a, b, c, d], [e, f, g]);
    endMatch(live, 0, 'A');
    expect(court.A).toEqual([e.id, b.id]);       // a 下（A[0] 坑），e 原位顶；b 留住半边
    expect(court.B).toEqual([f.id, d.id]);       // c 下（B[0] 坑），f 原位顶；d 留住
    expect(live.queue).toEqual([g.id, a.id, c.id]); // 先下的 a 排前面
    expect(e.courtSeq).toBe(5);                  // 换上者从换上起算
    expect(b.courtSeq).toBe(2);                  // 留下者资历序不动
  });

  it('3人下：资历序前三下、只留最浅一人；1人下：资历并列按当初上场先后（先上的先下）', () => {
    const a = mkP(1500), b = mkP(1500), c = mkP(1500), d = mkP(1500);
    const e = mkP(1500), f = mkP(1500), g = mkP(1500);
    vets([a], 3, 1); vets([b], 2, 2); vets([c], 2, 3); vets([d], 1, 4);
    const three = setup(R({ down: 'n3' }), [a, b, c, d], [e, f, g]);
    endMatch(three.live, 0, 'A');
    expect(three.court.A).toEqual([e.id, f.id]); // a、b 下，d 唯一留场者
    expect(three.court.B).toEqual([g.id, d.id]); // c 下
    expect(three.live.queue).toEqual([a.id, b.id, c.id]);
    const w = mkP(1500), x = mkP(1500), y = mkP(1500), z = mkP(1500);
    const q1 = mkP(1500);
    vets([w, x, y, z], 1, 1);                    // 开场第一场打完：四人并列，courtSeq 定先后
    const one = setup(R({ down: 'n1' }), [w, x, y, z], [q1]);
    endMatch(one.live, 0, 'A');
    expect(one.court.A).toEqual([q1.id, x.id]);  // 最先上的 w 下，q1 顶坑
    expect(one.court.B).toEqual([y.id, z.id]);
  });

  it('坑补不满：本场谁也不下、原班再战（比分清零、连庄资历照算不清零、队列不动）', () => {
    const a = mkP(1500), b = mkP(1500), c = mkP(1500), d = mkP(1500);
    const e = mkP(1500);
    vets([a], 3, 1); vets([b], 1, 2); vets([c], 1, 3); vets([d], 1, 4);
    const { live, court } = setup(R({ down: 'loser', champCap: 3 }), [a, b, c, d], [e], { streakA: 0 });
    endMatch(live, 0, 'A');                      // 输家下要 2 人，候场只有 1 人
    expect(court.A).toEqual([a.id, b.id]);       // 原班再战
    expect(court.B).toEqual([c.id, d.id]);
    expect(live.queue).toEqual([e.id]);          // 队列不动
    expect(court.streakA).toBe(1);               // 这场赢了照算
    expect(a.tenure).toBe(4);                    // 资历照算（3+1），不清零
    expect(court.sa).toBe(0);                    // 只清比分
    const all = setup(R({ down: 'all' }), [a, b, c, d], [e]);
    endMatch(all.live, 0, 'A');                  // 全上全下要 4 人，同样补不满
    expect(all.court.A).toEqual([a.id, b.id]);
    expect(all.court.B).toEqual([c.id, d.id]);
  });

  it('格式过渡（4.7-3）：双切单全场下、按新格式凑全新一队；补不够则原班再战续旧格式', () => {
    const a = mkP(1500), b = mkP(1500), c = mkP(1500), d = mkP(1500);
    const e = mkP(1500), f = mkP(1500), g = mkP(1500), h = mkP(1500);
    vets([a], 3, 1); vets([b], 1, 2); vets([c], 1, 3); vets([d], 1, 4);
    const { live, court } = setup(R({ singles: true, down: 'all' }), [a, b, c, d], [e, f, g, h], { singles: false });
    endMatch(live, 0, 'A');
    expect(court.singles).toBe(true);            // 片格式随新规
    expect(court.A).toEqual([e.id]);             // 单打补 2 人成全新一队
    expect(court.B).toEqual([f.id]);
    expect(live.queue).toEqual([g.id, h.id, a.id, b.id, c.id, d.id]); // 全场按资历序下，余额在前
    const w = mkP(1500);
    const short = setup(R({ singles: false, down: 'all' }), [e, f], [w], { singles: true }); // 单切双 queue(1)+2<4 真不足
    endMatch(short.live, 0, 'A');
    expect(short.court.singles).toBe(true);      // 补不满：原班再战、格式等下一场再切
    expect(short.court.A).toEqual([e.id]);
    expect(short.court.B).toEqual([f.id]);
    expect(short.live.queue).toEqual([w.id]);    // 队列不动
  });

  it('格式过渡供给含下场者（F-W1·4.7-3 无条件）：双切单候场 0 也全场下——4 下 2 上、片转单打、剩 2 人排队', () => {
    const a = mkP(1500), b = mkP(1500), c = mkP(1500), d = mkP(1500);
    vets([a], 3, 1); vets([b], 2, 2); vets([c], 1, 3); vets([d], 1, 4); // 资历序 a>b>c>d
    const { live, court } = setup(R({ singles: true, down: 'all' }), [a, b, c, d], [], { singles: false });
    endMatch(live, 0, 'A');
    expect(court.singles).toBe(true);            // 候场 0 不再被②短路：判「入队后」队列 4 ≥ 2
    expect(court.A).toEqual([a.id]);             // 全下 4 人、按资历序入队后队首 2 人上
    expect(court.B).toEqual([b.id]);
    expect(live.queue).toEqual([c.id, d.id]);    // 剩 2 人排队
    expect(court.sa).toBe(0);                    // 比分清零开新场
  });

  it('单打输家下：输家 1 人下、候场首补 1 人', () => {
    const a = mkP(1500), c = mkP(1500), e = mkP(1500);
    vets([a, c], 1, 1);
    const { live, court } = setup(R({ singles: true, down: 'loser', champCap: 3 }), [a, c], [e], { singles: true, streakA: 1 });
    endMatch(live, 0, 'A');
    expect(court.streakA).toBe(2);
    expect(court.A).toEqual([a.id]);             // 赢家留场
    expect(court.B).toEqual([e.id]);             // 单打补 1 人
    expect(live.queue).toEqual([c.id]);
  });
});

describe('口径单一源（2.4 技术设计 §0.5/§0.6）', () => {
  it('courtSize：双打 4 / 单打 2；courtCount：登记优先、未登记按人数兜底', () => {
    expect(courtSize(false)).toBe(4);
    expect(courtSize(true)).toBe(2);
    const ps = Array.from({ length: 8 }, (_, i) => mkP(1500 + i));
    const live = mkLive('rotate', ps);           // courts 未登记、maxPlayers 8 → 2 片
    expect(courtCount(live)).toBe(2);
    live.g.maxPlayers = 12;
    expect(courtCount(live)).toBe(3);
    live.g.courts = ['3号'];
    expect(courtCount(live)).toBe(1);
  });

  it('activePlayers：片上 + 候场队（absent/left 不算，歇轮者算）', () => {
    const a = mkP(1500, { skip: 1 });
    const gone = mkP(1500, { check: 'left' });
    const b = mkP(1500), c = mkP(1500);
    const on1 = mkP(1500), on2 = mkP(1500);
    const live = mkLive('rotate', [on1, on2, a, gone, b, c], {
      courts: [mkCourt([on1], [on2], { id: 0, singles: true })],
      queue: [a.id, gone.id, b.id, c.id],
    });
    expect(activePlayers(live)).toBe(5);         // 片上 2 + 候场 3（早退 gone 不算，歇轮 a 算）
  });
});
