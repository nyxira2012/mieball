<template>
  <!-- 梗句封面公共件：吃昵称表，挂载时随机定格一条（每次进页换一条）；
       名字单独柠檬加大（indexOf 切一刀，不搞分段机制） -->
  <view class="meme-line"
    ><text>{{ before }}</text
    ><text v-if="name" class="nm">{{ name }}</text
    ><text>{{ after }}</text></view
  >
</template>

<script setup lang="ts">
/* 纯展示组件：随机在 setup 定格一次，不随 props 重摇（页面重进=重新挂载=新梗）；
   模板与随机全在 utils/memes */
import { pickMeme } from "@/utils/memes";

const props = defineProps({
  names: { type: Array as () => string[], default: () => [] },
});

const pick = pickMeme(props.names);
const name = pick.name;
const i = name ? pick.text.indexOf(name) : -1;
const before = i >= 0 ? pick.text.slice(0, i) : pick.text;
const after = i >= 0 ? pick.text.slice(i + name!.length) : "";
</script>

<style lang="scss" scoped>
.meme-line {
  font-family: var(--disp);
  font-size: 21px;
  line-height: 1.4;
  color: var(--cream);
  word-break: break-all;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  overflow: hidden;
}
.nm {
  color: var(--lemon);
  font-size: 26px;
  font-weight: 700;
}
</style>
