<template>
  <!-- 确认类弹层（三用一壳）：quit 退局（alpha:1141-1146）/ cancel 取消局（alpha:1158-1162）/
       add-court 加场（alpha:1192-1196）。确认钮分别调 game.quitGame / cancelGame / addCourt
       （store 内含 toast）→ 关弹层；视图刷新靠 store 响应式（alpha:1152/1168/1205 的 render+go 等价物）。 -->
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

    <!-- ===== cancel：alpha:1158-1162 ===== -->
    <template v-else-if="kind === 'cancel'">
      <view class="t">取消这个局？</view>
      <view class="hint">已报名的 {{ hs }} 人都会收到取消通知 · 名额、订场一并作废</view>
      <view class="btns">
        <!-- alpha:1161 不取消了 → closeSheet -->
        <AppButton variant="ghost" class="flex1" @click="ui.closeSheet()">不取消了</AppButton>
        <!-- alpha:1162 确定取消 → doCancel -->
        <AppButton variant="burn" class="flex1" @click="onCancel">确定取消</AppButton>
      </view>
    </template>

    <!-- ===== add-court：alpha:1192-1196 ===== -->
    <template v-else>
      <view class="t">加一片场地</view>
      <view class="hint">人数上限 {{ g.cap }} → {{ g.cap + 2 }} · 候补按先后自动转正 · 总价记得在「改信息」里跟着改</view>
      <!-- alpha:1194-1195 当前候补名单 / 无候补文案 -->
      <view class="sub waitline">
        {{ g.wait.length ? `当前候补 ${g.wait.length} 人：${g.wait.map((e) => e.u.name).join('、')}` : '当前没有候补 · 加场先备着坑位' }}
      </view>
      <!-- alpha:1196 加场单钮 → doAddCourt -->
      <AppButton variant="pri" block @click="onAddCourt">加场 · 上限提到 {{ g.cap + 2 }}</AppButton>
    </template>
  </view>
</template>

<script setup lang="ts">
/* 确认弹层 ConfirmSheet（alpha.html:1148-1153 doQuit / 1164-1168 doCancel / 1198-1206 doAddCourt · P5b）。
   动作全在 game store（toast 文案逐字在 store 内）；本组件只出文案与触发。 */
import { computed } from 'vue';
import type { PropType } from 'vue';
import AppButton from '@/components/ui/AppButton.vue';
import { useGameStore } from '@/stores/game';
import { useUiStore } from '@/stores/ui';
import { heads } from '@/utils/format';

const props = defineProps({
  kind: { type: String as PropType<'quit' | 'cancel' | 'add-court'>, required: true },
  gameId: { type: Number, required: true },
});

const game = useGameStore();
const ui = useUiStore();

/** alpha:1141/1157/1191 games.find；取消局后 g 变 null，v-if 兜底不渲染 */
const g = computed(() => game.games.find((x) => x.id === props.gameId) ?? null);
/** alpha:1159 已报名人数（heads 口径，带的人也算） */
const hs = computed(() => (g.value ? heads(g.value) : 0));

/** alpha:1148-1152 doQuit */
function onQuit(): void {
  if (!g.value) return;
  game.quitGame(g.value.id);
  ui.closeSheet();
}
/** alpha:1164-1168 doCancel */
function onCancel(): void {
  if (!g.value) return;
  game.cancelGame(g.value.id);
  ui.closeSheet();
}
/** alpha:1198-1205 doAddCourt */
function onAddCourt(): void {
  if (!g.value) return;
  game.addCourt(g.value.id);
  ui.closeSheet();
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
/* alpha:1194-1195 候补行 .sub margin-bottom:10px */
.waitline {
  margin-bottom: 10px;
}
</style>
