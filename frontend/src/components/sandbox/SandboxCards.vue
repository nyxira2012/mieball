<template>
  <!-- 2.1 空态里新增的两张教学虚拟卡：点击进对应教学模式（sandbox.enter）。
       卡壳与字级照 gcard 家族常规卡（GameCard 同源副本惯例——styles/ 不新增文件），
       无时间列/场馆/角标，只有题+副句 -->
  <view class="tcard" @click="pick('participate')">
    <view class="name">{{ CARD_TITLES.participate.title }}</view>
    <view class="sub">{{ CARD_TITLES.participate.sub }}</view>
  </view>
  <view class="tcard" @click="pick('organize')">
    <view class="name">{{ CARD_TITLES.organize.title }}</view>
    <view class="sub">{{ CARD_TITLES.organize.sub }}</view>
  </view>
</template>

<script setup lang="ts">
/* 组件直调 store（项目惯例）：点卡=enter，教学模式切换由 live.vue 分支次序接管 */
import { CARD_TITLES } from "@/sandbox/data";
import { useSandboxStore } from "@/stores/sandbox";

const sandbox = useSandboxStore();

function pick(kind: "participate" | "organize"): void {
  sandbox.enter(kind);
}
</script>

<style lang="scss" scoped>
/* gcard 家族常规卡壳（GameCard.vue 同源副本）：细线边框/常规圆角/常规底色，
   整行一张竖着摞（margin-bottom 即卡距）；按下反馈同族 */
.tcard {
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: linear-gradient(160deg, var(--ink3), var(--ink2));
  padding: 16px 16px 14px;
  margin-bottom: 12px;
  cursor: pointer;
  transition:
    transform 0.18s ease,
    border-color 0.18s;
}
.tcard:active {
  transform: scale(0.975);
  border-color: rgba(255, 212, 0, 0.4);
}
.name {
  font-size: 15px;
  font-weight: 600;
  line-height: 1.2;
  margin-bottom: 2px;
}
.sub {
  font-size: 12px;
  color: var(--dim);
  line-height: 1.3;
}
</style>
