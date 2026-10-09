<template>
  <PageShell tab="power">
    <view>
      <!-- 标题区（alpha.html:1831-1843） -->
      <view class="stag">
        <view class="head">
          <view>
            <view class="kicker">Power Rating</view>
            <!-- alpha:1835 <h1 class="brand" style="margin-bottom:0">战<em>力</em>榜（em 用 text 承载，避堵小程序） -->
            <view class="brand">战<text class="em">力</text>榜</view>
          </view>
        </view>
        <!-- alpha:1842 副标题（1.4 批4v1 改双轨说明） -->
        <view class="sub sub-mt">
          DUPR 积分 2.0-8.0 管排名与配平 · 积分（Elo）另记涨跌
        </view>
      </view>

      <!-- 我的战力卡（alpha:1844-1861）：点卡开我的档案，卡内头像去「我的」页 -->
      <MyPowerCard :rank="myRank" @profile="openProfile(userStore.me.id)" />

      <!-- 前三打架图（alpha:1862-1870）：点人开档案 -->
      <SectionTitle title="前三 · 对峙中" more="点人看档案" />
      <BrawlStage :top3="t3" @profile="openProfile" />

      <!-- 评分排行（alpha:1871-1875）：前三高亮 · 懒加载每批 5 条 · 满 5 场才入榜（1.4 §6） -->
      <SectionTitle
        title="评分排行"
        :more="`${rows.length} 球员在榜 · 前三高亮`"
      />
      <view class="rank-frame">
        <view class="rank-list">
          <RankRow
            v-for="(u, i) in shown"
            :key="u.id"
            :user="u"
            :index="i"
            :lazy="i >= lazyFrom"
            @profile="openProfile"
          />
          <!-- 空榜/加载/失败三态：0 圈员=空榜句；在途=加载句；失败=点击重试 -->
          <EmptyBox v-if="!rows.length" :text="boardTxt" @click="retryBoard" />
        </view>
        <!-- alpha:1874/1774-1784 尾部：点击亦可加载；全部加载完显示完毕文案（逐字） -->
        <view class="rank-tail" @click="loadMoreRank">
          <template v-if="done">
            <text class="tl-dim"
              >· 全圈 {{ rows.length }} 位球员已加载完毕 ·</text
            >
          </template>
          <template v-else>
            <text class="tl-lemon">↑ 上滑显示更多</text>
            <!-- alpha:1782 两段间原有空格，这里用 4px 间距近似 -->
            <text class="tl-dim tl-gap"
              >({{ rankLimit }}/{{ rows.length }}) · 点击亦可加载</text
            >
          </template>
        </view>
      </view>

      <!-- 参考区（1.4 §6 榜单门槛）：打过但未满 5 场的未定级者，列此不参与排名 -->
      <template v-if="refs.length">
        <SectionTitle
          title="参考 · 未定级"
          :more="`满 ${RATED_PLAY} 场自动入榜`"
        />
        <view class="rank-frame">
          <view class="rank-list">
            <RankRow
              v-for="(u, i) in refs"
              :key="u.id"
              :user="u"
              :index="i"
              unrated
              @profile="openProfile"
            />
          </view>
        </view>
      </template>

      <!-- 规则折叠（alpha:1876-1885 结构 · 1.4 批4v1 文案改双轨说明） -->
      <view class="rulefold" :class="{ open: rOpen }">
        <view class="rfhead" @click="rOpen = !rOpen">
          <text>积分怎么算的？</text>
          <text class="q">?</text>
        </view>
        <view class="rfbody">
          <view
            >· <text class="b">双轨记分</text>：同一场球落两本账——DUPR
            积分管配平、榜单与段位；积分（Elo）管结束对局的涨跌爽感。</view
          >
          <view
            >· <text class="b">DUPR 积分</text>：2.0-8.0 三位小数；建号 2.5
            起步，满 5 场定级，只算近 30 场。</view
          >
          <view
            >· <text class="b">积分（Elo）</text>：初始 1200 · 地板 800 ·
            K=24，赢强者涨得多；结束对局弹窗里 ± 的就是它。</view
          >
          <view
            >·
            <text class="b">访客与双打</text
            >：双打按两队人均算、败方只扣胜方涨分的六成；访客不计分不进榜。</view
          >
        </view>
      </view>

      <!-- alpha:1886 <div style="height:10px"> -->
      <view class="tailpad" />
    </view>
  </PageShell>
