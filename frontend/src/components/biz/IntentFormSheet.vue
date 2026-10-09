<template>
  <!-- 留/改意向表单 · alpha.html:1264-1297 intentForm/ifTog/ifSetFreq/saveIntent 逐字对齐（P7）：
       4 时段 slotgrid（名 / 时段 desc / 同波段 N 人 青字，多选 toggle）·
       频率 seg 三段（每周 1 打 / 每周 2 打 / 随缘~）·「留下意向/保存修改」钮；
       校验「至少选一个时段」（toast 逐字由 store 发），保存 → game.saveIntent + closeSheet。 -->
  <view>
    <!-- alpha:1269 标题两态 -->
    <view class="sheet-t">{{
      game.myIntent ? "改我的意向" : "留我的意向"
    }}</view>
    <!-- alpha:1270 hint 逐字 -->
    <view class="sheet-hint"
      >大概什么时段想打、多久打一次 —— 组局的人凑人时会看见你</view
    >

    <!-- alpha:1271-1274 slotgrid：4 时段卡（on = 电青描边 + 淡青底）；同波段 match 数随 mock 退役（裁决②） -->
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
      </view>
    </view>

    <!-- alpha:1275-1277 频率字段：seg 三段，大字 = v（0 显 ~）+ small 频率名 -->
    <AppField label="频率" class="freq-field">
      <AppSeg v-model="ifFreq" :options="FREQ_OPTS" />
    </AppField>

    <!-- 4.13 备注：一句话可空，随保存透传（被邀人改意向即清已邀标记由后端管） -->
    <AppField label="备注 · 一句话，可不填" class="note-field">
      <AppInput
        v-model="ifNote"
        :maxlength="30"
        placeholder="如：只想约晚场 · 免费场优先"
      />
    </AppField>

    <!-- alpha:1278 保存/留下 -->
    <AppButton variant="pri" block class="save" @click="save">
      {{ game.myIntent ? "保存修改" : "留下意向" }}
    </AppButton>
  </view>
</template>

<script setup lang="ts">
/* 留/改意向表单（alpha.html:1264-1297 · P7；1.2 调用点适配：frequency 改名 + 4.13 备注编辑透传）。
   SheetHost 按 sheet.type==='intent-form' 挂载本组件（v-if，挂载即「开表」）：
   已有意向全量带入（含备注），无意向默认选「周末晚上」(we-n) · 频率 2。保存走 game.saveIntent
   （文案由 store 逐字发），失败不关弹层，成功 closeSheet。 */
import { ref } from "vue";
import AppButton from "@/components/ui/AppButton.vue";
import AppField from "@/components/ui/AppField.vue";
import AppInput from "@/components/ui/AppInput.vue";
import AppSeg from "@/components/ui/AppSeg.vue";
import { slots as slotDefs } from "@/api/dict";
import { useGameStore } from "@/stores/game";
import { useSessionStore } from "@/stores/session";
import { useUiStore } from "@/stores/ui";
import { errText } from "@/api/http";

const game = useGameStore();
const session = useSessionStore();
const ui = useUiStore();
const busy = ref(false);

/* alpha:1267 ifSlots = myIntent ? [...myIntent.slots] : ['we-n'] */
const ifSlots = ref<string[]>(
  game.myIntent ? [...game.myIntent.slots] : ["we-n"],
);
/* alpha:1268 ifFreq = myIntent ? myIntent.frequency : 2（string|number 对齐 AppSeg v-model 联合类型） */
const ifFreq = ref<string | number>(
  game.myIntent ? game.myIntent.frequency : 2,
);
/* 4.13 备注：一句话可空，编辑后随保存透传 */
const ifNote = ref(game.myIntent?.note ?? "");

/* alpha:1276-1277 三段：按钮内容 `${v===0?'~':v}<small>${l}</small>` → AppSeg label+sub */
const FREQ_OPTS = [
  { value: 1, label: "1", sub: "每周 1 打" },
  { value: 2, label: "2", sub: "每周 2 打" },
  { value: 0, label: "~", sub: "随缘" },
];

/* alpha:1280-1282 ifTog：在/不在 ifSlots → 删/增 */
function ifTog(k: string): void {
  if (ifSlots.value.includes(k))
    ifSlots.value = ifSlots.value.filter((x) => x !== k);
  else ifSlots.value = [...ifSlots.value, k];
}

/* alpha:1286-1292 saveIntent：至少一个时段（本地先拦，省一跳）；note 随保存透传（trim 去手滑空格）。
   游客先看后报（D3）：选完时段点保存 → 名片建号卡，建号成功自动落意向（pendingIntent 全量带走） */
async function save(): Promise<void> {
  if (!ifSlots.value.length) {
    ui.toast("至少选一个时段");
    return;
  }
  if (session.isGuest) {
    ui.signupThen({
      pendingIntent: {
        slots: [...ifSlots.value],
        frequency: Number(ifFreq.value),
        note: ifNote.value.trim(),
      },
    });
    return;
  }
  if (busy.value) return;
  busy.value = true;
  try {
    await game.saveIntent(
      [...ifSlots.value],
      Number(ifFreq.value),
      ifNote.value.trim(),
    );
    ui.closeSheet(); // alpha:1290
  } catch (e) {
    ui.toast(errText(e)); // intent_slots_empty 等后端文案直出
  } finally {
    busy.value = false;
  }
}
</script>

<style lang="scss" scoped>
/* 壳层标题/hint 走全局 .sheet-t/.sheet-hint（base.scss 收源） */
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
/* alpha:1275 field 内联 margin-top:12px（.field 基础在 AppField） */
.freq-field {
  margin-top: 12px;
}
/* alpha:1278 保存钮内联 margin-top:4px */
.save {
  margin-top: 4px;
}
/* 4.13 备注字段（同 freq-field 的内联间距） */
.note-field {
  margin-top: 12px;
}
</style>
