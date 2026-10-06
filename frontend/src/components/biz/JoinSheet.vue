<template>
  <!-- 加入球局弹层（alpha.html:1107-1122）：标题三态（满员 · 进候补 / 接受邀请 · 加入 / 加入）
       · hint（名单/剩坑/人均）· 带人 stepper（0-3，共占 N 坑联动）· 确认钮（加入候补/确定加入）。
       确定 → game.joinGame（store 内 toast：正式/候补分支）→ 关弹层；失败 toast 人话留在弹层可重试。
       1.1 先看后报：游客先弹名片建号卡，建号成功自动接着报名（D3）。 -->
  <view v-if="g" class="js">
    <view class="sheet-t">{{ full ? '满员 · 进候补' : g.my?.invited && !g.my?.myEntry ? '接受邀请 · 加入' : '加入' }}「{{ shortName }}」</view>
    <view class="sheet-hint">
      {{ tLine }} · {{ g.venueName }} · {{ g.heads }}/{{ g.maxPlayers }} ·
      {{ full ? `名额满了——加入将进入` : `剩 ${g.slotsLeft} 坑 ·` }}
      <text v-if="full" class="bb">候补栏</text><text v-if="full">，有人退出即刻递补</text>
      <text v-else> {{ feeTxt }}</text>
    </view>

    <!-- alpha:1116-1121 field「带几个人 · 带的人也占坑」+ stepper(0-3) + 共占坑数 hint -->
    <AppField label="带几个人 · 带的人也占坑">
      <view class="frow">
        <AppStepper v-model="jbring" :min="0" :max="3" />
        <view class="sub jbh">我 + 带的人共占 {{ 1 + jbring }} 个坑</view>
      </view>
    </AppField>

    <!-- alpha:1122 确认钮：btn pri blk，满员文案「加入候补」 -->
    <AppButton variant="pri" block :disabled="busy" @click="onConfirm">{{ busy ? '加入中…' : full ? '加入候补' : '确定加入' }}</AppButton>
  </view>
</template>

<script setup lang="ts">
/* 加入球局 JoinSheet（alpha.html:1107-1138 · P5b · 1.2 接线修订面）。
   jbring 每次开弹层重置为 0（alpha:1111）——SheetHost 按 type 分发，关闭即卸载本组件。 */
import { computed, ref } from 'vue';
import AppButton from '@/components/ui/AppButton.vue';
import AppField from '@/components/ui/AppField.vue';
import AppStepper from '@/components/ui/AppStepper.vue';
import { useGameStore } from '@/stores/game';
import { useSessionStore } from '@/stores/session';
import { useUiStore } from '@/stores/ui';
import { isoDay, isoHm } from '@/utils/time';
import { errText } from '@/api/http';

const props = defineProps({
  gameId: { type: Number, required: true },
});

const game = useGameStore();
const session = useSessionStore();
const ui = useUiStore();

/** 局被撤下等场景的兜底（v-if 不渲染）；链接直达的局走 store.current */
const g = computed(() => game.findGame(props.gameId));
/** alpha:1110 full = 剩坑 0（后端定值） */
const full = computed(() => !!g.value && g.value.slotsLeft <= 0);
const busy = ref(false);
/** alpha:1112 局短名（「 · 」起截断） */
const shortName = computed(() => (g.value ? g.value.name.replace(/ ·.*/, '') : ''));
const tLine = computed(() => (g.value ? `${isoDay(g.value.startAt)} ${isoHm(g.value.startAt)}` : ''));
/** 费用尾注：后端定值人均；未定 → 费用未定 */
const feeTxt = computed(() => (g.value?.perHead != null ? `人均约 ¥${g.value.perHead}` : '费用未定'));

/** alpha:1107/1111 let jbring=0（带的人数，0-3） */
const jbring = ref(0);

/** alpha:1127-1137 doJoin：成功关弹层（toast 在 store）；失败 toast 留在弹层可重试 */
async function onConfirm(): Promise<void> {
  if (!g.value || busy.value) return;
  if (session.isGuest) {
    ui.signupThen({ pendingJoin: { gameId: g.value.id, bring: jbring.value } });
    return;
  }
  busy.value = true;
  try {
    await game.joinGame(g.value.id, jbring.value);
    ui.closeSheet();
  } catch (e) {
    ui.toast(errText(e));
  } finally {
    busy.value = false;
  }
}
</script>

<style lang="scss" scoped>
/* 壳层标题/hint 走全局 .sheet-t/.sheet-hint（base.scss 收源） */
/* alpha:1114 <b>候补栏</b> */
.bb {
  font-weight: 700;
  color: var(--cream);
}
/* alpha:1117 display:flex;gap:12px;align-items:center */
.frow {
  display: flex;
  gap: 12px;
  align-items: center;
}
/* alpha:1120 #jb-hint .sub flex:1;font-size:11px */
.jbh {
  flex: 1;
  font-size: 11px;
}
</style>
