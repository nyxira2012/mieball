<template>
  <!-- 榜单单行（alpha.html:1765-1773 rankRowHtml 结构）：名次大字（参考区行
       unrated → 「—」不参与排名）· 头像 40 · 名 + 我徽章 + ♥ + 未定级 +
       TierBadge（段位/未定级是 DUPR 定级概念，Elo 视图不出现）·
       Last5Dots + 近 5 场 · N 战 · 右列主数字随视图：DUPR 分层三位小数 / Elo 整数 ·
       本月涨跌。前三 top-1/2/3 高亮，新批次行 lazy-in 入场。
       1.9 A6 #5：每行铺行主卡背（r 档右侧取景窗、左缘融进卡底）；金/橙/青语义
       描边在行 border 上、卡背窗贴 padding box 之内，两不相盖；无卡背行素卡。 -->
  <view
    class="rank-row"
    :class="[topCls, { 'lazy-in': lazy }]"
    @click="emit('profile', user.id)"
  >
    <CardBackdrop :cid="user.back ?? null" mode="r" />
    <!-- alpha:1769 名次（参考区行无位次） -->
    <view class="no">{{ unrated ? "—" : index + 1 }}</view>
    <AvatarBadge :url="user.avatarUrl ?? null" :size="40" />
    <view class="mid">
      <view class="nm">
        <text class="nm-t">{{ user.name }}</text>
        <!-- alpha:1770 u.id===CURRENT_USER_ID → 「我」徽章 · liked → ♥（本地态） -->
        <text v-if="userStore.isMe(user.id)" class="badge fire">我</text>
        <text v-if="userStore.isLiked(user.id)" class="hrt">♥</text>
        <TierBadge v-if="mode === 'dupr'" :tier="duprTier(duprOf(user))" />
        <text v-if="mode === 'dupr' && user.provisional" class="prov"
          >未定级</text
        >
      </view>
      <view class="st">
        <Last5Dots :results="user.last5 || []" />
        <text class="st-t">近 5 场 · {{ user.play }} 战</text>
      </view>
    </view>
    <view class="elo">
      <template v-if="mode === 'elo'">
        <text class="sc">{{ user.elo }}</text>
        <text class="unit">Elo</text>
      </template>
      <template v-else>
        <DuprScore :d="duprOf(user)" />
        <text class="unit">DUPR</text>
      </template>
      <text class="d" :class="user.month >= 0 ? 'up' : 'dn'">
        {{ user.month >= 0 ? "▲" : "▼" }}{{ Math.abs(user.month) }} 本月
      </text>
    </view>
  </view>
</template>

<script setup lang="ts">
/* 评分排行单行 RankRow（alpha.html:1765-1773 · P9）。business 件：组合
   AvatarBadge/TierBadge/Last5Dots/DuprScore。unrated=参考区行（1.4 §6：
   未满 5 场不参与排名，位次列「—」、不吃前三高亮）。 */
import { computed } from "vue";
import type { PropType } from "vue";
import AvatarBadge from "@/components/ui/AvatarBadge.vue";
import CardBackdrop from "@/components/ui/CardBackdrop.vue";
import TierBadge from "@/components/ui/TierBadge.vue";
import Last5Dots from "@/components/ui/Last5Dots.vue";
import DuprScore from "@/components/ui/DuprScore.vue";
import type { ScoreMode, User } from "@/api/types";
import { useUserStore } from "@/stores/user";
import { duprOf, duprTier } from "@/utils/elo";

const props = defineProps({
  /** 榜单行球员（rankRows 过滤 !shadow && play>0 后的有序一条） */
  user: { type: Object as PropType<User>, required: true },
  /** 0 起榜单位次（alpha:1766/1769） */
  index: { type: Number, required: true },
  /** 本批懒加载新行 → lazy-in 入场动画（alpha:1768 isLazy，初始 5 行不带） */
  lazy: { type: Boolean, default: false },
  /** 参考区行（未满 5 场，1.4 §6）：无位次、不参与排名 */
  unrated: { type: Boolean, default: false },
  /** 分数视图（power 页胶囊）：'dupr'=分层三位小数+段位；'elo'=整数+无段位 */
  mode: { type: String as PropType<ScoreMode>, default: "dupr" },
});

const emit = defineEmits<{ (e: "profile", userId: number): void }>();

