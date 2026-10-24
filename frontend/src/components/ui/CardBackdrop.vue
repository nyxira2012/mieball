<template>
  <!--
    宿主契约：position:relative; overflow:hidden —— 窗层 absolute 三边贴右靠宿主定位，
    四边结构性出血靠宿主裁圆角；z-index:-1 垫在文字下、卡底上（原型 .cbd 同款）。
    cid 空不渲染（宿主素卡兜底：访客/无卡背的格子素卡，不特殊处理）。
  -->
  <view
    v-if="cid"
    ref="el"
    class="cbd"
    :class="['cbd-' + mode, { on: shown }]"
    :style="layerStyle"
  />
</template>

<script setup lang="ts">
/* cbd 取景窗引擎：一张卡背原图走全站，六档取景/纱/暗晕参数逐值
   迁自 temp/原型-背景卡组件.html（对照面），样式变量名照原型（--bwin/--bscrim/
   --bmelt）利于两面对照。定位双轨：切片档（r/c）纯公式渲染期可算；cover 档
   （f/d/h/p）溢出倍率随容器实际宽高变，锚点写死会在高卡上把焦点挤到文字底下，
   必须渲染后量测（onMounted 首帧 + ResizeObserver 重算）——公式收在 utils/cardbg.ts。 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { tapEl } from "@/composables/blurOnBlank";
import {
  BACK_SPEC,
  DEFAULT_FOCUS,
  WIN,
  assetUrl,
  coverPos,
  preloadAsset,
  resolveAssetUrl,
  slicePos,
  type CardMode,
} from "@/utils/cardbg";

const props = defineProps<{
  /** 卡背编号；null/缺省=不渲染（宿主素卡兜底） */
  cid?: string | null;
  /** 取景档位（六档语义见 cardbg.ts WIN 注释） */
  mode: CardMode;
  /** 卡背主体焦点（册子 per-item 留位；首批全统一走 DEFAULT_FOCUS） */
  fx?: number;
  fy?: number;
}>();

const fx = computed(() => props.fx ?? DEFAULT_FOCUS.x);
const fy = computed(() => props.fy ?? DEFAULT_FOCUS.y);
const tier = computed(() => WIN[props.mode]);

/** 切片档定位：定值参数纯公式直出（clampPx 已带 0.1% 精度，直接拼 CSS 变量） */
const sliceVars = computed<Record<string, string>>(() => {
  const t = tier.value;
  // 覆盖档无切片定位；空对象显式归型避免与定位分支并成可选键联合
  if ("cover" in t) return {} as Record<string, string>;
  const pos = slicePos(t, fx.value, fy.value);
  return { "--bpx": pos.px + "%", "--bpy": pos.py + "%" };
});

/** cover 档定位：量测后回填（宽高没量到前缺省 50%/50%，量测即覆写） */
const coverVars = ref<Record<string, string>>({});

const el = ref<unknown>(null);
let ro: ResizeObserver | null = null;

function remeasure() {
  const t = tier.value;
  if (!("cover" in t)) {
    // 切片档定位走 computed，只需把历史量测清一次（重复赋新对象会触发无谓的响应式更新）
    if (Object.keys(coverVars.value).length) coverVars.value = {};
    return;
  }
  const node = tapEl(el.value);
  if (!node) return;
  const w = node.offsetWidth;
  const h = node.offsetHeight;
  if (!w || !h) return;
  const pos = coverPos(
    BACK_SPEC.w,
    BACK_SPEC.h,
    w,
    h,
    fx.value,
    fy.value,
    t.ax,
    t.ay,
  );
  coverVars.value = { "--bpx": pos.px + "%", "--bpy": pos.py + "%" };
}

/* 观察者只在 cover 档挂：切片档定位是纯公式、量测无活干，而 r 档全站量最大
   （局卡/意向/榜单/候场每行一个），白挂 RO 只剩首回调+resize 的空转重赋值。
   无 ResizeObserver 的环境（旧 webview）退化为首帧一次，拉伸窗口不重排可接受 */
function syncObserver() {
  const node = tapEl(el.value);
  const want =
    "cover" in tier.value && node && typeof ResizeObserver !== "undefined";
  if (!want) {
    ro?.disconnect();
    ro = null;
    return;
  }
  if (!ro) {
    ro = new ResizeObserver(remeasure);
    ro.observe(node);
  }
}

onMounted(() => {
  remeasure();
  syncObserver();
});
onBeforeUnmount(() => ro?.disconnect());
// 试穿位换图换焦点换档（装扮页即点即换）都要重算；切片档走 computed 自动跟。
// 换档同时补挂/摘观察者（cover↔slice 切换时 RO 跟着档位走）
watch([fx, fy, tier], () => {
  remeasure();
  syncObserver();
});

/* 出图前整层隐藏、宿主素底占位不跳版；加载失败保持隐藏——异常编号兜素卡不露破图。
   预载走 cardbg 的 URL 级共享缓存：同款卡背第二个实例起免重复拉取解码，
   已暖图的换装回看即点即显（免 0.25s 渐显等待）。
   取图真地址（基地址+版本号）在此一处解析，预载与 CSS 背景用同一个串，缓存才记同一账 */
const bgUrl = computed(() =>
  props.cid ? resolveAssetUrl(assetUrl(props.cid)) : null,
);
const shown = ref(false);
watch(
  bgUrl,
  (url) => {
    shown.value = false;
    if (!url) return;
    void preloadAsset(url).then((ok) => {
      if (ok) shown.value = true;
    });
  },
  { immediate: true },
);

