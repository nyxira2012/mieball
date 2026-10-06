import { describe, expect, it } from 'vitest';
import type { Game, MockGame, Person } from '@/api/types';
import {
  GAME_STATUS_NAMES,
  freqName,
  gameTapAction,
  isOrg,
  mockGameCard,
  newGameCard,
  slotBig,
  slotName,
} from '@/utils/format';
import { dayToken, toIso } from '@/utils/time';

/* 卡面时间换算（isoDay/isoHm）按设备本地墙钟走；本项目时区口径=北京时间（契约§2），
   测试环境钉死 TZ，避免开发机时区不同导致断言漂移。 */
process.env.TZ = 'Asia/Shanghai';

/* 1.2 接线重写：人头/剩坑/人均/forced 等本地公式退役（改读后端定值），
   本文件只测换下来的纯展示口径：状态文案表、卡面映射（真局/快照）、点卡分支、词表。 */

const ken: Person = { id: 11, nickname: '亮马河 Ken', chibi: {} };
const me: Person = { id: 0, nickname: '我', chibi: {} };

function mkGame(p: Partial<Game> = {}): Game {
  return {
    id: 1, name: '测试局', organizer: ken,
    startAt: '2026-10-10T10:00:00+08:00', endAt: '2026-10-10T12:00:00+08:00', deadlineAt: '2026-10-10T08:00:00+08:00',
    venueName: '亮马河 · 滨河球场', venueAddress: null,
    minPlayers: 4, maxPlayers: 8, visibility: 'public',
    scoring: 11, rotation: 'balance', scoreRule: 'rally',
    manualLock: false, courts: null, feeTotal: null,
    status: 'open', unlocked: false, joinable: true,
    heads: 1, slotsLeft: 7, perHead: null, forced: false,
    ...p,
  };
}

describe('GAME_STATUS_NAMES（视图 7 态文案表，单一源=后端 derive）', () => {
  it('7 态齐全', () => {
    expect(Object.keys(GAME_STATUS_NAMES)).toHaveLength(7);
    expect(GAME_STATUS_NAMES.open).toBe('报名中');
    expect(GAME_STATUS_NAMES.pending).toBe('待处置');
  });
});

describe('newGameCard（真局 → 卡面模型：定值直读，时间现场换算）', () => {
  it('时间/场馆/必打标/剩坑', () => {
    const start = new Date(2026, 9, 10, 10, 0); // 本地墙钟 2026-10-10 10:00，经 toIso 往返免 TZ 抖动
    const card = newGameCard(
      mkGame({
        startAt: toIso(start),
        courts: ['3号'], forced: true, slotsLeft: 3, heads: 5,
        entries: [
          { account: ken, bring: 0, standing: 'formal', waitSeq: null },
          { account: me, bring: 1, standing: 'formal', waitSeq: null },
          { account: { id: 2, nickname: '乙', chibi: {} }, bring: 0, standing: 'waitlist', waitSeq: 1 },
        ],
      }),
    );
    expect(card.hmText).toBe('10:00'); // ISO 现场换算
    expect(card.dayText).toBe(dayToken(start));
    expect(card.venueText).toBe('亮马河 · 滨河球场');
    expect(card.forcedLabel).toBe('已订场 · 必开'); // 场上有号优先于空锁文案
    expect(card.slotsLeft).toBe(3);
    // 候补不进头像叠层；带的人不计入头像数
    expect(card.stackAvatars).toHaveLength(2);
    expect(card.stackPlus).toBe('+');
  });

  it('myRole 三态 + 空锁标', () => {
    expect(newGameCard(mkGame({ my: { isOrganizer: true, myEntry: null, invited: false } })).myRole).toBe('org');
    expect(
      newGameCard(mkGame({ my: { isOrganizer: false, myEntry: null, invited: true } })).myRole,
    ).toBe('inv');
    expect(
      newGameCard(
        mkGame({ my: { isOrganizer: false, myEntry: { bring: 0, standing: 'formal', waitSeq: null }, invited: false } }),
      ).myRole,
    ).toBe('joined');
    expect(newGameCard(mkGame({ manualLock: true, forced: true })).forcedLabel).toBe('必开');
    expect(newGameCard(mkGame()).forcedLabel).toBeUndefined();
  });
});

describe('mockGameCard（快照局 → 卡面模型：5.1 口径逐字）', () => {
  it('heads 含 bring、含随行标记、done 战报透传', () => {
    const g: MockGame = {
      id: 102, organizer: { id: 0, name: '我', elo: 0, play: 0, win: 0, month: 0, chibi: {} },
      t: '周六 14:00', d: '10.07', tb: 'weekend', area: '望京', dur: 2, deadline: '周五 20:00',
      loc: '望京 · 花家地球馆 · 2 片', name: '周末午后局', min: 4, cap: 8, fee: 480,
      joined: [
        { u: { id: 0, name: '我', elo: 0, play: 0, win: 0, month: 0, chibi: {} } },
        { u: { id: 5, name: '亮马河快攻', elo: 0, play: 0, win: 0, month: 0, chibi: {} }, bring: 1 },
        { u: { id: 8, name: '北苑小钢炮', elo: 0, play: 0, win: 0, month: 0, chibi: {}, shadow: true } },
      ],
      wait: [], status: 'done', score: 11, mode: 'balance', lateRule: false,
      result: { sa: 21, sb: 15, myWin: true },
    };
    const card = mockGameCard(g);
    expect(card.slotsLeft).toBe(4); // cap 8 - heads 4（me1 + li带1共2 + bei1）
    expect(card.stackPlus).toContain('含随行');
    expect(card.myRole).toBe('org');
    expect(card.result?.myWin).toBe(true);
    expect(card.hmText).toBe('14:00');
    expect(card.dayText).toBe('周六');
  });
});

describe('gameTapAction（alpha:907 点局卡分支）：被邀请未加入 → join', () => {
  it('三态', () => {
    expect(gameTapAction(mkGame({ my: { isOrganizer: false, myEntry: null, invited: true } }))).toBe('join');
    expect(
      gameTapAction(mkGame({ my: { isOrganizer: false, myEntry: { bring: 0, standing: 'formal', waitSeq: null }, invited: true } })),
    ).toBe('detail'); // 已加入的邀请不算
    expect(gameTapAction(mkGame())).toBe('detail');
  });
});

describe('isOrg（viewer 块定值）', () => {
  it('my 缺省（游客）恒 false', () => {
    expect(isOrg(mkGame({ my: { isOrganizer: true, myEntry: null, invited: false } }))).toBe(true);
    expect(isOrg(mkGame())).toBe(false);
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
