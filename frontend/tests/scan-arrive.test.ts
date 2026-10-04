/* 扫码自签到链路（2.1·选项A）+ 「我」id 运行时化回归：
   - arriveMe：空降（名册没我）→ 报名进名册 + 中途加入队首；在册未到 → 到场；已在场 → 幂等
   - 真账号接管 U.me（id 非 0）后：isMe/myEntry 认得出、toggleMine 找得到人（快照常量回归） */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { U } from '@/api/mock';
import { isMe, myEntry } from '@/utils/format';
import { useGameStore } from '@/stores/game';
import { useLiveStore } from '@/stores/live';

/** 演示态快照（用例后恢复，避免串扰） */
const demo = { id: U.me.id, name: U.me.name };

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
  // 安静模式：store 动作的 toast 走 ui store（纯内存），无需 mock
});

/** 模拟真账号接管「我」位（session store applyIdentity 的等价操作） */
function takeoverAs(id: number, name: string): void {
  Object.assign(U.me, { id, name });
}

describe('arriveMe（扫码签到）', () => {
  it('空降：名册没我 → 先报名进局，人进名册并标「中途加入」排进队首', () => {
    const game = useGameStore();
    const live = useLiveStore();
    // 用一个我没报过名的局（102 我在 joined 里，选 103）
    const gid = game.games.find((g) => !myEntry(g) && g.status !== 'done')!.id;

    const msg = live.arriveMe(gid);

    expect(msg).toBe('已到场 · 进候场区');
    expect(myEntry(game.games.find((g) => g.id === gid)!)).toBeTruthy(); // 已报名
    const L = live.live!;
    expect(L.g.id).toBe(gid);
    const me = L.roster.find((p) => p.id === U.me.id);
    expect(me?.check).toBe('join');
    expect(L.queue[0]).toBe(U.me.id); // 中途加入 · 排队首
  });

  it('在册但被标「未到」→ 重新扫码标「中途加入」进场，不重复报名', () => {
    const game = useGameStore();
    const live = useLiveStore();
    const g = game.games.find((x) => !!myEntry(x) && x.status !== 'done')!;
    live.arriveMe(g.id); // 开现场（demo 局里我在前 9 → 已是 ok）
    live.setCheck(U.me.id, 'absent'); // 模拟被改判「未到」
    const before = g.joined.length;

    live.arriveMe(g.id);

    expect(g.joined.length).toBe(before); // 没有重复报名
    const L = live.live!;
    expect(L.roster.find((p) => p.id === U.me.id)?.check).toBe('join');
  });

  it('已在场 → 幂等提示，状态不再变', () => {
    const live = useLiveStore();
    const gid = live.live?.g.id ?? null;
    // 先到场一次
    const game = useGameStore();
    const target = gid ?? game.games.find((x) => x.status !== 'done')!.id;
    live.arriveMe(target);
    const L1 = live.live!;
    const checkAfterFirst = L1.roster.find((p) => p.id === U.me.id)!.check;
    const queueLen = L1.queue.length;

    const msg = live.arriveMe(target);

    expect(msg).toBeNull(); // 无新动作
    expect(live.live!.roster.find((p) => p.id === U.me.id)!.check).toBe(checkAfterFirst);
    expect(live.live!.queue.length).toBe(queueLen);
  });

  it('球局不存在 → 返回 null 并提示，不建现场', () => {
    const live = useLiveStore();
    expect(live.arriveMe(99999)).toBeNull();
    expect(live.hasLive).toBe(false);
  });
});

describe('真账号接管「我」位后的识别回归', () => {
  it('isMe/myEntry 运行时读 U.me.id：接管后旧 id 不再算我、新 id 认得出', () => {
    expect(isMe(0)).toBe(true);
    takeoverAs(42, '海淀反手王');
    expect(isMe(0)).toBe(false);
    expect(isMe(42)).toBe(true);
    // myEntry 按新 id 找得到「我」的报名条目（显式构造，不依赖共享 games 状态）
    expect(myEntry({ joined: [{ u: U.me }] } as unknown as Parameters<typeof myEntry>[0])).toBeTruthy();
    Object.assign(U.me, demo);
  });

  it('toggleMine 在真 id 下找得到「我」行（快照常量回归）', () => {
    takeoverAs(42, '海淀反手王');
    const game = useGameStore();
    const live = useLiveStore();
    const gid = game.games.find((x) => x.status !== 'done')!.id;
    live.startLive(gid);
    const L = live.live!;
    // 显式把「我」放进名册并排进队首（隔离共享 games 的历史改动）
    if (!L.roster.some((p) => p.id === 42)) L.roster.push(U.me);
    L.queue = L.queue.filter((x) => x !== 42);
    live.setCheck(42, 'join');

    live.toggleMine('fire');

    const me = L.roster.find((p) => p.id === 42)!;
    expect(me.fire).toBe(true);
    expect(L.queue[0]).toBe(42); // 连战保持队首
    Object.assign(U.me, demo);
  });
});
