<template>
  <!-- 全局单例弹层宿主：订阅 ui store 的 sheet（api/types.ts 的 SheetPayload 11 种联合类型），
       按 type 判别分发到 biz 弹层组件（11 种全部已实装：P5b join/confirm/invite、P6 launch、
       P7 intent-form、P9 profile、5.1 logout-confirm/delete-confirm）。
       遮罩点击关闭走 AppSheet 的 close 事件 → ui.closeSheet()（alpha:838 closeSheet）；
       页面隐藏时由 PageShell 的 onHide 统一关弹层（alpha:869 go() 进页前 closeSheet 的等价）。
       直接组合 ui/AppSheet（抽屉壳）；ui/SheetHost 为 P1 的通用注册表版本，试衣间页在用。
       WinPopup 不在这里——层级最高、独立组件，由 PageShell 挂载（alpha:565 #winpop z-110）。 -->
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

const ui = useUiStore();
/** 模板里对联合类型逐支收窄用 */
const s = computed(() => ui.sheet);
</script>
