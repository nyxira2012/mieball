<template>
  <!-- 沙盒结算窗（2.7 批3，复刻 EndSettleModal 长相手感——真局组件零改动）：
       开关单一源=sandbox.settleWindow（到分自动开，一次一扇，遮罩不可关——
       唯一非上传出口是「暂不结算 · 接着打」）。比分吃本机账、窗内可直录纠错
       （参与卡第二场「点到 11 自动弹窗、窗内可直录」）；胜方点选闸与真局同式
       （分低方选不中、平分双方可点）。±涨跌预览是写死示例数（data.ELO_PREVIEW
       ——规格 §6：界面一个数都不自算，胜败与比分无关、改比分数字不变化），
       胜队在前、访客行带「不计积分」标识。确认直调 store（战报+轮转在 engine） -->
  <view class="sb-swrap" :class="{ on: win != null }">
    <view class="sb-smask" />
    <view class="sb-smodal">
      <view class="sb-skick">SETTLE · {{ court?.no }}号场</view>
      <view class="sb-stitle">上传<text class="bem">比分</text></view>

      <!-- 胜方点选：A 柠檬 / B 冰蓝；分低方选不中 -->
      <view class="sb-winp">
        <view
          class="sb-wp"
          :class="{ on: winA === true, off: !canA }"
          @click="pick('a')"
        >
          <view class="t">TEAM A</view>
          <view class="n">{{ namesA }}</view>
        </view>
        <view
          class="sb-wp b"
          :class="{ on: winA === false, off: !canB }"
          @click="pick('b')"
        >
          <view class="t">TEAM B</view>
          <view class="n">{{ namesB }}</view>
        </view>
      </view>

      <!-- 大比分直录：空视同 0、失焦归一；写回本机账——暂不结算后接着打的就是纠偏后的分 -->
      <view class="sb-sscore">
        <input
          class="num a"
          :value="saText"
          type="number"
          @input="onScore('a', $event)"
          @blur="onBlurScore('a')"
        />
        <view class="c">:</view>
        <input
          class="num b"
          :value="sbText"
          type="number"
          @input="onScore('b', $event)"
          @blur="onBlurScore('b')"
        />
      </view>
      <view class="sb-stools">
        <text class="edit">点比分格 · 直接输数字</text>
      </view>

      <!-- ±积分预览（写死示例数，胜队在前）；访客带「不计积分」标识照真局 -->
      <view v-for="r in preview" :key="r.name" class="sb-elo">
        <text class="nm"
          >{{ r.name
          }}<text v-if="r.guest" class="gtag">访客 · 不计积分</text></text
        >
        <text class="d" :class="r.up ? 'up' : 'dn'">{{
          r.up ? `+${r.d}` : `−${Math.abs(r.d)}`
        }}</text>
      </view>
      <view class="sb-snote">±积分为结算预演 · 确认后落账生效</view>

      <view class="sb-sbtns">
        <AppButton
          variant="pri"
          block
          :disabled="!canConfirm"
          @click="onConfirm"
          >确认上传 · 落账</AppButton
        >
        <view v-if="winA === null" class="sb-fulltip"
          >平分不分胜负 · 先点胜方</view
        >
        <AppButton variant="ghost" block @click="sandbox.closeSettleWindow()"
          >暂不结算 · 接着打</AppButton
        >
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
/* 本地态只有 winA/sa/sb（EndSettleModal 同构）；编排归 sandbox store（confirmSettle
   关窗清账、closeSettleWindow 保分接着打）。followWinner/canPick 两行谓词就地写——
   真局版单一源在 live store 模块，沙盒旁挂原则不反向依赖真局模块（架构总决策） */
import { computed, ref, watch } from "vue";
import AppButton from "@/components/ui/AppButton.vue";
import { useSandboxStore } from "@/stores/sandbox";
import { pOf } from "@/sandbox/engine";
import { ELO_PREVIEW } from "@/sandbox/data";

const sandbox = useSandboxStore();

/** 窗位单一源在 store（null=关） */
const win = computed(() => sandbox.settleWindow);
const court = computed(() =>
  sandbox.state?.courts.find((c) => c.no === win.value?.courtNo),
);

