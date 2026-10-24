/* 用户 store（mock 世界退役后重造）：
   - me：身份位单一源——游客零战绩占位 ↔ 登录账号（applyAccount/resetGuest 单点换装，
     由 session store 调度；装扮/名片/现场/我的页全站读它）；
   - people：真人档案缓存（榜单行 + /users/{id} 拉取落这里）——档案卡/喜欢消费；
   - leaderboard：战力榜单一源（power 页），后端已排好序；
   - liked：喜欢（静默单向）退化为本地演示态——后端无此账，换设备不同步。
   不触碰任何 uni.*；页面跳转由页面层做。 */
import { reactive, ref } from "vue";
import { defineStore } from "pinia";
import type { User } from "@/api/types";
import type { AccountView } from "@/api/auth";
import type { DressingApi } from "@/api/cosmetics";
import {
  apiAccountView,
  apiLeaderboard,
  type LeaderboardRowApi,
} from "@/api/accounts";
import { useUiStore } from "./ui";

/** 游客占位身份（零战绩——假演示数字已随 mock 退役）：id 0 后端无此人，
    各页按「未开局」口径渲染（还没开张 / 起步分 / —）。头像/卡背不带键——
    AvatarBadge 默认公共款兜底、卡片素卡（访客的脸面口径） */
export const GUEST_USER: User = {
  id: 0,
  name: "访客",
  elo: 0,
  play: 0,
  win: 0,
  month: 0,
  last5: [],
};

/** 账号视图（AccountView/榜单行同形）→ 档案 User：elo 只在榜单行有
    （elo_rating 直读，无行后端回 1200）；账号视图不带 elo，保留现场
    结算行的回填值（live store 落）。装扮两键的 snake→camel 单点也在这
    （avatar_url→avatarUrl；穿戴原值展示用不到不落，见 User 注），两视图同形不分支 */
function accountToUser(view: AccountView | LeaderboardRowApi): User {
  return {
    id: view.id,
    name: view.name,
    elo: "elo_rating" in view ? view.elo_rating : 0,
    dupr: view.dupr_rating,
    provisional: view.dupr_provisional,
    play: view.dupr_games,
    win: view.dupr_wins,
    month: view.dupr_month_net ?? 0,
    last5: [...(view.dupr_last5 || [])] as ("W" | "L")[],
    avatarUrl: view.avatar_url,
    back: view.back,
  };
}

export const useUserStore = defineStore("user", () => {
  /** 我（reactive 原位换装：applyAccount/resetGuest Object.assign，全站引用联动） */
  const me = reactive<User>({ ...GUEST_USER });

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
      在途去重 + 失败冷却（现场轮询每拍重建都调——拉失败不记冷却，断网点会被
      打成每拍重发；60s 内不再试，成功落缓存自然出冷却） */
  const pendingIds = new Set<number>();
  const failedAt = new Map<number, number>();
  const FAIL_COOLDOWN_MS = 60_000;
  async function ensurePerson(id: number): Promise<void> {
    if (id === me.id || people[id] || pendingIds.has(id)) return;
    const f = failedAt.get(id);
    if (f != null && Date.now() - f < FAIL_COOLDOWN_MS) return;
    pendingIds.add(id);
    try {
      const { account } = await apiAccountView(id);
      people[id] = accountToUser(account);
      failedAt.delete(id);
    } catch {
      failedAt.set(id, Date.now());
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

  /** 装扮保存成功：dress 响应原位换装（snake→camel 与 accountToUser 同一映射口径，
    收在 store——页面手工逐键回写容易在响应加键时漏改） */
  function applyDress(d: DressingApi): void {
    me.avatarUrl = d.avatar_url;
    me.back = d.back;
  }

  /** 退出/注销回落游客：占位身份原位复位；喜欢是本地态，换了身份不带走。
      装扮两键显式清 undefined——GUEST_USER 没带这两键，不清会穿着上一具
      身份的形象当访客（访客的脸面：AvatarBadge 公共款兜底、卡片素卡） */
  function resetGuest(): void {
    likedIds.value.clear();
    Object.assign(me, GUEST_USER, {
      avatarUrl: undefined,
      back: undefined,
    });
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
    applyDress,
    resetGuest,
  };
});
