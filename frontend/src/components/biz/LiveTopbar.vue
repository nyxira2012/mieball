<template>
  <!-- 块一顶条（temp/打球页原型 .topbar 逐字）：局的身份证——banner（kicker+LIVE 呼吸灯+brand 大字
       +地址行+组织者 chip+二维码钮）→ 遥测三格（剩余时间倒计时/场地号直填/赛制模式入口）→ 单行轮播 ticker。
       点人入口在卡与候场条，这里只出 qr/rules 两个编排事件。 -->
  <view v-if="L" class="topbar">
    <view class="banner-top">
      <view class="banner-meta">
        <view class="kicker"><view class="live-dot" /> LIVE · 第 {{ L.round + 1 }} 轮</view>
        <view class="brand-t">{{ L.g.name }}<text v-if="venue" class="bem"> · {{ venue }}</text></view>
        <view class="banner-loc">
          <text class="loc-txt">{{ L.g.loc }}</text>
          <text class="chip ok">{{ orgChip }}</text>
        </view>
      </view>
      <!-- 签到二维码（原型 qrbtn：三个角框 + 三粒点；svg 不可进 uni 模板 → view 绘制） -->
      <view class="qrbtn" @click="emit('qr')">
        <view class="qr-ic">
          <view class="qr-box tl" /><view class="qr-box tr" /><view class="qr-box bl" />
          <view class="qr-dot d1" /><view class="qr-dot d2" /><view class="qr-dot d3" />
        </view>
      </view>
    </view>

    <view class="telemetry-bar">
      <view class="telem-cell">
        <text class="telem-k">剩余时间</text>
        <text class="timer-val">{{ timerTxt }}</text>
      </view>
      <view class="telem-cell">
        <text class="telem-k">打球场地</text>
        <!-- 组织者直填场号（原型 input：虚线下划线，blur/回车提交，校验不过回退 store 值）；非 org 只读文本 -->
        <view class="telem-v">
          <input
            v-if="org"
            class="courts-inp"
            :value="courtsText"
            placeholder="如 3、4"
            @input="onCourtsInput"
            @blur="commitCourts"
            @confirm="commitCourts"
          />
          <text v-else class="courts-ro">{{ courtsText }}</text>
          <text class="courts-unit">片</text>
        </view>
      </view>
      <view class="telem-cell mode-cell" @click="emit('rules')">
        <text class="telem-k">赛制模式</text>
        <view class="telem-v mode-v">{{ L.g.score }}分 · {{ MODE_NAMES[L.g.mode] }} ▾</view>
      </view>
    </view>

    <!-- 单行轮播（3.2s 换条，前缀 ▸；空数组整行隐藏）。不用 ui/Ticker：它是通栏 marquee 版式，
         顶条单行轮播是另一形态（首页 Ticker 塞不进 10px 高的 border-top 行，二者的动画机制也不同） -->
    <view v-if="curTick" class="tb-ticker">▸ <text v-if="curTick.hi" class="tk-hi">{{ curTick.hi }}</text>{{ curTick.txt }}</view>
  </view>
</template>

<script setup lang="ts">
/* 块一顶条（2.1 §3）：无 props——数据全读 live store（isOrg(L.g) 判组织者），
   emit 只留页面编排：qr（开二维码浮层）/ rules（开规则抽屉）。 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useLiveStore } from '@/stores/live';
import { isOrg, MODE_NAMES, venueOf } from '@/utils/format';
import { gameTime } from '@/utils/time';
import { pById } from '@/utils/rotate';
import { U } from '@/api';

const emit = defineEmits<{ (e: 'qr'): void; (e: 'rules'): void }>();

const liveStore = useLiveStore();
const L = computed(() => liveStore.live);
const org = computed(() => (L.value ? isOrg(L.value.g) : false));

/** brand-t 高亮场馆词（口径在 utils/format 的 venueOf 单一源）；空则连「 · 」都不拼 */
const venue = computed(() => (L.value ? venueOf(L.value.g) : ''));
const orgChip = computed(() => (org.value ? `组织者 · ${L.value!.g.organizer.name}` : `球友 · ${U.me.name}`));