/* 本地态：胜方可点选；比分两格文本直录 */
const winA = ref<boolean | null>(null);
const saText = ref("0");
const sbText = ref("0");
const sa = computed(() => Number(saText.value || "0"));
const sb = computed(() => Number(sbText.value || "0"));

/** 开窗对齐：按本机账重置本地态（一次一扇，窗开着不会换片）；胜方预选=分高方 */
watch(
  win,
  (w) => {
    if (!w) return;
    const acc = sandbox.localScores[w.courtNo];
    saText.value = String(acc?.sa ?? 0);
    sbText.value = String(acc?.sb ?? 0);
    winA.value = followWinner(sa.value, sb.value);
  },
  { immediate: true },
);

/** 分低方选不中；平分双方均可点（真局 §4.6 同式） */
const canA = computed(() => sa.value >= sb.value);
const canB = computed(() => sb.value >= sa.value);
const canConfirm = computed(() => winA.value !== null);

function followWinner(a: number, b: number): boolean | null {
  if (a > b) return true;
  if (b > a) return false;
  return null;
}

function pick(side: "a" | "b"): void {
  if (side === "a" ? !canA.value : !canB.value) return;
  winA.value = side === "a";
}

/** 比分直录：只收非负整数、至多 3 位；输入即写回本机账 */
function onScore(side: "a" | "b", ev: Event): void {
  const raw =
    (ev as { detail?: { value?: string } }).detail?.value ??
    (ev.target as { value?: string } | null)?.value ??
    "";
  const digits = raw.replace(/\D/g, "").slice(0, 3);
  if (side === "a") saText.value = digits;
  else sbText.value = digits;
  winA.value = followWinner(sa.value, sb.value);
  writeBack();
}

/** 失焦归一：空与前置零收成规范十进制 */
function onBlurScore(side: "a" | "b"): void {
  if (side === "a") saText.value = String(sa.value);
  else sbText.value = String(sb.value);
}

/** 写回本机账（懒建：没点过一分、窗内一次直录的主场景守卫会静默丢分） */
function writeBack(): void {
  const w = win.value;
  if (!w) return;
  const acc = (sandbox.localScores[w.courtNo] ??= {
    sa: 0,
    sb: 0,
    history: [],
  });
  acc.sa = sa.value;
  acc.sb = sb.value;
}

const namesA = computed(() => sideNames("a").join(" / "));
const namesB = computed(() => sideNames("b").join(" / "));
function sideNames(side: "a" | "b"): string[] {
  const ids = side === "a" ? (court.value?.a ?? []) : (court.value?.b ?? []);
  const s = sandbox.state;
  return s ? ids.map((id) => pOf(s, id).name) : [];
}

/** ±积分预演：写死小表组装（胜方队各 +win、败方队各 −|lose|，胜队在前）；
    名册没上榜的人不显行（教学剧本不走到） */
const preview = computed(() => {
  if (winA.value === null || !court.value) return [];
  const s = sandbox.state;
  if (!s) return [];
  const rowsOf = (ids: number[], up: boolean) =>
    ids
      .map((id) => pOf(s, id))
      .flatMap((p) => {
        const e = ELO_PREVIEW[p.name];
        if (!e) return [];
        return [{ name: p.name, guest: !!p.guest, up, d: up ? e.win : e.lose }];
      });
  return [
    ...rowsOf(winA.value ? court.value.a : court.value.b, true),
    ...rowsOf(winA.value ? court.value.b : court.value.a, false),
  ];
});

function onConfirm(): void {
  const c = court.value;
  if (!c || winA.value === null) return;
  sandbox.confirmSettle(c.no, winA.value ? "a" : "b", sa.value, sb.value);
}
</script>

<style lang="scss" scoped>
/* z-110 同 EndSettleModal 层级；遮罩不可关（关窗丢待结的账）——transition + visibility
   同款收口（backdrop-filter 对 opacity:0 照样生效，须连 visibility 一起收） */