const layerStyle = computed(() => {
  if (!bgUrl.value) return {};
  return {
    "--bimg": `url('${bgUrl.value}')`,
    ...sliceVars.value,
    ...coverVars.value,
  };
});
</script>

<style lang="scss" scoped>
/* 原型 .cbd 基座逐值迁入：窗宽/定位/尺寸/融边全走 CSS 变量，六档只改变量不改结构 */
.cbd {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: -1;
  pointer-events: none;
  width: var(--bwin);
  background-image: var(--bimg);
  background-position: var(--bpx, 50%) var(--bpy, 50%);
  background-size: var(--bsize, 100% auto);
  background-repeat: no-repeat;
  -webkit-mask-image: var(
    --bmask,
    linear-gradient(90deg, transparent 0, #000 var(--bmelt, 44%))
  );
  mask-image: var(
    --bmask,
    linear-gradient(90deg, transparent 0, #000 var(--bmelt, 44%))
  );
  /* 出图渐显（占位期素底，见 shown 注释） */
  opacity: 0;
  transition: opacity 0.25s;
}
.cbd.on {
  opacity: 1;
}
.cbd::after {
  content: "";
  position: absolute;
  inset: 0;
  background: var(--bscrim);
}

/* ---- 六档变量（原型 .cbd-r/.cbd-c/.cbd-f/.cbd-d/.cbd-h/.cbd-p 逐值） ---- */
.cbd-r {
  --bwin: 60%;
  --bsize: 132% auto;
  --bmelt: 44%;
  --bscrim: linear-gradient(
    270deg,
    rgba(14, 14, 18, 0.55) 0%,
    rgba(14, 14, 18, 0.16) 18%,
    transparent 40%
  );
}
.cbd-c {
  --bwin: 64%;
  --bsize: 128% auto;
  --bmelt: 42%;
  --bscrim: linear-gradient(
    270deg,
    rgba(14, 14, 18, 0.45) 0%,
    rgba(14, 14, 18, 0.12) 22%,
    transparent 46%
  );
}
.cbd-f {
  --bwin: 100%;
  --bsize: cover;
  --bmask: none;
  /* 全幅三重纱：纵纱保上下文字 + 横纱保左文右图 + 右舞台聚光压边（战力卡/档案/名片） */
  --bscrim:
    linear-gradient(
      180deg,
      rgba(14, 14, 18, 0.36) 0%,
      rgba(14, 14, 18, 0.06) 34%,
      rgba(14, 14, 18, 0.66) 100%
    ),
    linear-gradient(
      90deg,
      var(--ink2) 0%,
      rgba(22, 22, 29, 0.55) 28%,
      rgba(22, 22, 29, 0.1) 56%,
      rgba(22, 22, 29, 0.16) 78%,
      rgba(14, 14, 18, 0.34) 100%
    ),
    radial-gradient(
      ellipse 55% 82% at 80% 42%,
      rgba(14, 14, 18, 0) 0%,
      rgba(14, 14, 18, 0.18) 58%,
      rgba(14, 14, 18, 0.42) 100%
    );
}
.cbd-d {
  --bwin: 100%;
  --bsize: cover;
  --bmask: none;
  /* 试穿档同全幅锚、纱更轻（撤横纱——装扮页文字少，多露图） */
  --bscrim:
    linear-gradient(
      180deg,
      rgba(14, 14, 18, 0.3) 0%,
      rgba(14, 14, 18, 0.08) 40%,
      rgba(14, 14, 18, 0.6) 100%
    ),
    radial-gradient(
      ellipse 55% 82% at 80% 42%,
      rgba(14, 14, 18, 0) 0%,
      rgba(14, 14, 18, 0.18) 58%,
      rgba(14, 14, 18, 0.42) 100%
    );
}
.cbd-h {
  --bwin: 100%;
  --bsize: cover;
  --bmask: none;
  /* 头带档：锚偏中，底边羽化入素底（内阴影），抽屉行区不铺保信息密度 */
  --bscrim:
    linear-gradient(
      180deg,
      rgba(14, 14, 18, 0.4) 0%,
      rgba(14, 14, 18, 0.1) 40%,
      rgba(14, 14, 18, 0.72) 100%
    ),
    radial-gradient(
      ellipse 55% 100% at 70% 45%,
      rgba(14, 14, 18, 0) 0%,
      rgba(14, 14, 18, 0.12) 55%,
      rgba(14, 14, 18, 0.4) 100%
    );
  box-shadow: inset 0 -16px 18px -12px var(--ink2);
}
.cbd-p {
  --bwin: 100%;
  --bsize: cover;
  --bmask: none;
  /* 名单格档：内容居中（头像骑中、名字坐底）——头像坐垫暗椭圆（心 .68）解
     主体与贴纸相叠，纵纱下重护坐底名字 */
  --bscrim:
    linear-gradient(
      180deg,
      rgba(14, 14, 18, 0.14) 0%,
      rgba(14, 14, 18, 0) 30%,
      rgba(14, 14, 18, 0.55) 100%
    ),
    radial-gradient(
      ellipse 60% 70% at 50% 40%,
      rgba(14, 14, 18, 0.68) 0%,
      rgba(14, 14, 18, 0.3) 55%,
      rgba(14, 14, 18, 0) 100%
    );
}
</style>
