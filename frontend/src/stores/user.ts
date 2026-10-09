/* 用户 store（mock 世界退役后重造）：
   - me：身份位单一源——游客零战绩占位 ↔ 登录账号（applyAccount/resetGuest 单点换装，
     由 session store 调度；装扮/名片/现场/我的页全站读它）；
   - people：真人档案缓存（榜单行 + /users/{id} 拉取落这里）——档案卡/喜欢消费；
   - leaderboard：战力榜单一源（power 页），后端已排好序；
   - liked：喜欢（静默单向）退化为本地演示态——后端无此账，换设备不同步。
   不触碰任何 uni.*；页面跳转由页面层做。 */
import { reactive, ref } from "vue";
import { defineStore } from "pinia";
import type { CardBg, User } from "@/api/types";
import type { AccountView } from "@/api/auth";
import {
  apiAccountView,
  apiLeaderboard,
  type LeaderboardRowApi,
} from "@/api/accounts";
import { useUiStore } from "./ui";

import type { DressPart } from "@/utils/chibi";

/** 游客占位身份（零战绩——假演示数字已随 mock 退役）：id 0 后端无此人，
    各页按「未开局」口径渲染（还没开张 / 起步分 / —） */
export const GUEST_USER: User = {
  id: 0,
  name: "我",
  elo: 0,
  play: 0,
  win: 0,
  month: 0,
  last5: [],
  chibi: { skin: 1, hair: 5, hc: 0, shirt: 0, face: 1, acc: 2 },
  cardBg: "neon",
};

/** 账号视图（AccountView/榜单行同形）→ 档案 User：elo 轨不在账号视图，
    保留现场结算行的回填值（live store 落） */
function accountToUser(view: AccountView | LeaderboardRowApi): User {
  return {
    id: view.id,
    name: view.name,
    elo: 0,
    dupr: view.dupr_rating,
    provisional: view.dupr_provisional,
    duprGames: view.dupr_games,
    play: view.dupr_games,
    win: view.dupr_wins,
    month: view.dupr_month_net ?? 0,
    last5: [...(view.dupr_last5 || [])] as ("W" | "L")[],
    chibi: { ...view.chibi },
    cardBg: view.card_bg ?? undefined,
  };
}

export const useUserStore = defineStore("user", () => {
  /** 我（reactive 原位换装：applyAccount/resetGuest Object.assign，全站引用联动） */
  const me = reactive<User>({ ...GUEST_USER, chibi: { ...GUEST_USER.chibi } });

  /** 真人档案缓存（榜单灌入 + ensurePerson 单发补拉）：findUser 的非现场来源 */
  const people = reactive<Record<number, User>>({});

  /** 喜欢（静默单向，本地演示态）：按人 id 记 */
  const likedIds = ref(new Set<number>());

  /** 上过场谓词单一源（榜单/档案卡/我的卡三处口径收敛）：非随行且打过至少一场 */
  function hasPlayed(u: User): boolean {
    return !u.shadow && u.play > 0;
  }

  /** 是否当前登录用户（运行时读 me.id：登录换装后 id 联动） */
  function isMe(id?: number): boolean {
    return id === me.id;
  }

  /** 档案取人（账号 id 空间）：我本人 → people 缓存；查无 undefined
      （ProfileSheet 对 miss 自拉兜底）。现场名册行 id 是另一套空间（写动作
      靶位），不在这里混查——现场侧开档案一律传 accountId */
  function findUser(id: number): User | undefined {
    if (id === me.id) return me;
    return people[id];
  }

  /** 喜欢：静默单向（alpha:1922-1925），约球页/意向列表优先展示；本地态退出即清 */
  function toggleLike(id: number): string {
    const u = findUser(id);
    if (!u) return "";
    if (likedIds.value.has(id)) likedIds.value.delete(id);
    else likedIds.value.add(id);
    const on = likedIds.value.has(id);
    const msg = on ? `已喜欢 ${u.name} · 静默标记，约球页优先` : "已取消喜欢";
    useUiStore().toast(msg);
    return msg;
  }

  function isLiked(id: number): boolean {
    return likedIds.value.has(id);
  }

  /* ---- 战力榜（power 页单一源；后端 DUPR 降序同分 id 升序） ---- */

  const leaderboard = ref<User[]>([]);
  const lbLoading = ref(false);

  /** 拉榜：rows 落位并顺手灌 people 缓存（点榜上人开档案卡零等待）；
      失败上抛由页面 toast + 重试 */
  async function loadLeaderboard(): Promise<void> {
    lbLoading.value = true;
    try {
      const rows = await apiLeaderboard();
      leaderboard.value = rows.map((r) => accountToUser(r));
      for (const u of leaderboard.value) people[u.id] = u;
    } finally {
      lbLoading.value = false;
    }
  }

  /** 档案兜底：弹层开着的人/现场名册行不在缓存时单发 /users/{id}；
      在途去重（视图轮询 3s 一发，别把同一个人打成请求风暴） */
  const pendingIds = new Set<number>();
  async function ensurePerson(id: number): Promise<void> {
    if (id === me.id || people[id] || pendingIds.has(id)) return;
    pendingIds.add(id);
    try {
      const { account } = await apiAccountView(id);
      people[id] = accountToUser(account);
    } catch {
      /* 拉不到保持缺省：档案层自显空态，不弹错 */
    } finally {
      pendingIds.delete(id);
    }
  }

  /* ---- 身份换装（session store 调度：登录/退出/注销/改名片） ---- */

  /** 登录/改名片：账号视图落 me（原位 Object.assign，reactive 代理全站同步换新） */
  function applyAccount(view: AccountView): void {
    const elo = me.elo; // elo 轨不在账号视图，保留现场回填值
    Object.assign(me, accountToUser(view), { elo });
  }

  /** 退出/注销回落游客：占位身份原位复位；喜欢是本地态，换了身份不带走 */
  function resetGuest(): void {
    likedIds.value.clear();
    Object.assign(me, GUEST_USER, { chibi: { ...GUEST_USER.chibi } });
  }

  /* —— 5.1 我的页纯增量：装扮页即点即换 —— */

  /** 装扮页选件即换（5.1）：直接落 me.chibi，不 toast —— 预览即反馈，页面安静 */
  function setVariant(part: DressPart, v: number): void {
    me.chibi[part] = v;
  }

  /** 卡背背景即点即换（5.1）：落 me.cardBg 不 toast，即点即换全局同步（战力页卡背联动） */
  function setCardBg(v: CardBg): void {
    me.cardBg = v;
  }

  return {
    me,
    people,
    leaderboard,
    lbLoading,
    hasPlayed,
    isMe,
    isLiked,
    findUser,
    toggleLike,
    loadLeaderboard,
    ensurePerson,
    applyAccount,
    resetGuest,
    setVariant,
    setCardBg,
  };
});
