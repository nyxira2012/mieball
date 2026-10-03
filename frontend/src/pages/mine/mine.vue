<template>
  <!-- 我的页（P10）· alpha.html:644-673 模板 · 393-405 mecard/ledger 样式 · 1931-1976 renderMine/换装/mountDress -->
  <PageShell tab="mine">
    <!-- alpha:645-648 头部：kicker + brand（「的」字黄色） -->
    <view class="stag">
      <view class="kicker">Player Card</view>
      <view class="brand">我<text class="bem">的</text>球场</view>
    </view>

    <!-- alpha:649-659 mecard：点头像循环换装（alpha:1960-1964，toast 在 user store cyclePart 内） -->
    <view class="mecard">
      <view class="av" @click="user.cyclePart()">
        <ChibiAvatar :chibi="me.chibi" :size="88" />
      </view>
      <view class="minfo">
        <view class="mname">{{ meName }}</view>
        <view class="mrecord">{{ record }}</view>
        <view class="mchips">
          <!-- alpha:1939 me-elo：tierB 徽章 + ELO 分 + 段位（chip ok） -->
          <AppChip kind="ok">
            <TierBadge :tier="meTier" /> ELO {{ me.elo }} · {{ meTier }} 段
          </AppChip>
          <!-- alpha:656 尾号 chip -->
          <AppChip>尾号 ···4721</AppChip>
        </view>
      </view>
    </view>

    <!-- alpha:660 换装提示 notecard（文案逐字） -->
    <NoteCard>
      <text class="nb">换装：</text>点左边的小人，发型 / 衣服 / 表情随手换——你的球场形象你做主。
    </NoteCard>

    <!-- alpha:1966-1975 mountDress：部件选择 chips，选中态黄描边（chip ok）；
         点击切 dressPart 并 toast「选中「xx」· 点小人换」（user store setDressPart） -->
    <view class="dress-row">
      <AppChip
        v-for="p in DRESS_PARTS"
        :key="p"
        :kind="p === user.dressPart ? 'ok' : 'default'"
        @click="user.setDressPart(p)"
      >
        {{ PART_NAMES[p] }}
      </AppChip>
    </view>

    <!-- alpha:662-663 本期账本（ledger 样式 alpha:398-405 · 模板 alpha:1942-1951 逐字） -->
    <SectionTitle title="本期账本" more="10 月 · 一起结" />
    <view class="ledger">
      <view class="ltop">
        <view>
          <view class="kicker">AA POOL · {{ ledger.period }}</view>
          <view class="sum">¥{{ ledger.pool }}</view>
          <view class="sub sub11">本期总费用 · 结束时一起分</view>
        </view>
        <view class="rt">
          <view class="kicker">MY BALANCE</view>
          <!-- alpha:1941/1947 结余 = myPaid − myShare；垫多 lemon 带正号 / 还欠 coral -->
          <view class="bal" :class="bal >= 0 ? 'pos' : 'neg'">{{ bal >= 0 ? '+' : '' }}{{ bal }}</view>
          <view class="sub sub10">{{ bal >= 0 ? '垫多了 · 收钱' : '还欠着 · 转账' }}</view>
        </view>
      </view>
      <!-- alpha:1949-1950 逐笔：已垫付黄（pos）/ 待付珊瑚（neg） -->
      <view v-for="r in ledger.feeRows" :key="r.g" class="lrow">
        <text class="n">{{ r.g }}</text>
        <text class="amt" :class="r.paid ? 'pos' : 'neg'">{{ r.paid ? '已垫付 ¥' + r.amt : '待付 ¥' + r.amt }}</text>
      </view>
      <view class="lfoot">
        <!-- alpha:1951 结束本期 · 发起结算（toast 文案逐字） -->
        <AppButton variant="ghost" size="sm" block @click="onSettle">结束本期 · 发起结算</AppButton>
      </view>
    </view>

    <!-- alpha:665-666 我的球局：前 3 个未终止局（alpha:1952-1956 为简化行，P10 按任务口径复用完整 GameCard）；
         点击进详情（alpha:908 openDetail 语义 → uni.navigateTo） -->
    <SectionTitle title="我的球局" more="近期 3 场" />
    <GameCard v-for="g in myGames" :key="g.id" :game="g" @tap="openGame(g.id)" />

    <!-- alpha:668-672 账号：退出登录 / 注销账号（toast 文案逐字） -->
    <SectionTitle title="账号" more="1.1 规格已定" />
    <view class="acc-row">
      <AppButton variant="ghost" size="sm" class="grow" @click="onLogout">退出登录</AppButton>
      <AppButton variant="ghost" size="sm" class="grow" @click="onDeleteAcc">注销账号</AppButton>
    </view>
  </PageShell>
</template>

<script setup lang="ts">
/* 我的页（P10）· alpha.html:1931-1976 renderMine / 换装 / mountDress + 828-830 ledger */
import { computed } from 'vue';
import PageShell from '@/components/biz/PageShell.vue';
import ChibiAvatar from '@/components/ui/ChibiAvatar.vue';
import AppChip from '@/components/ui/AppChip.vue';
import AppButton from '@/components/ui/AppButton.vue';
import TierBadge from '@/components/ui/TierBadge.vue';
import NoteCard from '@/components/ui/NoteCard.vue';
import SectionTitle from '@/components/ui/SectionTitle.vue';
import GameCard from '@/components/biz/GameCard.vue';
import { useUserStore, DRESS_PARTS, PART_NAMES } from '@/stores/user';
import { useGameStore } from '@/stores/game';
import { useUiStore } from '@/stores/ui';
import { ledger } from '@/api';
import { tier } from '@/utils/elo';

