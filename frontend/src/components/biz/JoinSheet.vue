<template>
  <!-- 加入球局弹层（alpha.html:1107-1122 joinSheet 逐字）：标题三态（满员 · 进候补 / 接受邀请 · 加入 / 加入）
       · hint 两态（满员候补文案 or 名单/剩坑/人均+不足最少按最少摊括注）· 带人 stepper（0-3，共占 N 坑联动）
       · 确认钮（加入候补/确定加入）。确定 → game.joinGame(gameId, bring)（store 内 toast）→ 关弹层；
       视图刷新靠 store 响应式（alpha:1136 renderHome/renderMeet/openDetail 的等价物）。 -->
  <view v-if="g" class="js">
    <!-- alpha:1112 h3：`${full?'满员 · 进候补':(g.invitedMe&&!myEntry(g)?'接受邀请 · 加入':'加入')}「局短名」` -->
    <view class="t">{{ full ? '满员 · 进候补' : g.invitedMe && !my ? '接受邀请 · 加入' : '加入' }}「{{ shortName }}」</view>
    <!-- alpha:1113-1115 hint：满员 → 候补栏文案（<b>候补栏</b> 用加粗 text 等价）；未满 → 名单/剩坑/人均（+不足最少括注） -->
    <view v-if="full" class="hint">
      {{ g.t }} · {{ g.loc }} · 名额满了——加入将进入<text class="bb">候补栏</text>，有人退出即刻递补
    </view>
    <view v-else class="hint">
      {{ g.t }} · {{ g.loc }} · {{ hs }}/{{ g.cap }} · 剩 {{ need }} 坑 · 人均约 ¥{{ ph }}{{ hs < g.min ? `（不足最少 ${g.min} 人按最少摊）` : '' }}
    </view>

    <!-- alpha:1116-1121 field「带几个人 · 带的人也占坑」+ stepper(0-3) + 共占坑数 hint -->
    <AppField label="带几个人 · 带的人也占坑">
      <view class="frow">
        <AppStepper v-model="jbring" :min="0" :max="3" />
        <view class="sub jbh">我 + 带的人共占 {{ 1 + jbring }} 个坑</view>
      </view>
    </AppField>

    <!-- alpha:1122 确认钮：btn pri blk，满员文案「加入候补」 -->
    <AppButton variant="pri" block @click="onConfirm">{{ full ? '加入候补' : '确定加入' }}</AppButton>
  </view>
</template>

<script setup lang="ts">
/* 加入球局 JoinSheet（alpha.html:1107-1138 joinSheet/jStep/doJoin · P5b）。
   jbring 每次开弹层重置为 0（alpha:1111）——SheetHost 按 type 分发，关闭即卸载本组件。 */
import { computed, ref } from 'vue';
import AppButton from '@/components/ui/AppButton.vue';
import AppField from '@/components/ui/AppField.vue';
import AppStepper from '@/components/ui/AppStepper.vue';
import { useGameStore } from '@/stores/game';
import { useUiStore } from '@/stores/ui';
import { heads, needOf, perHead, myEntry } from '@/utils/format';

const props = defineProps({
  gameId: { type: Number, required: true },
});

const game = useGameStore();
const ui = useUiStore();

/** alpha:1109 games.find；局被撤下等场景的兜底（v-if 不渲染） */
const g = computed(() => game.games.find((x) => x.id === props.gameId) ?? null);
/** alpha:1110 full = heads >= cap */
const full = computed(() => !!g.value && heads(g.value) >= g.value.cap);
/** alpha:1112 局短名（「 · 」起截断，正则逐字取自 alpha 的 replace 调用） */
const shortName = computed(() => (g.value ? g.value.name.replace(/ ·.*/, '') : ''));
/** alpha:1112 标题里「接受邀请 · 加入」分支的 !myEntry(g) */
const my = computed(() => (g.value ? myEntry(g.value) : undefined));
/** alpha:1115 hint 数据（未满态） */
const hs = computed(() => (g.value ? heads(g.value) : 0));
const need = computed(() => (g.value ? needOf(g.value) : 0));
const ph = computed(() => (g.value ? perHead(g.value) : 0));

/** alpha:1107/1111 let jbring=0（带的人数，0-3，alpha:1124 jStep 的 min/max） */
const jbring = ref(0);

/** alpha:1127-1137 doJoin：store.joinGame（含 toast）→ closeSheet（已加入也只关弹层） */
function onConfirm(): void {
  if (!g.value) return;
  game.joinGame(g.value.id, jbring.value);
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
