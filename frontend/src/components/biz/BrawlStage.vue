<template>
  <!-- 前三打架图（alpha.html:1863-1870 结构 · alpha.html:1752「前三榜图：Q 版群斗插画，只标出名次与名字」）：
       中位 t3[0]（76px + 👑）· 左位 t3[1]（60px）· 右位 t3[2]（60px），两位之间各一颗 ⚡（无条件渲染，同 alpha）。
       每人可点 → emit('profile', userId)（alpha:1755 onclick=openProfileById）。 -->
  <view class="brawl">
    <view class="bk">TOP 3 · BRAWL</view>
    <view class="bstage">
      <template v-for="p in figs" :key="p.pos">
        <view v-if="p.u" class="bw" @click="emit('profile', p.u.id)">
          <view class="fig">
            <!-- alpha:1756 C 位才有 👑 -->
            <text v-if="p.pos === 'c'" class="crown">👑</text>
            <!-- 球拍 SVG（v-html 例外，见文件头登记；小程序端走 image 替身） -->
            <!-- #ifdef MP-WEIXIN -->
            <view class="pd-slot">
              <image
                class="pd-mp"
                :style="MP_PD_STYLE[p.pos]"
                :src="MP_PD_SRC"
              />
            </view>
            <!-- #endif -->
            <!-- #ifndef MP-WEIXIN -->
            <view class="pd-slot" v-html="paddles[p.pos]" />
            <!-- #endif -->
            <!-- 旧捏小人已退役：圆章 76/60 半身档（原 alpha:1758 位） -->
            <AvatarBadge :url="p.u.avatarUrl" :size="p.pos === 'c' ? 76 : 60" />
          </view>
          <!-- alpha:1759 plate：#名次 + 名字 -->
          <view class="plate">
            <view class="pno"
              >#{{ p.pos === "c" ? 1 : p.pos === "l" ? 2 : 3 }}</view
            >
            <view class="pnm">{{ p.u.name }}</view>
          </view>
        </view>
        <!-- alpha:1866-1868 两位之间 ⚡（右位后没有） -->
        <text v-if="p.pos !== 'r'" class="clash">⚡</text>
      </template>
    </view>
  </view>
</template>

<script setup lang="ts">
/* 前三打架图 BrawlStage（alpha.html:1862-1870 + 1753-1760 bw() + 1745-1751 paddleSvg · P9）。
   【v-html 例外登记】球拍 SVG 字符串（alpha:1745-1751 paddleSvg）经 v-html 注入——
   系全库 v-html 例外出口之一，出口清单见 src/api/types.ts；
   小程序端已换 svgDataUrl+image 替身（拍形本体共用，调用方零改动）。 */
import { computed } from "vue";
import type { PropType } from "vue";
import AvatarBadge from "@/components/ui/AvatarBadge.vue";
import type { User } from "@/api/types";
// #ifdef MP-WEIXIN
import { svgDataUrl } from "@/utils/svgUrl";
// #endif

type Pos = "l" | "c" | "r";

const props = defineProps({
  /** 榜单前三（alpha:1827 t3=rows.slice(0,3)；[0]=C 位、[1]=左、[2]=右） */
  top3: { type: Array as PropType<User[]>, required: true },
});

const emit = defineEmits<{ (e: "profile", userId: number): void }>();

/** alpha:1866-1868 槽位映射：左=t3[1] · 中=t3[0] · 右=t3[2]（缺人该位留空） */
const figs = computed<{ pos: Pos; u?: User }[]>(() => [
  { pos: "l", u: props.top3[1] },
  { pos: "c", u: props.top3[0] },
  { pos: "r", u: props.top3[2] },
]);

/** 拍形本体（拍面/拍柄/三铆点）：H5 v-html 与小程序 data-URL image 共用同一份
    几何——定位/旋转在两端各挂各的（H5 烤进 svg 的 style，小程序挂在壳 image 上，
    图内定位不生效） */
function paddleBody(color: string): string {
  return `
    <rect x="5" y="3" width="34" height="44" rx="15" fill="${color}"/>
    <rect x="17" y="44" width="10" height="26" rx="5" fill="#B8935A"/>
    <circle cx="15" cy="17" r="2.4" fill="rgba(0,0,0,.22)"/><circle cx="24" cy="13" r="2.4" fill="rgba(0,0,0,.22)"/>
    <circle cx="29" cy="22" r="2.4" fill="rgba(0,0,0,.22)"/>`;
}

