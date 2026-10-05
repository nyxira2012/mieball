<template>
  <!-- 签到二维码浮层（temp/打球页原型 .qr-wrap/.qr-card 逐字）：全屏深遮罩 blur，点任意处关。
       码图为前端演示图（真码后端接）——照原型 drawQr 的伪随机图案，rand 混入 g.id 作 seed 确定性渲染。 -->
  <view class="qrwrap" :class="{ on: visible }" @click="emit('close')">
    <view class="qr-card" @click.stop="emit('close')">
      <view class="qr-box">
        <!-- 三个定位角（7 格外框深 / 5 格奶油 / 3 格深，原型 finder 逐字） -->
        <view v-for="(f, i) in finders" :key="`f${i}`" class="finder" :style="{ left: f.l + 'px', top: f.t + 'px' }">
          <view class="f2"><view class="f3" /></view>
        </view>
        <!-- 数据点：非定位角区 rand>0.52 落深格 -->
        <view v-for="(d, i) in dots" :key="`d${i}`" class="cell" :style="{ left: d.l + 'px', top: d.t + 'px' }" />
      </view>
    </view>
    <view class="qr-meta">
      <view class="n">{{ metaName }}</view>
      <view class="s">已到场 {{ arrived }} 人 · LIVE</view>
      <view class="hint">扫码签到进场 · <text class="hi">没报名的空降也扫这码</text></view>
      <view class="s s2">点一下关闭</view>
    </view>
  </view>
</template>

<script setup lang="ts">
/* 二维码浮层（2.1 §2 扫码签到）：无本地态——已到场人数实时读 roster，码图 seed=g.id 确定性
   （同一局每次打开同一张图，computed 即「生成一次」，id 局内不变）。svg 不可进 uni 模板 → view 网格。 */
import { computed } from 'vue';
import { useLiveStore, isArrived } from '@/stores/live';
import { venueOf } from '@/utils/format';

defineProps({
  visible: { type: Boolean, default: false },
});
const emit = defineEmits<{ (e: 'close'): void }>();

const liveStore = useLiveStore();

/** 局名 + 场馆词（口径在 utils/format 的 venueOf 单一源） */
const metaName = computed(() => {
  const g = liveStore.live?.g;
  if (!g) return '';
  const v = venueOf(g);
  return v ? `${g.name} ${v}` : g.name;
});
const arrived = computed(
  () => (liveStore.live?.roster ?? []).filter((p) => isArrived(p.check)).length,
);

/* ---------- 假码图案（原型 drawQr：n=25 cell=8 pad=2；rand 混入 g.id 作 seed） ---------- */
const N = 25;
const CELL = 8;
const PAD = 2;
const finders = [
  { l: PAD * CELL, t: PAD * CELL },
  { l: (PAD + N - 7) * CELL, t: PAD * CELL },
  { l: PAD * CELL, t: (PAD + N - 7) * CELL },
];
const dots = computed<{ l: number; t: number }[]>(() => {
  const seed = liveStore.live?.g.id ?? 0;
  const rand = (x: number, y: number): number => {
    const v = Math.sin(x * 127.1 + y * 311.7 + seed * 0.7919) * 43758.5453;
    return v - Math.floor(v);
  };
  const out: { l: number; t: number }[] = [];
  for (let y = 0; y < N; y++) {
    for (let x = 0; x < N; x++) {
      const inFinder = (x < 8 && y < 8) || (x > N - 9 && y < 8) || (x < 8 && y > N - 9);
      if (!inFinder && rand(x, y) > 0.52) out.push({ l: (PAD + x) * CELL, t: (PAD + y) * CELL });
    }
  }
  return out;
});
</script>

<style lang="scss" scoped>
/* 原型 .qr-wrap/.qr-card/.qr-meta（逐字换 tokens）；z-110 同 EndSettleModal 层级 */
.qrwrap {
  position: fixed;
  inset: 0;
  z-index: 110;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  background: rgba(8, 8, 11, 0.9);
  backdrop-filter: blur(6px);
  opacity: 0;
  visibility: hidden; /* backdrop-filter 对 opacity:0 照样生效，须连 visibility 一起收（同 EndSettleModal mmask） */
  pointer-events: none;
  transition: 0.22s, visibility 0.22s;
  cursor: pointer;
}
.qrwrap.on {
  opacity: 1;
  visibility: visible;
  pointer-events: auto;
}
.qr-card {
  background: var(--cream);
  border-radius: 18px;
  padding: 16px;
}
.qr-box {
  position: relative;
  width: 232px;
  height: 232px;
  background: var(--cream);
  overflow: hidden;
}
/* 定位角：7×7 深外框 → 5×5 奶油 → 3×3 深（嵌套缩进 1 格） */
.finder {
  position: absolute;
  width: 56px;
  height: 56px;
  background: var(--ink);
}
.finder .f2 {
  position: absolute;
  inset: 8px;
  background: var(--cream);
}
.finder .f3 {
  position: absolute;
  inset: 8px;
  background: var(--ink);
}
.cell {
  position: absolute;
  width: 7px;
  height: 7px;
  background: var(--ink);
}
.qr-meta {
  text-align: center;
  max-width: 300px;
}
.qr-meta .n {
  font-size: 14px;
  font-weight: 700;
}
.qr-meta .s {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  letter-spacing: 0.12em;
  margin-top: 5px;
}
.qr-meta .s2 {
  margin-top: 14px;
  opacity: 0.6;
}
.qr-meta .hint {
  font-size: 11px;
  color: var(--dim);
  margin-top: 10px;
}
.qr-meta .hint .hi {
  color: var(--lemon);
  font-weight: 600;
}
</style>
