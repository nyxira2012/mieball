<template>
  <PageShell tab="power">
    <view>
      <!-- 标题区 + 分数切换胶囊（默认 DUPR） -->
      <view class="stag">
        <view class="head">
          <view>
            <view class="kicker">Power Rating</view>
            <!-- 战<em>力</em>榜（em 用 text 承载，避堵小程序） -->
            <view class="brand">战<text class="em">力</text>榜</view>
          </view>
          <!-- sw-capsule：DUPR=榜单正式口径 / Elo=按 Elo 重排的娱乐视图 -->
          <view class="sw-capsule">
            <text
              class="sw-opt"
              :class="{ on: mode === 'dupr' }"
              @click="setMode('dupr')"
              >DUPR</text
            >
            <text
              class="sw-opt"
              :class="{ on: mode === 'elo' }"
              @click="setMode('elo')"
              >Elo</text
            >
          </view>
        </view>
        <!-- 副标题随视图换文案：介绍当前那套积分 -->
        <view class="sub sub-mt">{{ subLine }}</view>
      </view>

      <!-- 我的战力卡：点卡开我的档案，卡内头像去「我的」页 -->
      <MyPowerCard
        :rank="myRank"
        :mode="mode"
        @profile="openProfile(userStore.me.id)"
      />

      <!-- 前三打架图：点人开档案。区头「奶茶三分糖」为用户定稿
           （前三＝三分糖；卡内 TOP 3 · BRAWL 兜底语义） -->
      <SectionTitle title="奶茶三分糖" />
      <BrawlStage :top3="t3" @profile="openProfile" />

      <!-- 评分排行：前三高亮 · 懒加载每批 5 条 · 满 5 场才入榜（DUPR 视图，1.4 §6） -->
      <SectionTitle title="评分排行" />
      <view class="rank-frame">
        <view class="rank-list">
          <RankRow
            v-for="(u, i) in shown"
            :key="u.id"
            :user="u"
            :index="i"
            :lazy="i >= lazyFrom"
            :mode="mode"
            @profile="openProfile"
          />
          <!-- 空榜/加载/失败三态：0 圈员=空榜句；在途=加载句；失败=点击重试 -->
          <EmptyBox v-if="!rows.length" :text="boardTxt" @click="retryBoard" />
        </view>
        <!-- 尾部：上滑/点尾行加载；全部加载完显示完毕文案 -->
        <view class="rank-tail" @click="loadMoreRank">
          <template v-if="done">
            <text class="tl-dim"
              >· 全圈 {{ rows.length }} 位球员已加载完毕 ·</text
            >
          </template>
          <template v-else>
            <text class="tl-lemon">↑ 上滑显示更多</text>
          </template>
        </view>
      </view>

      <!-- 参考区（1.4 §6，DUPR 视图专属——满 5 场门槛是 DUPR 定级概念，
           Elo 娱乐视图不设参考区）：未定级者列此不参与排名 -->
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

      <!-- 规则折叠。文案先说两套分是什么、再说机制，一条一行
           ——引擎参数（K 值/地板）不入文案：调参不该牵动文案 -->
      <view class="rulefold" :class="{ open: rOpen }">
        <view class="rfhead" @click="rOpen = !rOpen">
          <text>积分怎么算的？</text>
          <text class="q">?</text>
        </view>
        <view class="rfbody">
          <view
            >· <text class="b">DUPR</text>（Dynamic Universal Pickleball
            Rating，读『丢per』）：匹克球界的通用评分，2.0–8.0 三位小数。</view
          >
          <view
            >· <text class="b">DUPR</text> 只看最近 30 场：起步 2.5，打满 5
            场定级入榜。</view
          >
          <view
            >· <text class="b">Elo</text>（埃洛，Elo Rating
            System）：每场结算都涨跌的娱乐分，起步 1200，赢了强手涨得多。</view
          >
          <view
            >·
            <text class="b">双打与访客</text
            >：双打按两队人均算；朋友带来的访客不计分、不进榜。</view
          >
        </view>
      </view>

      <view class="tailpad" />
    </view>
  </PageShell>
</template>

<script setup lang="ts">
/* 战力页（P9）。榜单数据后端化：
   /stats/leaderboard 单一源（user store 缓存与灌 people，行带 elo_rating 供
   娱乐视图——Elo 视图前端按 Elo 重排，榜单端点排序口径仍只吃 DUPR，1.4 §11）。
   榜单懒加载走 §2.4 裁决的通道：IntersectionObserver → onPageScroll 距底
   160px；榜单/打架图/我的卡点击 → ui.openSheet({type:'profile',userId})。 */
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { onPageScroll, onShow } from "@dcloudio/uni-app";
import PageShell from "@/components/biz/PageShell.vue";
import MyPowerCard from "@/components/biz/MyPowerCard.vue";
import BrawlStage from "@/components/biz/BrawlStage.vue";
import RankRow from "@/components/biz/RankRow.vue";
import SectionTitle from "@/components/ui/SectionTitle.vue";
import EmptyBox from "@/components/ui/EmptyBox.vue";
import type { ScoreMode } from "@/api/types";
import { useUiStore } from "@/stores/ui";
import { useUserStore } from "@/stores/user";
import { errText } from "@/api/http";

const ui = useUiStore();
const userStore = useUserStore();

/** 定级门槛（1.4 §5/§6：满 5 场入榜=定级；play 即 dupr_games） */
const RATED_PLAY = 5;

/** 分数视图（4.1 分数切换）：'dupr'=榜单正式口径（默认）；'elo'=娱乐视图
    （Elo 重排、无段位无定级门槛） */
