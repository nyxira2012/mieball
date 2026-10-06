<template>
  <!-- 参加登记页（5.1 子页 · 1.2 隔离线）：已报名/组局的局一屏看全（含已结束局看签到行），点卡进原约球详情。
       数据直读 mock 种子（快照冻结——真局报名归 game store 的 myGames，接通前本页仍吃 5.1 演示快照）。 -->
  <PageShell>
    <!-- 子页统一返回行（BackRow） -->
    <BackRow />

    <view class="stag">
      <view class="kicker">My Games</view>
      <view class="brand">登<text class="bem">记</text></view>
    </view>

    <!-- 头统计：共 N 局 = 下方全量条数（不随筛选变）；签到次数 = myCheckins（done 且留了 checkIn） -->
    <view class="stat">共 {{ mySignups.length }} 局 · 签到 {{ myCheckins.length }} 次</view>

    <!-- 状态筛选（5.1 辅助功能：登记按状态） -->
    <FilterChips v-model="mode" :options="MODE_OPTS" />

    <template v-if="list.length">
      <view v-for="g in list" :key="g.id" class="cell">
        <GameCard :card="mockGameCard(g)" @tap="openGame(g)" />
        <!-- 签到底账行（验收故事 3「签到 19:02 · 早退 21:30」）：仅 done 且有 myLog 才渲染 -->
        <view v-if="g.myLog?.checkIn" class="logline">
          签到 {{ g.myLog.checkIn }}{{ g.myLog.checkOut ? ' · 早退 ' + g.myLog.checkOut : '' }}
        </view>
      </view>
    </template>
    <EmptyBox v-else :text="emptyTxt" />
  </PageShell>
</template>

<script setup lang="ts">
/* 登记口径（原 game store 的 mySignups/myCheckins 单一源随真局接线退役，
   隔离线消费面自带同口径：我组织/已报名 且未终止，含 done） */
import { computed, ref } from 'vue';
import PageShell from '@/components/biz/PageShell.vue';
import BackRow from '@/components/biz/BackRow.vue';
import GameCard from '@/components/biz/GameCard.vue';
import FilterChips from '@/components/ui/FilterChips.vue';
import EmptyBox from '@/components/ui/EmptyBox.vue';
import { games as seedGames } from '@/api';
import { dayOrd, gameTime } from '@/utils/time';
import { isMe, mockGameCard } from '@/utils/format';
import { goGame } from '@/utils/nav';
import type { MockGame } from '@/api/types';

/** 我的登记全集：我组织/已报名 且未终止（含 done —— 已结束局要在登记页看到签到行） */
const mySignups = computed(() =>
  seedGames.filter((g) => !g.dead && (isMe(g.organizer.id) || g.joined.some((e) => isMe(e.u.id)))),
);
/** 签到口径：其中打完（done）且我的到场底账留了 checkIn 的局 */
const myCheckins = computed(() => mySignups.value.filter((g) => g.status === 'done' && !!g.myLog?.checkIn));

/* 状态单选（BillPeriod 同族窄类型；FilterChips v-model 已收窄为 string|number） */
const mode = ref<string | number>('all');
const MODE_OPTS = [
  { value: 'all', label: '全部' },
  { value: 'open', label: '未开场' },
  { value: 'done', label: '已结束' },
];

/* 未开场按开打时刻升序；done 按 d 倒序 —— d 是 'M.DD' 且月份不补零，跨月时字符串比较
   会把 9.x 排到 10.x 之后，必须走 dayOrd（月*100+日）才与账单页同源单调 */
const openGames = computed(() =>
  mySignups.value.filter((g) => g.status !== 'done').sort((a, b) => gameTime(a.t).getTime() - gameTime(b.t).getTime()),
);
const doneGames = computed(() =>
  mySignups.value.filter((g) => g.status === 'done').sort((a, b) => dayOrd(b.d) - dayOrd(a.d)),
);
/** 全部档 = 未开场在前 + done 在后（5.1：登记页主看 upcoming） */
const list = computed<MockGame[]>(() => {
  if (mode.value === 'open') return openGames.value;
  if (mode.value === 'done') return doneGames.value;
  return [...openGames.value, ...doneGames.value];
});

const emptyTxt = computed(() => {
  if (mode.value === 'open') return '没有待开场的局 · 去约球页找一局';
  if (mode.value === 'done') return '还没有打完的局';
  return '还没有报过名 · 去约球页找一局';
});

/** 局卡点击进原约球详情页（5.1；路径契约在 utils/nav 单一源） */
function openGame(g: MockGame): void {
  goGame(g.id);
}
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

/* 签到行：贴在局卡下沿（GameCard 自带 margin-bottom 12px，负 margin 收拢） */
.logline {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  margin: -8px 4px 8px;
}
</style>
