import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';

/* 每个用例重置模块图 → 全新 mock 数据；104 局（balance · 8 cap）与 102 局做确定性推演 */
beforeEach(async () => {
  vi.resetModules();
  setActivePinia(createPinia());
});

async function load() {
  const liveMod = await import('@/stores/live');
  const uiMod = await import('@/stores/ui');
  const gameMod = await import('@/stores/game');
  return { live: liveMod.useLiveStore(), ui: uiMod.useUiStore(), game: gameMod.useGameStore() };
}

describe('startLive（alpha:1471-1490）', () => {
  it('随行展开成 shadow 访客（随机 chibi）· 前 9 人 ok · balance 蛇形发牌 · 红点亮', async () => {
    const { live, game } = await load();
    expect(live.hasLive).toBe(false);
    const msg = live.startLive(102); // joined: me + li(bring 1) + bei → 4 人
    const L = live.live!;
    const guest = L.roster[2];
    expect(msg).toBe('球局开始 · 现场已点亮');
    expect(live.hasLive).toBe(true);
    expect(L.g.status).toBe('live');
    expect(L.roster).toHaveLength(4);
    expect(L.roster.filter((p) => p.shadow)).toHaveLength(1);
    expect(guest.shadow).toBe(true);
    expect(guest.name).toBe('亮马的球友'); // li.name.slice(0,2) + 的球友
    expect(guest.elo).toBe(1200);
    expect(L.roster.every((p) => p.check === 'ok')).toBe(true); // 4 < 9 全部到场
    // balance 按分降序蛇形：li1574 / me1518 / bei1452 / 访客1200 → A=[li,访客] B=[me,bei]
    expect(L.cur!.A).toEqual([5, guest.id]);
    expect(L.cur!.B).toEqual([0, 8]);
    expect(L.cur!.sa).toBe(0);
    expect(L.queue).toEqual([]); // 全部上场
    expect(game.games.find((x) => x.id === 102)!.status).toBe('live');
  });
  it('超过 9 人时：前 9 ok 其余 absent（101 局：11 报名 + hai 带 2 访客 = 13）', async () => {
    const { live } = await load();
    live.startLive(101);
    const L = live.live!;
    expect(L.roster).toHaveLength(13);
    expect(L.roster.filter((p) => p.shadow)).toHaveLength(3); // hai 带 2 访客 + zhao 本就是随行
    expect(L.roster.filter((p) => p.check === 'ok')).toHaveLength(9);
    expect(L.roster.filter((p) => p.check === 'absent')).toHaveLength(4);
    // fillCourts 后队列重建：9 名可上场者中 8 人上两片，余 1 名访客候场（alpha:1519-1522）
    expect(L.queue).toHaveLength(1);
  });
});

