<template>
  <!-- 组局表单（3.3 改版 · 2026-10-04 用户定：瘦身 + 拨盘选准）：
       新建（无 gameId）/ 改局（带 gameId 带出原值）复用同一表单，编辑态标题「改局 · 名单不动」+ 截止只读框。
       相对旧版（alpha:1299-1398）的变化：
       ① 局名去标签，占位提示即自动默认名「日段 · 地点」（不填发布时用它）；
       ② 时间+打多久合并为「日期 / 开始 / 结束」三列拨盘（24 小时制 30 分钟一格，打多久由起止得出，默认两天后 19:00–21:00）；
       ③ 组局截止弃用 chips，改两列拨盘：默认自动=开打前 2 小时（随开打重算），手动拨过即固定、可点回自动，范围夹在 现在~开打 之间；
       ④ 预计费用整字段去掉（新局 fee=null 费用未定；改局不动原 fee）；
       ⑤ 说明字段去掉，改规则三件直选：分制（11/15/21）、轮转（均衡配对/赢家留场/纯粹轮转）、得分规则（每球/发球得分制），落 score/mode/scoreRule。
       入口：TabBar FAB / 详情页「改信息」都经 ui.openSheet({type:'launch'})；
       成功后只关弹层 —— toast 由 game store 的 publishGame/editGame 内置。 -->
  <view class="lc">
    <!-- alpha:1316 标题（壳层样式同 AppSheet 的 h3/.hint） -->
    <view class="t">{{ isEd ? '改局 · 名单不动' : '组局' }}</view>
    <view class="hint">{{
      isEd
        ? '名单里的人再打开，看到的就是新信息 · 截止时间定死不能改'
        : '从上到下拨完点发布 · 发完点局上的 ⤴ 转到群里拉人'
    }}</view>

    <!-- 局名：无标签（2026-10-04 定），占位即自动默认名 -->
    <view class="lc-name">
      <AppInput v-model="lf.name" :placeholder="autoName" />
    </view>

    <!-- 开打：日期 / 开始 / 结束 三列拨盘（结束只能在开始后 30 分钟 ~ 6 小时） -->
    <AppField label="开打 · 日期 / 开始 / 结束">
      <WheelPicker
        :model-value="tIdx"
        :cols="tCols"
        :headers="['日期', '开始', '结束']"
        :widths="[1.5, 1, 1]"
        @update:model-value="onPlayChange"
      />
      <view class="wheel-hint">{{ playHint }}</view>
    </AppField>

    <!-- 组局截止：编辑态定死只读；新建两列拨盘 + 自动跟随标记 -->
    <AppField v-if="isEd" label="组局截止 · 定死不能改">
      <view class="dl-ro">{{ lf.deadline }} · 到点名单锁定，参加者不能再退出</view>
    </AppField>
    <AppField v-else label="组局截止 · 到点名单锁定，低于最少自动终止">
      <view class="dl-tag" :class="{ on: dlAuto }" @click="onDlTag">{{
        dlAuto ? '自动 · 开打前 2 小时' : '已手动 · 点回自动'
      }}</view>
      <WheelPicker
        :model-value="dlIdx"
        :cols="dlCols"
        :headers="['日期', '时刻']"
        :widths="[1.5, 1]"
        @update:model-value="onDlChange"
      />
    </AppField>

    <!-- 地点 chips 4 项 + 手输（照旧） -->
    <AppField label="地点 · 球馆名">
      <OptionChips :model-value="venOn" :options="VENS" @update:model-value="venOn = String($event)" />
      <view v-if="venOn === '手输新场地'" class="mt8">
        <AppInput v-model="vCustom" placeholder="手输新场地：如 亮马河 · 滨河球场" />
      </view>
    </AppField>

    <!-- 人数双 stepper（照旧：min 2-12，cap min+1 至 16） -->
    <AppField label="人数 · 最少 — 最多（满员线）">
      <view class="ppl">
        <text class="ppl-lab">最少</text>
        <AppStepper class="ppl-st" :model-value="lf.min" :min="2" :max="12" @update:model-value="lfMin" />
        <text class="ppl-lab">最多</text>
        <AppStepper class="ppl-st" :model-value="lf.cap" :min="lf.min + 1" :max="16" @update:model-value="lf.cap = $event" />
      </view>
      <view class="ppl-hint">{{ pplHint }}</view>
    </AppField>

    <!-- 规则三件（2026-10-04 定：说明字段去掉，改直选分制/轮转/迟到，落局的规则数据） -->
    <AppField label="分制 · 先到 N 且净胜 2">
      <OptionChips :model-value="lf.score" :options="SCORES" @update:model-value="lf.score = Number($event)" />
    </AppField>
    <AppField label="轮转 · 怎么排人">
      <OptionChips :model-value="lf.mode" :options="MODES" @update:model-value="lf.mode = String($event) as CourtMode" />
    </AppField>
    <AppField label="得分规则 · 什么球算分">
      <OptionChips
        :model-value="lf.scoreRule"
        :options="SCORE_RULES"
        @update:model-value="lf.scoreRule = String($event) as 'rally' | 'serve'"
      />
    </AppField>

    <!-- 发布 / 保存修改（pri 通栏黄钮） -->
    <AppButton variant="pri" block @click="publish">{{ isEd ? '保存修改' : '发布' }}</AppButton>
  </view>
