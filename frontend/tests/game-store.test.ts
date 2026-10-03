import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';

/* 每个用例 vi.resetModules() 重新求值模块图 → 拿到全新 mock 数据（等价 alpha 刷新页面） */
beforeEach(async () => {
  vi.resetModules();
  setActivePinia(createPinia());
});
afterEach(() => {
  vi.useRealTimers();
});

async function loadStore() {
  const mod = await import('@/stores/game');
  return mod.useGameStore();
}

describe('joinGame（alpha:1127-1138 doJoin）', () => {
  it('带人占坑：joined 追加 {u:me, bring}，文案带共占坑数', async () => {
    const s = await loadStore();
    const msg = s.joinGame(103, 2); // 103：wu+yang 2 人，cap 6
    const g = s.games.find((x) => x.id === 103)!;
    expect(msg).toBe('已加入 · 带了 2 人（共占 3 坑）');
    const mine = g.joined.find((e) => e.u.id === 0);
    expect(mine?.bring).toBe(2);
    expect(g.invitedMe).toBeFalsy();
  });

  it('满员 → 进候补栏（heads≥cap 判定）', async () => {
    const s = await loadStore();
    const { U } = await import('@/api');
    const g = s.games.find((x) => x.id === 105)!; // tong 1 人 · cap 4
    g.joined.push({ u: U.wang }, { u: U.hai }, { u: U.wu }); // 排满到 4/4（用例布置）
    const msg = s.joinGame(105);
    expect(msg).toBe('已进候补栏 · 有人退出即刻递补');
    expect(g.wait.map((e) => e.u.id)).toEqual([0]);
    expect(g.joined.some((e) => e.u.id === 0)).toBe(false);
  });

  it('已加入 → 不重复加入（返回 null）', async () => {
    const s = await loadStore();
    const g = s.games.find((x) => x.id === 102)!; // 我在 102 名单里
    const n = g.joined.length;
    expect(s.joinGame(102)).toBeNull();
    expect(g.joined).toHaveLength(n);
  });

  it('被邀请局加入后 invitedMe 清除', async () => {
    const s = await loadStore();
    const g = s.games.find((x) => x.id === 106)!;
    expect(g.invitedMe).toBe(true);
    s.joinGame(106);
    expect(g.invitedMe).toBe(false);
  });
});

describe('hitDeadline 两分支（alpha:1177-1189）', () => {
  it('低于最少且未锁必打 → dead（自动终止）', async () => {
    const s = await loadStore();
    const msg = s.hitDeadline(103); // 2/4 人，未 sure
    const g = s.games.find((x) => x.id === 103)!;
    expect(msg).toBe('到截止 · 人数不足，局自动终止（组织者「我的局」留有未成局，可恢复）');
    expect(g.dead).toBe(true);
  });
  it('人数达标 → locked（名单锁定）', async () => {
    const s = await loadStore();
    const msg = s.hitDeadline(102); // 4/4 人 ≥ min
    const g = s.games.find((x) => x.id === 102)!;
    expect(msg).toBe('到截止 · 名单锁定，参加者不能再退出');
    expect(g.locked).toBe(true);
    expect(g.dead).toBeFalsy();
  });
  it('人不够但已锁必打 → locked 而非 dead', async () => {
    const s = await loadStore();
    s.sureGame(105); // 1/4 人
    const msg = s.hitDeadline(105);
    const g = s.games.find((x) => x.id === 105)!;
    expect(g.locked).toBe(true);
    expect(g.dead).toBeFalsy();
    expect(msg).toBe('到截止 · 名单锁定，参加者不能再退出');
  });
});