</template>

<script setup lang="ts">
/* 战力页（alpha.html:1824-1889 renderPower · P9 · 1.4 批4v1 榜单切 DUPR）。
   榜单数据后端化：/stats/leaderboard 单一源（user store 缓存与灌 people）；
   榜单懒加载 = alpha:1774-1822 的滚动通道（§2.4：IntersectionObserver → onPageScroll 距底 160px）；
   榜单/打架图/我的卡点击 → ui.openSheet({type:'profile',userId})。 */
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { onPageScroll, onShow } from "@dcloudio/uni-app";
import PageShell from "@/components/biz/PageShell.vue";
import MyPowerCard from "@/components/biz/MyPowerCard.vue";
import BrawlStage from "@/components/biz/BrawlStage.vue";
import RankRow from "@/components/biz/RankRow.vue";
import SectionTitle from "@/components/ui/SectionTitle.vue";
import EmptyBox from "@/components/ui/EmptyBox.vue";
import { useUiStore } from "@/stores/ui";
import { useUserStore } from "@/stores/user";
import { errText } from "@/api/http";

const ui = useUiStore();
const userStore = useUserStore();

/** 定级门槛（1.4 §5/§6：满 5 场入榜=定级；play 即 dupr_games） */
const RATED_PLAY = 5;

/** 榜单（后端 DUPR 降序单一源）：满 5 场入榜；打过但不足 5 场进参考区；
    0 场新号两区都不进（第一场球打出第一版排名） */
const rows = computed(() =>
  userStore.leaderboard.filter(
    (u) => userStore.hasPlayed(u) && u.play >= RATED_PLAY,
  ),
);
/** 参考区（1.4 §6）：未定级者同序排列但无位次 */
const refs = computed(() =>
  userStore.leaderboard.filter(
    (u) => userStore.hasPlayed(u) && u.play < RATED_PLAY,
  ),
);
/** alpha:1826 myRank = rows.findIndex(u=>u.id===me.id)+1（游客 id 0 恒不在榜 → 0） */
const myRank = computed(
  () => rows.value.findIndex((u) => u.id === userStore.me.id) + 1,
);
/** alpha:1827 t3 = rows.slice(0,3) */
const t3 = computed(() => rows.value.slice(0, 3));

/** alpha:1763 RANK_PAGE=5（框架最多 5 行，懒加载） */
const RANK_PAGE = 5;
/** alpha:1764 rankLimit */
const rankLimit = ref(RANK_PAGE);
/** 本批懒加载起始位次：≥ 此位的行带 lazy-in 入场（alpha:1768 isLazy，初始 5 行不带） */
const lazyFrom = ref(RANK_PAGE);
/** alpha:1873 rows.slice(0,rankLimit) */
const shown = computed(() => rows.value.slice(0, rankLimit.value));
/** alpha:1777 done = rankLimit>=total */
const done = computed(() => rankLimit.value >= rows.value.length);

/** 规则折叠展开态（alpha:1877 classList.toggle('open')） */
const rOpen = ref(false);

/** 拉榜失败旗（空榜三态分派用）；重试=再拉一次 */
const boardFailed = ref(false);
const boardTxt = computed(() =>
  userStore.lbLoading
    ? "正在翻榜 · 马上好…"
    : boardFailed.value
      ? "榜单没拉到 · 点一下重试"
      : "第一场球打出第一版排名",
);
function loadBoard(): void {
  boardFailed.value = false;
  userStore.loadLeaderboard().catch((e) => {
    boardFailed.value = true;
    ui.toast(errText(e));
  });
}
function retryBoard(): void {
  if (boardFailed.value) loadBoard();
}

/** alpha:1768/1755 openProfileById → openSheet profile */
function openProfile(id: number): void {
  ui.openSheet({ type: "profile", userId: id });
}

/* —— 懒加载（alpha:1774-1822 语义；容器滚动 → 页面 onPageScroll） —— */
const winH = ref(0);
let lastTop = 0; // 最近一次 onPageScroll 的 scrollTop
let pageH = 0; // 页面总内容高（=.page 的 bottom + 当时 scrollTop 折算）
let measuring = false; // Vue DOM 更新异步：本批量完页高前禁止连发（alpha 同步 innerHTML 无此问题）