describe('point / endMatch（alpha:1680-1728）：K=24 / 败方六成 / 随行半权重 / 同步 mock U', () => {
  it('11:9 收局：结算数值与 alpha 手工推演一致，战力榜联动', async () => {
    const { live, ui } = await load();
    live.startLive(102);
    const L = live.live!;
    const guest = L.roster[2].id;
    for (let i = 0; i < 9; i++) live.point('a');
    for (let i = 0; i < 9; i++) live.point('b'); // 9:9（先到 11 前不收局）
    live.point('a');
    live.point('a');                             // 11:9 → A 胜
    // A=[li,访客] vs B=[me,bei]：人均 1387 vs 1485 → delta=15，loss=9，访客 ceil(15/2)=8
    expect(L.cur).toBeNull();
    expect(L.history[0]).toEqual({ names: '亮马河快攻 & 亮马的球友', sa: 11, sb: 9 });
    const { U } = await import('@/api');
    expect(U.li.elo).toBe(1589);   // 1574+15 —— roster 与 mock U 同一对象
    expect(U.li.month).toBe(29);   // 14+15
    expect(U.li.win).toBe(30);     // 29+1
    expect(U.me.elo).toBe(1509);   // 1518-9
    expect(U.bei.elo).toBe(1443);  // 1452-9
    expect(U.me.last5).toEqual(['L', 'W', 'W', 'L', 'L']); // 输球 L 入尾（仅我滚动，alpha:1707）
    expect(guest >= 9000).toBe(true);
    expect(L.roster[2].elo).toBe(1208); // 访客 1200+8
    expect(L.lastWinners).toEqual([5]); // 随行不进胜者留场名单
    // 队列：败者回队尾；balance ≠ winner → 胜者也回队
    expect(L.queue).toEqual([0, 8, 5, guest]);
    // 胜利结算卡数据
    expect(ui.win!.names).toBe('亮马河快攻 & 亮马的球友');
    expect(ui.win!.sa).toBe(11);
    expect(ui.win!.chg).toEqual([
      { name: '亮马河快攻', up: true, d: 15 },
      { name: '亮马的球友', up: true, d: 8 },
      { name: '我', up: false, d: -9 },
      { name: '北苑小钢炮', up: false, d: -9 },
    ]);
  });
  it('11:10 不收局，undoPoint 按最后得分方回退，12:10 收局', async () => {
    const { live, ui } = await load();
    live.startLive(102);
    const L = live.live!;
    for (let i = 0; i < 10; i++) live.point('a');
    for (let i = 0; i < 10; i++) live.point('b');
    expect(L.cur).not.toBeNull(); // 10:10
    live.point('a');
    expect(L.cur!.sa).toBe(11);
    expect(L.cur).not.toBeNull(); // 11:10 净胜 1 → 继续
    expect(ui.win).toBeNull();
    live.undoPoint();
    expect(L.cur!.sa).toBe(10);   // 撤回 A 的分
    live.point('a');
    live.point('a');              // 12:10 → 收局
    expect(L.cur).toBeNull();
    expect(L.history[0].sa).toBe(12);
    expect(L.history[0].sb).toBe(10);
  });
});

describe('newRound / setCheck / toggleMine（alpha:1591-1648）', () => {
  async function setup() {
    const h = await load();
    h.live.startLive(102);
    const L = h.live.live!;
    const guest = L.roster[2].id;
    for (let i = 0; i < 9; i++) h.live.point('a');
    for (let i = 0; i < 9; i++) h.live.point('b');
    h.live.point('a');
    h.live.point('a'); // 11:9 收局 → 队列 [0,8,5,guest]
    return { ...h, L, guest };
  }
  it('setCheck：迟到排队尾 / 早退出列 / 中途加入队首（alpha:1591-1605）', async () => {
    const { live, L } = await setup();
    expect(L.queue).toEqual([0, 8, 5, L.roster[2].id]);
    live.setCheck(8, 'late');
    expect(L.queue).toEqual([0, 5, L.roster[2].id, 8]); // 迟到 → 队尾
    live.setCheck(5, 'left');
    expect(L.queue).toEqual([0, L.roster[2].id, 8]);    // 早退 → 出列
    expect(L.roster.find((p) => p.id === 5)!.check).toBe('left');
    live.setCheck(5, 'join');
    expect(L.queue).toEqual([5, 0, L.roster[2].id, 8]); // 中途加入 → 队首（不在队列才 unshift，alpha 原样）
    expect(L.roster.find((p) => p.id === 5)!.check).toBe('join');
  });
  it('toggleMine：歇一轮与连战互斥、连战队首', async () => {
    const { live, L } = await setup();
    live.toggleMine('skip');
    expect(L.roster.find((p) => p.id === 0)!.skip).toBe(true);
    live.toggleMine('fire');
    const meP = L.roster.find((p) => p.id === 0)!;
    expect(meP.fire).toBe(true);
    expect(meP.skip).toBe(false);          // 互斥
    expect(L.queue[0]).toBe(0);            // 连战 → 队首
    live.toggleMine('fire');
    expect(meP.fire).toBe(false);
  });
  it('newRound：未打完场次退回重排（人回队尾）', async () => {
    const { live, L, guest } = await setup();
    // 收局后 cur=null；先把 cur 弄成“未打完”：手动开一轮再点 1 分
    live.newRound(); // round 1：重新发牌（balance → A=[5,guest] B=[0,8]）
    expect(L.round).toBe(1);
    expect(L.cur!.A).toEqual([5, guest]);
    live.point('b'); // B 1:0，未打完
    live.newRound(); // cur 退回 → 4 人回队尾重排
    expect(L.round).toBe(2);
    expect(L.cur).not.toBeNull();
    expect(L.queue).toEqual([]);
  });
});
