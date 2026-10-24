<template>
  <!-- 我的战力卡：rank 位 #N / 未开局 — · AvatarBadge 76
       （点卡开我的档案、点头像去「我的」页）· 主数字随视图：DUPR 分层三位小数+
       段位徽章 / Elo 整数无段位 · 底部数据行带本月涨跌。
       完整铺我的卡背（f 档全幅+文字安全纱），无卡背（游客）素卡渐变兜底；
       四档渐变卡背（bg-neon/gold/cyber/aurora）随旧装扮退役。 -->
  <view class="mycardp cbd-host" @click="emit('profile')">
    <CardBackdrop :cid="me.back" mode="f" />
    <view class="top-row">
      <!-- rkbox：#N 或 —（未开局/未入榜参考区；Elo 视图名次跟 Elo 榜走） -->
      <view class="rkbox">
        <view class="rk">{{ played && rank > 0 ? "#" + rank : "—" }}</view>
        <view class="rl">MY RANK</view>
      </view>
      <!-- av：点头像切我的页，stopPropagation 防误触卡身的档案事件（goTab=nav 单一源） -->
      <view class="av" @click.stop="goTab('mine')">
        <AvatarBadge :url="me.avatarUrl" :size="76" />
      </view>
      <view class="info">
        <view class="nrow">
          <text class="ttl">{{ cardTitle }}</text>
          <!-- 段位/未定级是 DUPR 定级概念，Elo 视图不出现 -->
          <template v-if="mode === 'dupr'">
            <TierBadge v-if="played" :tier="duprTier(duprOf(me))" />
            <text v-else class="tierb-fb">?</text>
            <text v-if="played && me.provisional" class="prov">未定级</text>
          </template>
        </view>
        <!-- myscore：DUPR 未定级 dim（起步分不作数）、Elo 未开局 dim -->
        <view class="myscore">
          <template v-if="mode === 'elo'">
            <text class="big" :class="{ dim: !played }">{{ myElo }}</text>
            <text class="unit">Elo</text>
          </template>
          <template v-else>
            <DuprScore
              :d="duprOf(me)"
              class="big"
              :class="{ dim: !played || me.provisional }"
            />
            <text class="unit">DUPR</text>
          </template>
          <!-- 涨跌小签删：与底部数据行「本月 ±N」双份显示，且名次框+头像夹出的
               窄列放不下三件（320 必两行）；榜单行/档案列宽富余，涨跌签照旧 -->
        </view>
      </view>
    </view>
    <!-- 数据行：已开局「N 胜 N 负 · 本月 ±N」（dupr_wins/games + 月净胜，mock
         的小时/大卡无后端真值随演示数字退役）；未开局「开启巅峰赛之旅吧」 -->
    <view class="telemetry">{{ telemetry }}</view>
  </view>
</template>

<script setup lang="ts">
/* 我的战力卡。business 件：组合 ui 件（AvatarBadge/TierBadge/DuprScore）+
   业务数据。rank 位由 power 页按当前视图的榜算好传入
   （0=不在榜：未开局或 DUPR 视图未满 5 场的参考区）。 */
import { computed } from "vue";
import type { PropType } from "vue";
import AvatarBadge from "@/components/ui/AvatarBadge.vue";
import CardBackdrop from "@/components/ui/CardBackdrop.vue";
import TierBadge from "@/components/ui/TierBadge.vue";
import DuprScore from "@/components/ui/DuprScore.vue";
import type { ScoreMode } from "@/api/types";
import { useUserStore } from "@/stores/user";
import { useSessionStore } from "@/stores/session";
import { ELO_INIT, duprOf, duprTier } from "@/utils/elo";
import { goTab } from "@/utils/nav";

defineProps({
  /** 我的排名；0=不在榜，名次框显示「—」（未开局/参考区） */
  rank: { type: Number, default: 0 },
  /** 分数视图（power 页胶囊）：'dupr'=分层三位小数+段位；'elo'=整数+无段位 */
  mode: { type: String as PropType<ScoreMode>, default: "dupr" },
});

const emit = defineEmits<{ (e: "profile"): void }>();

const userStore = useUserStore();
const session = useSessionStore();
const me = userStore.me;

const played = computed(() => me.play > 0);
/** 游客态卡片名称为「访客」，登录态按是否开局区分「我的战力卡」/「我的起步分」 */
const cardTitle = computed(() => {
  if (session.isGuest) return "访客";
  return played.value ? "我的战力卡" : "我的起步分";
});
/** 我的 Elo 吃榜单行（账号视图不带 elo；游客/未拉榜回落展示兜底 1200） */
const myElo = computed(
  () => userStore.leaderboard.find((u) => u.id === me.id)?.elo ?? ELO_INIT,
);
/** 数据行：胜负来自 dupr 账（win/play 真值），月净胜 me.month（stats card 口径） */
const telemetry = computed(() =>
  played.value
    ? `${me.win} 胜 ${me.play - me.win} 负 · 本月 ${me.month >= 0 ? "+" : ""}${me.month}`
    : "开启巅峰赛之旅吧",
);
</script>

<style lang="scss" scoped>
/* 宿主契约三件套挂全局 .cbd-host（base.scss 收源），让负 z-index 的卡底层垫在
   卡底渐变之上、文字之下。渐变即素卡兜底（游客/无卡背）；旧四档渐变 bg-* 已退役 */
.mycardp {
  margin-top: 14px;
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  padding: 16px;
  background: linear-gradient(150deg, var(--ink3), var(--ink2));
  cursor: pointer;
  transition:
    border-color 0.2s,
    background 0.3s;
}
.mycardp:active {
  border-color: rgba(255, 212, 0, 0.4);
}
.top-row {
  display: flex;
  gap: 14px;
  align-items: center;
}
.rkbox {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  flex: none;
}
.rk {
  font-family: var(--disp);
  font-size: 34px;
  color: var(--lemon);
  line-height: 1;
}
.rl {
  font-family: var(--mono);
  font-size: 8px;
  letter-spacing: 0.2em;
  color: var(--dim);
}
.av {
  width: 76px;
  height: 76px;
  flex: none;
}
.info {
  flex: 1;
  min-width: 0;
}
.nrow {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.ttl {
  font-size: 16px;
  font-weight: 700;
}
/* 未开局 ? 徽章 */
.tierb-fb {
  display: inline-grid;
  place-items: center;
  min-width: 24px;
  height: 19px;
  padding: 0 5px;
  border-radius: 6px;
  font-family: var(--disp);
  font-size: 11px;
  letter-spacing: 0.04em;
  vertical-align: middle;
  background: rgba(245, 241, 232, 0.1);
  color: var(--dim);
}
/* 未定级小 chip（1.4 §5：DUPR 可信度两态，浅丁香角标） */
.prov {
  display: inline-block;
  font-family: var(--mono);
  font-size: 9px;
  border-radius: 6px;
  padding: 1px 5px;
  background: rgba(184, 169, 255, 0.15);
  color: var(--lilac);
}
.myscore {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 3px 0 3px;
  flex-wrap: wrap;
}
.big {
  font-family: var(--disp);
  font-size: 34px;
  color: var(--lemon);
  line-height: 1;
}
.big.dim {
  color: var(--dim);
}
.unit {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
}
.telemetry {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid rgba(245, 241, 232, 0.08);
  text-align: center;
  font-family: var(--mono);
  font-size: 11px;
  color: var(--cream);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
