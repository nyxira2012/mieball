/* ui 全局状态（alpha:832-847 toast/sheet · alpha:850 scoreMode · alpha:1716 winpop）
   不触碰任何 uni.* —— 纯状态层；SheetHost/AppToast/WinPopup 组件负责渲染（P1/P3 接线） */
import { ref } from 'vue';
import { defineStore } from 'pinia';
import type { ScoreMode, SheetPayload, WinData } from '@/api/types';

export const useUiStore = defineStore('ui', () => {
  /** 分制，默认 elo（alpha:850 let scoreMode='elo'） */
  const scoreMode = ref<ScoreMode>('elo');
  /** 全局单例弹层（alpha:836 openSheet：全局唯一 #sheet，按 payload.type 分发渲染） */
  const sheet = ref<SheetPayload | null>(null);
  /** 胜利结算卡（alpha:1716-1725：层级最高，独立 WinPopup 组件、不走 SheetHost） */
  const win = ref<WinData | null>(null);
  /** 自绘 toast（alpha:834-835）。key 自增：重复消息也能重触发组件动画。
      2200ms 自动隐藏的计时器由 AppToast 组件按 toastKey 变化自行管理。 */
  const toastMsg = ref('');
  const toastKey = ref(0);

  function openSheet(p: SheetPayload): void { sheet.value = p; }
  function closeSheet(): void { sheet.value = null; }
  function toast(msg: string): void {
    toastMsg.value = msg;
    toastKey.value++;
  }
  /** alpha:1739-1744 setScoreMode（切回同档静默；切换 toast 文案逐字保留） */
  function setScoreMode(m: ScoreMode): void {
    if (scoreMode.value === m) return;
    scoreMode.value = m;
    toast(m === 'elo' ? '已切至 Elo 分制 · 默认 1500 起' : '已切至 NTRP 分制 · 2.0-5.0 国际分级');
  }
  function showWin(w: WinData): void { win.value = w; }
  function closeWin(): void { win.value = null; } // alpha:1729 closeWin

  return { scoreMode, sheet, win, toastMsg, toastKey, openSheet, closeSheet, toast, setScoreMode, showWin, closeWin };
});
