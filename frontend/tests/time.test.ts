import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { gameTime, untilTxt } from '@/utils/time';

/* 以 2026-10-04（周日）12:00 为「现在」做确定性解析（fake timers 冻结 Date） */
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date(2026, 9, 4, 12, 0, 0));
});
afterEach(() => {
  vi.useRealTimers();
});

describe('gameTime（alpha:959-974 中文相对日解析）', () => {
  it('今晚 → 今天该点', () => {
    expect(gameTime('今晚 19:00')).toEqual(new Date(2026, 9, 4, 19, 0));
  });
  it('明晚 → 明天该点', () => {
    expect(gameTime('明晚 19:30')).toEqual(new Date(2026, 9, 5, 19, 30));
  });
  it('周六（今天周日）→ 顺延到本周六', () => {
    expect(gameTime('周六 14:00')).toEqual(new Date(2026, 9, 10, 14, 0));
  });
  it('今天的周X已过 → 顺延下周（alpha:970）', () => {
    // 今天就是周日，10:00 已过 → 下周日
    expect(gameTime('周日 10:00')).toEqual(new Date(2026, 9, 11, 10, 0));
  });
  it('本周还没到的周X → 本周', () => {
    expect(gameTime('周三 20:00')).toEqual(new Date(2026, 9, 7, 20, 0));
  });
  it('下周X → 恒定跳到下周（alpha:965-966）', () => {
    expect(gameTime('下周三 20:00')).toEqual(new Date(2026, 9, 14, 20, 0));
  });
});

describe('untilTxt（alpha:975-981）', () => {
  it('分钟 / 小时 / 天 三档', () => {
    expect(untilTxt(new Date(2026, 9, 4, 12, 30))).toBe('30 分钟');
    expect(untilTxt(new Date(2026, 9, 4, 13, 30))).toBe('1 小时 30 分');
    expect(untilTxt(new Date(2026, 9, 7, 12, 0))).toBe('3 天');
  });
  it('已过 → null', () => {
    expect(untilTxt(new Date(2026, 9, 4, 11, 0))).toBeNull();
  });
});