const mode = ref<ScoreMode>("dupr");
function setMode(m: ScoreMode): void {
  if (mode.value === m) return;
  mode.value = m;
  rankLimit.value = RANK_PAGE;
  lazyFrom.value = RANK_PAGE;
  nextTick(() => measure()); // 换榜=换页高，重测保 160px 触发线
}

/** 副标题随视图介绍两套积分
    （文案用户定稿逐字——一句一行，全名细节归底部折叠区） */
const subLine = computed(() =>
  mode.value === "dupr"
    ? "DUPR（DU Pickleball Rating）丢per，匹克球通用评分"
    : "ELO（埃洛，Elo Rating System）相对积分排名",
);

/** 打过球的在册球友（两视图共用底池；0 场新号两区都不进） */
const playedList = computed(() =>
  userStore.leaderboard.filter((u) => userStore.hasPlayed(u)),
);
/** 当前视图的榜（myRank/t3/shown 全跟它走）：DUPR=后端序直用、滤满 5 场
    定级门槛（1.4 §6）；Elo=无门槛打过就排，前端按 Elo 降序同分 id 升序重排 */
const rows = computed(() => {
  if (mode.value === "elo")
    return [...playedList.value].sort((a, b) => b.elo - a.elo || a.id - b.id);
  return playedList.value.filter((u) => u.play >= RATED_PLAY);
});
/** 参考区（1.4 §6，DUPR 视图专属——门槛是 DUPR 定级概念）：未满 5 场无位次 */
const refs = computed(() =>
  mode.value === "dupr"
    ? playedList.value.filter((u) => u.play < RATED_PLAY)
    : [],
);
/** 我的位次=findIndex+1（游客 id 0 恒不在榜 → 0） */
const myRank = computed(
  () => rows.value.findIndex((u) => u.id === userStore.me.id) + 1,
);
const t3 = computed(() => rows.value.slice(0, 3));

/** 懒加载每批 5 行 */
const RANK_PAGE = 5;
const rankLimit = ref(RANK_PAGE);
/** 本批懒加载起始位次：≥ 此位的行带 lazy-in 入场（初始 5 行不带） */
const lazyFrom = ref(RANK_PAGE);
const shown = computed(() => rows.value.slice(0, rankLimit.value));
const done = computed(() => rankLimit.value >= rows.value.length);

/** 规则折叠展开态 */
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

/** 点人 → 名片弹层 */
function openProfile(id: number): void {
  ui.openSheet({ type: "profile", userId: id });
}

/* —— 懒加载 —— */
const winH = ref(0);
let lastTop = 0; // 最近一次 onPageScroll 的 scrollTop
let pageH = 0; // 页面总内容高（=.page 的 bottom + 当时 scrollTop 折算）
let measuring = false; // Vue DOM 更新异步：本批量完页高前禁止连发

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

/** 加一批；全部加载完即止 */
function loadMoreRank(): void {
  if (measuring || rankLimit.value >= rows.value.length) return;
  lazyFrom.value = rankLimit.value;
  rankLimit.value = Math.min(rows.value.length, rankLimit.value + RANK_PAGE);
  measuring = true;
  nextTick(() => measure(() => (measuring = false)));
}

/** 距底 160px 自动加载 */
onPageScroll((e) => {
  lastTop = e.scrollTop;
  if (!pageH || done.value) return;
  if (lastTop + winH.value >= pageH - 160) loadMoreRank();
});

onMounted(() => {
  winH.value = uni.getSystemInfoSync().windowHeight || 0;
  nextTick(() => measure());
});

/** 每次进页 rankLimit 归 5 并回顶；榜单未在册就拉一次 */
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
.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
}
/* 其余 brand/em 版式走全局 .brand 类 */
.brand {
  margin: 6px 0 0;
}
/* sw-capsule 分数切换胶囊：只在战力页用，不入 ui 组件库；
   AppSeg 是表单大分段控件，形态不同不共用 */
.sw-capsule {
  display: inline-flex;
  align-items: center;
  background: var(--ink2);
  border: 1px solid rgba(245, 241, 232, 0.14);
  border-radius: 99px;
  padding: 3px;
  cursor: pointer;
  user-select: none;
  transition: border-color 0.2s;
  flex: none;
  margin-bottom: 2px; /* 与 .head 底对齐时给胶囊一点呼吸 */
}
.sw-capsule:active {
  border-color: rgba(255, 212, 0, 0.4);
}
.sw-opt {
  padding: 5px 12px;
  font-family: var(--disp);
  font-size: 12px;
  letter-spacing: 0.04em;
  color: var(--dim);
  border-radius: 99px;
  transition:
    background 0.2s,
    color 0.2s;
  line-height: 1;
}
.sw-opt.on {
  background: var(--lemon);
  color: var(--ink);
  box-shadow: 0 0 10px rgba(255, 212, 0, 0.25);
}
.sub-mt {
  margin-top: 6px;
}
.rank-frame {
  border: 1px solid rgba(245, 241, 232, 0.12);
  border-radius: var(--r-lg);
  background: rgba(20, 20, 26, 0.65);
  padding: 10px 10px 4px;
  margin-bottom: 12px;
  position: relative;
}
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
.tl-dim {
  color: var(--dim);
}
.tl-lemon {
  color: var(--lemon);
  font-weight: 700;
}
.rulefold {
  border: 1px dashed rgba(245, 241, 232, 0.16);
  border-radius: var(--r-md);
  margin-top: 10px;
  overflow: hidden;
}
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
.rfbody .b {
  color: var(--lemon);
}
.tailpad {
  height: 10px;
}
</style>