</template>

<script setup lang="ts">
/* 组局表单 LaunchSheet（3.3 改版）。
   拨盘受控值约定：时间为「分钟数」（30 分钟一格），下标 = 分钟/30；
   日期列 = 今天起 14 天，日段文案用 utils/time 的 dayToken（今天/明天/后天/M.DD 周X），
   发布时落成「日段 HH:mm」，gameTime 的精确日期分支可原样解析回来。 */
import { computed, onMounted, reactive, ref, watch } from 'vue';
import AppField from '@/components/ui/AppField.vue';
import AppInput from '@/components/ui/AppInput.vue';
import AppButton from '@/components/ui/AppButton.vue';
import AppStepper from '@/components/ui/AppStepper.vue';
import OptionChips from '@/components/ui/OptionChips.vue';
import WheelPicker from '@/components/ui/WheelPicker.vue';
import { useGameStore } from '@/stores/game';
import { useSessionStore } from '@/stores/session';
import { useUiStore } from '@/stores/ui';
import type { CourtMode, PublishInput } from '@/api/types';
import { dayToken, durTxt, gameTime } from '@/utils/time';

const props = defineProps({
  /** 有 gameId = 改局（带原值）；无/查不到 = 新建（查不到按新建兜底） */
  gameId: { type: Number, default: undefined },
});

const game = useGameStore();
const session = useSessionStore();
const ui = useUiStore();

/* ---- 拨盘常量与网格 ---- */
const DAY_N = 14; // 日期范围：今天起 14 天
const STEP = 30; // 时刻步进（分钟）——2026-10-04 定：30 分钟一格
const GRID_N = 48; // 24h × 2 格（00:00–23:30）
const GRID_MAX = 23 * 60 + 30; // 网格最后一格
const GRID_LABELS: string[] = Array.from(
  { length: GRID_N },
  (_, i) => `${String(Math.floor(i / 2)).padStart(2, '0')}:${String((i % 2) * 30).padStart(2, '0')}`,
);
/** 规则三件（3.3：说明字段去掉，直选分制/轮转/迟到；词表与 detail 规则牌/现场页同源） */
const SCORES = [11, 15, 21];
const MODES: Array<{ value: CourtMode; label: string }> = [
  { value: 'balance', label: '均衡配对' },
  { value: 'winner', label: '赢家留场' },
  { value: 'rotate', label: '纯粹轮转' },
];
const SCORE_RULES = [
  { value: 'rally', label: '每球得分制' },
  { value: 'serve', label: '发球得分制' },
];
/** 旧版 chips（alpha:1308-1310/1344-1345，3.3 改版弃用）：时间/时长/费用/截止 chips → 拨盘与预设 */
const VENS = ['工体北路 · 京篮匹克球馆', '望京 · 花家地球馆', '五棵松 · 万事达球馆', '手输新场地'];

