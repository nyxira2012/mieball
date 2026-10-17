<template>
  <!-- 改场号面板（2026-10-17 顶条长条直填退役的落点）：全权者点顶条「打球场地」
       格子弹出，逐框组件改场号（与订场登记/直接开场同一件同一清洗口径）。
       只改片名与片数——片数走 apiLiveRules courtsCount（缩片先撤空闲片），
       在打+待开的片收不掉（守卫在 store，失败 toast 后面板留着改）。 -->
  <AppSheet
    :visible="visible"
    title="改场地号"
    hint="一框一片，填几个号开几片；在打和待开的场地收不掉"
    @close="emit('close')"
  >
    <view class="cs-sec">
      <CourtInputs v-model="courts" />
      <view class="cs-hint">
        {{
          courts.length
            ? `识别到 ${courts.length} 片：${courts.join("、")}`
            : "至少要有一片场地"
        }}
      </view>
    </view>
    <view class="cs-acts">
      <AppButton variant="pri" block :disabled="saving" @click="onSave"
        >保存</AppButton
      >
    </view>
  </AppSheet>
</template>

<script setup lang="ts">
/* 顶条改场号面板：数据与动作全在 live store（RulesSheet 同款薄面板）；
   打开时按当前片名逐框带出，保存成功关面板（toast 在 store）。 */
import { ref, watch } from "vue";
import AppSheet from "@/components/ui/AppSheet.vue";
import AppButton from "@/components/ui/AppButton.vue";
import CourtInputs from "./CourtInputs.vue";
import { useLiveStore } from "@/stores/live";

const props = defineProps({ visible: { type: Boolean, default: false } });
const emit = defineEmits<{ (e: "close"): void }>();

const liveStore = useLiveStore();
const courts = ref<string[]>([]);
const saving = ref(false);

watch(
  () => props.visible,
  (v) => {
    if (v) courts.value = [...(liveStore.live?.g.courts ?? [])];
  },
);

async function onSave(): Promise<void> {
  if (saving.value) return;
  saving.value = true;
  try {
    const ok = await liveStore.setCourts(courts.value);
    if (ok) emit("close");
  } finally {
    saving.value = false;
  }
}
</script>

<style lang="scss" scoped>
.cs-sec {
  margin-top: 14px;
}
.cs-hint {
  margin-top: 6px;
  font-size: 11px;
  color: var(--dim);
}
.cs-acts {
  margin-top: 18px;
}
</style>
