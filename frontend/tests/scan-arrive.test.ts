/* 扫码自签到链路（2.1·选项A）+ 「我」id 运行时化回归（1.2 接线重写）：
   - arriveMe：空降（名册没我）→ 报名（api mock）进名册 + 中途加入队首；在册未到 → 到场；已在场 → 幂等
   - 真账号接管 U.me（id 非 0）后：isMe 认得出、togglePerson 找得到人（快照常量回归）
   局 fixture 与后端 game_view 镜像；store 列表直接注入，joinGame 走 api mock。 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { U } from '@/api/mock';
import type { GameViewApi } from '@/api/games';
import { isMe } from '@/utils/format';
import { useGameStore } from '@/stores/game';
import { useLiveStore } from '@/stores/live';

/** 演示态快照（用例后恢复，避免串扰） */
const demo = { id: U.me.id, name: U.me.name };

const api = vi.hoisted(() => ({
  apiPublishGame: vi.fn(),
  apiListGames: vi.fn(),
  apiMyGames: vi.fn(),
  apiGameDetail: vi.fn(),
  apiJoinGame: vi.fn(),
  apiQuitGame: vi.fn(),
  apiEditGame: vi.fn(),
  apiLockGame: vi.fn(),
  apiBookCourt: vi.fn(),
  apiClearBooking: vi.fn(),
  apiCancelGame: vi.fn(),
  apiRestoreGame: vi.fn(),
  apiInviteUser: vi.fn(),
  apiListIntents: vi.fn(),
  apiMyIntent: vi.fn(),
  apiSaveIntent: vi.fn(),
  apiDeleteIntent: vi.fn(),
}));
vi.mock('@/api/games', () => api);

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
});

/** 模拟真账号接管「我」位（session store applyIdentity 的等价操作） */
function takeoverAs(id: number, name: string): void {
  Object.assign(U.me, { id, name });
}

const person = (id: number, nickname: string) => ({ id, nickname, chibi: {} });
const entry = (id: number, nickname: string, bring = 0) => ({
  account: person(id, nickname), bring, standing: 'formal' as const, wait_seq: null,
});

/** 107 同构（原「加时夜战」：我未报名 · shi/gu 在册），球友视角 my.myEntry 为空 */
function viewOf(overrides: Partial<GameViewApi> = {}): GameViewApi {
  return {
    id: 107, name: '加时夜战 · 临时凑',
    organizer: person(6, '石景山铁腰'),
    start_at: '2026-10-06T21:00:00+08:00', end_at: '2026-10-06T22:00:00+08:00', deadline_at: '2026-10-06T19:00:00+08:00',
    venue_name: '望京 · 花家地球馆', venue_address: null,
    min_players: 4, max_players: 6, visibility: 'played',
    scoring: 11, rotation: 'balance', score_rule: 'rally',
    manual_lock: false, courts: null, fee_total: 300,
    status: 'open', unlocked: false, joinable: true, heads: 2, slots_left: 4, per_head: null, forced: false,
    entries: [entry(6, '石景山铁腰'), entry(4, '国贸截击手')],
    my: { is_organizer: false, my_entry: null, invited: false },
    ...overrides,
  };
}

/** 把视图灌进 store（games 列表 + current，等价 loadGames/loadDetail 的落点） */
async function seedStore(...views: GameViewApi[]) {
  api.apiListGames.mockResolvedValue(views);
  api.apiGameDetail.mockResolvedValue(views[0]!);
  const mod = await import('@/stores/game');
  const store = mod.useGameStore();
  await store.loadGames();
  return store;
}

describe('arriveMe（扫码签到）', () => {
  it('空降：名册没我 → 先报名进局，人进名册并标「中途加入」排进队首', async () => {
    const store = await seedStore(viewOf()); // 我未报名（my_entry null）
    const live = useLiveStore();
    api.apiJoinGame.mockResolvedValue(
      viewOf({
        heads: 3, slots_left: 3,
        my: { is_organizer: false, my_entry: { bring: 0, standing: 'formal', wait_seq: null }, invited: false },
      }),
    );

    const msg = await live.arriveMe(107);

    expect(msg).toBe('已到场 · 进候场区');
    expect(api.apiJoinGame).toHaveBeenCalledWith(107, 0); // 空降先成为报名球友
    const L = live.live!;
    expect(L.g.id).toBe(107);
    const me = L.roster.find((p) => p.id === U.me.id);
    expect(me?.check).toBe('join');
    expect(L.queue[0]).toBe(U.me.id); // 中途加入 · 排队首
    expect(store.findGame(107)?.heads).toBe(3); // 报名后列表已回填
  });

  it('在册但被标「未到」→ 重新扫码标「中途加入」进场，不重复报名', async () => {
    await seedStore(viewOf());
    const live = useLiveStore();
    await live.arriveMe(107); // 开现场（前 9 人 ok → 我已 ok）
    live.setCheck(U.me.id, 'absent'); // 模拟被改判「未到」
    api.apiJoinGame.mockClear();

    await live.arriveMe(107);

    expect(api.apiJoinGame).not.toHaveBeenCalled(); // 在册不重复报名
    const L = live.live!;
    expect(L.roster.find((p) => p.id === U.me.id)?.check).toBe('join');
  });

  it('已在场 → 幂等提示，状态不再变', async () => {
    await seedStore(viewOf());
    const live = useLiveStore();
    await live.arriveMe(107);
    const L1 = live.live!;
    const checkAfterFirst = L1.roster.find((p) => p.id === U.me.id)!.check;
    const queueLen = L1.queue.length;

    const msg = await live.arriveMe(107);

    expect(msg).toBeNull(); // 无新动作
    expect(live.live!.roster.find((p) => p.id === U.me.id)!.check).toBe(checkAfterFirst);
    expect(live.live!.queue.length).toBe(queueLen);
  });

  it('球局不存在 → 返回 null 并提示，不建现场', async () => {
    api.apiGameDetail.mockRejectedValue(new Error('game_not_found'));
    const live = useLiveStore();
    expect(await live.arriveMe(99999)).toBeNull();
    expect(live.hasLive).toBe(false);
  });
});

describe('真账号接管「我」位后的识别回归', () => {
  it('isMe 运行时读 U.me.id：接管后旧 id 不再算我、新 id 认得出', () => {
    expect(isMe(0)).toBe(true);
    takeoverAs(42, '海淀反手王');
    expect(isMe(0)).toBe(false);
    expect(isMe(42)).toBe(true);
    Object.assign(U.me, demo);
  });

  it('togglePerson 在真 id 下找得到「我」行（快照常量回归）', async () => {
    takeoverAs(42, '海淀反手王');
    await seedStore(viewOf());
    const live = useLiveStore();
    live.startLive((await import('@/stores/game')).useGameStore().games[0]!);
    const L = live.live!;
    // 显式把「我」放进名册并排进队首（隔离 fixture 的历史改动）
    if (!L.roster.some((p) => p.id === 42)) L.roster.push(U.me);
    L.queue = L.queue.filter((x) => x !== 42);
    live.setCheck(42, 'join');

    live.togglePerson(42, 'fire');

    const me = L.roster.find((p) => p.id === 42)!;
    expect(me.fire).toBe(true);
    expect(L.queue[0]).toBe(42); // 连战保持队首
    Object.assign(U.me, demo);
  });
});
