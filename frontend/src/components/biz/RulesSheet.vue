<template>
  <!-- 规则抽屉（2.4 批3 重造 · §4.1）：分制照旧（11/15/21）＋轮换四件套——单双打（全场统一）、
       谁下（单打两项/双打五项，推荐项亮「推荐」标签＋一句理由）、怎么配（仅双打，四档）、连打上限
       （全场常驻，不随谁下方式藏显——上限管所有下法；步进器 0＝不限）。点选即生效、
       不关抽屉、无确认弹窗（A3）；球友同一抽屉只读（§4.1）：选项禁用态、推荐标签与
       理由隐藏、switch-singles 提示可见不可点。 -->
  <AppSheet
    class="rules-sheet"
    :visible="visible"
    title="现场规则调整"
    :hint="
      full
        ? '点选即生效 · 在打对局照旧打完，下一场起按新规'
        : '只读查看 · 改规则请找组织者或管理员'
    "
    @close="emit('close')"
  >
    <view :class="{ ro: !full }">
      <AppField label="局分分制 · First To">
        <AppSeg
          :options="SCORE_OPTS"
          :model-value="g?.scoring ?? 11"
          @update:model-value="onScore($event)"
        />
      </AppField>

      <AppField label="单双打 · 全场统一">
        <AppSeg
          :options="SINGLES_OPTS"
          :model-value="rules?.singles ? 'singles' : 'doubles'"
          @update:model-value="onSingles($event)"
        />
      </AppField>
    </view>

    <!-- 改单打提示（§4.2：双打铺不满片、但人够按单打铺满）：全权者点了即全场换单打；
         球友也看得见（局面事实）但不可点 -->
    <view
      v-if="advice?.kind === 'switch-singles'"
      class="switch-tip"
      :class="{ tappable: full }"
      @click="onSwitchSingles"
    >
      <text class="st-k">改单打可全员上场</text>
      <text class="st-r">{{ advice.reason }}</text>
    </view>

    <view :class="{ ro: !full }">
      <AppField label="谁下">
        <view class="down-row">
          <view
            v-for="opt in downOpts"
            :key="opt"
            class="down-chip"
            :class="{ on: rules?.down === opt }"
            @click="onDown(opt)"
          >
            {{ DOWN_NAMES[opt] }}
            <text v-if="rec?.down === opt" class="rec-tag">推荐</text>
          </view>
        </view>
        <text v-if="rec" class="rec-reason">推荐理由：{{ rec.reason }}</text>
      </AppField>

      <AppField v-if="!rules?.singles" label="怎么配 · 双打分队">
        <AppSeg
          :options="PAIRING_OPTS"
          :model-value="rules?.pairing ?? 'queue'"
          @update:model-value="onPairing($event)"
        />
      </AppField>

      <AppField label="连打上限 · 全场统一">
        <view class="cap-row">
          <AppStepper
            :model-value="rules?.champCap ?? 3"
            :min="0"
            @update:model-value="onCap"
          />
          <text class="cap-hint">{{
            rules?.champCap === 0 ? "当前＝不限" : "场"
          }}</text>
        </view>
      </AppField>
    </view>
  </AppSheet>
</template>

<script setup lang="ts">
/* 规则抽屉（2.1 §3 · 2.4 批3 重造）：直调 store——分制 setRuleScore 下一场起生效
   （在打片照旧打完，2.6 切真）、四件套 setRules 点选即生效（toast 在 store）；
   推荐消费 store 已导出的 advice computed
   （总账算好定值，画面不自算、不造假延时——A2 无加载态）。只读三保险：.ro 罩层
   pointer-events / 处理器 full 判 / store needFull guard（双保险不动）。 */
import { computed } from "vue";
import AppSheet from "@/components/ui/AppSheet.vue";
import AppField from "@/components/ui/AppField.vue";
import AppSeg from "@/components/ui/AppSeg.vue";
import AppStepper from "@/components/ui/AppStepper.vue";
import { useLiveStore } from "@/stores/live";
import { DOWN_NAMES, PAIRING_NAMES, SCORE_OPTS } from "@/utils/format";
import type { DownMode, PairingMode } from "@/api/types";

defineProps({
  visible: { type: Boolean, default: false },
});
const emit = defineEmits<{ (e: "close"): void }>();

const liveStore = useLiveStore();
const g = computed(() => liveStore.live?.g);
const rules = computed(() => liveStore.live?.rules);
/** 全权（组织者 ∨ 管理员）单一源在 store；只读态与提示可点性都由它派生 */
const full = computed(() => liveStore.isFullPower);
const advice = computed(() => liveStore.advice);

