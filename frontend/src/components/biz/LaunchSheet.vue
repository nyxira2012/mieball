<template>
  <!-- 组局表单（3.3 改版 + 1.2 修订面）：
       新建（无 gameId）/ 改局（带 gameId 带出原值）复用同一表单，编辑态标题「改局 · 名单不动」+ 截止只读框。
       1.2 修订：新增「谁能翻到」三选（跟我打过的人/任何人/仅邀请，默认第一档——A1）；
       提交值换算成 ISO 绝对时刻（契约§2），组局截止默认自动=开打前 2 小时、手动拨过即固定。
       规则三件/人数/地点沿用 3.3；费用与说明不在表单（新局费用未定，改局不动原 fee）。
       入口：TabBar FAB / 详情页「改信息」都经 ui.openSheet({type:'launch'})；
       成功后只关弹层 —— toast 由 game store 的 publishGame/editGame 内置。 -->
  <view class="lc">
    <view class="sheet-t">{{ isEd ? "改局 · 名单不动" : "组局" }}</view>
    <view class="sheet-hint">{{
      isEd
        ? "名单里的人再打开，看到的就是新信息 · 截止时间定死不能改"
        : "从上到下拨完点发布 · 发完点局上的 ⤴ 转到群里拉人"
    }}</view>

    <!-- 局名：无标签，占位即自动默认名 -->
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
      <view class="dl-ro"
        >{{ lf.deadlineTxt }} · 到点名单锁定，参加者不能再退出</view
      >
    </AppField>
    <AppField v-else label="组局截止 · 到点名单锁定，低于最少自动终止">
      <view class="dl-tag" :class="{ on: dlAuto }" @click="onDlTag">{{
        dlAuto ? "自动 · 开打前 2 小时" : "已手动 · 点回自动"
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
      <OptionChips
        :model-value="venOn"
        :options="VENS"
        @update:model-value="venOn = String($event)"
      />
      <view v-if="venOn === '手输新场地'" class="mt8">
        <AppInput
          v-model="vCustom"
          placeholder="手输新场地：如 亮马河 · 滨河球场"
        />
      </view>
    </AppField>

    <!-- 谁能翻到（1.2 A1 新增三选，默认跟我打过的人） -->
    <AppField label="谁能翻到 · 只管列表，链接永远能进">
      <OptionChips
        :model-value="lf.visibility"
        :options="VIS_OPTS"
        @update:model-value="lf.visibility = String($event) as Visibility"
      />
      <view class="ppl-hint">{{ visHint }}</view>
    </AppField>

    <!-- 人数双 stepper（照旧：min 2-12，cap min+1 至 16） -->
    <AppField label="人数 · 最少 — 最多（满员线）">
      <view class="ppl">
        <text class="ppl-lab">最少</text>
        <AppStepper
          class="ppl-st"
          :model-value="lf.min"
          :min="2"
          :max="12"
          @update:model-value="lfMin"
        />
        <text class="ppl-lab">最多</text>
        <AppStepper
          class="ppl-st"
          :model-value="lf.cap"
          :min="lf.min + 1"
          :max="16"
          @update:model-value="lf.cap = $event"
        />
      </view>
      <view class="ppl-hint">{{ pplHint }}</view>
      <!-- A3 编辑态上限改小：保存时将有 formal 人转候补的预估提示 -->
      <view v-if="toWaitHint" class="ppl-hint ppl-warn">{{ toWaitHint }}</view>
    </AppField>

    <!-- 规则三件（2026-10-04 定：说明字段去掉，改直选分制/轮转/得分规则） -->
    <AppField label="分制 · 先到 N 且净胜 2">
      <OptionChips
        :model-value="lf.scoring"
        :options="SCORES"
        @update:model-value="lf.scoring = Number($event)"
      />
    </AppField>
    <AppField label="轮转 · 怎么排人">
      <OptionChips
        :model-value="lf.rotation"
        :options="MODES"
        @update:model-value="lf.rotation = String($event) as CourtMode"
      />
    </AppField>
    <AppField label="得分规则 · 什么球算分">
      <OptionChips
        :model-value="lf.scoreRule"
        :options="SCORE_RULES"
        @update:model-value="lf.scoreRule = String($event) as 'rally' | 'serve'"
      />
    </AppField>

    <!-- 发布 / 保存修改（pri 通栏黄钮） -->
    <AppButton variant="pri" block :disabled="busy" @click="publish">{{
      busy ? "提交中…" : isEd ? "保存修改" : "发布"
    }}</AppButton>
  </view>
</template>

<script setup lang="ts">
/* 组局表单 LaunchSheet（3.3 改版 · 1.2 修订面）。
   拨盘受控值约定：时间为「分钟数」（30 分钟一格）；发布时 toIso 落成绝对时刻（契约§2）。 */
import { computed, onMounted, reactive, ref, watch } from "vue";
import AppField from "@/components/ui/AppField.vue";
import AppInput from "@/components/ui/AppInput.vue";
import AppButton from "@/components/ui/AppButton.vue";
import AppStepper from "@/components/ui/AppStepper.vue";
import OptionChips from "@/components/ui/OptionChips.vue";
import WheelPicker from "@/components/ui/WheelPicker.vue";
import { useGameStore } from "@/stores/game";
import { useSessionStore } from "@/stores/session";
import { useUiStore } from "@/stores/ui";
import { venueSuggestions } from "@/api/dict";
import type { CourtMode, PublishGameInput, Visibility } from "@/api/types";
import { MODE_NAMES, SCORE_RULE_NAMES, autoGameName } from "@/utils/format";
import { beijingAt, isoDay, isoDayOff, isoParts, toIso } from "@/utils/time";
import { errText } from "@/api/http";
import { goMeet } from "@/utils/nav";

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
  (_, i) =>
    `${String(Math.floor(i / 2)).padStart(2, "0")}:${String((i % 2) * 30).padStart(2, "0")}`,
);
/** 规则三件 + 谁能翻到（label 引 MODE_NAMES/SCORE_RULE_NAMES 与 detail/live 同源；
    可见档文案表落本组件内——技术设计§4 知识落点） */
const SCORES = [11, 15, 21];
const MODES: Array<{ value: CourtMode; label: string }> = [
  { value: "balance", label: MODE_NAMES.balance },
  { value: "winner", label: MODE_NAMES.winner },
  { value: "rotate", label: MODE_NAMES.rotate },
];
const SCORE_RULES = [
  { value: "rally", label: SCORE_RULE_NAMES.rally },
  { value: "serve", label: SCORE_RULE_NAMES.serve },
];
const VIS_OPTS: Array<{ value: Visibility; label: string }> = [
  { value: "played", label: "跟我打过的人" },
  { value: "public", label: "任何人" },
  { value: "invite_only", label: "仅邀请" },
];
const visHint = computed(() => {
  if (lf.visibility === "played")
    return "只给同局打过球的人翻到 · 新球友主要靠你转的链接进来";
  if (lf.visibility === "public") return "任何人翻约球页都能看到这局";
  return "列表里不出现 · 只把链接或邀请发给人";
});
/** 地点 chips：场馆建议名单一源（api/dict）+ 手输项 */
const VENS = [...venueSuggestions, "手输新场地"];

/** 分钟 ↔ 网格下标（夹取） */
const m2g = (m: number): number =>
  Math.max(0, Math.min(Math.round(m / STEP), GRID_N - 1));
const clamp = (v: number, lo: number, hi: number): number =>
  Math.max(lo, Math.min(v, hi));

/* ---- 表单状态 ---- */
const isEd = ref(false);
const busy = ref(false);
const lf = reactive({
  gid: 0,
  name: "",
  deadlineTxt: "",
  min: 4,
  cap: 6,
  visibility: "played" as Visibility,
  scoring: 11,
  rotation: "balance" as CourtMode,
  scoreRule: "rally" as "rally" | "serve",
});
const venOn = ref("");
const vCustom = ref("");

/* 开打拨盘：dayI + startMin/endMin（分钟）为真值，tIdx 为派生下标 */
const dayI = ref(2);
const startMin = ref(19 * 60);
const endMin = ref(21 * 60);

/* 拨盘全按北京历法（2026-10-10 修复批 F2）：日列锚「北京今天」（beijingAt 单源，
   月末滚动交给 Date.UTC），回填与索引共用 isoDayOff 一个口径——此前日列吃设备
   本地历、回填吃北京历，非东八区机器初始停在错误的日上。锚取北京**午夜**：
   拨盘分钟数（startMin/dlMin）正是距午夜，playStart/dlDate 锚上加分钟即正确。 */
const days = computed(() => {
  const n = isoParts(new Date());
  return Array.from({ length: DAY_N }, (_, i) =>
    beijingAt(n.y, n.m, n.d + i, 0),
  );
});
const dayLabels = computed(() => days.value.map((d) => isoDay(d)));

/** 结束时刻列：开始后 30 分钟 ~ 6 小时（且不越过 23:55） */
const endLabels = computed(() => {
  const hi = Math.min(startMin.value + 360, GRID_MAX);
  const out: string[] = [];
  for (let m = startMin.value + 30; m <= hi; m += STEP)
    out.push(GRID_LABELS[m2g(m)]);
  return out;
});
const endRow = computed(() =>
  clamp(
    Math.round((endMin.value - startMin.value - 30) / STEP),
    0,
    Math.max(0, endLabels.value.length - 1),
  ),
);
const tIdx = computed(() => [dayI.value, m2g(startMin.value), endRow.value]);
const tCols = computed(() => [dayLabels.value, GRID_LABELS, endLabels.value]);

const playStart = computed(() => {
  const d = days.value[clamp(dayI.value, 0, DAY_N - 1)];
  return new Date(d.getTime() + startMin.value * 60000); // 北京当日锚 + 分钟数
});
const playHint = computed(
  () =>
    `${dayLabels.value[dayI.value]} ${GRID_LABELS[m2g(startMin.value)]}–${GRID_LABELS[m2g(endMin.value)]}`,
);

/** 开打拨盘变化：夹结束时刻；截止为手动态时把越界部分收进新的可拨范围 */
function onPlayChange(v: number[]): void {
  dayI.value = v[0] ?? dayI.value;
  startMin.value = clamp((v[1] ?? 0) * STEP, 0, GRID_MAX);
  endMin.value = clamp(
    endMin.value,
    startMin.value + 30,
    Math.min(startMin.value + 360, GRID_MAX),
  );
  if (!dlAuto.value) fitDlToRange();
}

/* 截止拨盘：可拨范围从源头限死（日期 ≤ 开打日；同日时刻 ≤ 开打前 5 分，今天再叠「现在+5分」下限），
   越界的值拨不出来。自动态 = 开打前 2 小时（随开打重算）；手动拨过即固定，点标签可回自动。 */
const dlAuto = ref(true);
const dlDayI = ref(2);
const dlMin = ref(17 * 60);
const nowMin = (): number => {
  const p = isoParts(new Date()); // 北京墙钟的当前分钟（不随设备时区）
  return p.h * 60 + p.min;
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
  return clamp(
    Math.round((dlMin.value - lo) / STEP),
    0,
    Math.max(0, dlTimeLabels.value.length - 1),
  );
});
const dlIdx = computed(() => [
  clamp(dlDayI.value, 0, dayI.value),
  dlTimeRow.value,
]);
const dlCols = computed(() => [dlDayLabels.value, dlTimeLabels.value]);
/** 自动态的截止时刻：开打前 2 小时，早于现在+5分则抬到现在+5分 */
const autoDlDate = computed(() => {
  const t = new Date(playStart.value.getTime() - 120 * 60000);
  const lo = new Date(Date.now() + 5 * 60000);
  return t < lo ? lo : t;
});
/** 把截止状态收进所选日期的合法窗（自动重算 / 开打变化后的手动态都走这里） */
function applyDl(d: Date): void {
  dlDayI.value = clamp(isoDayOff(d), 0, dayI.value);
  const { lo, hi } = dlBounds(dlDayI.value);
  const p = isoParts(d); // 北京墙钟取分（同拨盘历法）
  dlMin.value = clamp(ceilStep(p.h * 60 + p.min), lo, hi);
}
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

