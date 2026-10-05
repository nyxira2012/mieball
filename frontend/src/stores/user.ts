/* 用户 store（alpha:846-847 findUser · alpha:1922-1929 toggleLike · alpha:1958-1975 换装）
   不触碰任何 uni.*；页面跳转由页面层做。 */
import { computed, reactive } from 'vue';
import { defineStore } from 'pinia';
import { U } from '@/api';
import type { CardBg, User } from '@/api/types';
import { useLiveStore } from './live';
import { useUiStore } from './ui';

import type { DressPart } from '@/utils/chibi';

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

  /** 上过场谓词单一源（alpha:865 榜单 / 1027 意向卡 / 1895 档案卡三处口径收敛）：非随行且打过至少一场 */
  function hasPlayed(u: User): boolean {
    return !u.shadow && u.play > 0;
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

  /* —— 5.1 我的页纯增量：装扮页即点即换 + 账号操作（mock 不接真后端，toast 即验收面）—— */
  /* 批4：旧换装三件套（选中部件 ref + 选件/点小人循环换两个动作，SC5 化石）已随「点头像循环换装」
     交互退场 —— 新交互（装扮页变体 chips）走下方 setVariant */

  /** 装扮页选件即换（5.1）：直接落 me.chibi，不 toast —— 预览即反馈，页面安静 */
  function setVariant(part: DressPart, v: number): void {
    users.me.chibi[part] = v;
  }

  /** 卡背背景即点即换（5.1）：与 setVariant 同族 —— 落 me.cardBg 不 toast，即点即换全局同步（战力页卡背联动） */
  function setCardBg(v: CardBg): void {
    users.me.cardBg = v;
  }

  /* 账号动作（建号/找回/接管/退出/注销/云端保存名片）已移至 session store（1.1）；
     密码与微信授权随 MVP 下架（评审 D1）。 */

  return {
    users, me, findUser, hasPlayed, toggleLike,
    setVariant, setCardBg,
  };
});
