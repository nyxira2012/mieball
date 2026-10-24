<template>
  <!--
    圆窗占位底色常显：出图前是素圆、onload 后 img 淡入（版面不跳）；
    加载失败 img 永隐，素圆即兜底。正式素材按「半身填圆、圆外透明」直摆。
  -->
  <view
    class="avatar-badge"
    :style="{ width: size + 'px', height: size + 'px' }"
  >
    <img
      v-if="src"
      :key="src"
      :src="src"
      alt=""
      class="ab-img"
      :class="{ on: loaded }"
      :style="{ transform: fitStyle }"
      @load="loaded = true"
    />
  </view>
</template>

<script setup lang="ts">
/* 圆章头像：一枚圆章走全站。img 铺满圆窗（width/height 100% + object-fit:cover，
   排版工具 .badge-chip img 同基），取景参数随图走——读素材 XMP 自带的
   bust/face 两档（picfit 写入），按大小位取档套 transform 复现排版画面；
   无参数素材（默认脸 g-00 未带参/外链微信头像/读取失败）回落静态两档兜底。 */
import { computed, ref, watch } from "vue";
import { DEFAULT_AVATAR_CID, assetUrl } from "@/utils/cardbg";
import {
  FALLBACK_FIT,
  frameTransform,
  loadAvatarFit,
  type AvatarFit,
} from "@/utils/avatarfit";

/* url 空（访客/未记微信头像的老球友/异常编号兜底）一律落默认款素材，不露破图；
   路径拼接收口 cardbg 的 assetUrl 单一源 */
const DEFAULT_AVATAR_URL = assetUrl(DEFAULT_AVATAR_CID);

const props = withDefaults(
  defineProps<{
    /** 素材 URL（后端 avatar_url 直出）；null/缺省=默认公共款 */
    url?: string | null;
    /** 边长 px（名片 88 · 试穿框 140 · 档案 84 · 战力卡 76 · 对局卡 44 · 小位 20~30） */
    size?: number;
  }>(),
  { size: 56 },
);

const src = computed(() => props.url || DEFAULT_AVATAR_URL);
/* 取景两档按大小位分：大位（≥40px）吃素材 bust 档、小位吃 face 档 */
const framing = computed<"bust" | "face">(() =>
  props.size >= 40 ? "bust" : "face",
);

/* 素材自带取景参数（avatarfit 按 URL 记忆，同图多枚圆章只取一次字节）。
   换图重取竞态守 url 相等——旧图迟到的参数不溅到新图上；参数未到/取不到
   先按兜底档渲染，到了原位换 transform */
const fit = ref<AvatarFit | null>(null);
const fitStyle = computed(() =>
  frameTransform((fit.value ?? FALLBACK_FIT)[framing.value]),
);

/* :key 换图即重建节点，loaded 随之归零重走淡入（试穿换头像不闪旧图） */
const loaded = ref(false);
watch(
  src,
  (url) => {
    loaded.value = false;
    fit.value = null;
    void loadAvatarFit(url).then((f) => {
      if (src.value === url) fit.value = f;
    });
  },
  { immediate: true },
);
</script>

<style lang="scss" scoped>
.avatar-badge {
  border-radius: 50%;
  overflow: hidden;
  flex: none;
  display: grid;
  place-items: center;
  background: var(--ink2); /* 占位圆底（素材未到的素圆） */
  line-height: 0;
}
.ab-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0;
  transition: opacity 0.25s;
}
.ab-img.on {
  opacity: 1;
}
</style>
