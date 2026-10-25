<template>
  <!-- 签到二维码浮层（temp/打球页原型 .qr-wrap/.qr-card 逐字）：全屏深遮罩 blur，点任意处关。
       码芯 = 真码（qrcode-generator 编码现场深链，前端直接做）。
       【v-html 例外登记】码图 SVG 串（utils/qr.ts qrSvg 产出）经 v-html 注入——
       与 TabBar（导航图标）、BrawlStage（球拍）并列的 v-html 出口；
       小程序端三出口均已改走 svgDataUrl+image 替身（本件 MP 分支：
       小程序码直显后端 PNG、链接码退 image data URL），登记在各组件文件头。 -->

  <view class="qrwrap" :class="{ on: visible }" @click="emit('close')">
    <!-- 可见关闭钮（2026-10-11 替代说明书式「点一下关闭」）：整层本就点哪都关，这里给个看得见的把手 -->
    <view class="qr-close" @click.stop="emit('close')">✕</view>
    <view class="qr-card" @click.stop="emit('close')">
      <!-- 码不销毁（§4.9-4：散场转只读回看，同一张码扫出来就是回看） -->
      <view class="qr-box">
        <!-- 教学沙盒示意模式（2.7 §4.4）：不出真码（示例局的码扫了是死链、更不能外传），
             码位换明显示意占位图；真局用法零变化（demo 缺省 false 走原路） -->
        <view v-if="demo" class="qr-demo">
          <view class="qr-demo-slash" /><text class="qr-demo-t">示意</text>
        </view>
        <!-- #ifdef MP-WEIXIN -->
        <!-- 小程序端码芯：真局开浮层即向后台现取小程序码（在途占位不空窗），
             取不到静默退网页链接码——现场永远有码可扫，全程不弹错 -->
        <view v-else-if="mpStage === 'loading'" class="qr-fetch"
          >正在取码…</view
        >
        <image
          v-else-if="mpStage === 'mp' && mpB64"
          class="qr-img"
          :src="'data:image/png;base64,' + mpB64"
          mode="aspectFit"
        />
        <image
          v-else-if="linkQrSrc"
          class="qr-img"
          :src="linkQrSrc"
          mode="aspectFit"
        />
        <!-- #endif -->
        <!-- #ifndef MP-WEIXIN -->
        <view v-else-if="svg" class="qr-svg" v-html="svg" />
        <!-- #endif -->
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
        <!-- 示意模式的亮码说明句由调用方传入（demoNote）——文案口径归沙盒域，biz 零沙盒依赖 -->
        <view class="hint">
          <template v-if="demo && demoNote">{{ demoNote }}</template>
          <template v-else
            >扫码签到进场 ·
            <text class="hi">没报名的空降也扫这码</text></template
          >
        </view>
      </template>
    </view>
  </view>
</template>

<script setup lang="ts">
/* 二维码浮层（2.1 §2 扫码签到）：无本地态——已到场人数实时读 roster。
   码芯换真：deepUrl 拼现场深链 → qrSvg 编码成 SVG（明文无私密信息，
   前端直接做——推翻旧「后端接码」口径，2026-10-10 用户定稿）。
   demo（2.7）：教学沙盒示意模式——码位不编真码、外壳吃沙盒假数据 props；
   缺省 false 时一切照旧（真局调用方零改动）。 */
import { computed, ref, watch } from "vue";
import { useLiveStore, isArrived } from "@/stores/live";
import { qrSvg } from "@/utils/qr";
import { liveShareUrl } from "@/utils/deeplink";
// #ifdef MP-WEIXIN
import { apiWxacode } from "@/api/wechat";
import { svgDataUrl } from "@/utils/svgUrl";
// #endif

const props = defineProps({
  visible: { type: Boolean, default: false },
  /** 示意模式：不出真码，码位换占位图+亮码说明句 */
  demo: { type: Boolean, default: false },
  /** 示意外壳假数据（局名/场馆/已到场人数=engine 在场数）；空串/缺省回真局数据源 */
  demoName: { type: String, default: "" },
  demoVenue: { type: String, default: "" },
  demoArrived: { type: Number, default: 0 },
  /** 示意亮码说明句（调用方传入，缺省不显示——demo 唯一消费方是教学沙盒） */
  demoNote: { type: String, default: "" },
});
const emit = defineEmits<{ (e: "close"): void }>();

