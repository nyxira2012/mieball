<template>
  <!-- 球局卡 · alpha.html:898-917 gameCard 为基底（P5a 全量版）：
       时间大字（dd 大字 + tt 小字两行）· 局名 · 地点行 · foot 状态 chips（进行中 = live-dot + 「进行中」hot；满员 = 「满员 · 候补」full；
       否则「剩 N 坑」ok；done = 「已结束」+ 比分胜/负，隐去满员/剩坑与人数 chip）+「min-max 人」chip。
       批4 裁决①：props 收窄为卡面展示原子（GameCardModel）——meet 传真局映射、登记/记录页传 mock 映射，
       组件不再认识任何一种 Game 形状（与数据源解耦）。
       2026-10-10 卡面改版（用户拍板，推翻 2026-10-04「头像右上/角色右下/卡面不放场号」）：
       角色标签（我发起/被邀请/已加入）挪局名行右端（原头像叠层位，纯展示无功能，替换之；live 态让位 LIVE 角标）；
       头像叠层缩小（26→20）挪场馆行右端；foot 撤出必打 chip 与角色 chip——「已订场」场号 /「必开」/ 倒计时灰字
       全部落时间列下方固定槽（.tsub，钉 max-width 不随长短撑宽挤压 chips 行）。
       人均 chip 已按用户要求移除（信息仍在局详情与报名弹层）。
       is-live：珊瑚描边 + LIVE 角标；is-inv：被邀请珊瑚描边（alpha:329）。
       emit('tap')：进详情或 joinSheet 分支由父层决定（gameTapAction）；emit('enter')：卡片入场窗内
       的「进入现场」按钮（2.5 批2），父层 goLive（组织者成员同路）。 -->
  <view
    class="gcard"
    :class="{ 'is-live': live, 'is-inv': inv }"
    @click="emit('tap')"
  >
    <view class="gd">
      <!-- alpha:909 时间位：大字 = 时刻，小字 = 日段（今晚 / 10.06 周一） -->
      <view class="time">
        {{ card.hmText }}
        <text class="tt">{{ card.dayText }}</text>
        <!-- 固定槽小字（2026-10-10 卡面改版）：订场场号 / 仅手动锁「必开」，done/live 不亮 -->
        <text v-if="card.timeSub && !done && !live" class="tsub">{{
          card.timeSub
        }}</text>
        <!-- 2.5 §4.1 倒计时灰字自 foot 挪入同槽：长短不一不再挤压 chips 行 -->
        <text v-if="card.countdown" class="tsub">{{ card.countdown }}</text>
      </view>
      <view class="meta">
        <view class="name">
          <text class="title-txt">{{ card.name }}</text>
          <!-- 角色标识在局名行右端（2026-10-10 挪位；live 态让位右上角 LIVE 角标） -->
          <AppChip v-if="role && !live" :kind="role">{{ roleTxt }}</AppChip>
        </view>
        <view class="loc">
          <text class="loc-txt">{{ card.venueText }}</text>
          <!-- 头像叠层（缩小）挂场馆行右端：谁在局里仍在卡面一眼可见 -->
          <view class="loc-stack">
            <AvatarStack :avatars="card.stackAvatars" :max="5" />
            <text class="plusn">{{ card.stackPlus }}</text>
          </view>
        </view>
        <view class="foot">
          <!-- done 形态：[已结束]，隐去满员/剩坑与人数 chip（比分看局详情/战报，卡面不放） -->
          <template v-if="done">
            <AppChip>已结束</AppChip>
          </template>
          <template v-else-if="live">
            <view class="live-dot" />
            <AppChip kind="hot">进行中</AppChip>
          </template>
          <AppChip v-else-if="full" kind="full">满员 · 候补</AppChip>
          <AppChip v-else kind="ok">剩 {{ card.slotsLeft }} 坑</AppChip>
          <AppChip v-if="!done"
            >{{ card.minPlayers }}-{{ card.maxPlayers }} 人</AppChip
          >
          <view class="sp" />
          <!-- 2.5 卡片三态：入场窗内亮「进入现场」出口（stop 防触发整卡 tap） -->
          <view
            v-if="card.liveEnter"
            class="tbtn on-in"
            @click.stop="emit('enter')"
            >进入现场</view
          >
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
/* alpha.html:898-917 gameCard（P5a）。卡面字段契约见 types.ts GameCardModel（批4 裁决①）。 */
import { computed } from "vue";
import type { PropType } from "vue";
import AppChip from "@/components/ui/AppChip.vue";
import AvatarStack from "@/components/ui/AvatarStack.vue";
import type { GameCardModel } from "@/api/types";