/** 分钟 ↔ 网格下标（夹取） */
const m2g = (m: number): number => Math.max(0, Math.min(Math.round(m / STEP), GRID_N - 1));
const clamp = (v: number, lo: number, hi: number): number => Math.max(lo, Math.min(v, hi));
/** 某日期距今天的天数偏移（用于把 Date 映射回日期列下标） */
function dayOffset(d: Date): number {
  const now = new Date();
  const day0 = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime() - day0.getTime()) / 86400000);
}

/* ---- 表单状态 ---- */
const isEd = ref(false);
const lf = reactive({
  gid: 0, name: '', deadline: '', venue: '', min: 4, cap: 6,
  score: 11, mode: 'balance' as CourtMode, scoreRule: 'rally' as 'rally' | 'serve',
});
const venOn = ref('');
const vCustom = ref('');

/* 开打拨盘：dayI + startMin/endMin（分钟）为真值，tIdx 为派生下标 */
const dayI = ref(2);
const startMin = ref(19 * 60);
const endMin = ref(21 * 60);

const days = computed(() =>
  Array.from({ length: DAY_N }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() + i);
    return d;
  }),
);
const dayLabels = computed(() => days.value.map((d) => dayToken(d)));

/** 结束时刻列：开始后 30 分钟 ~ 6 小时（且不越过 23:55） */
const endLabels = computed(() => {
  const hi = Math.min(startMin.value + 360, GRID_MAX);
  const out: string[] = [];
  for (let m = startMin.value + 30; m <= hi; m += STEP) out.push(GRID_LABELS[m2g(m)]);
  return out;
});
const endRow = computed(() =>
  clamp(Math.round((endMin.value - startMin.value - 30) / STEP), 0, Math.max(0, endLabels.value.length - 1)),
);
const tIdx = computed(() => [dayI.value, m2g(startMin.value), endRow.value]);
const tCols = computed(() => [dayLabels.value, GRID_LABELS, endLabels.value]);

const playStart = computed(() => {
  const d = new Date(days.value[clamp(dayI.value, 0, DAY_N - 1)]);
  d.setHours(0, startMin.value, 0, 0);
  return d;
});
const playHint = computed(
  () =>
    `${dayLabels.value[dayI.value]} ${GRID_LABELS[m2g(startMin.value)]}–${GRID_LABELS[m2g(endMin.value)]} · 打 ${durTxt((endMin.value - startMin.value) / 60)}`,
);

/** 开打拨盘变化：夹结束时刻；截止为手动态时把越界部分收进新的可拨范围 */
function onPlayChange(v: number[]): void {
  dayI.value = v[0] ?? dayI.value;
  startMin.value = clamp((v[1] ?? 0) * STEP, 0, GRID_MAX);
  endMin.value = clamp(endMin.value, startMin.value + 30, Math.min(startMin.value + 360, GRID_MAX));
  if (!dlAuto.value) fitDlToRange();
}

/* 截止拨盘：可拨范围从源头限死（日期 ≤ 开打日；同日时刻 ≤ 开打前 5 分，今天再叠「现在+5分」下限），
   越界的值拨不出来，也就不需要「夹回」——uni 的受控回滚不可靠（见 3.3 实测）。
   自动态 = 开打前 2 小时（随开打重算）；手动拨过即固定，点标签可回自动。 */
