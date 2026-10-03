<template>
  <!-- 组局表单（alpha.html:1299-1398 openLaunch/lfMin/lfCap/publish · P6）。
       新建（无 gameId）/ 改局（带 gameId 带出原值，alpha:1302-1306）复用同一表单；
       编辑态标题「改局 · 名单不动」+ hint（alpha:1316-1318），截止字段只读虚线框（alpha:1327-1329）。
       入口：TabBar FAB / 详情页「改信息」都经 ui.openSheet({type:'launch'})；
       成功后只关弹层 —— toast 由 game store 的 publishGame/editGame 内置（alpha:1393/1398 文案）。 -->
  <view class="lc">
    <!-- alpha:1316 标题（壳层样式同 AppSheet 的 h3/.hint，alpha:558-561；ProfileSheet 同款做法） -->
    <view class="t">{{ isEd ? '改局 · 名单不动' : '组局' }}</view>
    <!-- alpha:1317-1318 -->
    <view class="hint">{{
      isEd
        ? '名单里的人再打开，看到的就是新信息 · 截止时间定死不能改'
        : '从上到下填完点发布 · 发完点局上的 ⤴ 转到群里拉人'
    }}</view>

    <!-- alpha:1319-1320 局名 -->
    <AppField label="局名 · 不填就用「时间 · 地点」自动起">
      <AppInput v-model="lf.name" placeholder="如：新手友好局" />
    </AppField>

    <!-- alpha:1321-1324 时间 chips 5 项 + 自定义输入（选中「自定义…」才显示） -->
    <AppField label="时间 · 哪天几点开打">
      <OptionChips :model-value="timeOn" :options="TIMES" @update:model-value="onTime" />
      <view v-if="timeOn === '自定义…'" class="mt8">
        <AppInput v-model="tCustom" placeholder="自定义：如 周日 15:00" />
      </view>
    </AppField>

    <!-- alpha:1325-1326 时长 chips -->
    <AppField label="打多久">
      <OptionChips :model-value="lf.dur" :options="DURS" @update:model-value="onDur" />
    </AppField>

    <!-- alpha:1327-1329 编辑态：截止定死，只读虚线框；alpha:1330-1332 新建：chips 3 项 + 自定义 -->
    <AppField v-if="isEd" label="组局截止 · 定死不能改">
      <view class="dl-ro">{{ lf.deadline }} · 到点名单锁定，参加者不能再退出</view>
    </AppField>
    <AppField v-else label="组局截止 · 到点名单锁定，低于最少自动终止">
      <OptionChips :model-value="dlOn" :options="DLS" @update:model-value="onDl" />
      <view v-if="dlOn === '自定义…'" class="mt8">
        <AppInput v-model="dCustom" placeholder="自定义：如 周五 12:00" />
      </view>
    </AppField>

    <!-- alpha:1333-1336 地点 chips 4 项 + 手输 -->
    <AppField label="地点 · 球馆名">
      <OptionChips :model-value="venOn" :options="VENS" @update:model-value="onVen" />
      <view v-if="venOn === '手输新场地'" class="mt8">
        <AppInput v-model="vCustom" placeholder="手输新场地：如 亮马河 · 滨河球场" />
      </view>
    </AppField>

    <!-- alpha:1337-1342 人数双 stepper（alpha:1369-1373 联动：min 2-12，cap min+1 至 16） -->
    <AppField label="人数 · 最少 — 最多（满员线）">
      <view class="ppl">
        <text class="ppl-lab">最少</text>
        <AppStepper class="ppl-st" :model-value="lf.min" :min="2" :max="12" @update:model-value="lfMin" />
        <text class="ppl-lab">最多</text>
        <AppStepper class="ppl-st" :model-value="lf.cap" :min="lf.min + 1" :max="16" @update:model-value="lfCap" />
      </view>
      <!-- alpha:1314/1342 人数 hint 实时联动 -->
      <view class="ppl-hint">{{ pplHint }}</view>
    </AppField>

    <!-- alpha:1343-1350 费用 chips + 手输输入（宽 50%） -->
    <AppField label="预计费用 · 总价（人均在局详情里自动摊）">
      <OptionChips :model-value="feeOn" :options="FEES" @update:model-value="onFee" />
      <view v-if="feeOn === '自定义'" class="mt8 fee-in">
        <AppInput v-model="feeCustom" type="number" placeholder="自定义总价：如 350" />
      </view>
    </AppField>

    <!-- alpha:1351-1352 说明 -->
    <AppField label="说明 · 这局什么打法">
      <AppInput v-model="lf.note" placeholder="如：新手友好 / 高手过招 / 迟到排队尾" />
    </AppField>

    <!-- alpha:1353 发布 / 保存修改（pri 通栏黄钮） -->
    <AppButton variant="pri" block @click="publish">{{ isEd ? '保存修改' : '发布' }}</AppButton>
  </view>
