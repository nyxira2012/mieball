<template>
  <!-- 打球记录页（5.1 子页 · 2.6 换源）：一场一行按散场倒序（排序真值在后端）+ 期间
       筛选，点卡进局详情（战报从详情「查看战报」进）。数据源 = 后端三笔规矩
       （上过场 ∨ 账单有份 ∨ 组织者，GET /api/games/playlog）——记录页不自判
       （A4）：删旧的 myGames+status==="done" 前端过滤，空降无 Entry 行不再漏。 -->
  <PageShell>
    <!-- 子页统一返回行（BackRow） -->
    <BackRow />

    <view class="stag">
      <view class="kicker">Match Log</view>
      <view class="brand">记<text class="bem">录</text></view>
    </view>

    <!-- 头统计（4.4-9 单位写全）：吃后端定值 matches_count（上过场的场次），与列表
         条数解耦（补账追溯的局无上场也进列表、一人多场只按上场计） -->
    <view class="stat">累计 {{ matchesCount }} 场对局</view>

    <!-- 期间筛选（5.1 辅助功能：记录按时间） -->
    <FilterChips v-model="period" :options="PERIOD_OPTS" />

    <template v-if="list.length">
      <GameCard
        v-for="g in list"
        :key="g.id"
        :card="newGameCard(g)"
        @tap="openGame(g)"
      />
    </template>
    <EmptyBox v-else :text="emptyText" />
  </PageShell>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import PageShell from "@/components/biz/PageShell.vue";
import BackRow from "@/components/biz/BackRow.vue";
import GameCard from "@/components/biz/GameCard.vue";
import FilterChips from "@/components/ui/FilterChips.vue";
import EmptyBox from "@/components/ui/EmptyBox.vue";
import { useGameStore } from "@/stores/game";
import { useUiStore } from "@/stores/ui";
import { PERIOD_OPTS, periodFrom, type BillPeriod } from "@/stores/bill";
import { newGameCard } from "@/utils/format";
import { ApiError, errText } from "@/api/http";
import { goGame } from "@/utils/nav";
import type { Game } from "@/api/types";

const game = useGameStore();
const ui = useUiStore();

/** 头统计吃后端定值（不自算）；加载中显 0 一拍，与列表同源到达 */
const matchesCount = computed(() => game.playlog?.matchesCount ?? 0);

/* 期间档位与账单页同源（BillPeriod/PERIOD_OPTS），下界换算在 bill store 单点 */
const period = ref<BillPeriod>("all");

/** 记录列表：后端三笔规矩整袋（散场倒序已排好，不重排）按期间过滤（startAt 绝对时间） */
const list = computed<Game[]>(() => {
  const all = game.playlog?.games ?? [];
  const from = period.value === "all" ? null : periodFrom(period.value);
  return from ? all.filter((g) => new Date(g.startAt) >= from) : all;
});

/** 空态文案二分：整袋就空=还没打过；筛完才空=换个筛法（沿用原句语义） */
const emptyText = computed(() =>
  (game.playlog?.games.length ?? 0) === 0
    ? "还没有打过的球局"
    : "这段期间没有打过的局 · 换个筛法",
);

/** 局卡点击进局详情页（5.1 修订册：先进详情再「查看战报」；路径契约在 utils/nav 单一源） */
function openGame(g: Game): void {
  goGame(g.id);
}

onShow(() => {
  game.loadPlaylog().catch((e) => {
    if (!(e instanceof ApiError && e.code === "no_identity"))
      ui.toast(errText(e));
  });
});
</script>

<style lang="scss" scoped>
/* ---------- 头部 brand：版式走全局 .brand 类，只补 700 加粗（bills 同款） ---------- */
.brand {
  font-weight: 700;
}

/* 头统计行（mono 10px dim） */
.stat {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  margin: 4px 2px 8px;
}
</style>
