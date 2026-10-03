<template>
  <!-- 我的战力卡（alpha.html:1844-1861 逐字结构）：
       rank 位 #N / 未开局 — · ChibiAvatar 76（点卡开我的档案、点头像去「我的」页 stopPropagation alpha:1847）·
       段位 TierBadge / 未开局 ? 徽章 · 大分数 fmtScore + ELO/NTRP 单位 · 本月涨跌 ▲▼ ·
       底部运动数据行 recentStats（alpha:1858-1860，未开局两态文案逐字）。 -->
  <view class="mycardp" :class="`bg-${me.cardBg || 'neon'}`" @click="emit('profile')">
    <view class="top-row">
      <!-- alpha:1846 rkbox：#N 或 —（未开局） -->
      <view class="rkbox">
        <view class="rk">{{ played ? '#' + rank : '—' }}</view>
        <view class="rl">MY RANK</view>
      </view>
      <!-- alpha:1847 av：event.stopPropagation();go('mine') → uni.switchTab 到我的页 -->
      <view class="av" @click.stop="goMine">
        <ChibiAvatar :chibi="me.chibi" :size="76" />
      </view>
      <!-- alpha:1848 -->
      <view class="info">
        <view class="nrow">
          <text class="ttl">{{ played ? '我的战力卡' : '我的起步分' }}</text>
          <!-- alpha:1851 已开局 tierB(me.elo)，未开局灰 ? 徽章 -->
          <TierBadge v-if="played" :tier="tier(me.elo)" />
          <text v-else class="tierb-fb">?</text>
        </view>
        <!-- alpha:1852-1855 myscore -->
        <view class="myscore">
          <text class="big" :class="{ dim: !played }">{{ fmtScore(me.elo, ui.scoreMode) }}</text>
          <text class="unit">{{ ui.scoreMode === 'elo' ? 'ELO' : 'NTRP' }}</text>
          <text v-if="played" class="d" :class="me.month >= 0 ? 'up' : 'dn'">
            {{ me.month >= 0 ? '▲' : '▼' }}{{ Math.abs(me.month) }} 本月
          </text>
        </view>
      </view>
    </view>
    <!-- alpha:1858-1860 运动数据行：已开局「N 胜 N 负 · 运动 N 小时 · 消耗 N 大卡 · 积分 ±N」，
         未开局「待第一局校准 · 自评起步分」（文案逐字） -->
    <view class="telemetry">{{ telemetry }}</view>
  </view>
</template>

<script setup lang="ts">
/* 我的战力卡（alpha.html:1844-1861 · P9）。business 件：组合 ui 件（ChibiAvatar/TierBadge）+ 业务数据。
   rank 位（myRank）由 power 页按 rankRows（alpha:865/1826）算好传入。 */
import { computed } from 'vue';
import ChibiAvatar from '@/components/ui/ChibiAvatar.vue';
import TierBadge from '@/components/ui/TierBadge.vue';
import { useUserStore } from '@/stores/user';
import { useUiStore } from '@/stores/ui';
import { fmtScore, tier } from '@/utils/elo';

defineProps({
  /** 我的排名（alpha:1826 myRank=rows.findIndex(u=>u.id===0)+1；未开局时组件内不展示） */
  rank: { type: Number, default: 0 },
});

const emit = defineEmits<{ (e: 'profile'): void }>();

const userStore = useUserStore();
const ui = useUiStore();
const me = userStore.me;

/** alpha:1828 played = me.play>0 */
const played = computed(() => me.play > 0);
/** alpha:1829 rs = me.recentStats || {win:0,loss:0,hours:0,kcal:0} */
const rs = computed(() => me.recentStats || { win: 0, loss: 0, hours: 0, kcal: 0 });
/** alpha:1859-1860 底部数据行文案（逐字口径） */
const telemetry = computed(() =>
  played.value
    ? `${rs.value.win} 胜 ${rs.value.loss} 负 · 运动 ${rs.value.hours} 小时 · 消耗 ${rs.value.kcal} 大卡 · 积分 ${me.month >= 0 ? '+' : ''}${me.month}`
    : '待第一局校准 · 自评起步分',
);

/** alpha:1847 点头像区域：stopPropagation + go('mine')（跳转在页面层做，TabBar 同款 switchTab） */
function goMine(): void {
  uni.switchTab({ url: '/pages/mine/mine' });
}
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
  transition: border-color 0.2s, background 0.3s;
}
.mycardp:active {
  border-color: rgba(255, 212, 0, 0.4);
}
/* alpha.html:414-420 bg-neon */
.mycardp.bg-neon {
  background:
    radial-gradient(circle at 90% 10%, rgba(255, 212, 0, 0.15), transparent 55%),
    radial-gradient(circle at 10% 90%, rgba(111, 231, 255, 0.08), transparent 60%),
    linear-gradient(150deg, #1c1b26, var(--ink2));
  border-color: rgba(255, 212, 0, 0.35);
  box-shadow: inset 0 0 24px rgba(255, 212, 0, 0.04);
}
/* alpha.html:421-426 bg-gold */
.mycardp.bg-gold {
  background:
    radial-gradient(circle at 85% 15%, rgba(255, 212, 0, 0.24), transparent 55%),
    linear-gradient(135deg, #2b2313 0%, #181512 60%, #0e0d0c 100%);
  border-color: rgba(255, 212, 0, 0.5);
  box-shadow: inset 0 0 30px rgba(255, 212, 0, 0.08);
}
/* alpha.html:427-433 bg-cyber */
.mycardp.bg-cyber {
  background:
    radial-gradient(circle at 80% 20%, rgba(255, 90, 54, 0.18), transparent 50%),
    radial-gradient(circle at 20% 80%, rgba(184, 169, 255, 0.12), transparent 50%),
    linear-gradient(150deg, #221426, var(--ink2));
  border-color: rgba(255, 90, 54, 0.4);
  box-shadow: inset 0 0 26px rgba(255, 90, 54, 0.06);
}
/* alpha.html:434-440 bg-aurora */
.mycardp.bg-aurora {
  background:
    radial-gradient(circle at 85% 15%, rgba(111, 231, 255, 0.2), transparent 55%),
    radial-gradient(circle at 15% 85%, rgba(184, 169, 255, 0.14), transparent 55%),
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
/* alpha.html:449 .d.up/.d.dn（本月涨跌两色，MyPowerCard/RankRow/ProfileSheet 各自持有） */
.d.up {
  color: var(--lemon);
}
.d.dn {
  color: var(--coral);
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