/* ---- 地点 / 人数 ---- */
const venueSel = computed(() =>
  venOn.value === "手输新场地"
    ? vCustom.value.trim() || venOn.value
    : venOn.value,
);
/** 自动默认名「日段 · 地点」：占位提示与不填时的发布名同源（utils/format 的 autoGameName） */
const autoName = computed(() =>
  autoGameName(dayLabels.value[dayI.value], venueSel.value),
);

function lfMin(v: number): void {
  lf.min = v;
  if (lf.cap < lf.min + 1) lf.cap = lf.min + 1;
}
const pplHint = computed(
  () => `${lf.min}-${lf.cap} 人 · 不足最少截止时自动终止 · 到最多进候补`,
);
/* A3 编辑态上限改小预估：formal 人头（Σ(1+bring)）− 新上限 > 0 即提示将转候补人数；
   后端会保组织者行，前端不做该细节模拟，超额按人头口径直说 */
const formalHeads = computed(() => {
  const ed = game.findGame(lf.gid);
  return (ed?.entries ?? [])
    .filter((e) => e.standing === "formal")
    .reduce((s, e) => s + 1 + (e.bring || 0), 0);
});
const toWaitHint = computed(() => {
  if (!isEd.value) return "";
  const x = Math.max(0, formalHeads.value - lf.cap);
  return x > 0 ? `保存后有 ${x} 人将转入候补` : "";
});

