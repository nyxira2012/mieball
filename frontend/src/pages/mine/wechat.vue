<template>
  <!-- 微信授权页（5.1 子页）：小程序端微信授权登录，使小程序 / H5 / App 端账号通用。
       mock 单次动作，toast 在 user store；无需已授权态。 -->
  <PageShell>
    <!-- 子页统一返回行（bills.vue 同形态） -->
    <view class="backrow" @click="goBack">◂ 返回</view>

    <view class="stag">
      <view class="kicker">WeChat</view>
      <view class="brand">授<text class="bem">权</text></view>
    </view>

    <NoteCard text="授权后微信账号与本工具账号打通 · 小程序 / H5 / App 三端登录同一份底账" />

    <AppButton variant="pri" block class="save" @click="user.wechatAuth()">微信授权登录</AppButton>
  </PageShell>
</template>

<script setup lang="ts">
import PageShell from '@/components/biz/PageShell.vue';
import AppButton from '@/components/ui/AppButton.vue';
import NoteCard from '@/components/ui/NoteCard.vue';
import { useUserStore } from '@/stores/user';

const user = useUserStore();

function goBack(): void {
  uni.navigateBack();
}
</script>

<style lang="scss" scoped>
/* ---------- 子页统一返回行（mono 11px dim · :active lemon） ---------- */
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

/* ---------- 头部 brand（bills.vue 同款） ---------- */
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

/* 保存钮上间距 */
.save {
  margin-top: 6px;
}
</style>