const user = useUserStore();
const gameStore = useGameStore();
const ui = useUiStore();

/** 我（alpha:1935 U.me；user store 与 games/live 同源引用，换装全产品同步） */
const me = computed(() => user.me);
/** alpha:1937：默认名「我」显示为「我的球场小人」 */
const meName = computed(() => (me.value.name === '我' ? '我的球场小人' : me.value.name));
/** alpha:1938 战绩行：N 场 · N 胜 · 胜率 N% */
const record = computed(
  () => `${me.value.play} 场 · ${me.value.win} 胜 · 胜率 ${Math.round((me.value.win / me.value.play) * 100)}%`,
);
/** alpha:1939 ELO chip 的段位（utils/elo.ts tier） */
const meTier = computed(() => tier(me.value.elo));
/** alpha:1941 结余 = myPaid − myShare（验收 C35 口径） */
const bal = computed(() => ledger.myPaid - ledger.myShare);
/** alpha:1952 前 3 个未终止局（!dead） */
const myGames = computed(() => gameStore.games.filter((g) => !g.dead).slice(0, 3));

/** alpha:1951 结束本期 · 发起结算（toast 文案逐字） */
function onSettle(): void {
  ui.toast('本期账单已生成 · 群里甩一张图，各自转账，不用每局分钱');
}
/** 球局卡 → 局详情（alpha:1953 openDetail(g.id) 的 uni 路由等价） */
function openGame(id: number): void {
  uni.navigateTo({ url: `/pages/detail/detail?id=${id}` });
}
/** alpha:670 退出登录（toast 文案逐字） */
function onLogout(): void {
  ui.toast('已退出本机记忆 · 数据在云端');
}
/** alpha:671 注销账号（toast 文案逐字） */
function onDeleteAcc(): void {
  ui.toast('注销 = 档案匿名化 · 手机号释放');
}
</script>

<style lang="scss" scoped>
/* ---------- 头部 brand（alpha:85-87 h1.brand / h1.brand em）：
   base.scss 的 h1.brand 选择器带元素名、匹配不上 uni-view，故在页面内按同值复制类；
   font-weight 700 补 alpha h1 的 UA 默认加粗 ---------- */
.brand {
  font-family: var(--disp);
  font-size: 34px;
  line-height: 1.04;
  margin: 6px 0 2px;
  font-weight: 700;
}
.brand .bem {
  font-style: normal;
  color: var(--lemon);
}

/* ---------- mecard（alpha:394-397 · 结构 alpha:649-659） ---------- */
.mecard {
  display: flex;
  gap: 16px;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  padding: 18px;
  background: linear-gradient(150deg, var(--ink3), var(--ink2));
}
.mecard .av {
  width: 88px;
  height: 88px;
  flex: none;
  cursor: pointer;
  transition: transform 0.2s;
}
.mecard .av:active {
  transform: scale(0.92) rotate(-6deg);
}
/* alpha:651 flex:1 信息列 */
.minfo {
  flex: 1;
  min-width: 0;
}
/* alpha:652 名字 */
.mname {
  font-size: 20px;
  font-weight: 800;
}
/* alpha:653 战绩行 */
.mrecord {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--dim);
  margin: 3px 0 8px;
}
/* alpha:654 chips 行 */
.mchips {
  display: flex;
  gap: 8px;
  align-items: center;
}

/* alpha:660 notecard 内 <b> 的淡紫强调（槽内容持有本页 scope，scoped 可达） */
.nb {
  color: var(--lilac);
}

/* ---------- 换装部件选择 chips 行（alpha:1968 mountDress 容器 style 逐字） ---------- */
.dress-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin: -6px 0 16px;
}

/* ---------- 账本（alpha:398-405） ---------- */
.ledger {
  border: 1px solid rgba(255, 212, 0, 0.22);
  border-radius: var(--r-lg);
  overflow: hidden;
  background: var(--ink2);
}
.ltop {
  padding: 16px;
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  background: linear-gradient(140deg, rgba(255, 212, 0, 0.1), transparent 60%);
}
.sum {
  font-family: var(--disp);
  font-size: 40px;
  color: var(--lemon);
  line-height: 1;
}
/* alpha:1946 右列 text-align:right */
.rt {
  text-align: right;
}
/* alpha:1947 结余大字（颜色按正负二态，同 alpha 内联 style） */
.bal {
  font-family: var(--disp);
  font-size: 26px;
  line-height: 1.1;
}
.bal.pos {
  color: var(--lemon);
}
.bal.neg {
  color: var(--coral);
}
/* alpha:1945/1948 两行 sub 的内联字号覆盖 */
.sub11 {
  font-size: 11px;
}
.sub10 {
  font-size: 10px;
}
.lrow {
  display: flex;
  justify-content: space-between;
  padding: 11px 16px;
  border-top: 1px solid rgba(245, 241, 232, 0.07);
  font-size: 12px;
}
.lrow .n {
  color: var(--dim);
}
.lrow .amt {
  font-family: var(--mono);
  font-weight: 500;
}
.lrow .amt.pos {
  color: var(--lemon);
}
.lrow .amt.neg {
  color: var(--coral);
}
/* alpha:1951 按钮容器 */
.lfoot {
  padding: 14px 16px;
}

/* ---------- 账号按钮行（alpha:669 flex + 按钮 flex:1） ---------- */
.acc-row {
  display: flex;
  gap: 10px;
}
.acc-row .grow {
  flex: 1;
}
</style>