const props = defineProps({
  card: { type: Object as PropType<GameCardModel>, required: true },
});
const emit = defineEmits<{ (e: "tap"): void; (e: "enter"): void }>();

const live = computed(() => props.card.status === "live");
const full = computed(() => props.card.slotsLeft <= 0);
const done = computed(() => props.card.status === "done");
const inv = computed(() => props.card.myRole === "inv");

const role = computed(() =>
  props.card.myRole === "joined" ? "dim" : props.card.myRole,
);
const roleTxt = computed(() =>
  props.card.myRole === "org"
    ? "我发起"
    : props.card.myRole === "inv"
      ? "被邀请"
      : "已加入",
);
</script>

<style lang="scss" scoped>
/* gcard 家族样式（alpha:104-126）为本组件所有；chip/roletag 归 AppChip、stack 归 AvatarStack。
   （DeadCard 的未成局卡壳同源，各自持有副本——styles/ 不允许新增文件。） */
.gcard {
  position: relative;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: linear-gradient(160deg, var(--ink3), var(--ink2));
  padding: 16px 16px 14px;
  margin-bottom: 12px;
  height: 108px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: center;
  transition:
    transform 0.18s ease,
    border-color 0.18s;
  overflow: hidden;
  cursor: pointer;
}
.gcard:active {
  transform: scale(0.975);
  border-color: rgba(255, 212, 0, 0.4);
}
.gd {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}
.time {
  font-family: var(--disp);
  font-size: 30px;
  line-height: 0.95;
  color: var(--lemon);
  min-width: 64px;
  flex: none;
  /* 子行固定槽一律单行省略。写在父级：uni-app 框架给 uni-text 强制
     white-space:inherit!important，子级自写 nowrap 不生效，继承父级才落得住 */
  white-space: nowrap;
}
/* alpha:108 .time small */
.time .tt {
  display: block;
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  letter-spacing: 0.2em;
  margin-top: 2px;
}
/* 时间列下方固定槽小字（2026-10-10 卡面改版）：场号/必开与倒计时同族灰字。
   钉 max-width+省略号：长短不随内容撑宽时间列挤压右侧（Anton 大字天然窄，
   列宽由日段小字决定 ≈72px，槽位与之同宽级）；108px 卡高预算内最多两行 */
.tsub {
  display: block;
  max-width: 76px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--mono);
  font-size: 10px;
  line-height: 1.3;
  color: var(--dim);
  margin-top: 3px;
}
.meta {
  flex: 1;
  min-width: 0;
}
.name {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 2px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  line-height: 1.2;
}
.title-txt {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.loc {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--dim);
  line-height: 1.3;
}
.loc-txt {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
/* 头像叠层缩小副本（26→20）：场馆行容不下原尺寸；:deep 只作用本卡 */
.loc-stack {
  flex: none;
  display: flex;
  align-items: center;
}
.loc-stack :deep(.stack-av) {
  width: 20px;
  height: 20px;
  margin-left: -7px;
}
.loc-stack :deep(.stack-av:first-child) {
  margin-left: 0;
}
.foot {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  flex-wrap: nowrap;
  overflow: hidden;
}
.sp {
  flex: 1;
}
/* alpha:123-125 live-dot 呼吸灯（pulse 在 animations.scss） */
.live-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--coral);
  box-shadow: 0 0 0 0 rgba(255, 90, 54, 0.6);
  animation: pulse 1.6s infinite;
  flex: none;
}
/* alpha:126-129 is-live 珊瑚描边 + LIVE 角标 */
.gcard.is-live {
  border-color: rgba(255, 90, 54, 0.5);
}
.gcard.is-live::after {
  content: "LIVE";
  position: absolute;
  top: 12px;
  right: 14px;
  font-family: var(--disp);
  font-size: 12px;
  letter-spacing: 0.2em;
  color: var(--coral);
}
/* alpha:329 is-inv 被邀请描边 */
.gcard.is-inv {
  border-color: rgba(255, 90, 54, 0.45);
}
/* alpha:132 .plusn。不设 nowrap：窄位换行是 alpha 原样 */
.plusn {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  margin-left: 2px;
}
</style>
