<template>
  <!-- 订场登记 / 锁定必打（3.2 订场改版）：三态锁共用的面板——
       没锁 →「锁定必打（不订场）」上手动空锁（今天的行为）；
       填了场地号+总价 → 保存即订场锁（必开 + 费用落定 + 场地号告诉大家），不用再点一次锁定；
       已订场 → 面板可重开改登记（退一片删一个号、总价改成退完后实际花的钱）或清空。
       组装全用公共件（AppField/AppInput/AppButton）；动作走 game store（bookCourt/clearBooking/sureGame，toast 在 store 内）。 -->
  <view v-if="g" class="bks">
    <view class="t">锁定必打 · 订场登记</view>
    <view class="hint">订了场这局就必开 · 场地号和总价随时可改，退一片就删一个号、照小票改总价</view>

    <!-- 现状行：订几片、花多少的参考（截止后本面板仍可改——临到场场馆换号很常见，名单锁定只锁人） -->
    <view class="sub stat">
      已报 {{ hs }} 人（含带的人）· 最少 {{ g.min }} · 上限 {{ g.cap }}{{ forced ? ' · 已锁定必打' : '' }}
    </view>

    <AppField label="场地号 · 几片填几个号（顿号/逗号/空格隔开）">
      <AppInput v-model="courtsText" placeholder="如：3号、5号" />
      <view class="sub fh">{{ parseHint }}</view>
    </AppField>

    <AppField label="总价 · 免费场填 0（按订场小票，人均按当前人数摊）">
      <AppInput v-model="feeText" type="number" placeholder="如：480" />
      <view class="sub fh">{{ feeHint }}</view>
    </AppField>

    <view class="btns">
      <!-- 有登记才有清空（全退光：局回未订场原样，手动锁不跟着松） -->
      <AppButton v-if="hasBooking" variant="ghost" class="flex1 clear-btn" @click="onClear">清空登记</AppButton>
      <AppButton v-if="courts.length" variant="pri" class="flex1" @click="onSave">保存 · 已订场必开</AppButton>
      <!-- 空锁：今天的行为原样保留（已手动锁定则不再出现） -->
      <AppButton v-else-if="!g.sure" variant="pri" class="flex1" @click="onSure">🔒 锁定必打（不订场）</AppButton>
    </view>
    <view v-if="!courts.length && g.sure" class="sub sure-note">已手动锁定必打 · 填场地号和总价可升级为「已订场」</view>
  </view>
</template>

<script setup lang="ts">
/* 订场登记 BookingSheet（3.2 订场改版）。场地号解析：顿号/逗号/空格/斜杠分隔，
   去空格去重保序——片数不单独填，就是识别出的个数（现场开打的默认片数同源）。
   每次打开按当前登记带出原值（SheetHost 按 type 分发，关闭即卸载重挂）。 */
import { computed, ref } from 'vue';
import AppButton from '@/components/ui/AppButton.vue';
import AppField from '@/components/ui/AppField.vue';
import AppInput from '@/components/ui/AppInput.vue';
import { useGameStore } from '@/stores/game';
import { useUiStore } from '@/stores/ui';
import { heads, isForced } from '@/utils/format';

const props = defineProps({
  gameId: { type: Number, required: true },
});

const game = useGameStore();
const ui = useUiStore();

/** 局被撤下等场景的兜底（v-if 不渲染） */
const g = computed(() => game.games.find((x) => x.id === props.gameId) ?? null);
const hs = computed(() => (g.value ? heads(g.value) : 0));
const forced = computed(() => (g.value ? isForced(g.value) : false));
const hasBooking = computed(() => !!g.value?.booked?.length);

/** 场地号解析（公共口径）：分隔符切 → 去空 → 去重保序 */
const courts = computed<string[]>(() => {
  const seen = new Set<string>();
  return courtsText.value
    .split(/[\s,，、/]+/)
    .map((s) => s.trim())
    .filter((s) => {
      if (!s || seen.has(s)) return false;
      seen.add(s);
      return true;
    });
});

const courtsText = ref(g.value?.booked?.join('、') ?? '');
const feeText = ref(g.value?.fee != null ? String(g.value.fee) : '');

const parseHint = computed(() =>
  courts.value.length
    ? `识别到 ${courts.value.length} 片：${courts.value.join('、')}`
    : '不填场地号 = 只锁定必打，不登记订场',
);

const feeHint = computed(() => {
  if (!courts.value.length) return '先填场地号，总价才有落点';
  const n = Number(feeText.value);
  if (feeText.value === '') return '按订场小票的总价填（片数 × 时段价，晚场贵白天便宜）';
  if (!Number.isFinite(n) || n < 0) return '总价得是非负数字';
  return n === 0 ? '免费场 · 人均 ¥0' : `按现在 ${hs.value} 人 · 人均 ¥${Math.round(n / Math.max(1, hs.value))}（人多会更低）`;
});

/** 保存订场：场地号 ≥1 且总价合法才落（toast 在 store 内） */
function onSave(): void {
  if (!g.value || !courts.value.length) return;
  const n = Number(feeText.value);
  if (feeText.value === '' || !Number.isFinite(n) || n < 0) {
    ui.toast('填一下总价 · 免费场填 0');
    return;
  }
  game.bookCourt(g.value.id, courts.value, n);
  ui.closeSheet();
}

/** 空锁：store.sureGame（原 alpha:1171-1176 行为） */
function onSure(): void {
  if (!g.value) return;
  game.sureGame(g.value.id);
  ui.closeSheet();
}

/** 清空登记（场地全退光）：局回未订场原样，手动锁保留（store 内判） */
function onClear(): void {
  if (!g.value) return;
  game.clearBooking(g.value.id);
  ui.closeSheet();
}
</script>

<style lang="scss" scoped>
/* 壳层标题/hint 同款（各弹层自带的做法，同 ProfileSheet/JoinSheet） */
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
/* 现状行（11px dim，同 LaunchSheet ppl-hint 家族） */
.stat {
  color: var(--dim);
  font-size: 11px;
  margin-bottom: 14px;
}
/* 字段下方实时提示 */
.fh {
  color: var(--dim);
  font-size: 11px;
  margin-top: 6px;
}
.btns {
  display: flex;
  gap: 10px;
}
.flex1 {
  flex: 1;
}
.clear-btn {
  color: var(--coral);
  border-color: rgba(255, 90, 54, 0.4);
}
.sure-note {
  color: var(--ice);
  font-size: 11px;
  margin-top: 10px;
}
</style>