/** 量 .page（PageShell 容器，含底部 nav 预留 padding）得到页面总高 */
function measure(after?: () => void): void {
  uni
    .createSelectorQuery()
    .select(".page")
    .boundingClientRect()
    .exec((res) => {
      const r = res && res[0];
      if (r && typeof r.bottom === "number") pageH = lastTop + r.bottom;
      if (after) after();
    });
}

/** alpha:1785-1800 loadMoreRank：+RANK_PAGE，全部加载完即止 */
function loadMoreRank(): void {
  if (measuring || rankLimit.value >= rows.value.length) return;
  lazyFrom.value = rankLimit.value;
  rankLimit.value = Math.min(rows.value.length, rankLimit.value + RANK_PAGE);
  measuring = true;
  nextTick(() => measure(() => (measuring = false)));
}

/** alpha:1808-1813 距底 160px 自动加载 */
onPageScroll((e) => {
  lastTop = e.scrollTop;
  if (!pageH || done.value) return;
  if (lastTop + winH.value >= pageH - 160) loadMoreRank();
});

onMounted(() => {
  winH.value = uni.getSystemInfoSync().windowHeight || 0;
  nextTick(() => measure());
});

/** alpha:874 go('power')：每次进页 rankLimit 归 5 并回顶；榜单未在册就拉一次 */
onShow(() => {
  rankLimit.value = RANK_PAGE;
  lazyFrom.value = RANK_PAGE;
  uni.pageScrollTo({ scrollTop: 0, duration: 0 });
  nextTick(() => measure());
  if (!userStore.leaderboard.length) loadBoard();
});

/** 折叠展开改变页高 → 重测，保持 160px 触发线准确 */
watch(rOpen, () => nextTick(() => measure()));
</script>

<style lang="scss" scoped>
/* alpha:1832 头行 flex 两端 · 底对齐 */
.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
}
/* alpha:1835 power 大字 margin-bottom:0（其余 brand/em 版式走全局 .brand 类） */
.brand {
  margin: 6px 0 0;
}
/* alpha:1842 sub margin-top:6px */
.sub-mt {
  margin-top: 6px;
}
/* alpha.html:493-494 .rank-frame */
.rank-frame {
  border: 1px solid rgba(245, 241, 232, 0.12);
  border-radius: var(--r-lg);
  background: rgba(20, 20, 26, 0.65);
  padding: 10px 10px 4px;
  margin-bottom: 12px;
  position: relative;
}
/* alpha.html:516-518 .rank-tail */
.rank-tail {
  text-align: center;
  font-family: var(--mono);
  font-size: 11px;
  color: var(--dim);
  padding: 11px 0 8px;
  cursor: pointer;
  border-radius: 10px;
  transition:
    background 0.2s,
    color 0.2s;
  user-select: none;
}
.rank-tail:active {
  color: var(--lemon);
  background: rgba(255, 212, 0, 0.05);
}
/* alpha:1779/1782 尾部两态配色 */
.tl-dim {
  color: var(--dim);
}
.tl-lemon {
  color: var(--lemon);
  font-weight: 700;
}
.tl-gap {
  margin-left: 4px;
}
/* alpha.html:532 .rulefold */
.rulefold {
  border: 1px dashed rgba(245, 241, 232, 0.16);
  border-radius: var(--r-md);
  margin-top: 10px;
  overflow: hidden;
}
/* alpha.html:533-534 .rfhead */
.rfhead {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  background: none;
  color: var(--cream);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  font-family: var(--sans);
}
/* alpha.html:535-536 .q */
.q {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 1px solid var(--lemon);
  color: var(--lemon);
  display: grid;
  place-items: center;
  font-size: 11px;
  font-family: var(--mono);
  flex: none;
}
/* alpha.html:537-538 .rfbody 默认收起 */
.rfbody {
  display: none;
  padding: 0 14px 12px;
  font-size: 12px;
  color: var(--dim);
  line-height: 1.9;
}
.rulefold.open .rfbody {
  display: block;
}
/* alpha.html:539 .rfbody b */
.rfbody .b {
  color: var(--lemon);
}
/* alpha:1886 页尾 10px 垫高 */
.tailpad {
  height: 10px;
}
</style>
