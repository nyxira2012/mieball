<template>
  <!-- 子页统一返回行（mine 系子页 bills/logs/signup/login/dress 共用；原为各页同值三件套） -->
  <view class="backrow" @click="goBack">◂ 返回</view>
</template>

<script setup lang="ts">
function goBack(): void {
  uni.navigateBack();
}
</script>

<style lang="scss" scoped>
/* mono 11px dim · :active lemon */
.backrow {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--dim);
  padding: 8px 2px;
  cursor: pointer;
  display: inline-block;
}
.backrow:active {
  color: var(--lemon);
}
</style>