describe('addCourt 候补转正（alpha:1198-1206：上限 +2，候补按先后自动转正）', () => {
  it('候补全部转正', async () => {
    const s = await loadStore();
    const { U } = await import('@/api');
    const g = s.games.find((x) => x.id === 105)!; // 1/4
    g.joined.push({ u: U.wang }, { u: U.hai }, { u: U.wu }); // 4/4
    s.joinGame(105); // 我进候补
    const msg = s.addCourt(105);
    expect(g.cap).toBe(6);
    expect(g.wait).toHaveLength(0);
    expect(g.joined.some((e) => e.u.id === 0)).toBe(true);
    expect(msg).toBe('已加场 · 候补已全部转正');
  });
  it('候补多于新增坑位：按先后转正，剩余留候补', async () => {
    const s = await loadStore();
    const { U } = await import('@/api');
    const g = s.games.find((x) => x.id === 107)!; // 2/6
    g.joined.push({ u: U.wang }, { u: U.hai }, { u: U.wu }, { u: U.yang }); // 6/6
    s.joinGame(107); // 候补[我]
    g.wait.push({ u: U.tong }, { u: U.ken }, { u: U.zhang }); // 候补共 4 人（用例布置）
    const msg = s.addCourt(107); // cap 6→8，只转正 2 人（我、tong）
    expect(g.cap).toBe(8);
    expect(g.wait.map((e) => e.u.id)).toEqual([11, 12]); // 先进先出，ken/zhang 留下
    expect(g.joined.at(-2)?.u.id).toBe(0);
    expect(g.joined.at(-1)?.u.id).toBe(9); // tong
    expect(msg).toBe('已加场 · 候补转正，仍剩 2 人满员（建议下次再参加）');
  });
});

describe('publish / edit（alpha:1375-1398）', () => {
  it('发布：局名自动起名「时间 · 地点」、tb/area 推断、我在名单头一个、插到列表最前', async () => {
    const s = await loadStore();
    const n = s.games.length;
    const msg = s.publishGame({
      name: '', time: '周六 10:00', dur: 2, deadline: '打前 2 小时',
      venue: '工体北路 · 京篮匹克球馆', min: 4, cap: 6, fee: 300, note: '  ',
    });
    const g = s.games[0];
    expect(msg).toBe('局已发布 · 名单头一个就是你，点局上的 ⤴ 分享到群里拉人');
    expect(s.games).toHaveLength(n + 1);
    expect(g.name).toBe('周六 · 京篮匹克球馆');
    expect(g.tb).toBe('weekend');
    expect(g.area).toBe('工体');
    expect(g.joined).toEqual([{ u: expect.objectContaining({ id: 0 }) }]);
    expect(g.note).toBe('');
    expect(g.status).toBe('open');
  });
  it('发布：今晚/自定义场地 → tonight / 其他', async () => {
    const s = await loadStore();
    s.publishGame({
      name: '自定义名', time: '今晚 21:30', dur: 1, deadline: '打前 2 小时',
      venue: '朝阳公园某馆', min: 2, cap: 4, fee: 100, note: '',
    });
    const g = s.games[0];
    expect(g.name).toBe('自定义名');
    expect(g.tb).toBe('tonight');
    expect(g.area).toBe('其他');
  });
  it('编辑：名单不动、截止定死不改', async () => {
    const s = await loadStore();
    const g = s.games.find((x) => x.id === 101)!;
    const joinedBefore = g.joined.map((e) => e.u.id);
    const msg = s.editGame(101, {
      name: '改名夜战', time: '今晚 20:00', dur: 3, deadline: '今天 17:00',
      venue: '望京 · 花家地球馆', min: 6, cap: 10, fee: 500, note: '改了说明',
    });
    expect(msg).toBe('局已改好 · 名单里的人看到的就是新信息');
    expect(g.deadline).toBe('今天 17:00'); // 截止定死
    expect(g.joined.map((e) => e.u.id)).toEqual(joinedBefore);
    expect(g.name).toBe('改名夜战');
    expect(g.area).toBe('望京');
    expect(g.tb).toBe('tonight');
    expect(g.cap).toBe(10);
  });
});

