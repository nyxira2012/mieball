<template>
  <!-- 弹层占位壳（P3 脚手架专用）：各 biz 弹层 stub 共用，统一渲染「标题 + P 阶段待实现」。
       各弹层在后续阶段填充真实内容时，把 <SheetStub> 换成正式结构即可，props 契约已就位。 -->
  <view class="stub">
    <view class="t">{{ title }}</view>
    <view class="p">{{ phase }} 待实现</view>
    <view v-for="l in lines" :key="l" class="ln">{{ l }}</view>
  </view>
</template>

<script setup lang="ts">
defineProps({
  title: { type: String, required: true },
  /** 落地阶段标记，如 'P5b' / 'P9' */
  phase: { type: String, required: true },
  /** 附加信息行（如收到的 id，便于联调核对分发是否正确） */
  lines: { type: Array as () => string[], default: () => [] },
});
</script>

<style lang="scss" scoped>
.stub {
  padding: 12px 0 22px;
}
.t {
  font-family: var(--disp);
  font-size: 21px;
  margin-bottom: 6px;
}
.p {
  font-size: 13px;
  color: var(--dim);
}
.ln {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.06em;
  color: var(--lilac);
  margin-top: 6px;
}
</style>
