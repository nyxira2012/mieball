/* 用户 store（alpha:846-847 findUser · alpha:1922-1929 toggleLike · alpha:1958-1975 换装）
   不触碰任何 uni.*；页面跳转由页面层做。 */
import { computed, reactive } from 'vue';
import { defineStore } from 'pinia';
import { U } from '@/api';
import type { CardBg, User } from '@/api/types';
import { useLiveStore } from './live';
import { useUiStore } from './ui';

/** 换装部件（alpha:1932-1933） */
export const DRESS_PARTS = ['skin', 'hair', 'hc', 'shirt', 'face', 'acc'] as const;
export type DressPart = typeof DRESS_PARTS[number];
export const PART_NAMES: Record<DressPart, string> = { skin: '肤色', hair: '发型', hc: '发色', shirt: '球衣', face: '表情', acc: '配饰' };
/** 每部件可选变体数（值域 0..n-1）。同一真值还有两处硬编码：utils/chibi.ts 的越界模数、
    stores/live.ts startLive 给随行访客随机的 Math.random()*n —— 改这里必须三处同步，
    否则随机/渲染会越界出图。 */
export const DRESS_RANGES: Record<DressPart, number> = { skin: 4, hair: 6, hc: 6, shirt: 8, face: 4, acc: 3 };

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

  /** 保存资料（5.1 装扮页）：昵称非空才落；我是同一份对象引用，改名即全站同步 */
  function saveProfile(name: string): string {
    const n = name.trim();
    if (!n) {
      const m = '昵称不能为空';
      useUiStore().toast(m);
      return m;
    }
    users.me.name = n;
    const msg = '已保存 · 全局同步换新';
    useUiStore().toast(msg);
    return msg;
  }

  /** 修改密码（5.1）：原密非空 / 新密≥6 位 / 两次一致，按序拦截 */
  function changePwd(oldPwd: string, p1: string, p2: string): string {
    const fail = !oldPwd ? '请输入原密码'
      : p1.length < 6 ? '新密码至少 6 位'
        : p1 !== p2 ? '两次输入的新密码不一致' : null;
    if (fail) {
      useUiStore().toast(fail);
      return fail;
    }
    const msg = '密码已修改 · 下次登录用新密码';
    useUiStore().toast(msg);
    return msg;
  }

  /** 微信授权登录（5.1）：小程序 / H5 / App 三端账号通用 */
  function wechatAuth(): string {
    const msg = '已授权 · 小程序 / H5 / App 账号通用';
    useUiStore().toast(msg);
    return msg;
  }

  /** 退出账号（5.1）：仅本机登出，云端数据不动 */
  function logout(): string {
    const msg = '已退出本机登录 · 数据都在云端';
    useUiStore().toast(msg);
    return msg;
  }

  /** 注销账号（5.1）：永久删除；mock 无真后端，toast 即验收面 */
  function deleteAccount(): string {
    const msg = '已注销 · 形象匿名化 · 手机号释放';
    useUiStore().toast(msg);
    return msg;
  }

  return {
    users, me, findUser, toggleLike,
    setVariant, setCardBg, saveProfile, changePwd, wechatAuth, logout, deleteAccount,
  };
});