describe('quit / cancel / restore（alpha:1148-1212）', () => {
  it('退局：名单与候补里都有我就清掉', async () => {
    const s = await loadStore();
    const { U } = await import('@/api');
    s.joinGame(103);      // 我进名单
    const g = s.games.find((x) => x.id === 103)!;
    g.wait.push({ u: U.me }); // 用例布置：候补里也有我
    const msg = s.quitGame(103);
    expect(msg).toBe('已退出 · 名单里少了你');
    expect(g.joined.some((e) => e.u.id === 0)).toBe(false);
    expect(g.wait.some((e) => e.u.id === 0)).toBe(false);
  });
  it('取消局：从列表整体消失', async () => {
    const s = await loadStore();
    const n = s.games.length;
    const msg = s.cancelGame(103);
    expect(msg).toBe('局已撤下 · 报名的球友「我的局」里同步消失');
    expect(s.games).toHaveLength(n - 1);
    expect(s.games.some((x) => x.id === 103)).toBe(false);
  });
  it('恢复未成局：dead 归位、名单原样', async () => {
    const s = await loadStore();
    s.hitDeadline(103); // → dead
    const g = s.games.find((x) => x.id === 103)!;
    expect(g.dead).toBe(true);
    const msg = s.restoreGame(103);
    expect(msg).toBe('局已恢复 · 名单原样回来，再决定必定开局还是撤局');
    expect(g.dead).toBe(false);
    expect(g.joined.map((e) => e.u.id)).toEqual([3, 7]); // wu, yang 原样
  });
});

describe('shareGame（alpha:1224-1237）：3 秒模拟小张加入并带 1 人（仅组织者首次）', () => {
  it('组织者分享 → 3 秒后小张带 1 人进名单；再次分享不重复', async () => {
    vi.useFakeTimers();
    const s = await loadStore();
    const g = s.games.find((x) => x.id === 102)!; // 我是组织者
    const msg = s.shareGame(102);
    expect(msg).toBe('分享卡片已生成 · 转到微信群里拉人');
    expect(g.joined.some((e) => e.u.id === 12)).toBe(false);
    await vi.advanceTimersByTimeAsync(3000);
    expect(g.joined.find((e) => e.u.id === 12)?.bring).toBe(1);
    s.shareGame(102); // 第二次分享不重复拉人
    await vi.advanceTimersByTimeAsync(3000);
    expect(g.joined.filter((e) => e.u.id === 12)).toHaveLength(1);
  });
  it('非组织者分享 → 无人加入', async () => {
    vi.useFakeTimers();
    const s = await loadStore();
    const g = s.games.find((x) => x.id === 103)!;
    s.shareGame(103);
    await vi.advanceTimersByTimeAsync(3000);
    expect(g.joined.some((e) => e.u.id === 12)).toBe(false);
  });
});

describe('inviteUser（alpha:1249-1263）：3.2 秒模拟对方点一下就加入，意向标记 done', () => {
  it('邀请后对方加入名单（未满员 → joined）', async () => {
    vi.useFakeTimers();
    const s = await loadStore();
    const msg = s.inviteUser(9, 103); // 通州长胶姨 → 夜光单挑夜
    expect(msg).toBe('已邀请 通州长胶姨 · 局已出现在 ta 的「我的局」');
    const g = s.games.find((x) => x.id === 103)!;
    await vi.advanceTimersByTimeAsync(3200);
    expect(g.joined.some((e) => e.u.id === 9)).toBe(true);
    expect(s.intents.find((i) => i.u.id === 9)?.done).toBe(true);
  });
});

describe('saveIntent / delIntent / waveCount（alpha:827, 1286-1297）', () => {
  it('空时段拦截 / 更新 / 删除 / 同波段计数', async () => {
    const s = await loadStore();
    expect(s.waveCount).toBe(3); // 初始 we-n：wang/hai/li
    expect(s.saveIntent([], 2)).toBe('至少选一个时段');
    expect(s.myIntent).toEqual({ slots: ['we-n'], freq: 2 }); // 原值未动
    expect(s.saveIntent(['wd', 'we-d'], 1)).toBe('意向已更新 · 想改随时改');
    expect(s.myIntent).toEqual({ slots: ['wd', 'we-d'], freq: 1 });
    expect(s.waveCount).toBe(7); // wd:hai/wu/shi/zhang + we-d:li/yang/ken
    expect(s.delIntent()).toBe('意向已删 · 随时可以再留');
    expect(s.myIntent).toBeNull();
    expect(s.waveCount).toBe(0);
  });
});
