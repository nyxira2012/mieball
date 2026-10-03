/* 用户 store（alpha:846-847 findUser · alpha:1922-1929 toggleLike · alpha:1958-1975 换装）
   不触碰任何 uni.*；页面跳转由页面层做。 */
import { computed, reactive, ref } from 'vue';
import { defineStore } from 'pinia';
import { U } from '@/api';
import type { User } from '@/api/types';
import { useLiveStore } from './live';
import { useUiStore } from './ui';

/** 换装部件（alpha:1932-1933） */
export const DRESS_PARTS = ['skin', 'hair', 'hc', 'shirt', 'face', 'acc'] as const;
export type DressPart = typeof DRESS_PARTS[number];
export const PART_NAMES: Record<DressPart, string> = { skin: '肤色', hair: '发型', hc: '发色', shirt: '球衣', face: '表情', acc: '配饰' };

export const useUserStore = defineStore('user', () => {
  /** U 的同一份可变引用；reactive(U) 与 games/live 根读到的都是同一批代理对象 */
  const users = reactive(U);
  /** 我（alpha:762 U.me） */
  const me = computed(() => users.me);

  /** alpha:846-847：现场名册优先，再查 U 全表 */
  function findUser(id: number): User | undefined {
    const live = useLiveStore();
    if (live.live) {
      const p = live.live.roster.find((x) => x.id === id);
      if (p) return p;
    }
    return Object.values(users).find((u) => u.id === id);
  }

  /** 喜欢：静默单向（alpha:1922-1925），约球页/意向列表优先展示 */
  function toggleLike(id: number): string {
    const u = findUser(id);
    if (!u) return '';
    u.liked = !u.liked;
    const msg = u.liked ? `已喜欢 ${u.name} · 静默标记，约球页优先` : '已取消喜欢';
    useUiStore().toast(msg);
    return msg;
  }

  /** 当前选中的换装部件（alpha:1959 let dressPart='shirt'） */
  const dressPart = ref<DressPart>('shirt');
  /** 部件选择 chips（alpha:1970-1972） */
  function setDressPart(p: DressPart): string {
    dressPart.value = p;
    const msg = `选中「${PART_NAMES[p]}」· 点小人换`;
    useUiStore().toast(msg);
    return msg;
  }
  /** 点小人循环换（alpha:1960-1964：chibi[part]+1，逐字口径） */
  function cyclePart(): string {
    const m = users.me;
    m.chibi[dressPart.value] = (m.chibi[dressPart.value] || 0) + 1;
    const msg = `已换${PART_NAMES[dressPart.value]} · 再点继续换`;
    useUiStore().toast(msg);
    return msg;
  }

  return { users, me, findUser, toggleLike, dressPart, setDressPart, cyclePart };
});
