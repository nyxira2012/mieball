<template>
  <!-- 确认类弹层（两用一壳）：quit 退局（alpha:1141-1146）/ cancel 取消局（alpha:1158-1162）。
       确认钮 await game.quitGame / cancelGame（toast 在 store）→ 成功关弹层回约球页；
       失败 toast 人话留在弹层可重试（game_locked 等后端文案直出）。
       3.2 订场改版：cancel 分支带订场退订提醒。 -->
  <view v-if="g" class="cs">
    <!-- ===== quit：alpha:1142-1146 ===== -->
    <template v-if="kind === 'quit'">
      <view class="sheet-t">退出这局？</view>
      <view class="sheet-hint">{{ tLine }} · {{ g.venueName }} · 退出后名额立刻释放，你带的人也一起退</view>
      <view class="btns">
        <AppButton variant="ghost" class="flex1" @click="ui.closeSheet()">再想想</AppButton>
        <AppButton variant="burn" class="flex1" :disabled="busy" @click="onQuit">{{ busy ? '退出中…' : '确定退出' }}</AppButton>
      </view>
    </template>

    <!-- ===== cancel：alpha:1158-1162 + 订场退订提醒 ===== -->
    <template v-else>
      <view class="sheet-t">取消这个局？</view>
      <view class="sheet-hint">已报名的 {{ g.heads }} 人（含带的人）都会看到局被撤下 · 名额、订场一并作废</view>
      <!-- 已订场：钱已花在 app 外，撤局前提醒去场馆退订 -->
      <view v-if="g.courts?.length" class="sub warnline">
        这局已登记订场（{{ g.courts.join('、') }}）· 撤局后记得去场馆退订
      </view>
      <view class="btns">
        <AppButton variant="ghost" class="flex1" @click="ui.closeSheet()">不取消了</AppButton>
        <AppButton variant="burn" class="flex1" :disabled="busy" @click="onCancel">{{ busy ? '取消中…' : '确定取消' }}</AppButton>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
/* 确认弹层 ConfirmSheet（alpha.html:1148-1153 doQuit / 1164-1168 doCancel · P5b）。
   动作全在 game store（toast 文案逐字在 store 内）；本组件只出文案与触发；
   P11 导航语义对齐：成功后按 alpha:1152/1168 的 go('meet') 切到约球页（store 不做导航）。 */
import { computed, ref } from 'vue';
import type { PropType } from 'vue';
import AppButton from '@/components/ui/AppButton.vue';
import { useGameStore } from '@/stores/game';
import { useUiStore } from '@/stores/ui';
import { isoDay, isoHm } from '@/utils/time';
import { errText } from '@/api/http';
import { goMeet } from '@/utils/nav';

const props = defineProps({
  kind: { type: String as PropType<'quit' | 'cancel'>, required: true },
  gameId: { type: Number, required: true },
});

const game = useGameStore();
const ui = useUiStore();
const busy = ref(false);

/** alpha:1141/1157 findGame；取消局后 g 变 null，v-if 兜底不渲染 */
const g = computed(() => game.findGame(props.gameId));
const tLine = computed(() => (g.value ? `${isoDay(g.value.startAt)} ${isoHm(g.value.startAt)}` : ''));

/** alpha:1148-1152 doQuit：game_locked（截止锁退出）等失败留在弹层，toast 后端人话 */
async function onQuit(): Promise<void> {
  if (!g.value || busy.value) return;
  busy.value = true;
  try {
    await game.quitGame(g.value.id);
    ui.closeSheet();
    goMeet(); // alpha:1152 go('meet')
  } catch (e) {
    ui.toast(errText(e));
  } finally {
    busy.value = false;
  }
}
/** alpha:1164-1168 doCancel */
async function onCancel(): Promise<void> {
  if (!g.value || busy.value) return;
  busy.value = true;
  try {
    await game.cancelGame(g.value.id);
    ui.closeSheet();
    goMeet(); // alpha:1168 go('meet')
  } catch (e) {
    ui.toast(errText(e));
  } finally {
    busy.value = false;
  }
}
</script>

<style lang="scss" scoped>
/* 壳层标题/hint 走全局 .sheet-t/.sheet-hint（base.scss 收源） */
/* alpha:1144/1160 双钮排 display:flex;gap:10px（两钮各 flex:1） */
.btns {
  display: flex;
  gap: 10px;
}
.flex1 {
  flex: 1;
}
/* 撤局时的订场退订提醒行（coral 小字，接在 hint 下） */
.warnline {
  color: var(--coral);
  font-size: 12px;
  margin-bottom: 10px;
}
</style>
