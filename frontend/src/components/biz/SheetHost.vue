<template>
  <!-- 全局单例弹层宿主：订阅 ui store 的 sheet（api/types.ts 的 SheetPayload 11 种联合类型），
       按 type 判别分发到 biz 弹层组件（11 种全部已实装：P5b join/confirm/invite、P6 launch、
       P7 intent-form、P9 profile、5.1 logout-confirm/delete-confirm）。
       遮罩点击关闭走 AppSheet 的 close 事件 → ui.closeSheet()（alpha:838 closeSheet）；
       页面隐藏时由 PageShell 的 onHide 统一关弹层（alpha:869 go() 进页前 closeSheet 的等价）。
       直接组合 ui/AppSheet（抽屉壳）。（P1 时代的 ui/SheetHost 通用注册表版本已随试衣间页退役删除）
       2.1 打球页的终局结算弹窗是 live 页本地弹层、不走本宿主（WinPopup 已退役）。 -->
  <AppSheet :visible="ui.sheet != null" @close="ui.closeSheet()">
    <ProfileSheet v-if="s?.type === 'profile'" :user-id="s.userId" />
    <JoinSheet v-else-if="s?.type === 'join'" :game-id="s.gameId" />
    <ConfirmSheet v-else-if="s?.type === 'quit-confirm'" kind="quit" :game-id="s.gameId" />
    <ConfirmSheet v-else-if="s?.type === 'cancel-confirm'" kind="cancel" :game-id="s.gameId" />
    <BookingSheet v-else-if="s?.type === 'booking'" :game-id="s.gameId" />
    <InviteSheet v-else-if="s?.type === 'invite-to-game'" mode="to-game" :game-id="s.gameId" />
    <InviteSheet v-else-if="s?.type === 'invite-to-slot'" mode="to-slot" :user-id="s.userId" />
    <IntentFormSheet v-else-if="s?.type === 'intent-form'" />
    <LaunchSheet v-else-if="s?.type === 'launch'" :game-id="s.gameId" />
    <AccountSheet v-else-if="s?.type === 'logout-confirm'" kind="logout" />
    <AccountSheet v-else-if="s?.type === 'delete-confirm'" kind="delete" />
    <SignupSheet v-else-if="s?.type === 'signup-card'" :pending-join="s.pendingJoin" :pending-launch="s.pendingLaunch" :pending-checkin="s.pendingCheckin" />
  </AppSheet>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useUiStore } from '@/stores/ui';
import AppSheet from '@/components/ui/AppSheet.vue';
import ProfileSheet from './ProfileSheet.vue';
import JoinSheet from './JoinSheet.vue';
import ConfirmSheet from './ConfirmSheet.vue';
import BookingSheet from './BookingSheet.vue';
import InviteSheet from './InviteSheet.vue';
import IntentFormSheet from './IntentFormSheet.vue';
import LaunchSheet from './LaunchSheet.vue';
import AccountSheet from './AccountSheet.vue';
import SignupSheet from './SignupSheet.vue';

const ui = useUiStore();
/** 模板里对联合类型逐支收窄用 */
const s = computed(() => ui.sheet);
</script>
