<template>
  <!-- 签到二维码浮层（temp/打球页原型 .qr-wrap/.qr-card 逐字）：全屏深遮罩 blur，点任意处关。
       码芯 = 真码（qrcode-generator 编码现场深链，前端直接做）。
       【v-html 例外登记】码图 SVG 串（utils/qr.ts qrSvg 产出）经 v-html 注入——
       与 ChibiAvatar（Q 版头像）、TabBar（导航图标）、BrawlStage（球拍）并列的 v-html 出口；
       后续小程序化时集中替换为静态资源/canvas，调用方零改动。 -->
  <view class="qrwrap" :class="{ on: visible }" @click="emit('close')">
    <view class="qr-card" @click.stop="emit('close')">
      <!-- 码不销毁（§4.9-4：散场转只读回看，同一张码扫出来就是回看） -->
      <view class="qr-box">
        <view v-if="svg" class="qr-svg" v-html="svg" />
        <!-- stub 局（id<=0）不编废链接，占位等真局落地 -->
        <view v-else class="qr-empty">码未就绪</view>
      </view>
    </view>
    <view class="qr-meta">
      <view class="n">{{ metaName }}</view>
      <template v-if="ended">
        <view class="s">现场已散 · 扫码可回看</view>
        <view class="hint"
          >扫码进入只读回看 · <text class="hi">翻战报与名单</text></view
        >
      </template>
      <template v-else>
        <view class="s">已到场 {{ arrived }} 人 · LIVE</view>
        <view class="hint"
          >扫码签到进场 · <text class="hi">没报名的空降也扫这码</text></view
        >
      </template>
      <view class="s s2">点一下关闭</view>
    </view>
  </view>
</template>

<script setup lang="ts">
/* 二维码浮层（2.1 §2 扫码签到）：无本地态——已到场人数实时读 roster。
   码芯换真：deepUrl 拼现场深链 → qrSvg 编码成 SVG（明文无私密信息，
   前端直接做——推翻旧「后端接码」口径，2026-10-10 用户定稿）。 */
import { computed } from "vue";
import { useLiveStore, isArrived } from "@/stores/live";
import { qrSvg } from "@/utils/qr";
import { deepUrl } from "@/utils/deeplink";

defineProps({
  visible: { type: Boolean, default: false },
});
const emit = defineEmits<{ (e: "close"): void }>();

const liveStore = useLiveStore();

/** 局名 + 场馆 */
const metaName = computed(() => {
  const g = liveStore.live?.g;
  if (!g) return "";
  return g.venueName ? `${g.name} ${g.venueName}` : g.name;
});
const arrived = computed(
  () => (liveStore.live?.roster ?? []).filter((p) => isArrived(p.check)).length,
);
/** 散场回看态（§4.10）：endedAt 有值=码转只读回看入口（同一张码，扫出来是回看） */
const ended = computed(() => !!liveStore.live?.endedAt);

/** 码芯内容：进现场的深链（id>0 才编——stub 局没有真 id，不编废链接） */
const qrText = computed(() => {
  const id = liveStore.liveView?.gameId ?? liveStore.live?.g.id ?? 0;
  return id > 0 ? deepUrl(`/pages/live/live?id=${id}`) : "";
});
const svg = computed(() => (qrText.value ? qrSvg(qrText.value) : ""));
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
  transition:
    0.22s,
    visibility 0.22s;
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
  box-sizing: border-box;
  padding: 16px; /* 静区：原假码 PAD=2 格（16px）口径保留 */
}
/* 码色单一源：暗格 fill=currentColor，随这里的 color 走 */
.qr-svg {
  width: 100%;
  height: 100%;
  color: var(--ink);
}
/* v-html 注入的 svg 无 scope 属性，用 :deep 命中（同 TabBar .nbtn svg） */
.qr-svg :deep(svg) {
  display: block;
  width: 100%;
  height: 100%;
}
.qr-empty {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  letter-spacing: 0.12em;
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