const dlAuto = ref(true);
const dlDayI = ref(2);
const dlMin = ref(17 * 60);
const nowMin = (): number => {
  const d = new Date();
  return d.getHours() * 60 + d.getMinutes();
};
const ceilStep = (m: number): number => Math.ceil(m / STEP) * STEP;
/** 截止当前所选日期行的合法时刻窗 [lo, hi]（分钟） */
function dlBounds(day: number): { lo: number; hi: number } {
  return {
    lo: day <= 0 ? Math.min(ceilStep(nowMin() + 5), GRID_MAX) : 0,
    hi: day >= dayI.value ? startMin.value - STEP : GRID_MAX,
  };
}
const dlDayLabels = computed(() => dayLabels.value.slice(0, dayI.value + 1));
const dlTimeLabels = computed(() => {
  const { lo, hi } = dlBounds(dlDayI.value);
  const out: string[] = [];
  for (let m = lo; m <= hi; m += STEP) out.push(GRID_LABELS[m2g(m)]);
  return out.length ? out : [GRID_LABELS[m2g(dlLo0())]];
});
function dlLo0(): number {
  return Math.min(ceilStep(nowMin() + 5), GRID_MAX);
}
const dlTimeRow = computed(() => {
  const { lo } = dlBounds(dlDayI.value);
  return clamp(Math.round((dlMin.value - lo) / STEP), 0, Math.max(0, dlTimeLabels.value.length - 1));
});
const dlIdx = computed(() => [clamp(dlDayI.value, 0, dayI.value), dlTimeRow.value]);
const dlCols = computed(() => [dlDayLabels.value, dlTimeLabels.value]);
/** 自动态的截止时刻：开打前 2 小时，早于现在+5分则抬到现在+5分 */
const autoDlDate = computed(() => {
  const t = new Date(playStart.value.getTime() - 120 * 60000);
  const lo = new Date(Date.now() + 5 * 60000);
  return t < lo ? lo : t;
});
/** 把截止状态收进所选日期的合法窗（自动重算 / 开打变化后的手动态都走这里） */
function applyDl(d: Date): void {
  dlDayI.value = clamp(dayOffset(d), 0, dayI.value);
  const { lo, hi } = dlBounds(dlDayI.value);
  dlMin.value = clamp(ceilStep(d.getHours() * 60 + d.getMinutes()), lo, hi);
}
/** 开打变化后（手动态）：日期列可能超出新的可拨范围，直接改状态值（程序化改值能正常同步滚轮） */
function fitDlToRange(): void {
  if (dlDayI.value > dayI.value) dlDayI.value = dayI.value;
  const { lo, hi } = dlBounds(dlDayI.value);
  dlMin.value = clamp(dlMin.value, lo, hi);
}
function onDlChange(v: number[]): void {
  dlAuto.value = false; // 手动拨过即固定（列已限死范围，拨出的值天然合法）
  dlDayI.value = clamp(v[0] ?? 0, 0, dayI.value);
  const { lo, hi } = dlBounds(dlDayI.value);
  dlMin.value = clamp(lo + (v[1] ?? 0) * STEP, lo, hi);
}
function onDlTag(): void {
  if (!dlAuto.value) {
    dlAuto.value = true;
    applyDl(autoDlDate.value);
  }
}
/* 自动态跟随：开打变化 → 截止重算 */
watch([dayI, startMin], () => {
  if (dlAuto.value) applyDl(autoDlDate.value);
});

/* ---- 地点 / 人数 / 说明 ---- */
const venueSel = computed(() => (venOn.value === '手输新场地' ? vCustom.value.trim() || venOn.value : venOn.value));
/** 自动默认名「日段 · 地点」：占位提示与不填时的发布名同源 */
const autoName = computed(() => `${dayLabels.value[dayI.value]} · ${venueSel.value.split(' · ').pop()}`);

function lfMin(v: number): void {
  lf.min = v;
  if (lf.cap < lf.min + 1) lf.cap = lf.min + 1;
}
const pplHint = computed(() => `${lf.min}-${lf.cap} 人 · 不足最少截止时自动终止 · 到最多进候补`);