</template>

<script setup lang="ts">
/* 组局表单 LaunchSheet（alpha.html:1299-1398 · P6）。
   本地 ref 状态机对应 alpha 的 lf 对象；自定义输入框的值对应 alpha 从 DOM 读的 #lc-tin 等
   （alpha:1376 $in 的「隐藏输入框不取值」语义，改由 v-if + 条件取值实现）。 */
import { computed, onMounted, reactive, ref, watch } from 'vue';
import type { CrowOption } from '@/components/ui/OptionChips.vue';
import AppField from '@/components/ui/AppField.vue';
import AppInput from '@/components/ui/AppInput.vue';
import AppButton from '@/components/ui/AppButton.vue';
import AppStepper from '@/components/ui/AppStepper.vue';
import OptionChips from '@/components/ui/OptionChips.vue';
import { useGameStore } from '@/stores/game';
import { useUiStore } from '@/stores/ui';
import type { PublishInput } from '@/api/types';

const props = defineProps({
  /** 有 gameId = 改局（带原值）；无/查不到 = 新建（alpha:1302-1307，查不到按新建兜底） */
  gameId: { type: Number, default: undefined },
});

const game = useGameStore();
const ui = useUiStore();

/** alpha:1308-1310 chips 选项（逐字） */
const TIMES = ['今晚 19:30', '明晚 19:30', '周六 10:00', '周六 19:30', '自定义…'];
const VENS = ['工体北路 · 京篮匹克球馆', '望京 · 花家地球馆', '五棵松 · 万事达球馆', '手输新场地'];
const DLS = ['打前 2 小时', '前一天 20:00', '自定义…'];
/** alpha:1326/1344-1345 时长与费用（含「手输」= 自定义占位值） */
const DURS: CrowOption[] = [
  { value: 1, label: '1 小时' },
  { value: 1.5, label: '1.5 小时' },
  { value: 2, label: '2 小时' },
  { value: 3, label: '3 小时' },
];
const FEES: CrowOption[] = [
  { value: 200, label: '¥200' },
  { value: 300, label: '¥300' },
  { value: 400, label: '¥400' },
  { value: 600, label: '¥600' },
  { value: '自定义', label: '手输' },
];

/** 编辑态（alpha:1307 isEd=!!ed） */
const isEd = ref(false);

/** alpha:1300/1303-1306 lf 表单状态机（fee 由 feeOn 承载，对应 lf.fee 数字或 '自定义'） */
const lf = reactive({
  gid: 0,
  name: '',
  time: '周六 10:00',
  dur: 2,
  deadline: '打前 2 小时',
  venue: '工体北路 · 京篮匹克球馆',
  min: 4,
  cap: 6,
  note: '',
});
/** chips 当前选中值（= alpha lf.time/lf.deadline/lf.venue/lf.fee 被点 chips 覆写后的值） */
const timeOn = ref('');
const dlOn = ref('');
const venOn = ref('');
const feeOn = ref<string | number>(300);
/** 自定义输入框的值（alpha:1323/1332/1335/1350 的 #lc-tin/#lc-din/#lc-vin/#lc-fin） */
const tCustom = ref('');
const dCustom = ref('');
const vCustom = ref('');
const feeCustom = ref('');

/** 打开时初始化（alpha:1301-1313）。SheetHost 的 v-if 使每次打开都重新挂载 → onMounted 即开表；
   watch 兜底同组件实例上 payload 换 gameId 的情况。 */
function init(): void {
  const ed = props.gameId != null ? game.games.find((x) => x.id === props.gameId) : null; // alpha:1302
  isEd.value = !!ed; // alpha:1307
  const src = ed
    ? { name: ed.name, time: ed.t, dur: ed.dur, deadline: ed.deadline, venue: ed.loc, min: ed.min, cap: ed.cap, fee: ed.fee, note: ed.note || '' } // alpha:1303-1304
    : { name: '', time: '周六 10:00', dur: 2, deadline: '打前 2 小时', venue: '工体北路 · 京篮匹克球馆', min: 4, cap: 6, fee: 300, note: '' }; // alpha:1305-1306
  lf.gid = ed ? ed.id : 0;
  lf.name = src.name;
  lf.time = src.time;
  lf.dur = src.dur;
  lf.deadline = src.deadline;
  lf.venue = src.venue;
  lf.min = src.min;
  lf.cap = src.cap;
  lf.note = src.note;
  timeOn.value = TIMES.includes(src.time) ? src.time : '自定义…'; // alpha:1311
  venOn.value = VENS.includes(src.venue) ? src.venue : '手输新场地'; // alpha:1312
  dlOn.value = DLS.includes(src.deadline) ? src.deadline : '自定义…'; // alpha:1313
  // 自定义输入框带出原值（alpha:1324/1336 对不在 chips 里的原值回填，否则留空）
  tCustom.value = timeOn.value === '自定义…' && !TIMES.includes(src.time) ? src.time : '';
  vCustom.value = venOn.value === '手输新场地' && !VENS.includes(src.venue) ? src.venue : '';
  dCustom.value = ''; // alpha:1332 无初值
  feeCustom.value = ''; // alpha:1350 无初值
  feeOn.value = src.fee; // 数字落在 chips 才亮（含 350 等自定义值：无 chip 亮、手输入框隐藏，alpha:1344-1345 同款行为）
}
onMounted(init);
watch(() => props.gameId, init);

