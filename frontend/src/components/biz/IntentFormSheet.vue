<template>
  <!-- 留/改意向表单 · alpha.html:1264-1297 intentForm/ifTog/ifSetFreq/saveIntent 逐字对齐（P7）：
       4 时段 slotgrid（名 / 时段 desc / 同波段 N 人 青字，多选 toggle）·
       频率 seg 三段（每周 1 打 / 每周 2 打 / 随缘~）·「留下意向/保存修改」钮；
       校验「至少选一个时段」（toast 逐字由 store 发），保存 → game.saveIntent + closeSheet。 -->
  <view>
    <!-- alpha:1269 标题两态 -->
    <view class="t">{{ game.myIntent ? '改我的意向' : '留我的意向' }}</view>
    <!-- alpha:1270 hint 逐字 -->
    <view class="hint">大概什么时段想打、多久打一次 —— 组局的人凑人时会看见你</view>

    <!-- alpha:1271-1274 slotgrid：4 时段卡（on = 电青描边 + 淡青底） -->
    <view class="slotgrid">
      <view
        v-for="s in slotDefs"
        :key="s.k"
        class="slot"
        :class="{ on: ifSlots.includes(s.k) }"
        @click="ifTog(s.k)"
      >
        <view class="snm">{{ s.n }}</view>
        <view class="cnt">{{ s.desc }}</view>
        <!-- alpha:1274 同波段 N 人（ice 青字） -->
        <view class="cnt ice">同波段 {{ s.match }} 人</view>
      </view>
    </view>

    <!-- alpha:1275-1277 频率字段：seg 三段，大字 = v（0 显 ~）+ small 频率名 -->
    <AppField label="频率" class="freq-field">
      <AppSeg v-model="ifFreq" :options="FREQ_OPTS" />
    </AppField>

    <!-- alpha:1278 保存/留下 -->
    <AppButton variant="pri" block class="save" @click="save">
      {{ game.myIntent ? '保存修改' : '留下意向' }}
    </AppButton>
  </view>
</template>

<script setup lang="ts">
/* 留/改意向表单（alpha.html:1264-1297 · P7）。
   SheetHost 按 sheet.type==='intent-form' 挂载本组件（v-if，挂载即「开表」）：
   state 初值即 alpha:1266-1268 intentForm() 打开口径 —— 已有意向全量带入，
   无意向默认选「周末晚上」(we-n) · 频率 2。保存走 game.saveIntent（文案由 store 逐字发），
   失败不关弹层（alpha:1287），成功 closeSheet（alpha:1290，页面意向区经 store 响应式刷新）。 */
import { ref } from 'vue';
import AppButton from '@/components/ui/AppButton.vue';
import AppField from '@/components/ui/AppField.vue';
import AppSeg from '@/components/ui/AppSeg.vue';
import { slots as slotDefs } from '@/api';
import { useGameStore } from '@/stores/game';
import { useUiStore } from '@/stores/ui';

const game = useGameStore();
const ui = useUiStore();

/* alpha:1267 ifSlots = myIntent ? [...myIntent.slots] : ['we-n'] */
const ifSlots = ref<string[]>(game.myIntent ? [...game.myIntent.slots] : ['we-n']);
/* alpha:1268 ifFreq = myIntent ? myIntent.freq : 2（string|number 对齐 AppSeg v-model 联合类型） */
const ifFreq = ref<string | number>(game.myIntent ? game.myIntent.freq : 2);

/* alpha:1276-1277 三段：按钮内容 `${v===0?'~':v}<small>${l}</small>` → AppSeg label+sub */
const FREQ_OPTS = [
  { value: 1, label: '1', sub: '每周 1 打' },
  { value: 2, label: '2', sub: '每周 2 打' },
  { value: 0, label: '~', sub: '随缘' },
];

/* alpha:1280-1282 ifTog：在/不在 ifSlots → 删/增 */
function ifTog(k: string): void {
  if (ifSlots.value.includes(k)) ifSlots.value = ifSlots.value.filter((x) => x !== k);
  else ifSlots.value = [...ifSlots.value, k];
}

/* alpha:1286-1292 saveIntent：至少一个时段（toast 逐字「至少选一个时段」由 store 发，弹层不关） */
function save(): void {
  if (!ifSlots.value.length) {
    game.saveIntent([], Number(ifFreq.value));
    return;
  }
  game.saveIntent([...ifSlots.value], Number(ifFreq.value)); // alpha:1289 写入（成功 toast 由 store 发）
  ui.closeSheet(); // alpha:1290
}
</script>

<style lang="scss" scoped>
/* alpha:558-561 壳层 h3/.hint 同款（SheetHost 未传壳层 title，表单自带，同 ProfileSheet 约定） */
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
/* alpha.html:362-367 slotgrid / slot */
.slotgrid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.slot {
  border: 1px solid rgba(245, 241, 232, 0.12);
  border-radius: 14px;
  padding: 12px;
  background: var(--ink2);
  transition: 0.2s;
  position: relative;
}
.slot.on {
  border-color: var(--ice);
  background: rgba(111, 231, 255, 0.09);
}
.slot .snm {
  font-size: 13px;
  font-weight: 700;
}
.slot .cnt {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  margin-top: 3px;
}
/* alpha:1274 同波段 N 人（内联 color:var(--ice)） */
.slot .cnt.ice {
  color: var(--ice);
}
/* alpha:1275 field 内联 margin-top:12px（.field 基础在 AppField） */
.freq-field {
  margin-top: 12px;
}
/* alpha:1278 保存钮内联 margin-top:4px */
.save {
  margin-top: 4px;
}
</style>
