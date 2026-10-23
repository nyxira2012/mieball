<template>
  <!--
    圆窗占位底色常显：出图前是素圆、onload 后 img 淡入（版面不跳）；
    加载失败 img 永隐，素圆即兜底。取景是 CSS 放大裁切（过渡期模拟，见下）。
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
/* 圆章头像：一枚圆章走全站，大小位只差取景远近，同一张素材同一规矩。
   过渡期取景模拟：现有素材是全身方形，用圆窗放大裁切模拟圆章观感；正式素材按
   「半身填圆、圆外透明、描边随圆」规格到位后撤掉取景模拟、改直摆——届时只改
   本组件样式。 */
import { computed, ref, watch } from "vue";
import { avatarUrl } from "@/utils/cardbg";

/* 后端册子 DEFAULT_AVATAR='a-p1' 的镜像：url=null（访客/未记微信头像的老球友/
   异常编号兜底）一律指定公共款素材，不露破图（访客与示例局人物同款公共头）；
   路径拼接收口 cardbg 的 avatarUrl 单一源 */
const DEFAULT_AVATAR_URL = avatarUrl("a-p1");

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
/* 取景档位全站总规则（原型 av() 同款、无例外用例）：边长 ≥40px 半身圆章、
   <40px 放大取脸特写。判定收在组件内，调用方只报 size、不各自复制规矩 */
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
/* 小位脸特写（原型 .zoomcrop img）：放大 230% 只取脸锚 (50%,32%) 一带 */
.zoom-face {
  width: 230%;
  height: 230%;
  object-fit: cover;
  margin-top: 38%;
}
/* 大位半身圆章（原型 .zoomcrop.zb img）：放大 190% 取半身 */
.zoom-bust {
  width: 190%;
  height: 190%;
  object-fit: cover;
  margin-top: 30%;
}
</style>