/* —— chips 选择（alpha:1354-1368：点 chip 写回 lf + 切自定义输入框显隐；显隐此处由 v-if 派生）—— */
const onTime = (v: string | number): void => { timeOn.value = String(v); }; // alpha:1354-1357
const onDl = (v: string | number): void => { dlOn.value = String(v); }; // alpha:1358-1361
const onVen = (v: string | number): void => { venOn.value = String(v); }; // alpha:1362-1365
const onFee = (v: string | number): void => { feeOn.value = v; }; // alpha:1366-1368
const onDur = (v: string | number): void => { lf.dur = Number(v); }; // alpha:1358（时长 chips）

/** alpha:1369-1371 lfMin：min 夹 [2,12]（AppStepper 已夹），cap 不足 min+1 时抬到 min+1 */
function lfMin(v: number): void {
  lf.min = v;
  if (lf.cap < lf.min + 1) lf.cap = lf.min + 1;
}
/** alpha:1372-1374 lfCap：cap 夹 [min+1,16]（AppStepper :min/:max 等价实现） */
function lfCap(v: number): void {
  lf.cap = v;
}

/** alpha:1314 人数 hint（computed 随 min/cap 实时更新） */
const pplHint = computed(() => `${lf.min}-${lf.cap} 人 · 不足最少截止时自动终止 · 到最多进候补`);

/** alpha:1375-1398 publish：收集值 → store（toast 在 store 内置）→ 关弹层。
   alpha:1388-1392 改局（名单不动）/ alpha:1394-1397 新建（插最前，我是名单头一个）。 */
function publish(): void {
  // alpha:1378-1380：自定义输入框可见才取值，空则回落 chip 值
  const tSel = timeOn.value === '自定义…' ? tCustom.value.trim() || timeOn.value : timeOn.value;
  const vSel = venOn.value === '手输新场地' ? vCustom.value.trim() || venOn.value : venOn.value;
  const dlSel = dlOn.value === '自定义…' ? dCustom.value.trim() || dlOn.value : dlOn.value;
  // alpha:1381-1382：手输费用 parseInt 失败回落 300
  const feeRaw = feeOn.value === '自定义' ? feeCustom.value.trim() : '';
  const fee = feeRaw ? parseInt(feeRaw, 10) || 300 : typeof feeOn.value === 'number' ? feeOn.value : 300;
  // alpha:1383：局名空则「时间 · 地点」自动起
  const name = lf.name.trim() || `${tSel.split(' ')[0]} · ${vSel.split(' · ').pop()}`;
  const input: PublishInput = {
    name, time: tSel, dur: lf.dur, deadline: dlSel, venue: vSel,
    min: lf.min, cap: lf.cap, fee, note: lf.note.trim(), // alpha:1384 note trim
  };
  if (isEd.value) game.editGame(lf.gid, input);
  else {
    game.publishGame(input);
    uni.switchTab({ url: '/pages/meet/meet' }); // alpha:1397 发布成功 go('meet')
  }
  ui.closeSheet(); // alpha:1393/1398 closeSheet
}
</script>

<style lang="scss" scoped>
/* alpha:558-561 壳层标题/hint（.t/.hint 同 ProfileSheet 做法） */
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
/* alpha:1323/1332/1335/1350 自定义输入框 margin-top:8px */
.mt8 {
  margin-top: 8px;
}
/* alpha:1327-1329 编辑态截止只读框（.sub 底色字 + 虚线描边，逐字） */
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
/* alpha:1339/1341 「最少/最多」.sub 11px flex:none */
.ppl-lab {
  color: var(--dim);
  font-size: 11px;
  flex: none;
}
/* alpha:1340/1343 stepper flex:1 */
.ppl-st {
  flex: 1;
}
/* alpha:1342 人数 hint .sub 11px margin-top:6px */
.ppl-hint {
  color: var(--dim);
  font-size: 11px;
  margin-top: 6px;
}
/* alpha:1350 费用手输入框 width:50% */
.fee-in {
  width: 50%;
}
</style>
