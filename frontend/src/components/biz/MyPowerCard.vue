<template>
  <!-- 我的战力卡（alpha.html:1844-1861）：rank 位 #N / 未开局 — · ChibiAvatar 76
       （点卡开我的档案、点头像去「我的」页）· 主数字随视图：DUPR 分层三位小数+
       段位徽章 / Elo 整数无段位 · 底部数据行带本月涨跌。 -->
  <view
    class="mycardp"
    :class="`bg-${me.cardBg || 'neon'}`"
    @click="emit('profile')"
  >
    <view class="top-row">
      <!-- alpha:1846 rkbox：#N 或 —（未开局/未入榜参考区；Elo 视图名次跟 Elo 榜走） -->
      <view class="rkbox">
        <view class="rk">{{ played && rank > 0 ? "#" + rank : "—" }}</view>
        <view class="rl">MY RANK</view>
      </view>
      <!-- alpha:1847 av：event.stopPropagation();go('mine') → goTab 切我的页（nav 单一源） -->
      <view class="av" @click.stop="goTab('mine')">
        <ChibiAvatar :chibi="me.chibi" :size="76" />
      </view>
      <!-- alpha:1848 -->
      <view class="info">
        <view class="nrow">
          <text class="ttl">{{ cardTitle }}</text>
          <!-- 段位/未定级是 DUPR 定级概念，Elo 视图不出现 -->
          <template v-if="mode === 'dupr'">
            <TierBadge v-if="played" :tier="duprTier(me.dupr ?? GUEST_DUPR)" />
            <text v-else class="tierb-fb">?</text>
            <text v-if="played && me.provisional" class="prov">未定级</text>
          </template>
        </view>
        <!-- alpha:1852-1855 myscore：DUPR 未定级 dim（起步分不作数）、Elo 未开局 dim -->
        <view class="myscore">
          <template v-if="mode === 'elo'">
            <text class="big" :class="{ dim: !played }">{{ myElo }}</text>
            <text class="unit">Elo</text>
          </template>
          <template v-else>
            <DuprScore
              :d="me.dupr ?? GUEST_DUPR"
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
         的小时/大卡无后端真值随演示数字退役）；未开局「待第一局校准 · 起步 2.5」 -->
    <view class="telemetry">{{ telemetry }}</view>
  </view>
</template>

<script setup lang="ts">
/* 我的战力卡（alpha.html:1844-1861 · P9）。business 件：组合 ui 件
   （ChibiAvatar/TierBadge/DuprScore）+ 业务数据。rank 位由 power 页按当前
   视图的榜算好传入（0=不在榜：未开局或 DUPR 视图未满 5 场的参考区）。 */
import { computed } from "vue";
import type { PropType } from "vue";
import ChibiAvatar from "@/components/ui/ChibiAvatar.vue";
import TierBadge from "@/components/ui/TierBadge.vue";
import DuprScore from "@/components/ui/DuprScore.vue";
import type { ScoreMode } from "@/api/types";
import { useUserStore } from "@/stores/user";
import { useSessionStore } from "@/stores/session";
import { ELO_INIT, GUEST_DUPR, duprTier } from "@/utils/elo";
import { goTab } from "@/utils/nav";

defineProps({
  /** 我的排名（alpha:1826 myRank=rows.findIndex(...)+1；未开局时组件内不展示） */
  rank: { type: Number, default: 0 },
  /** 分数视图（power 页胶囊）：'dupr'=分层三位小数+段位；'elo'=整数+无段位 */
  mode: { type: String as PropType<ScoreMode>, default: "dupr" },
});

const emit = defineEmits<{ (e: "profile"): void }>();

const userStore = useUserStore();
const session = useSessionStore();
const me = userStore.me;

/** alpha:1828 played = me.play>0 */
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
    : "待第一局校准 · 起步 2.5",
);
</script>

<style lang="scss" scoped>
/* alpha.html:410-413 .mycardp（margin-top:14px 来自 alpha:1844 内联样式） */
.mycardp {
  margin-top: 14px;
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  padding: 16px;
  background: linear-gradient(150deg, var(--ink3), var(--ink2));
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition:
    border-color 0.2s,
    background 0.3s;
}
.mycardp:active {
  border-color: rgba(255, 212, 0, 0.4);
}
/* alpha.html:414-420 bg-neon */
.mycardp.bg-neon {
  background:
    radial-gradient(
      circle at 90% 10%,
      rgba(255, 212, 0, 0.15),
      transparent 55%
    ),
    radial-gradient(
      circle at 10% 90%,
      rgba(111, 231, 255, 0.08),
      transparent 60%
    ),
    linear-gradient(150deg, #1c1b26, var(--ink2));
  border-color: rgba(255, 212, 0, 0.35);
  box-shadow: inset 0 0 24px rgba(255, 212, 0, 0.04);
}
/* alpha.html:421-426 bg-gold */
.mycardp.bg-gold {
  background:
    radial-gradient(
      circle at 85% 15%,
      rgba(255, 212, 0, 0.24),
      transparent 55%
    ),
    linear-gradient(135deg, #2b2313 0%, #181512 60%, #0e0d0c 100%);
  border-color: rgba(255, 212, 0, 0.5);
  box-shadow: inset 0 0 30px rgba(255, 212, 0, 0.08);
}
/* alpha.html:427-433 bg-cyber */
.mycardp.bg-cyber {
  background:
    radial-gradient(
      circle at 80% 20%,
      rgba(255, 90, 54, 0.18),
      transparent 50%
    ),
    radial-gradient(
      circle at 20% 80%,
      rgba(184, 169, 255, 0.12),
      transparent 50%
    ),
    linear-gradient(150deg, #221426, var(--ink2));
  border-color: rgba(255, 90, 54, 0.4);
  box-shadow: inset 0 0 26px rgba(255, 90, 54, 0.06);
}
/* alpha.html:434-440 bg-aurora */
.mycardp.bg-aurora {
  background:
    radial-gradient(
      circle at 85% 15%,
      rgba(111, 231, 255, 0.2),
      transparent 55%
    ),
    radial-gradient(
      circle at 15% 85%,
      rgba(184, 169, 255, 0.14),
      transparent 55%
    ),
    linear-gradient(150deg, #10222b, var(--ink2));
  border-color: rgba(111, 231, 255, 0.45);
  box-shadow: inset 0 0 26px rgba(111, 231, 255, 0.06);
}
/* alpha.html:441-445 .top-row/.rkbox/.rk/.rl/.av */
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
/* alpha:1848 右列 flex:1;min-width:0 */
.info {
  flex: 1;
  min-width: 0;
}
/* alpha:1849 nrow：flex · gap 8 · wrap */
.nrow {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
/* alpha:1850 <b style="font-size:16px"> */
.ttl {
  font-size: 16px;
  font-weight: 700;
}
/* alpha:1851 未开局 ? 徽章（.tierb 基础形 alpha:408-409 + 内联底色字色） */
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
/* alpha.html:446-448 .myscore/.big/.unit */
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
  color: var(--dim); /* alpha:1853 未开局大分数 color:var(--dim) */
}
.unit {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
}
/* alpha.html:1858 运动数据行（mono 11px 居中 · 上分隔线 · 超出省略） */
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
