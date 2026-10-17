<template>
  <!-- 块一顶条（temp/打球页原型 .topbar 逐字）：局的身份证——banner（kicker+LIVE 呼吸灯+brand 大字
       +地址行+组织者 chip+二维码钮）→ 遥测三格（剩余时间倒计时/场地号直填/赛制模式入口）→ 单行轮播 ticker。
       点人入口在卡与候场条，这里只出 qr/rules 两个编排事件。 -->
  <view v-if="L" class="topbar">
    <view class="banner-top">
      <view class="banner-meta">
        <view class="kicker"
          ><view class="live-dot" /> LIVE · 第 {{ L.round + 1 }} 轮</view
        >
        <view class="brand-t">{{ L.g.name }}</view>
        <view class="banner-loc">
          <text class="loc-txt">{{ L.g.venueAddress || L.g.venueName }}</text>
          <text class="chip ok">{{ orgChip }}</text>
        </view>
      </view>
      <!-- 右侧动作列：签到二维码（原型 qrbtn）＋ 底账/散场（2.3 §4.9：散场钮按
           canEndLive 可见——组织者，或组织者已标早退时的管理员代收；点它进清扫流，
           由页面编排；散场后现场转回看，钮消失，底账仍可查） -->
      <view class="top-acts">
        <view class="qrbtn" @click="emit('qr')">
          <view class="qr-ic">
            <view class="qr-box tl" /><view class="qr-box tr" /><view
              class="qr-box bl"
            />
            <view class="qr-dot d1" /><view class="qr-dot d2" /><view
              class="qr-dot d3"
            />
          </view>
        </view>
        <view v-if="full" class="mini-act" @click="emit('ledger')">底账</view>
        <view
          v-if="canEnd && !L.endedAt"
          class="mini-act danger"
          @click="emit('end')"
          >散场</view
        >
      </view>
    </view>

    <view class="telemetry-bar">
      <view class="telem-cell">
        <text class="telem-k">剩余时间</text>
        <text class="timer-val">{{ timerTxt }}</text>
      </view>
      <view
        class="telem-cell"
        :class="{ 'courts-cell': full }"
        @click="full && emit('courts')"
      >
        <text class="telem-k">打球场地</text>
        <!-- 只读短标签（2026-10-17 顶条长条输入退役）：「16、5号场」吃 courtsShortLabel
             单一源；全权者点格子弹改场号面板（逐框组件），球友只读不响应 -->
        <view class="telem-v courts-v">{{ courtsLabel }}</view>
      </view>
      <view class="telem-cell mode-cell" @click="emit('rules')">
        <text class="telem-k">规则设置</text>
        <!-- 读 rules 四件套里的两件：配对规则 + 谁下——单双打不进格（对局卡头已有
             「双打 · 11分」）。一行摆：配对当主字、谁下缩成小尾巴同行跟，分隔点
             挂尾巴头上（用户裁决：点不在尾巴后面挂）；最长组合（积分均衡+全上全下）
             在标准屏贴边放得下、格子高度与邻格齐平不撑高整排；窄屏尾巴省略兜底
             （全量规则本就在抽屉里） -->
        <view class="telem-v mode-v">
          <text class="mv-pair">{{ PAIRING_NAMES[L.rules.pairing] }}</text>
          <text class="mv-down">· {{ DOWN_NAMES[L.rules.down] }}</text>
        </view>
      </view>
    </view>

    <!-- 单行轮播（3.2s 换条，前缀 ▸；空数组整行隐藏）。不用 ui/Ticker：它是通栏 marquee 版式，
         顶条单行轮播是另一形态（首页 Ticker 塞不进 10px 高的 border-top 行，二者的动画机制也不同） -->
    <view v-if="curTick" class="tb-ticker"
      >▸ <text v-if="curTick.hi" class="tk-hi">{{ curTick.hi }}</text
      >{{ curTick.txt }}</view
    >
  </view>
</template>

<script setup lang="ts">
/* 块一顶条（2.1 §3）：无 props——数据全读 live store；emit 只留页面编排：qr / rules。 */
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useLiveStore } from "@/stores/live";
import { useUserStore } from "@/stores/user";
import { courtsShortLabel, DOWN_NAMES, PAIRING_NAMES } from "@/utils/format";
import { pById } from "@/utils/rotate";

const emit = defineEmits<{
  (e: "qr"): void;
  (e: "rules"): void;
  (e: "ledger"): void;
  (e: "end"): void;
  (e: "courts"): void;
}>();

const liveStore = useLiveStore();
const userStore = useUserStore();
const L = computed(() => liveStore.live);
/** 全权（组织者 ∨ 管理员）单一源在 store；组织者 chip 按视图身份旗（管理员不算组织者） */
const full = computed(() => liveStore.isFullPower);
/** 散场权（§4.9 组织者独占 + 组织者早退时管理员代收）：散场钮可见性单一源在 store */
const canEnd = computed(() => liveStore.canEndLive);

const orgChip = computed(() =>
  L.value && liveStore.liveView?.isOrganizer
    ? `组织者 · ${L.value.g.organizer.nickname}`
    : `球友 · ${userStore.me.name}`,
);