const liveStore = useLiveStore();

/** 局名 + 场馆 */
const metaName = computed(() => {
  if (props.demo)
    return props.demoVenue
      ? `${props.demoName} ${props.demoVenue}`
      : props.demoName;
  const g = liveStore.live?.g;
  if (!g) return "";
  return g.venueName ? `${g.name} ${g.venueName}` : g.name;
});
const arrived = computed(() =>
  props.demo
    ? props.demoArrived
    : (liveStore.live?.roster ?? []).filter((p) => isArrived(p.check)).length,
);
/** 散场回看态（§4.10）：endedAt 有值=码转只读回看入口（同一张码，扫出来是回看）。
    示意局没有散场面——恒 false 走 LIVE 文案 */
const ended = computed(() => !props.demo && !!liveStore.live?.endedAt);

/** 码芯指向的局 id：真局才 >0（stub 局 0——不编废链接也不取小程序码）；
    demo 恒 0=示例局永不编真码。qrText 与小程序取码共用这一个取数口 */
const gameId = computed(() => {
  if (props.demo) return 0;
  return liveStore.liveView?.gameId ?? liveStore.live?.g.id ?? 0;
});
const qrText = computed(() =>
  gameId.value > 0 ? liveShareUrl(gameId.value) : "",
);
const svg = computed(() => (qrText.value ? qrSvg(qrText.value) : ""));

// #ifdef MP-WEIXIN
/* 小程序码状态机：浮层翻真才向后台要（真局且非示意）；在途占位不空窗、
   成败只走一次；任何失败（未配/超时/未登录）静默退链接码——二维码按钮永不
   失灵。关层即清：下次打开重取（后台不连环重试的口径，等下一次点击再试） */
const mpStage = ref<"idle" | "loading" | "mp" | "fallback">("idle");
const mpB64 = ref("");
/** 兜底链接码 data URL：H5 走 v-html + var(--ink)，image 进不去 CSS——墨色
    以实色烤进 data URL（与 tokens --ink 同值） */
const MP_QR_INK = "#0e0e12";
const linkQrSrc = computed(() =>
  qrText.value ? svgDataUrl(qrSvg(qrText.value), MP_QR_INK) : "",
);
watch(
  () => props.visible,
  (open) => {
    mpB64.value = "";
    mpStage.value = "idle";
    if (!open || gameId.value <= 0) return; // demo/id<=0：不取码，走示意/链接码分支
    mpStage.value = "loading";
    apiWxacode(gameId.value)
      .then((r) => {
        mpB64.value = r.image_b64;
        mpStage.value = "mp";
      })
      .catch(() => {
        mpStage.value = "fallback";
      });
  },
  { immediate: true },
);
// #endif
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
/* 可见关闭钮：右上角圆圈 ✕（dim 配色不抢码的视线）。触点 44×44（BackRow 热区先例），
   视觉圆 34px 经 ::before 内缩 5px 画出——几何与初版一致，只放大了可点面积 */
.qr-close {
  position: absolute;
  top: calc(env(safe-area-inset-top, 0px) + 13px);
  right: 15px;
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--dim);
  font-size: 15px;
}
.qr-close::before {
  content: "";
  position: absolute;
  inset: 5px;
  border: 1px solid rgba(245, 241, 232, 0.28);
  border-radius: 50%;
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
/* #ifdef MP-WEIXIN */
/* 小程序码/链接码的 image 壳：尺寸同 v-html 码图（image 默认 320×240，不钉即撑破）；
   取码在途占位与 .qr-empty 同口吻（取码等一眨眼，画面不空窗） */
.qr-img {
  width: 100%;
  height: 100%;
}
.qr-fetch {
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
/* #endif */
/* 示意占位码（demo）：虚线框+对角斜杠+「示意」——一眼是假的、扫无可扫 */
.qr-demo {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px dashed rgba(0, 0, 0, 0.35);
  border-radius: 8px;
  box-sizing: border-box;
  overflow: hidden;
}
.qr-demo-slash {
  position: absolute;
  left: -18%;
  top: 50%;
  width: 136%;
  height: 2px;
  background: rgba(0, 0, 0, 0.3);
  transform: rotate(-33deg);
}
.qr-demo-t {
  font-family: var(--mono);
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0.3em;
  color: rgba(0, 0, 0, 0.55);
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
