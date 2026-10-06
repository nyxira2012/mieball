import { describe, expect, it } from 'vitest';
import { recommend } from '@/utils/recommend';

/* 2.4 §4.2 推荐矩阵逐行 + §5 spot（从上往下先命中为准；理由句逐字用规格表） */

describe('推荐矩阵 · 双打', () => {
  it('1 片：1 人不荐——先等人（连单打都铺不满）', () => {
    expect(recommend(false, 1, 1)).toEqual({ kind: 'none', reason: '先等人' });
  });

  it('1 片：2/3 人提示可点改单打（铺不满片、但人够按单打铺满：≥片×2）', () => {
    expect(recommend(false, 2, 1)).toEqual({ kind: 'switch-singles', reason: '改了就能全员上场，不混格式' });
    expect(recommend(false, 3, 1)).toEqual({ kind: 'switch-singles', reason: '改了就能全员上场，不混格式' });
  });

  it('1 片：4 人刚好铺满荐全上全下', () => {
    expect(recommend(false, 4, 1)).toEqual({ kind: 'down', down: 'all', reason: '人人每轮都在场上' });
  });

  it('1 片：多 1/2/3 人分别荐 1/2/3人下', () => {
    expect(recommend(false, 5, 1)).toEqual({ kind: 'down', down: 'n1', reason: '等的人下一场马上轮进来' });
    expect(recommend(false, 6, 1)).toEqual({ kind: 'down', down: 'n2', reason: '候场周转顺，连庄天然被拆' });
    expect(recommend(false, 7, 1)).toEqual({ kind: 'down', down: 'n3', reason: '候场周转顺，连庄天然被拆' }); // 规格表「同上」= 同句
  });

  it('1 片：≥8 人（多出 ≥ 一整片）荐全上全下', () => {
    expect(recommend(false, 8, 1)).toEqual({ kind: 'down', down: 'all', reason: '队伍长了，全下轮得最快最公平' });
    expect(recommend(false, 20, 1)).toEqual({ kind: 'down', down: 'all', reason: '队伍长了，全下轮得最快最公平' });
  });

  it('2 片：3 人不荐、6/7 人提示改单打（两片单打铺得满）、8 人全上全下、9 人 1人下、12 人全上全下', () => {
    expect(recommend(false, 3, 2)).toEqual({ kind: 'none', reason: '先等人' });
    expect(recommend(false, 6, 2)).toEqual({ kind: 'switch-singles', reason: '改了就能全员上场，不混格式' });
    expect(recommend(false, 7, 2)).toEqual({ kind: 'switch-singles', reason: '改了就能全员上场，不混格式' });
    expect(recommend(false, 8, 2)).toEqual({ kind: 'down', down: 'all', reason: '人人每轮都在场上' });
    expect(recommend(false, 9, 2)).toEqual({ kind: 'down', down: 'n1', reason: '等的人下一场马上轮进来' });
    expect(recommend(false, 10, 2)).toEqual({ kind: 'down', down: 'n2', reason: '候场周转顺，连庄天然被拆' });
    expect(recommend(false, 11, 2)).toEqual({ kind: 'down', down: 'n3', reason: '候场周转顺，连庄天然被拆' });
    expect(recommend(false, 12, 2)).toEqual({ kind: 'down', down: 'all', reason: '队伍长了，全下轮得最快最公平' });
  });

  it('先命中：恰够单打铺满时是「改单打」行，不是「不荐」（4 人 2 片双打）', () => {
    expect(recommend(false, 4, 2).kind).toBe('switch-singles');
    expect(recommend(false, 4, 2).kind).not.toBe('none');
  });
});

describe('推荐矩阵 · 单打', () => {
  it('1 片：1 人不荐、2 人全上全下、3 人输家下、≥4 人全上全下', () => {
    expect(recommend(true, 1, 1)).toEqual({ kind: 'none', reason: '先等人' });
    expect(recommend(true, 2, 1)).toEqual({ kind: 'down', down: 'all', reason: '人人每轮都在场上' });
    expect(recommend(true, 3, 1)).toEqual({ kind: 'down', down: 'loser', reason: '单打就两种，赢家留场最顺' });
    expect(recommend(true, 4, 1)).toEqual({ kind: 'down', down: 'all', reason: '轮得最快最公平' });
    expect(recommend(true, 9, 1)).toEqual({ kind: 'down', down: 'all', reason: '轮得最快最公平' });
  });

  it('2 片：3 人不荐、4 人全上全下、5 人输家下、≥6 人全上全下', () => {
    expect(recommend(true, 3, 2)).toEqual({ kind: 'none', reason: '先等人' });
    expect(recommend(true, 4, 2)).toEqual({ kind: 'down', down: 'all', reason: '人人每轮都在场上' });
    expect(recommend(true, 5, 2)).toEqual({ kind: 'down', down: 'loser', reason: '单打就两种，赢家留场最顺' });
    expect(recommend(true, 6, 2)).toEqual({ kind: 'down', down: 'all', reason: '轮得最快最公平' });
  });
});
