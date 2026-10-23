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
      :class="[framing === 'face' ? 'zoom-face' : 'zoom-bust', { on: loaded }]"
      @load="loaded = true"
    />
  </view>
</template>

<script setup lang="ts">
/* 圆章头像：一枚圆章走全站。正式素材按「半身填圆、圆外透明、描边随圆」直出规范摆放。
   单图单源（/cosmetics/{cid}.webp），前端零裁切，按 105% 饱满贴合圆窗边缘。 */
import { computed, ref, watch } from "vue";
import { avatarUrl } from "@/utils/cardbg";

/* 后端册子 DEFAULT_AVATAR='g-00' 的镜像：url=null（访客/未记微信头像的老球友/
   异常编号兜底）一律落默认款素材，不露破图；
   路径拼接收口 cardbg 的 avatarUrl 单一源 */
const DEFAULT_AVATAR_URL = avatarUrl("g-00");

const props = withDefaults(
  defineProps<{
    /** 素材 URL（后端 avatar_url 直出）；null=默认公共款 */
    url: string | null;
    /** 边长 px（名片 88 · 试穿框 140 · 档案 84 · 战力卡 76 · 对局卡 44 · 小位 20~30） */
    size?: number;
  }>(),
  { size: 56 },
);

const src = computed(() => props.url || DEFAULT_AVATAR_URL);
/* 取景档位兼容保留：正式素材到位后大位直摆（105%）、小位极微放大（112%）微聚焦脸部 */
const framing = computed<"bust" | "face">(() =>
  props.size >= 40 ? "bust" : "face",
);
/* :key 换图即重建节点，loaded 随之归零重走淡入（试穿换头像不闪旧图） */
const loaded = ref(false);
watch(src, () => {
  loaded.value = false;
});
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
  opacity: 0;
  transition: opacity 0.25s;
}
.ab-img.on {
  opacity: 1;
}
/* 小位脸特写（<40px）：125% 聚焦圆心脸部特写 */
.zoom-face {
  width: 125%;
  height: 125%;
  object-fit: cover;
}
/* 大位半身圆章（≥40px）：100% 原样直摆（由可视化调图工具定格烘焙） */
.zoom-bust {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
