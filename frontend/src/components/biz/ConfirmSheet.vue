<template>
  <!-- 确认类弹层（两用一壳）：quit 退局（alpha:1141-1146）/ cancel 取消局（alpha:1158-1162）。
       确认钮分别调 game.quitGame / cancelGame（store 内含 toast）→ 关弹层；视图刷新靠 store 响应式
       （alpha:1152/1168 的 render+go 等价物）。
       P11 导航语义对齐：quit/cancel 确认成功后按 alpha:1152/1168 的 go('meet') 切到约球页
       （store 硬约束不做导航，由本组件层承担）。
       3.2 订场改版：add-court 分支取消（加场并入改局的候补转正），cancel 分支补订场退订提醒。 -->
  <view v-if="g" class="cs">
    <!-- ===== quit：alpha:1142-1146 ===== -->
    <template v-if="kind === 'quit'">
      <view class="t">退出这局？</view>
      <view class="hint">{{ g.t }} · {{ g.loc }} · 退出后名额立刻释放，你带的人也一起退</view>
      <view class="btns">
        <!-- alpha:1145 再想想 → closeSheet -->
        <AppButton variant="ghost" class="flex1" @click="ui.closeSheet()">再想想</AppButton>
        <!-- alpha:1146 确定退出 → doQuit -->
        <AppButton variant="burn" class="flex1" @click="onQuit">确定退出</AppButton>
      </view>
    </template>

    <!-- ===== cancel：alpha:1158-1162 + 订场退订提醒 ===== -->
    <template v-else>
      <view class="t">取消这个局？</view>
      <view class="hint">已报名的 {{ hs }} 人都会收到取消通知 · 名额、订场一并作废</view>
      <!-- 已订场：钱已花在 app 外，撤局前提醒去场馆退订 -->
      <view v-if="g.booked?.length" class="sub warnline">
        这局已登记订场（{{ g.booked.join('、') }}）· 撤局后记得去场馆退订
      </view>
      <view class="btns">
        <!-- alpha:1161 不取消了 → closeSheet -->
        <AppButton variant="ghost" class="flex1" @click="ui.closeSheet()">不取消了</AppButton>
        <!-- alpha:1162 确定取消 → doCancel -->
        <AppButton variant="burn" class="flex1" @click="onCancel">确定取消</AppButton>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
/* 确认弹层 ConfirmSheet（alpha.html:1148-1153 doQuit / 1164-1168 doCancel · P5b）。
   动作全在 game store（toast 文案逐字在 store 内）；本组件只出文案与触发。 */
import { computed } from 'vue';
import type { PropType } from 'vue';
import AppButton from '@/components/ui/AppButton.vue';
import { useGameStore } from '@/stores/game';
import { useUiStore } from '@/stores/ui';
import { heads } from '@/utils/format';

const props = defineProps({
  kind: { type: String as PropType<'quit' | 'cancel'>, required: true },
  gameId: { type: Number, required: true },
});

const game = useGameStore();
const ui = useUiStore();

/** alpha:1141/1157/1191 games.find；取消局后 g 变 null，v-if 兜底不渲染 */
const g = computed(() => game.games.find((x) => x.id === props.gameId) ?? null);
/** alpha:1159 已报名人数（heads 口径，带的人也算） */
const hs = computed(() => (g.value ? heads(g.value) : 0));

/** P11（alpha:1152/1168 doQuit/doCancel 末尾的 go('meet')）：确认成功后切到约球页。
    已在约球页时跳过（uni.switchTab 到当前 tab 会重触发 onShow/重排，
    alpha 同页 go() 只是原地重渲染，语义等价「不动」）。 */
function goMeet(): void {
  const pages = getCurrentPages();
  const cur = pages[pages.length - 1];
  if (!cur || cur.route !== 'pages/meet/meet') uni.switchTab({ url: '/pages/meet/meet' });
}

/** alpha:1148-1152 doQuit */
function onQuit(): void {
  if (!g.value) return;
  game.quitGame(g.value.id);
  ui.closeSheet();
  goMeet(); // alpha:1152 go('meet')
}
/** alpha:1164-1168 doCancel */
function onCancel(): void {
  if (!g.value) return;
  game.cancelGame(g.value.id);
  ui.closeSheet();
  goMeet(); // alpha:1168 go('meet')
}
</script>

<style lang="scss" scoped>
/* alpha:558-561 壳层 h3/.hint 同款（SheetHost 不传壳层 title，各弹层自带，同 ProfileSheet） */
.t {
  font-family: var(--disp);
  font-size: 21px;
  margin-bottom: 4px;
}
.hint {
  font-size: 12px;
  color: var(--dim);
  margin-bottom: 16px;
}
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
