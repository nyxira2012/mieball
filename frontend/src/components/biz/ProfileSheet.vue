<template>
  <!-- 球员档案弹层（全产品共用：榜单/意向卡/现场队员/我的头像都唤起）。
       alpha.html:1891-1929 openProfile · P9 填充：
       标题+hint · ChibiAvatar 84 · 名+随行/我/♥ 徽章 · TierBadge+大分数+分制单位+本月涨跌 ·
       摘要行三态（已开局 / 访客 / 未开局，文案逐字）· Last5Dots 近 5 场 ·
       意向行（game store intents 查该用户）· 非我双按钮：喜欢(burn/ghost) + 邀请入局。 -->
  <view v-if="u" class="pf">
    <!-- alpha:1900 h3 + hint（SheetHost 未传壳层 title，档案自带，样式同 AppSheet 壳 alpha:558-561） -->
    <view class="sheet-t">球员档案</view>
    <view class="sheet-hint">全产品同一份 · 约球意向 / 现场页 / 榜单打开的都是它</view>

    <!-- alpha:1901-1913 头像 + 右列 -->
    <view class="hero">
      <ChibiAvatar :chibi="u.chibi" :size="84" />
      <view class="hr">
        <!-- alpha:1904-1905 名 + 随行/我/♥ -->
        <view class="nmrow">
          <text class="nm">{{ u.name }}</text>
          <text v-if="u.shadow" class="badge shadow">随行</text>
          <text v-if="isMe" class="badge fire">我</text>
          <text v-if="u.liked" class="hrt">♥</text>
        </view>
        <!-- alpha:1906-1910 徽章 + 大分数 + 单位 + 本月涨跌 -->
        <view class="scorerow">
          <TierBadge v-if="played" :tier="tier(u.elo)" />
          <text class="big">{{ played ? fmtScore(u.elo, ui.scoreMode) : '—' }}</text>
          <text class="unit">{{ played ? (ui.scoreMode === 'elo' ? 'ELO' : 'NTRP') : '起步' }}</text>
          <text v-if="played" class="d" :class="u.month >= 0 ? 'up' : 'dn'">
            {{ u.month >= 0 ? '▲' : '▼' }}{{ Math.abs(u.month) }} 本月
          </text>
        </view>
        <!-- alpha:1911 摘要行（三态逐字） -->
        <view class="sum">{{ sum }}</view>
        <!-- alpha:1912 近 5 场（已开局才有） -->
        <view v-if="played" class="l5row">
          <Last5Dots :results="u.last5 || []" />
          <text class="l5t">近 5 场</text>
        </view>
      </view>
    </view>

    <!-- alpha:1914-1916 意向行（intents 里有该用户才出现） -->
    <view v-if="intent" class="intent">
      <text class="it-t">打球意向</text>
      <text class="it-b">{{ intentTxt }}</text>
    </view>

    <!-- alpha:1917-1920 非我双按钮：喜欢（burn/ghost 随 liked 切换）+ 邀请入局 -->
    <view v-if="!isMe" class="btns">
      <AppButton :variant="u.liked ? 'burn' : 'ghost'" class="flex1" @click="onLike">
        {{ u.liked ? '♥ 已喜欢 · 再点取消' : '♡ 喜欢' }}
      </AppButton>
      <AppButton variant="ghost" class="flex1" @click="onInvite">邀请入局</AppButton>
    </view>
  </view>
</template>

<script setup lang="ts">
/* 球员档案 ProfileSheet（alpha.html:1891-1929 · P9）。
   SheetHost 传 userId（SheetPayload {type:'profile',userId} 约定不变）；
   findUser（现场名册优先）取人；分数/段位随 ui.scoreMode 全局联动。 */
import { computed } from 'vue';
import type { PropType } from 'vue';
import ChibiAvatar from '@/components/ui/ChibiAvatar.vue';
import TierBadge from '@/components/ui/TierBadge.vue';
import Last5Dots from '@/components/ui/Last5Dots.vue';
import { useUserStore } from '@/stores/user';
import { useGameStore } from '@/stores/game';
import { useUiStore } from '@/stores/ui';
import { fmtScore, tier } from '@/utils/elo';
import { freqName, slotName } from '@/utils/format';

const props = defineProps({
  /** 档案目标用户 id（我的档案传 me.id；随行访客也可开） */
  userId: { type: Number as PropType<number>, required: true },
});

