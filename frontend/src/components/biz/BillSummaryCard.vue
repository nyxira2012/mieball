<template>
  <!-- 账单三数总览卡（5.1 一行三数：应付 coral / 已付默认 / 该收 lemon，_disp 数字 + mono 小字口径）。
       纯展示件：数字进 props、文案内聚（两个使用方口径逐字相同）；点击态由使用方经根元素
       透传 class/@click 自行挂（BillSummaryCard 首例：我的页账单卡 / 账单页总览）。 -->
  <view class="trio">
    <view class="cell due">
      <view class="num">¥{{ due }}</view>
      <view class="lab">我还欠的</view>
    </view>
    <view class="cell">
      <view class="num">¥{{ paid }}</view>
      <view class="lab">结清了的</view>
    </view>
    <view class="cell rec">
      <view class="num">¥{{ receivable }}</view>
      <view class="lab">垫付待收</view>
    </view>
  </view>
</template>

<script setup lang="ts">
defineProps({
  due: { type: Number, required: true },
  paid: { type: Number, required: true },
  receivable: { type: Number, required: true },
});
</script>

<style lang="scss" scoped>
.trio {
  display: flex;
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  padding: 16px;
  background: var(--ink2);
}
.cell {
  flex: 1;
  min-width: 0;
}
.num {
  font-family: var(--disp);
  font-size: 22px;
  line-height: 1.1;
}
.cell.due .num {
  color: var(--coral);
}
.cell.rec .num {
  color: var(--lemon);
}
.lab {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
  margin-top: 4px;
  letter-spacing: 0.06em;
}
</style>
