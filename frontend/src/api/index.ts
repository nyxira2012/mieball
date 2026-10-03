/* api 统一出口 —— stores / 页面一律从这里取数（后续接真后端只动 api/ 这一层） */
export * from './types';
export * from './mock';

/** 约 3 秒模拟网络延时（shareGame 3 秒 · inviteUser 3.2 秒的 setTimeout 模拟要用，alpha:1229 / 1255） */
export function delay(ms = 3000): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