.sb-swrap {
  position: fixed;
  inset: 0;
  z-index: 110;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  pointer-events: none;
}
.sb-swrap.on {
  pointer-events: auto;
}
.sb-smask {
  position: absolute;
  inset: 0;
  background: rgba(8, 8, 11, 0.72);
  backdrop-filter: blur(3px);
  opacity: 0;
  visibility: hidden;
  transition:
    opacity 0.22s,
    visibility 0.22s;
}
.sb-swrap.on .sb-smask {
  opacity: 1;
  visibility: visible;
}
.sb-smodal {
  position: relative;
  width: 82%;
  max-width: 330px;
  background: linear-gradient(180deg, var(--ink3), var(--ink2));
  border: 1px solid rgba(255, 212, 0, 0.25);
  border-radius: var(--r-lg);
  padding: 20px 16px 16px;
  transform: scale(0.94);
  opacity: 0;
  transition: 0.22s;
  pointer-events: none;
}
.sb-swrap.on .sb-smodal {
  transform: scale(1);
  opacity: 1;
  pointer-events: auto;
}
.sb-skick {
  text-align: center;
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.34em;
  color: var(--dim);
  text-transform: uppercase;
}
.sb-stitle {
  text-align: center;
  font-family: var(--disp);
  font-size: 24px;
  margin: 6px 0 14px;
}
.sb-stitle .bem {
  color: var(--lemon);
}

/* 胜方二选一 */
.sb-winp {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.sb-wp {
  flex: 1;
  text-align: center;
  border: 1px solid rgba(245, 241, 232, 0.16);
  border-radius: 13px;
  background: var(--ink);
  padding: 10px 4px;
  cursor: pointer;
  transition: 0.15s;
  min-width: 0;
}
.sb-wp .t {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.18em;
  color: var(--dim);
}
.sb-wp .n {
  font-size: 12px;
  font-weight: 700;
  margin-top: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sb-wp.on {
  border-color: var(--lemon);
  background: rgba(255, 212, 0, 0.08);
}
.sb-wp.on .t {
  color: var(--lemon);
}
.sb-wp.b.on {
  border-color: var(--ice);
  background: rgba(111, 231, 255, 0.08);
}
.sb-wp.b.on .t {
  color: var(--ice);
}
.sb-wp.off {
  opacity: 0.45;
  pointer-events: none;
}

/* 大比分输入格（uni-input 内层 wrapper 恒 100% 宿主内容区，无高有值即塌 0——显式定高） */
.sb-sscore {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  margin: 4px 0 10px;
}
.sb-sscore .num {
  width: 88px;
  height: 68px;
  border: 1px solid rgba(245, 241, 232, 0.16);
  border-radius: 13px;
  background: var(--ink);
  text-align: center;
  font-family: var(--disp);
  font-size: 40px;
  color: var(--cream);
}
.sb-sscore .num.a {
  color: var(--lemon);
}
.sb-sscore .num.b {
  color: var(--ice);
}
.sb-sscore .c {
  font-family: var(--disp);
  font-size: 22px;
  color: var(--coral);
}
.sb-stools {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
}
.edit {
  font-size: 11px;
  color: var(--dim);
}

/* ±积分预览行 */
.sb-elo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid rgba(245, 241, 232, 0.08);
  border-radius: 12px;
  background: var(--ink2);
  margin-bottom: 6px;
}
.sb-elo .nm {
  flex: 1;
  font-size: 12px;
  font-weight: 600;
}
.sb-elo .gtag {
  margin-left: 6px;
  font-family: var(--mono);
  font-size: 9px;
  font-weight: 400;
  color: var(--lilac);
}
.sb-elo .d {
  font-family: var(--mono);
  font-size: 13px;
  font-weight: 700;
}
.sb-elo .d.up {
  color: var(--lemon);
}
.sb-elo .d.dn {
  color: var(--coral);
}
.sb-snote {
  text-align: center;
  font-size: 10px;
  color: var(--dim);
  margin: 8px 0 12px;
}

.sb-sbtns {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sb-fulltip {
  text-align: center;
  font-size: 11px;
  color: var(--dim);
}
</style>