const userStore = useUserStore();
const game = useGameStore();
const ui = useUiStore();

/** alpha:1892 findUser（现场名册优先，再查 U 全表） */
const u = computed(() => userStore.findUser(props.userId));
/** alpha:1894 isMe = u.id===me.id（响应式：真账号接管「我」位后 id 联动） */
const isMe = computed(() => u.value?.id === userStore.me.id);
/** alpha:1895 played（上过场谓词单一源在 user store 的 hasPlayed） */
const played = computed(() => !!u.value && userStore.hasPlayed(u.value));

/** alpha:1896-1897 摘要三态：已开局 / 访客 / 未开局（逐字口径） */
const sum = computed(() => {
  const x = u.value;
  if (!x) return '';
  if (played.value)
    return `${x.play} 场 · 胜率 ${Math.round((x.win / x.play) * 100)}% · 本月 ${x.month >= 0 ? '+' : ''}${x.month || 0}`;
  return x.shadow ? '访客 · 费用照常 · 积分半权重不进榜' : '还没打过 · 待第一局校准';
});

/** alpha:1898 it = intents.find(i=>i.u.id===u.id) */
const intent = computed(() => game.intents.find((i) => i.u.id === u.value?.id));
/** alpha:1915 意向行正文：slots · 频率 · note */
const intentTxt = computed(() => {
  const it = intent.value;
  if (!it) return '';
  return ` · ${it.slots.map(slotName).join(' · ')} · ${freqName(it.freq)}${it.note ? ` · 「${it.note}」` : ''}`;
});

/** alpha:1918 toggleLike：store 内置 toast（alpha:1925 文案），liked 变化由响应式联动榜单/按钮态 */
function onLike(): void {
  if (u.value) userStore.toggleLike(u.value.id);
}

/** alpha:1919 inviteSheet(u.id)：切到「选局邀请」弹层（invite-to-slot） */
function onInvite(): void {
  ui.openSheet({ type: 'invite-to-slot', userId: props.userId });
}
</script>

<style lang="scss" scoped>
/* 壳层标题/hint 走全局 .sheet-t/.sheet-hint（base.scss 收源） */
/* alpha:1901 hero 行 */
.hero {
  display: flex;
  gap: 14px;
  align-items: center;
}
/* alpha:1903 */
.hr {
  flex: 1;
  min-width: 0;
}
/* alpha:1904 名行 */
.nmrow {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 16px;
  font-weight: 800;
  flex-wrap: wrap;
}
/* alpha:1905 liked ♥ */
.hrt {
  color: var(--coral);
}
/* alpha:1906 分数行 */
.scorerow {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 5px 0 3px;
  flex-wrap: wrap;
}
/* alpha:1908 大分数（含未开局 '—'，同样柠檬色） */
.big {
  font-family: var(--disp);
  font-size: 26px;
  color: var(--lemon);
  line-height: 1;
}
/* alpha:1909 分制单位 / 起步 */
.unit {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
}
/* alpha.html:449 涨跌两色 */
.d.up {
  color: var(--lemon);
}
.d.dn {
  color: var(--coral);
}
/* alpha:1911 摘要行 */
.sum {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
}
/* alpha:1912 近 5 场行 */
.l5row {
  margin-top: 5px;
  display: flex;
  align-items: center;
  gap: 5px;
}
.l5t {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
}
/* alpha:1914 意向行 */
.intent {
  margin-top: 12px;
  padding: 9px 12px;
  border-radius: 10px;
  background: rgba(245, 241, 232, 0.04);
  border: 1px dashed rgba(245, 241, 232, 0.14);
  font-size: 11px;
}
/* alpha:1915 */
.it-t {
  color: var(--lemon);
  font-weight: 700;
}
.it-b {
  font-size: 11px;
}
/* alpha:1917 按钮排 */
.btns {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}
/* alpha:1918/1919 两按钮均 style="flex:1" */
.flex1 {
  flex: 1;
}
/* alpha.html:291 徽章基础形 + 293/294 fire/shadow 两态 */
.badge {
  display: inline-block;
  font-family: var(--mono);
  font-size: 9px;
  border-radius: 6px;
  padding: 1px 5px;
  margin-top: 2px;
}
.badge.fire {
  background: rgba(255, 90, 54, 0.18);
  color: var(--coral);
}
.badge.shadow {
  background: rgba(184, 169, 255, 0.15);
  color: var(--lilac);
}
</style>