/** 打开时初始化。SheetHost 的 v-if 使每次打开都重新挂载 → onMounted 即开表；watch 兜底换 gameId。 */
function init(): void {
  const ed = props.gameId != null ? game.games.find((x) => x.id === props.gameId) : null;
  isEd.value = !!ed;
  lf.gid = ed ? ed.id : 0;
  lf.name = ed ? ed.name : '';
  lf.venue = ed ? ed.loc : VENS[0];
  lf.min = ed ? ed.min : 4;
  lf.cap = ed ? ed.cap : 6;
  lf.score = ed ? ed.score : 11;
  lf.mode = ed ? ed.mode : 'balance';
  lf.scoreRule = ed?.scoreRule ?? 'rally';
  venOn.value = VENS.includes(lf.venue) ? lf.venue : '手输新场地';
  vCustom.value = venOn.value === '手输新场地' && !VENS.includes(lf.venue) ? lf.venue : '';
  if (ed) {
    const sd = gameTime(ed.t);
    dayI.value = clamp(dayOffset(sd), 0, DAY_N - 1);
    startMin.value = m2g(sd.getHours() * 60 + sd.getMinutes()) * STEP;
    endMin.value = clamp(
      startMin.value + Math.round(ed.dur * 60),
      startMin.value + 30,
      Math.min(startMin.value + 360, GRID_MAX),
    );
    lf.deadline = ed.deadline; // 编辑态只读展示
  } else {
    dayI.value = 2; // 默认两天后 19:00–21:00
    startMin.value = 19 * 60;
    endMin.value = 21 * 60;
    dlAuto.value = true;
    applyDl(autoDlDate.value);
  }
}
onMounted(init);
watch(() => props.gameId, init);

/** 发布 / 保存修改：拨盘状态落成字符串 → store（toast 在 store 内置）→ 关弹层 */
function publish(): void {
  const time = `${dayLabels.value[dayI.value]} ${GRID_LABELS[m2g(startMin.value)]}`;
  const dur = (endMin.value - startMin.value) / 60;
  const deadline = isEd.value
    ? lf.deadline
    : `${dayLabels.value[clamp(dlDayI.value, 0, DAY_N - 1)]} ${GRID_LABELS[m2g(dlMin.value)]}`;
  const input: PublishInput = {
    name: lf.name.trim() || autoName.value,
    time,
    dur,
    deadline,
    venue: venueSel.value,
    min: lf.min,
    cap: lf.cap,
    score: lf.score,
    mode: lf.mode,
    scoreRule: lf.scoreRule,
  };
  if (isEd.value) game.editGame(lf.gid, input);
  else {
    // 1.1 先看后报：游客建局先弹名片建号卡，建号成功由弹层接着发布（表单值随身带走不重填）
    if (session.isGuest) {
      ui.closeSheet();
      ui.openSheet({ type: 'signup-card', pendingLaunch: input });
      return;
    }
    game.publishGame(input);
    uni.switchTab({ url: '/pages/meet/meet' }); // 发布成功回约球页（alpha:1397 go('meet')）
  }
  ui.closeSheet();
}
</script>

<style lang="scss" scoped>
/* 壳层标题/hint（alpha:558-561 同 ProfileSheet 做法） */
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
/* 局名无标签：与 AppField 内容区同距 */
.lc-name {
  margin-bottom: 14px;
}
.mt8 {
  margin-top: 8px;
}
/* 拨盘下方实时摘要（11px dim，同 ppl-hint 家族） */
.wheel-hint {
  color: var(--dim);
  font-size: 11px;
  margin-top: 6px;
}
/* 截止自动/手动标记（小 chip：auto 态柠檬描边，手动态灰） */
.dl-tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 8px;
  border: 1px solid rgba(245, 241, 232, 0.16);
  color: var(--dim);
  font-size: 10px;
  font-family: var(--mono);
  margin-bottom: 6px;
}
.dl-tag.on {
  border-color: var(--lemon);
  color: var(--lemon);
}
/* 编辑态截止只读框（alpha:1327-1329 逐字） */
.dl-ro {
  color: var(--dim);
  font-size: 12px;
  padding: 10px 12px;
  border: 1px dashed rgba(245, 241, 232, 0.16);
  border-radius: 10px;
}
/* alpha:1338 人数双 stepper 行 */
.ppl {
  display: flex;
  gap: 10px;
  align-items: center;
}
.ppl-lab {
  color: var(--dim);
  font-size: 11px;
  flex: none;
}
.ppl-st {
  flex: 1;
}
.ppl-hint {
  color: var(--dim);
  font-size: 11px;
  margin-top: 6px;
}
</style>
