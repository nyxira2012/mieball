<template>
  <!-- 直接开场抽屉（2026-10-17 用户裁决②：开场前填基本信息防误点）：
       只问三件事——在哪、哪几片、打多久；其余（可见档/必开/人数/截止）全后端默认。
       场地号收拢（走查裁决）：片数唯一真值=场地号个数（订场同源），有两个号自然开两片。
       游客确认走先看后报（pendingDirect 建号后续办开场+跳现场）；成功
       recordVenue 记忆场馆 → goLive 进现场（ensureLive 拉开账视图）。 -->
  <AppSheet
    :visible="visible"
    title="直接开场"
    hint="不用组局——场馆、场地号和时长定了就开"
    @close="emit('close')"
  >
    <view class="do-sec">
      <AppField label="地点 · 球馆名">
        <VenuePicker v-model="venue" />
      </AppField>
    </view>

    <view class="do-sec">
      <AppField label="场地号 · 填几个号开几片">
        <AppInput v-model="courtRaw" placeholder="如 3号、5号 · 不填先开一片" />
      </AppField>
    </view>

    <view class="do-sec">
      <AppField label="打多久">
        <OptionChips v-model="hours" :options="HOUR_OPTS" />
        <view class="do-hint">从点「开场」那刻起算，顶条倒计时按它走</view>
      </AppField>
    </view>

    <view class="do-note"
      >开场后亮二维码就能收人；一场对局没打就散场的话，这局不留任何记录</view
    >

    <view class="do-acts">
      <AppButton
        variant="pri"
        block
        :disabled="!venue.trim() || opening"
        @click="onOpen"
        >开场 ▸</AppButton
      >
    </view>
  </AppSheet>
</template>

<script setup lang="ts">
/* 直接开场表单（2026-10-17）：场馆/场地号/时长三问——组局表单的「快进版」，不复用
   LaunchSheet（截止/可见档/人数对直接开场无意义），复用 VenuePicker 零键选馆与
   AppInput（场地号，订场登记同款自由文本）。 */
import { ref } from "vue";
import AppSheet from "@/components/ui/AppSheet.vue";
import AppField from "@/components/ui/AppField.vue";
import AppButton from "@/components/ui/AppButton.vue";
import AppInput from "@/components/ui/AppInput.vue";
import OptionChips from "@/components/ui/OptionChips.vue";
import VenuePicker from "@/components/biz/VenuePicker.vue";
import { errText } from "@/api/http";
import type { DirectOpenInput } from "@/api/types";
import { autoGameName } from "@/utils/format";
import { recordVenue } from "@/utils/venues";
import { goLive } from "@/utils/nav";
import { useGameStore } from "@/stores/game";
import { useSessionStore } from "@/stores/session";
import { useUiStore } from "@/stores/ui";
import { useUserStore } from "@/stores/user";

defineProps({ visible: { type: Boolean, default: false } });
const emit = defineEmits<{ (e: "close"): void }>();

const HOUR_OPTS = [1, 2, 3, 4].map((n) => ({ value: n, label: `${n} 小时` }));

const venue = ref("");
const courtRaw = ref("");
const hours = ref(2);
const opening = ref(false);
const game = useGameStore();
const session = useSessionStore();
const ui = useUiStore();

/** 场地号解析：逗号/顿号/空白分隔，去空去重保序（后端同款清洗，双闸不依赖单侧） */
function parseCourts(raw: string): string[] {
  const out: string[] = [];
  for (const c of raw.split(/[，,、\s]+/)) {
    const n = c.trim();
    if (n && !out.includes(n)) out.push(n);
  }
  return out;
}

async function onOpen(): Promise<void> {
  if (opening.value) return;
  const input: DirectOpenInput = {
    name: autoGameName(useUserStore().me.name, venue.value.trim()),
    venue_name: venue.value.trim(),
    venue_address: null,
    hours: Number(hours.value),
    courts: parseCourts(courtRaw.value),
  };
  if (session.isGuest) {
    // 游客先看后报：昵称此刻没落地，名字留空由续办补定（pendingLaunch 同款）
    input.name = "";
    ui.signupThen({ pendingDirect: input });
    emit("close");
    return;
  }
  opening.value = true;
  try {
    const g = await game.directOpen(input);
    recordVenue(input.venue_name);
    emit("close");
    goLive(g.id);
  } catch (e) {
    ui.toast(errText(e));
  } finally {
    opening.value = false;
  }
}
</script>

<style lang="scss" scoped>
.do-sec {
  margin-top: 14px;
}
.do-hint {
  margin-top: 6px;
  font-size: 11px;
  color: var(--dim);
}
.do-note {
  margin-top: 14px;
  padding: 10px 12px;
  border: 1px solid rgba(245, 241, 232, 0.1);
  border-radius: var(--r-sm);
  background: var(--ink2);
  font-size: 12px;
  line-height: 1.6;
  color: var(--dim);
}
.do-acts {
  margin-top: 18px;
}
</style>
