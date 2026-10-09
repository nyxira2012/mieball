<template>
  <!-- 打球记录页（5.1 子页）：done 局一场一行按时间倒序 + 期间筛选，点卡进打球详情。
       数据切真：game store 的 myGames 的 done 行（mock 种子已随演示世界退役）；
       期间下界按当下墙钟推算（原 mock 基准日随快照退役）。 -->
  <PageShell>
    <!-- 子页统一返回行（BackRow） -->
    <BackRow />

    <view class="stag">
      <view class="kicker">Match Log</view>
      <view class="brand">记<text class="bem">录</text></view>
    </view>

    <!-- 头统计：累计 N 场 = me.play（DUPR 已结算场数，与档案卡同口径），与列表条数解耦 -->
    <view class="stat">累计 {{ me.play }} 场</view>

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
    <EmptyBox v-else text="这段期间没有打过的局 · 换个筛法" />
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
import { useUserStore } from "@/stores/user";
import { useUiStore } from "@/stores/ui";
import { PERIOD_OPTS, periodFrom, type BillPeriod } from "@/stores/bill";
import { newGameCard } from "@/utils/format";
import { ApiError, errText } from "@/api/http";
import { goGame } from "@/utils/nav";
import type { Game } from "@/api/types";

const game = useGameStore();
const user = useUserStore();
const ui = useUiStore();

const me = computed(() => user.me);

/* 期间档位与账单页同源（BillPeriod/PERIOD_OPTS），下界换算在 bill store 单点 */
const period = ref<BillPeriod>("all");

/** 记录列表：myGames 的 done 行按期间过滤（startAt 绝对时间）后开打倒序 */
const list = computed<Game[]>(() => {
  const done = game.myGames.filter((g) => g.status === "done");
  const from = period.value === "all" ? null : periodFrom(period.value);
  const hit = from ? done.filter((g) => new Date(g.startAt) >= from) : done;
  return hit.sort((a, b) => b.startAt.localeCompare(a.startAt));
});

/** 局卡点击进打球详情页（5.1；路径契约在 utils/nav 单一源） */
function openGame(g: Game): void {
  goGame(g.id);
}

onShow(() => {
  game.loadMine().catch((e) => {
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