/* ---------- 剩余时间倒计时：结束时刻（开打 + dur）只随局变化，拆开缓存——
     否则每秒重算都把固定的开打时间串重新 gameTime 解析一遍 ---------- */
const now = ref(Date.now());
let secTimer: ReturnType<typeof setInterval> | null = null;
onMounted(() => {
  secTimer = setInterval(() => { now.value = Date.now(); }, 1000);
});
onUnmounted(() => { if (secTimer) clearInterval(secTimer); });
const endAt = computed(() => {
  const g = L.value?.g;
  if (!g) return null;
  return gameTime(g.t).getTime() + g.dur * 3600e3;
});
const timerTxt = computed(() => {
  if (endAt.value == null) return '0:00:00';
  const s = Math.max(0, Math.floor((endAt.value - now.value) / 1000));
  const h = Math.floor(s / 3600);
  return `${h}:${String(Math.floor((s % 3600) / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
});

/* ---------- 场地号直填（组织者）：booked 去「号」展示；blur/confirm 提交，不过回退 store 值 ---------- */
const storeTxt = computed(() => (L.value?.g.booked ?? []).map((b) => b.replace(/号$/, '')).join('、'));
const courtsText = ref(storeTxt.value);
watch(storeTxt, (v) => { courtsText.value = v; });
function onCourtsInput(ev: Event): void {
  const detail = (ev as { detail?: { value?: unknown } }).detail;
  courtsText.value = detail && typeof detail.value === 'string' ? detail.value : courtsText.value;
}
function commitCourts(): void {
  if (!liveStore.setCourtsInput(courtsText.value)) courtsText.value = storeTxt.value; // toast 在 store
}

/* ---------- 单行轮播：history[0] 战报 → 下一场已排 → 候场人数，3.2s 换条 ---------- */
const tickItems = computed<{ hi: string; txt: string }[]>(() => {
  const l = L.value;
  if (!l) return [];
  const out: { hi: string; txt: string }[] = [];
  const h = l.history[0];
  if (h) out.push({ hi: `${h.names} ${h.sa}:${h.sb}`, txt: ' 拿下' });
  if (l.queue.length) {
    // 过滤名册查不到的 id（建号换 id 的 mock 路径），不出「—」占位名
    const names = l.queue
      .slice(0, 4)
      .map((id) => pById(l, id)?.name)
      .filter((n): n is string => !!n)
      .join(' / ');
    out.push({ hi: '', txt: `下一场已排：${names}` });
  }
  out.push({ hi: '', txt: `候场 ${l.queue.length} 人` });
  return out;
});
const tickIdx = ref(0);
let tickTimer: ReturnType<typeof setInterval> | null = null;
onMounted(() => {
  tickTimer = setInterval(() => { tickIdx.value++; }, 3200);
});
onUnmounted(() => { if (tickTimer) clearInterval(tickTimer); });
const curTick = computed(() => tickItems.value[tickIdx.value % tickItems.value.length]);
</script>

<style lang="scss" scoped>
/* ---------- 原型 .topbar/.banner-top/.banner-meta（逐字换 tokens） ---------- */
.topbar {
  background: rgba(14, 14, 18, 0.92);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--line);
  z-index: 5;
  flex: none;
  position: relative;
}
.banner-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: calc(env(safe-area-inset-top) + 14px) 14px 0;
  gap: 10px;
}
.banner-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.kicker {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.3em;
  text-transform: uppercase;
  color: var(--lemon);
}
.brand-t {
  font-family: var(--disp);
  font-size: 26px;
  font-weight: 400;
  line-height: 1.05;
  margin: 4px 0 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.brand-t .bem {
  color: var(--lemon);
}
.banner-loc {
  font-size: 12px;
  color: var(--dim);
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.loc-txt {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chip {
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 400;
  letter-spacing: 0.08em;
  padding: 2px 8px;
  border-radius: 99px;
  border: 1px solid rgba(245, 241, 232, 0.16);
  background: none;
  flex: none;
}
.chip.ok {
  border-color: rgba(255, 212, 0, 0.5);
  color: var(--lemon);
}
.live-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--coral);
  flex: none;
  box-shadow: 0 0 0 0 rgba(255, 90, 54, 0.6);
  animation: pulse 1.6s infinite;
}
/* 二维码钮（原型 qrbtn svg 的 view 等价：3 角框 + 3 粒点） */
.qrbtn {
  flex: none;
  width: 34px;
  height: 34px;
  border-radius: 11px;
  cursor: pointer;
  border: 1px solid rgba(255, 212, 0, 0.35);
  background: rgba(255, 212, 0, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: 0.15s;
}
.qrbtn:active {
  transform: scale(0.92);
}
.qr-ic {
  position: relative;
  width: 17px;
  height: 17px;
}
.qr-box {
  position: absolute;
  width: 6px;
  height: 6px;
  border: 1.5px solid var(--lemon);
  border-radius: 1px;
}
.qr-box.tl { top: 0; left: 0; }
.qr-box.tr { top: 0; right: 0; }
.qr-box.bl { bottom: 0; left: 0; }
.qr-dot {
  position: absolute;
  width: 2.5px;
  height: 2.5px;
  background: var(--lemon);
}
.qr-dot.d1 { top: 8px; left: 8px; }
.qr-dot.d2 { top: 11px; left: 11px; }
.qr-dot.d3 { top: 13.5px; left: 13.5px; }

/* ---------- 遥测三格（原型 .telemetry-bar/.telem-cell） ---------- */
.telemetry-bar {
  display: grid;
  grid-template-columns: 1.1fr 1fr 1.1fr;
  gap: 8px;
  margin: 12px 14px 0;
}
.telem-cell {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(245, 241, 232, 0.08);
  border-radius: 12px;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 2px;
  transition: 0.15s;
}
.mode-cell {
  cursor: pointer;
}
.mode-cell:active {
  transform: scale(0.97);
  border-color: var(--lemon);
}
.telem-k {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
  letter-spacing: 0.15em;
  text-transform: uppercase;
}
.telem-v {
  font-family: var(--disp);
  font-size: 16px;
  color: var(--lemon);
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
}
.timer-val {
  font-family: var(--mono);
  font-weight: 700;
  color: var(--coral);
  letter-spacing: 0.05em;
  font-size: 14px;
}
.mode-v {
  font-family: var(--sans);
  font-size: 13px;
  font-weight: 700;
}
/* 场号直填（原型 .telem-v input：虚线下划线，focus 变实线）；非 org 纯文本同位 */
.courts-inp {
  width: 76px;
  background: none;
  border: none;
  outline: none;
  border-bottom: 1px dashed rgba(255, 212, 0, 0.35);
  color: var(--lemon);
  font-family: var(--mono);
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 0.05em;
  padding: 0 2px 1px;
  height: 20px;
}
.courts-inp:focus {
  border-bottom-color: var(--lemon);
  border-bottom-style: solid;
}
.courts-ro {
  font-family: var(--mono);
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 0.05em;
}
.courts-unit {
  font-size: 10px;
  color: var(--dim);
}

/* ---------- 单行轮播（原型 .tb-ticker：border-top 收口顶条） ---------- */
.tb-ticker {
  padding: 10px 14px;
  margin-top: 12px;
  border-top: 1px solid var(--line);
  font-size: 10px;
  color: var(--dim);
  white-space: nowrap;
  overflow: hidden;
}
.tk-hi {
  color: var(--lemon);
  font-weight: 600;
}
</style>