/* ---------- 剩余时间倒计时：结束时刻（ISO）只随局变化，拆开缓存 ---------- */
const now = ref(Date.now());
let secTimer: ReturnType<typeof setInterval> | null = null;
onMounted(() => {
  secTimer = setInterval(() => {
    now.value = Date.now();
  }, 1000);
});
onUnmounted(() => {
  if (secTimer) clearInterval(secTimer);
});
const endAt = computed(() =>
  L.value ? new Date(L.value.g.endAt).getTime() : null,
);
const timerTxt = computed(() => {
  if (endAt.value == null) return "0:00:00";
  const s = Math.max(0, Math.floor((endAt.value - now.value) / 1000));
  const h = Math.floor(s / 3600);
  return `${h}:${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
});

/* ---------- 打球场地只读短标签：「16、5号场」（单一源 format.courtsShortLabel；
     改场号走全权者点格弹出的逐框面板，长条直填已退役） ---------- */
const courtsLabel = computed(() => courtsShortLabel(L.value?.g.courts ?? []));

/* ---------- 单行轮播：feed 战报句（新到旧优先）→ history[0] 战报 → 下一场已排 → 候场人数，3.2s 换条 ---------- */
const tickItems = computed<{ hi: string; txt: string }[]>(() => {
  const l = L.value;
  if (!l) return [];
  const out: { hi: string; txt: string }[] = l.feed.map((txt) => ({
    hi: "",
    txt,
  }));
  const h = l.history[0];
  if (h) out.push({ hi: `${h.names} ${h.sa}:${h.sb}`, txt: " 拿下" });
  if (l.queue.length) {
    // 过滤名册查不到的 id（建号换 id 的 mock 路径），不出「—」占位名
    const names = l.queue
      .slice(0, 4)
      .map((id) => pById(l, id)?.name)
      .filter((n): n is string => !!n)
      .join(" / ");
    out.push({ hi: "", txt: `下一场已排：${names}` });
  }
  out.push({ hi: "", txt: `候场 ${l.queue.length} 人` });
  return out;
});
const tickIdx = ref(0);
let tickTimer: ReturnType<typeof setInterval> | null = null;
onMounted(() => {
  tickTimer = setInterval(() => {
    tickIdx.value++;
  }, 3200);
});
onUnmounted(() => {
  if (tickTimer) clearInterval(tickTimer);
});
const curTick = computed(
  () => tickItems.value[tickIdx.value % tickItems.value.length],
);
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
/* 右侧动作列：qrbtn 下方叠 底账/散场 小钮（mono 小字胶囊，同徽章语言） */
.top-acts {
  flex: none;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 6px;
}
.mini-act {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.2em;
  color: var(--dim);
  border: 1px solid rgba(245, 241, 232, 0.16);
  border-radius: 9px;
  padding: 4px 8px;
  text-align: center;
  cursor: pointer;
  transition: 0.15s;
}
.mini-act:active {
  transform: scale(0.94);
}
/* 散场=危险动作位：珊瑚色示警（确认流在页面层，A3） */
.mini-act.danger {
  color: var(--coral);
  border-color: rgba(255, 90, 54, 0.4);
  background: rgba(255, 90, 54, 0.08);
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
.qr-box.tl {
  top: 0;
  left: 0;
}
.qr-box.tr {
  top: 0;
  right: 0;
}
.qr-box.bl {
  bottom: 0;
  left: 0;
}
.qr-dot {
  position: absolute;
  width: 2.5px;
  height: 2.5px;
  background: var(--lemon);
}
.qr-dot.d1 {
  top: 8px;
  left: 8px;
}
.qr-dot.d2 {
  top: 11px;
  left: 11px;
}
.qr-dot.d3 {
  top: 13.5px;
  left: 13.5px;
}

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
  color: var(
    --cream
  ); /* 倒计时改文字暖白（2026-10-17 用户裁决）：珊瑚橙红让位给警示位专用 */
  letter-spacing: 0.05em;
  font-size: 14px;
}
/* 规则设置格（2026-10-17 用户裁决）：这格是入口不是遥测——标签标黄、内容改文字白 */
.mode-cell .telem-k {
  color: var(--lemon);
}
/* 规则设置格（一行摆）：配对当主字、谁下缩成小尾巴同行跟——行高与邻格齐平。
   最长组合贴边刚好放得下；尾巴允许收缩截断（省略号）兜窄屏 */
.mode-v {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-top: 2px;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
}
.mv-pair {
  font-family: var(--sans);
  font-size: 12px;
  font-weight: 700;
  color: var(--cream);
  flex: none;
}
.mv-down {
  font-family: var(--sans);
  font-size: 9px;
  font-weight: 700;
  color: var(--cream);
  opacity: 0.75;
  flex: 0 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}
/* 场地格只读标签：短标签可能比格宽（多片「1、2、3号场」），小字收着显；
   全权者整格可点（telem-cell 上挂 courts-cell 类给按压反馈） */
.courts-v {
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.courts-cell {
  cursor: pointer;
}
.courts-cell:active {
  transform: scale(0.97);
  border-color: var(--lemon);
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