/** 打开时初始化。SheetHost 的 v-if 使每次打开都重新挂载 → onMounted 即开表；watch 兜底换 gameId。 */
function init(): void {
  const ed = props.gameId != null ? game.findGame(props.gameId) : null;
  isEd.value = !!ed;
  lf.gid = ed ? ed.id : 0;
  lf.name = ed ? ed.name : "";
  lf.visibility = ed ? ed.visibility : "played";
  const loc = ed ? ed.venueName : VENS[0];
  lf.min = ed ? ed.minPlayers : 4;
  lf.cap = ed ? ed.maxPlayers : 6;
  lf.scoring = ed ? ed.scoring : 11;
  lf.rotation = ed ? ed.rotation : "balance";
  lf.scoreRule = ed?.scoreRule === "serve" ? "serve" : "rally";
  venOn.value = VENS.includes(loc) ? loc : "手输新场地";
  vCustom.value =
    venOn.value === "手输新场地" && !VENS.includes(loc) ? loc : "";
  if (ed) {
    // 走查#1 收口：编辑回填按北京墙钟取数（此前 new Date(iso).getHours() 吃设备时区，非东八区机器回填漂 3 小时）
    const sp = isoParts(ed.startAt);
    dayI.value = clamp(isoDayOff(ed.startAt), 0, DAY_N - 1);
    startMin.value = clamp(sp.h * 60 + sp.min, 0, GRID_MAX);
    const ep = isoParts(ed.endAt);
    endMin.value = clamp(
      ep.h * 60 + ep.min,
      startMin.value + 30,
      Math.min(startMin.value + 360, GRID_MAX),
    );
    const dp = isoParts(ed.deadlineAt);
    lf.deadlineTxt = `${isoDay(ed.deadlineAt)} ${GRID_LABELS[m2g(dp.h * 60 + dp.min)]}`;
    dlAuto.value = false; // 编辑态截止只读，拨盘状态不参与提交
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

/** 自动态截止的 Date（新建提交用） */
const dlDate = computed(() => {
  const d = days.value[clamp(dlDayI.value, 0, DAY_N - 1)];
  return new Date(d.getTime() + dlMin.value * 60000);
});

/** 发布 / 保存修改：拨盘状态落成 ISO 绝对时刻（契约§2）→ store（toast 在 store 内置）→ 关弹层；
     失败 toast 人话留在表单（A2：已填内容不丢） */
async function publish(): Promise<void> {
  if (busy.value) return;
  const endDate = new Date(
    playStart.value.getTime() + (endMin.value - startMin.value) * 60000,
  );
  const input: PublishGameInput = {
    name: lf.name.trim() || autoName.value,
    start_at: toIso(playStart.value),
    end_at: toIso(endDate),
    deadline_at: isEd.value ? "" : toIso(dlDate.value),
    venue_name: venueSel.value,
    venue_address: null,
    min_players: lf.min,
    max_players: lf.cap,
    visibility: lf.visibility,
    scoring: lf.scoring,
    rotation: lf.rotation,
    score_rule: lf.scoreRule,
  };
  busy.value = true;
  try {
    if (isEd.value) {
      const { deadline_at: _omit, ...edits } = input; // 截止不在改局参数表（不变承诺3）
      void _omit;
      await game.editGame(lf.gid, edits);
    } else {
      // 1.1 先看后报：游客建局先弹名片建号卡，建号成功由弹层接着发布（表单值随身带走不重填）
      if (session.isGuest) {
        ui.signupThen({ pendingLaunch: input });
        busy.value = false;
        return;
      }
      await game.publishGame(input);
      goMeet(); // 发布成功回约球页（alpha:1397 go('meet')）
    }
    ui.closeSheet();
  } catch (e) {
    ui.toast(errText(e)); // deadline_inverted / range_invalid 等后端人话直出
  } finally {
    busy.value = false;
  }
}
</script>

<style lang="scss" scoped>
/* 壳层标题/hint 走全局 .sheet-t/.sheet-hint（base.scss 收源） */
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
/* A3 转候补预估行：警示色（同 detail 剩坑为 0 的 coral 口径） */
.ppl-warn {
  color: var(--coral);
}
</style>
