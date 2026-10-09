<template>
  <!-- 参加登记页（5.1 子页）：已报名/组局的局一屏看全（含已结束局），点卡进原约球详情。
       数据切真：game store 的 myGames（后端 /games/mine 按角色裁好——组织者在办局全量、
       参加者含当日灰字行；mock 种子已随演示世界退役）。 -->
  <PageShell>
    <!-- 子页统一返回行（BackRow） -->
    <BackRow />

    <view class="stag">
      <view class="kicker">My Games</view>
      <view class="brand">登<text class="bem">记</text></view>
    </view>

    <!-- 头统计：共 N 局 = 在办+已结束全量（不含死局行）；打完 M 局 = done 计数
         （mock 时代的「签到时刻」无后端读取面，随演示快照退役） -->
    <view class="stat"
      >共 {{ mySignups.length }} 局 · 打完 {{ myDone.length }} 局</view
    >

    <!-- 状态筛选（5.1 辅助功能：登记按状态） -->
    <FilterChips v-model="mode" :options="MODE_OPTS" />

    <template v-if="list.length">
      <view v-for="g in list" :key="g.id" class="cell">
        <GameCard :card="newGameCard(g)" @tap="openGame(g)" />
      </view>
    </template>
    <EmptyBox v-else :text="emptyTxt" />
  </PageShell>
</template>

<script setup lang="ts">
/* 登记口径：myGames 里非死局的行（open/locked/live/done——死局行归约球页死局区处置，
   4.8/4.9/4.10 口径不在这里重复）；未开场按开打时刻升序，已结束按开打倒序 */
import { computed, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import PageShell from "@/components/biz/PageShell.vue";
import BackRow from "@/components/biz/BackRow.vue";
import GameCard from "@/components/biz/GameCard.vue";
import FilterChips from "@/components/ui/FilterChips.vue";
import EmptyBox from "@/components/ui/EmptyBox.vue";
import { useGameStore } from "@/stores/game";
import { useUiStore } from "@/stores/ui";
import { deadRowKind, newGameCard } from "@/utils/format";
import { ApiError, errText } from "@/api/http";
import { goGame } from "@/utils/nav";
import type { Game } from "@/api/types";

const game = useGameStore();
const ui = useUiStore();

/** 我的登记全集：myGames 去掉死局行（pending/恢复窗/灰字——约球页已接管处置出口） */
const mySignups = computed(() =>
  game.myGames.filter((g) => deadRowKind(g) === null),
);
/** 打完口径：done 局（散场封存/到点结束都算） */
const myDone = computed(() =>
  mySignups.value.filter((g) => g.status === "done"),
);

/* 状态单选（BillPeriod 同族窄类型；FilterChips v-model 已收窄为 string|number） */
const mode = ref<string | number>("all");
const MODE_OPTS = [
  { value: "all", label: "全部" },
  { value: "open", label: "未开场" },
  { value: "done", label: "已结束" },
];

/* 未开场按开打时刻升序；done 按开打倒序（startAt ISO 绝对时间可直接比较） */
const openGames = computed(() =>
  mySignups.value
    .filter((g) => g.status !== "done")
    .sort((a, b) => a.startAt.localeCompare(b.startAt)),
);
/** 全部档 = 未开场在前 + done 在后（5.1：登记页主看 upcoming） */
const list = computed<Game[]>(() => {
  if (mode.value === "open") return openGames.value;
  if (mode.value === "done") return myDone.value;
  return [...openGames.value, ...myDone.value];
});

const emptyTxt = computed(() => {
  if (mode.value === "open") return "没有待开场的局 · 去约球页找一局";
  if (mode.value === "done") return "还没有打完的局";
  return "还没有报过名 · 去约球页找一局";
});

/** 局卡点击进原约球详情页（5.1；路径契约在 utils/nav 单一源） */
function openGame(g: Game): void {
  goGame(g.id);
}

/* 每次进页重拉：真局状态随时刻翻（懒判定发生在任何人打开的那一刻）；
   游客 401 no_identity 静默（没有「我的局」，空态文案自解释） */
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
