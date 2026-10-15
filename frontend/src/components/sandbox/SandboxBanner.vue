<template>
  <!-- 教学沙盒常驻横幅（2.7 §4.1 两档）：访客带「登录 ▸」转化出口（§4.6 三处之一
       ——点开名片建号卡，pending 空对象＝建号成功回现场页接着玩）；已登录讲空态事实。
       教学态顶部挂一条（规格：横幅常驻），两档文案单一源在 sandbox/data -->
  <view class="sb-banner">
    <text class="msg">{{
      session.isGuest ? BANNER_GUEST : BANNER_LOGGED_IN
    }}</text>
    <text v-if="session.isGuest" class="go" @click="ui.signupThen({})">{{
      BANNER_GUEST_ACTION
    }}</text>
  </view>
</template>

<script setup lang="ts">
import { useSessionStore } from "@/stores/session";
import { useUiStore } from "@/stores/ui";
import {
  BANNER_GUEST,
  BANNER_GUEST_ACTION,
  BANNER_LOGGED_IN,
} from "@/sandbox/data";

const session = useSessionStore();
const ui = useUiStore();
</script>

<style lang="scss" scoped>
/* 细横幅：一行浅字+右侧出口，占位克制（规格「常驻细横幅」） */
.sb-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border: 1px solid rgba(245, 241, 232, 0.14);
  border-radius: var(--r-md);
  padding: 9px 12px;
  font-size: 12px;
  color: var(--dim);
}
.sb-banner .go {
  flex: none;
  color: var(--lemon);
  font-weight: 600;
}
</style>
