import { describe, expect, it } from 'vitest';
import { shouldEnd, undoScore } from '@/utils/score';

describe('shouldEnd：先到 N 且净胜 2 才算赢（alpha:1686）', () => {
  const T = 11;
  it('11:9 → 收局', () => {
    expect(shouldEnd(11, 9, T)).toBe(true);
  });
  it('11:10 → 继续（净胜不足 2）', () => {
    expect(shouldEnd(11, 10, T)).toBe(false);
  });
  it('12:10 → 收局', () => {
    expect(shouldEnd(12, 10, T)).toBe(true);
  });
  it('10:11 → 继续（B 到分但净胜 1）', () => {
    expect(shouldEnd(10, 11, T)).toBe(false);
  });
  it('没到 target 不收', () => {
    expect(shouldEnd(10, 8, T)).toBe(false);
  });
  it('15 分制的局（103 夜光单挑夜）', () => {
    expect(shouldEnd(15, 13, 15)).toBe(true);
    expect(shouldEnd(15, 14, 15)).toBe(false);
  });
});

describe('undoScore：按最后得分方回退（alpha:1676-1679）', () => {
  it('最后 A 得分 → 退 A', () => {
    expect(undoScore(5, 3, 'a')).toEqual({ sa: 4, sb: 3 });
  });
  it('最后 B 得分 → 退 B', () => {
    expect(undoScore(3, 5, 'b')).toEqual({ sa: 3, sb: 4 });
  });
  it('alpha 原样 quirk：last=a 但 sa=0 时落到 else-if 退 B', () => {
    expect(undoScore(0, 5, 'a')).toEqual({ sa: 0, sb: 4 });
  });
  it('0:0 且无 last → 原样', () => {
    expect(undoScore(0, 0, undefined)).toEqual({ sa: 0, sb: 0 });
  });
});