const userStore = useUserStore();

/** alpha:1766 topCls = i===0?'top-1':i===1?'top-2':i===2?'top-3':''（参考区行不吃高亮） */
const topCls = computed(() =>
  props.unrated
    ? ""
    : props.index === 0
      ? "top-1"
      : props.index === 1
        ? "top-2"
        : props.index === 2
          ? "top-3"
          : "",
);
</script>

<style lang="scss" scoped>
/* alpha.html:495-498 .rank-row；宿主契约（CardBackdrop）：relative+hidden 裁
   取景窗出血；z-index:0 立层叠上下文，负 z-index 卡底层垫在不透明行底之上、
   文字之下（不立层会被行自己的 background 盖死） */
.rank-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 12px;
  border-radius: 14px;
  border: 1px solid rgba(245, 241, 232, 0.08);
  background: var(--ink2);
  margin-bottom: 8px;
  cursor: pointer;
  position: relative;
  z-index: 0;
  overflow: hidden;
  transition:
    border-color 0.15s,
    transform 0.12s;
}
.rank-row:active {
  border-color: rgba(255, 212, 0, 0.4);
  transform: scale(0.98);
}
/* alpha.html:499-508 前三行高亮 */
.rank-row.top-1 {
  border-color: rgba(255, 212, 0, 0.55);
  background: linear-gradient(150deg, rgba(255, 212, 0, 0.15), var(--ink2));
  box-shadow: inset 0 0 18px rgba(255, 212, 0, 0.08);
}
.rank-row.top-1 .no {
  color: var(--lemon);
  font-weight: 800;
  text-shadow: 0 0 10px rgba(255, 212, 0, 0.5);
}
.rank-row.top-2 {
  border-color: rgba(255, 90, 54, 0.45);
  background: linear-gradient(150deg, rgba(255, 90, 54, 0.11), var(--ink2));
  box-shadow: inset 0 0 16px rgba(255, 90, 54, 0.06);
}
.rank-row.top-2 .no {
  color: var(--coral);
  font-weight: 700;
}
.rank-row.top-3 {
  border-color: rgba(111, 231, 255, 0.45);
  background: linear-gradient(150deg, rgba(111, 231, 255, 0.1), var(--ink2));
  box-shadow: inset 0 0 16px rgba(111, 231, 255, 0.06);
}
.rank-row.top-3 .no {
  color: var(--ice);
  font-weight: 700;
}
/* alpha.html:509-514 .no/.mid/.nm/.st/.elo */
.no {
  font-family: var(--disp);
  font-size: 18px;
  width: 26px;
  color: var(--dim);
  text-align: center;
  flex: none;
}
.mid {
  flex: 1;
  min-width: 0;
}
.nm {
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}
/* alpha:1770 u.liked → ♥（内联 color:var(--coral);font-size:12px） */
.hrt {
  color: var(--coral);
  font-size: 12px;
}
.st {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  margin-top: 2px;
}
/* alpha:1771 「近 5 场 · N 战」margin-left:4px */
.st-t {
  margin-left: 4px;
}
.elo {
  font-family: var(--disp);
  font-size: 20px;
  color: var(--cream);
  text-align: right;
}
/* alpha:1772 DUPR 单位角标（font-size:9px · mono · dim · margin-left:2px） */
.unit {
  font-size: 9px;
  font-family: var(--mono);
  color: var(--dim);
  margin-left: 2px;
}
/* alpha.html:515 .rank-row .d（块级）+ 449 两色 */
.d {
  font-family: var(--mono);
  font-size: 10px;
  display: block;
}
.d.up {
  color: var(--lemon);
}
.d.dn {
  color: var(--coral);
}
/* alpha.html:291+293 「我」徽章（badge.fire） */
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
/* 未定级小 chip（1.4 §5：DUPR 可信度两态，浅丁香角标） */
.prov {
  font-family: var(--mono);
  font-size: 9px;
  border-radius: 6px;
  padding: 1px 5px;
  background: rgba(184, 169, 255, 0.15);
  color: var(--lilac);
}
/* alpha.html:519 懒加载新行入场（rankFadeIn keyframes 全局 animations.scss alpha:520） */
.rank-row.lazy-in {
  animation: rankFadeIn 0.28s ease-out backwards;
}
</style>