/** 单双打全场统一（§4.1 禁止一片单打一片双打混打）；默认双打（§4.2） */
const SINGLES_OPTS = [
  { value: "doubles", label: "双打" },
  { value: "singles", label: "单打" },
];
/** 怎么配主标 = PAIRING_NAMES 单一源，选项键序直接从它派生——加档动 api/types.ts 的
    PairingMode 联合 + format.ts 一处名单（Record 编译期逼改，类型联合是第一落点）；
    不进推荐（§4.2 口味问题，组织者自定） */
const PAIRING_OPTS = (Object.keys(PAIRING_NAMES) as PairingMode[]).map((p) => ({
  value: p,
  label: PAIRING_NAMES[p],
}));

/** 谁下选项随单双打折半/展开（单打×N人下不合法，store 组合回落兜底） */
const downOpts = computed<DownMode[]>(() =>
  rules.value?.singles ? ["all", "loser"] : ["all", "loser", "n1", "n2", "n3"],
);

/** 推荐项＋理由（仅全权者可见——§4.1 球友看不到推荐标签与理由；
    「不荐」/提示型推荐 → null 不亮；谁下占位值由 store syncRules 落，抽屉如实显示） */
const rec = computed<{ down: DownMode; reason: string } | null>(() => {
  const a = liveStore.advice;
  return full.value && a?.kind === "down"
    ? { down: a.down, reason: a.reason }
    : null;
});

function onScore(v: string | number): void {
  if (full.value) liveStore.setRuleScore(Number(v));
}
function onSingles(v: string | number): void {
  if (full.value) liveStore.setRules({ singles: v === "singles" });
}
function onSwitchSingles(): void {
  if (full.value) liveStore.setRules({ singles: true });
}
function onDown(d: DownMode): void {
  if (full.value) liveStore.setRules({ down: d });
}
function onPairing(v: string | number): void {
  if (full.value) liveStore.setRules({ pairing: v as PairingMode });
}
function onCap(n: number): void {
  if (full.value) liveStore.setRules({ champCap: n });
}
</script>

<style lang="scss" scoped>
/* F-N1 底缘让位：AppSheet 面板默认贴屏底、靠 calc(nav+20px) 内边距躲 nav——本抽屉
   四件套内容长、面板可滚，滚动中内容仍从 nav 亮条后穿过（底缘与 TabBar 视觉重叠）。
   只本抽屉把面板底缘抬到 nav 之上（live 页同款 --nav-total-h 让位口径，PageShell→
   BizBackdrop 同款父覆写 :deep 手法），内边距回落常规值；不动 AppSheet 全局。 */
.rules-sheet :deep(.sheet) {
  bottom: var(--nav-total-h);
  padding-bottom: 20px;
}

/* 球友只读罩层（§4.1）：禁用态观感＝整体压暗＋点击穿透；处理器/store guard 是二三层 */
.ro {
  opacity: 0.45;
  pointer-events: none;
}

/* 改单打提示行：全权者柠檬描边可点；球友平铺不可点 */
.switch-tip {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 9px 12px;
  margin-bottom: 14px;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.03);
  font-size: 13px;
}
.switch-tip.tappable {
  cursor: pointer;
  border-color: rgba(255, 212, 0, 0.45);
}
.switch-tip.tappable:active {
  transform: scale(0.98);
}
.st-k {
  color: var(--lemon);
  font-weight: 700;
  flex: none;
}
.st-r {
  color: var(--dim);
  font-size: 11px;
}

/* 谁下选项 chips（.crow/.cbtn 同观感 + 推荐/选中双标记）：五项塞 AppSeg 过挤，
   且要挂「推荐」角标——AppSeg/OptionChips 均无角标位，本 sheet 内自绘 */
.down-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.down-chip {
  position: relative;
  padding: 9px 14px;
  border-radius: 12px;
  border: 1px solid rgba(245, 241, 232, 0.14);
  background: var(--ink);
  color: var(--dim);
  font-size: 13px;
  font-family: var(--sans);
  cursor: pointer;
  transition: 0.15s;
}
.down-chip.on {
  background: var(--lemon);
  color: var(--ink);
  border-color: var(--lemon);
  font-weight: 700;
}
.rec-tag {
  font-size: 9px;
  font-family: var(--mono);
  border: 1px solid currentColor;
  border-radius: 4px;
  padding: 0 3px;
  margin-left: 5px;
  vertical-align: 1px;
}
.rec-reason {
  display: block;
  margin-top: 8px;
  font-size: 11px;
  color: var(--lemon);
}

/* 连打上限行：stepper ＋ 单位/不限说明（选 0 常驻「当前＝不限」；下限 0=不限） */
.cap-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.cap-hint {
  font-size: 12px;
  color: var(--dim);
}
</style>