/** alpha.html:1745-1751 paddleSvg(side,color) 逐字（rot l=-26 / r=26；C 位持左拍，alpha:1757） */
function paddleSvg(side: "l" | "r", color: string): string {
  const rot = side === "l" ? -26 : 26;
  return `<svg class="pd" viewBox="0 0 44 86" width="30" height="52" style="${side === "l" ? "left:-20px" : "right:-20px"};transform:rotate(${rot}deg)">${paddleBody(color)}</svg>`;
}

/** alpha:1757 paddleSvg(pos==='c'?'l':pos,'#F5F1E8')：C 位/左位左拍 · 右位右拍 */
const paddles: Record<Pos, string> = {
  l: paddleSvg("l", "#F5F1E8"),
  c: paddleSvg("l", "#F5F1E8"),
  r: paddleSvg("r", "#F5F1E8"),
};

// #ifdef MP-WEIXIN
/* 小程序替身：三把拍同色只差朝向，src 一份共用；壳 style 复刻 H5 svg 自带的
   定位/旋转与 .fig :deep(.pd) 的绝对底（尺寸另钉在 .pd-mp 类上） */
const MP_PD_SRC = svgDataUrl(
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 44 86" width="30" height="52">${paddleBody("#F5F1E8")}</svg>`,
);
const MP_PD_STYLE: Record<Pos, string> = {
  l: "left:-20px;transform:rotate(-26deg)",
  c: "left:-20px;transform:rotate(-26deg)",
  r: "right:-20px;transform:rotate(26deg)",
};
// #endif
</script>

<style lang="scss" scoped>
/* alpha.html:470-472 .brawl */
.brawl {
  border: 1px solid rgba(255, 90, 54, 0.28);
  border-radius: var(--r-lg);
  padding: 20px 12px 12px;
  position: relative;
  overflow: hidden;
  margin-bottom: 4px;
  background:
    radial-gradient(
      circle at 50% 130%,
      rgba(255, 90, 54, 0.14),
      transparent 62%
    ),
    var(--ink2);
}
/* alpha.html:473-474 .bk */
.bk {
  position: absolute;
  top: 10px;
  left: 14px;
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.24em;
  color: var(--coral);
}
/* alpha.html:475 .bstage */
.bstage {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 2px;
  padding-top: 10px;
}
/* alpha.html:476-478 .bw/.bw:active/.fig */
.bw {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  position: relative;
}
.bw:active {
  transform: scale(0.94);
}
.fig {
  position: relative;
  animation: bob 2.8s ease-in-out infinite;
}
/* alpha.html:479-480 交错浮动的 delay（首元素=左位 .9s，第三子=C 位 .4s —— 子位含 ⚡ 同 alpha） */
.bstage .bw:nth-child(1) .fig {
  animation-delay: 0.9s;
}
.bstage .bw:nth-child(3) .fig {
  animation-delay: 0.4s;
}
/* alpha.html:482 .crown */
.crown {
  position: absolute;
  top: -20px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 24px;
  z-index: 2;
}
/* alpha.html:483 .bw .pd（v-html 注入的 svg 无 scope 属性，用 :deep 命中） */
.fig :deep(.pd) {
  position: absolute;
  bottom: 4px;
  z-index: -1;
}
/* 球拍注入壳：svg 自带绝对定位样式，壳不占布局 */
.pd-slot {
  line-height: 0;
}
/* #ifdef MP-WEIXIN */
/* 小程序球拍壳（.fig :deep(.pd) 的 image 复刻）：绝对底同款，尺寸=svg 的
   width/height（image 默认 320×240，不钉即撑破打架图） */
.pd-mp {
  position: absolute;
  bottom: 4px;
  z-index: -1;
  width: 30px;
  height: 52px;
}
/* #endif */
/* alpha.html:484-486 .plate/.pno/.pnm */
.plate {
  text-align: center;
  min-width: 86px;
}
.pno {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--coral);
  letter-spacing: 0.16em;
}
.pnm {
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100px;
}
/* alpha.html:488-489 .clash（⚡，bob/clashp keyframes 已在全局 animations.scss alpha:481/490） */
.clash {
  font-family: var(--disp);
  font-size: 24px;
  color: var(--coral);
  align-self: center;
  padding-bottom: 48px;
  animation: clashp 1.2s infinite;
  flex: none;
}
</style>
