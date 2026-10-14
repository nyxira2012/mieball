<template>
  <!-- 教学底盘（2.7 §4.4/A3）：一张步进表驱动的提示行——句子吃 store.stepText
       （函数步解析单点在 store），右端两粒小字常驻（退出教学/重新教学，想走想重来随时）。
       三形态：普通提示行 / final 收尾行（整行可点跳约球页，几秒后 store autoTimer 推过
       末条）/ 尾巴态（走完收窄成最下一行「✓ 教学走完了」，两粒照旧——提示不消失）。
       随便逛逛（freeroam）不带引导：提示槽只有「重新来一遍 ▸」（§4.5），两粒照旧给出路。 -->
  <view
    v-if="sandbox.mode !== 'pick'"
    class="sb-tutor"
    :class="{ tail: isTail }"
  >
    <!-- freeroam：倒带行（不占步进表） -->
    <view
      v-if="sandbox.mode === 'freeroam'"
      class="sb-tutor-line link"
      @click="sandbox.restart()"
      >重新来一遍 ▸</view
    >
    <!-- final 收尾行：整行可点（真出口：跳约球页——切 tab 触发 onHide，局面照 §4.5 即散） -->
    <view
      v-else-if="sandbox.step?.final"
      class="sb-tutor-line link"
      @click="goMeet"
      >{{ sandbox.stepText }}</view
    >
    <!-- 尾巴态：走完不消失，收窄一行钉在最下 -->
    <view v-else-if="isTail" class="sb-tutor-line dim">{{ TUTOR_TAIL }}</view>
    <view v-else class="sb-tutor-line">{{ sandbox.stepText }}</view>

    <view class="sb-tutor-acts">
      <text @click="sandbox.exit()">退出教学</text>
      <text @click="sandbox.restart()">重新教学</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useSandboxStore } from "@/stores/sandbox";
import { goMeet } from "@/utils/nav";
import { TUTOR_TAIL } from "@/sandbox/data";

const sandbox = useSandboxStore();

/** 尾巴态 = 两卡步进表走完（stepIdx 推过末条，step 为 null）；freeroam 无表，不算走完 */
const isTail = computed(
  () => sandbox.mode !== "freeroam" && sandbox.step === null,
);
</script>

<style lang="scss" scoped>
/* 页面最下的教学底盘：提示行左、两粒小字右；比真局候场条轻一档（细字浅底），
   让位给教学画面本身 */
.sb-tutor {
  flex: none;
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(22, 22, 29, 0.95);
  backdrop-filter: blur(8px);
  border-top: 1px solid rgba(255, 212, 0, 0.22);
  padding: 10px 14px calc(10px + env(safe-area-inset-bottom, 0px));
}
.sb-tutor-line {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--cream);
  line-height: 1.45;
}
.sb-tutor-line.dim {
  font-size: 12px;
  color: var(--dim);
  font-weight: 400;
}
/* 可点行（final 收尾/重新来一遍）：柠檬示可点 */
.sb-tutor-line.link {
  color: var(--lemon);
  cursor: pointer;
}
.sb-tutor-line.link:active {
  opacity: 0.7;
}

/* 两粒小字常驻右端（规格 4.4：想走想重来随时） */
.sb-tutor-acts {
  flex: none;
  display: flex;
  gap: 12px;
}
.sb-tutor-acts text {
  font-size: 11px;
  color: var(--dim);
  cursor: pointer;
}
.sb-tutor-acts text:active {
  color: var(--lemon);
}

/* 走完尾巴：整条收窄一档（§4.5「收窄成一行小尾巴」） */
.sb-tutor.tail {
  padding-top: 7px;
  padding-bottom: calc(7px + env(safe-area-inset-bottom, 0px));
  border-top-color: rgba(245, 241, 232, 0.1);
}
</style>
