import { describe, expect, it } from 'vitest';
import { U } from '@/api';
import type { Game, GameEntry, User } from '@/api/types';
import { freqName, heads, isMine, isOrg, known, myEntry, needOf, perHead, slotBig, slotName } from '@/utils/format';

function mkGame(p: Partial<Game>): Game {
  return {
    id: 1, organizer: U.ken, t: '周六 10:00', d: '10.07', tb: 'weekend', area: '亮马河', dur: 2,
    deadline: '周五 18:00', loc: '亮马河 · 滨河球场', name: '测试局', min: 4, cap: 8, fee: 300,
    joined: [] as GameEntry[], wait: [], status: 'open', score: 11, mode: 'balance', lateRule: false,
    ...p,
  };
}

describe('heads / needOf（带的人也占坑，alpha:882-883）', () => {
  it('bring 计入坑位', () => {
    const g = mkGame({ cap: 12, joined: [{ u: U.wang }, { u: U.hai, bring: 2 }, { u: U.wu }] });
    expect(heads(g)).toBe(5);          // 1 + (1+2) + 1
    expect(needOf(g)).toBe(7);
  });
  it('超员时剩几坑钳到 0', () => {
    const g = mkGame({ cap: 4, joined: [{ u: U.wang, bring: 1 }, { u: U.wu, bring: 2 }] });
    expect(heads(g)).toBe(5);
    expect(needOf(g)).toBe(0);
  });
});

describe('perHead 三口径（alpha:884 一字不差：不足最少按最少摊 / 够最少按当前摊 / sure 后最少作废按当前摊）', () => {
  it('口径一：不足最少按最少摊（fee 300 · min 4 · heads 2 → 300/4=75）', () => {
    const g = mkGame({ fee: 300, min: 4, joined: [{ u: U.wang }, { u: U.wu }] });
    expect(perHead(g)).toBe(75);
  });
  it('口径二：够最少按当前人数摊（fee 300 · min 4 · heads 5 → 60）', () => {
    const g = mkGame({ fee: 300, min: 4, joined: [{ u: U.wang }, { u: U.wu }, { u: U.gu }, { u: U.li }, { u: U.shi }] });
    expect(heads(g)).toBe(5);
    expect(perHead(g)).toBe(60);
  });
  it('口径三：sure 后最少作废按当前摊（fee 300 · min 8 · heads 5 · sure → 60 而非 38）', () => {
    const noSure = mkGame({ fee: 300, min: 8, joined: [{ u: U.wang }, { u: U.wu }, { u: U.gu }, { u: U.li }, { u: U.shi }] });
    expect(heads(noSure)).toBe(5);
    expect(perHead(noSure)).toBe(38); // 300/8=37.5 → 38
    const sured = { ...noSure, sure: true };
    expect(perHead(sured)).toBe(60);  // 300/5=60
  });
  it('mock 局抽查：102 局人均 50（200 ÷ max(4, 4)）', () => {
    const g = mkGame({ fee: 200, min: 4, joined: [{ u: U.me }, { u: U.li, bring: 1 }, { u: U.bei }] });
    expect(perHead(g)).toBe(50);
  });
});

describe('myEntry / isOrg / isMine（alpha:885-887）', () => {
  it('组织者 / 已加入 / 被邀请三态', () => {
    expect(isOrg(mkGame({ organizer: U.me }))).toBe(true);
    expect(isOrg(mkGame({ organizer: U.wang }))).toBe(false);
    expect(myEntry(mkGame({ joined: [{ u: U.wang }, { u: U.me, bring: 1 }] }))?.bring).toBe(1);
    expect(myEntry(mkGame({ joined: [{ u: U.wang }] }))).toBeUndefined();
    expect(isMine(mkGame({ organizer: U.me }))).toBe(true);
    expect(isMine(mkGame({ joined: [{ u: U.me }] }))).toBe(true);
    expect(isMine(mkGame({ invitedMe: true }))).toBe(true);
    expect(isMine(mkGame({}))).toBe(false);
  });
});

describe('known（alpha:888-889，同局打过 = 熟人；静态集合按启动时 mock 局算）', () => {
  it('喜欢过 → known', () => {
    expect(known(U.wang)).toBe(true); // liked
  });
  it('与我同局（101 我已加入 / 102 我组织）→ known', () => {
    expect(known(U.wu)).toBe(true);   // 101 名单
    expect(known(U.li)).toBe(true);   // 101/102 名单
    expect(known(U.zhao)).toBe(true); // 101 随行也是名单里的人
  });
  it('无交集且未喜欢 → 不算熟人', () => {
    // 5.1 done 局入 mock 后，我参与的 93-98 把 U 全员变成同局熟人（ken 是 95 组织者），
    // 「无交集」fixture 只能造局外人；zhang 未进我任何一局，仍守此分支。
    const outsider: User = { id: 99, name: '局外人', elo: 1200, play: 0, win: 0, month: 0, chibi: {} };
    expect(known(outsider)).toBe(false);
    expect(known(U.zhang)).toBe(false);
  });
});

describe('slotName / freqName / slotBig（alpha:890-891, 1023-1024）', () => {
  it('时段名与兜底', () => {
    expect(slotName('wd')).toBe('工作日晚间');
    expect(slotName('we-n')).toBe('周末晚上');
    expect(slotName('nope')).toBe('nope');
  });
  it('频率名', () => {
    expect(freqName(0)).toBe('随缘');
    expect(freqName(1)).toBe('每周 1 打');
    expect(freqName(2)).toBe('每周 2 打');
  });
  it('意向卡大字时段（大字=时段 / 小字=天）', () => {
    expect(slotBig('wd')).toEqual(['晚间', '工作日']);
    expect(slotBig('ln')).toEqual(['午休', '工作日']);
    expect(slotBig('we-d')).toEqual(['白天', '周末']);
    expect(slotBig('we-n')).toEqual(['晚上', '周末']);
  });
});
