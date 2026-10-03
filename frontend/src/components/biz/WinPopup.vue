<template>
  <!-- 胜利结算卡 · alpha.html:1716-1724 逐字 + 565-578 样式（P8b）。层级最高（z-110，压过 sheet 90、
       toast/confetti 之下约定见 PageShell），不走 SheetHost——PageShell 全页挂载本组件，
       由 ui store 的 win 状态直接驱动（v-if，等价 alpha:1727 classList.add('on')）。
       关闭仅「收下 · 下一轮」钮 → ui.closeWin()（alpha:1723/1729；点遮罩不关，与 alpha 一致）。 -->
  <view v-if="ui.win" class="winpop">
    <view class="wincard">
      <!-- alpha:1717 kicker 逐字 -->
      <view class="k">MATCH POINT</view>
      <!-- alpha:1718 胜队名「拿下」（<br> → text 块级化，避开小程序不支持的标签） -->
      <view class="wteam">
        <text class="wl">{{ ui.win.names }}</text>
        <text class="wl">拿下</text>
      </view>
      <!-- alpha:1719 大比分（内联 disp 38px cream） -->
      <view class="bigsc">{{ ui.win.sa }} : {{ ui.win.sb }}</view>
      <!-- alpha:1720 胜者头像行 -->
      <view class="avs">
        <view v-for="(p, i) in winners" :key="i" class="avslot">
          <ChibiAvatar :chibi="p.chibi" :size="56" />
        </view>
      </view>
      <!-- alpha:1721 每人 Elo 涨跌：名字取前 4 字；d>=0 显示 + / 负显示 −（U+2212 逐字） -->
      <view class="elochg">
        <text v-for="(x, i) in ui.win.chg" :key="i" class="e" :class="x.up ? 'up' : 'dn'">
          {{ x.name.slice(0, 4) }} {{ x.d >= 0 ? '+' : '−' }}{{ Math.abs(x.d) }}
        </text>
      </view>
      <!-- alpha:1722 注脚（内联 mono 9px dim margin:-8px 0 14px）逐字 -->
      <view class="foot">K=24 · 败方只扣六成 · 访客半权重已计入</view>
      <!-- alpha:1723 btn pri blk -->
      <AppButton variant="pri" block @click="ui.closeWin()">收下 · 下一轮</AppButton>
    </view>
  </view>
</template>

<script setup lang="ts">
/* 胜利结算卡（P8b）：展示件，数据只读 ui store 的 win（WinData，store 在 endMatch 末尾 showWin），
   关闭走 closeWin；关闭后页面（live）随响应式自动刷新（alpha:1729 的 renderLive 等价）。 */
import { computed } from 'vue';
import ChibiAvatar from '@/components/ui/ChibiAvatar.vue';
import AppButton from '@/components/ui/AppButton.vue';
import { useUiStore } from '@/stores/ui';
import { useLiveStore } from '@/stores/live';
import type { User } from '@/api/types';

const ui = useUiStore();
const liveStore = useLiveStore();

/** alpha:1720 avs = 胜者 chibi 头像（av(pById(id).chibi,56)）。WinData 契约只带名字（chg.up），
    这里按名回现场名册解析（随行访客只存在于名册、不在 U——正好覆盖）；查不到的跳过。 */
const winners = computed<User[]>(() => {
  const w = ui.win;
  if (!w) return [];
  const roster = liveStore.live?.roster ?? [];
  return w.chg
    .filter((x) => x.up)
    .map((x) => roster.find((p) => p.name === x.name))
    .filter((p): p is User => !!p);
});
</script>

<style lang="scss" scoped>
/* alpha.html:565-566 #winpop：全屏遮罩 + 居中（display 由 v-if 承担，等价 #winpop.on{display:grid}） */
.winpop {
  position: fixed;
  inset: 0;
  z-index: 110;
  display: grid;
  place-items: center;
  background: rgba(6, 6, 9, 0.86);
  backdrop-filter: blur(6px);
}
/* P11 桌面宽屏（§2.5）：>560px 时结算卡整体约束到 480px 画布居中（alpha #winpop 在 #phone 内） */
@media (min-width: 561px) {
  .winpop {
    max-width: 480px;
    margin: 0 auto;
  }
}
/* alpha.html:568-570 .wincard；#23201a 为 alpha 原文渐变首色（无对应 token，逐字保留）；
   pop keyframes 在全局 animations.scss（alpha:571） */
.wincard {
  width: 82%;
  max-width: 330px;
  border-radius: 24px;
  border: 1px solid rgba(255, 212, 0, 0.4);
  background: linear-gradient(160deg, #23201a, var(--ink2));
  padding: 26px 20px;
  text-align: center;
  animation: pop 0.45s cubic-bezier(0.18, 1.4, 0.4, 1);
}
/* alpha.html:572 .wincard .k */
.k {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.4em;
  color: var(--coral);
}
/* alpha.html:573 .wteam（<br> 两行 → text 块级化等价） */
.wteam {
  font-family: var(--disp);
  font-size: 26px;
  margin: 8px 0 2px;
  color: var(--lemon);
}
.wteam .wl {
  display: block;
}
/* alpha.html:1719 内联 font-family:var(--disp);font-size:38px;color:var(--cream) */
.bigsc {
  font-family: var(--disp);
  font-size: 38px;
  color: var(--cream);
}
/* alpha.html:574-575 .avs / .avs .av（56px 由 ChibiAvatar :size 承载，这里补 -6px 叠压） */
.avs {
  display: flex;
  justify-content: center;
  margin: 12px 0;
}
.avslot {
  margin: 0 -6px;
}
/* alpha.html:576-578 .elochg / .e / up・dn */
.elochg {
  display: flex;
  justify-content: center;
  gap: 22px;
  margin: 10px 0 18px;
  flex-wrap: wrap;
}
.e {
  font-family: var(--disp);
  font-size: 22px;
}
.e.up {
  color: var(--lemon);
}
.e.dn {
  color: var(--coral);
}
/* alpha.html:1722 内联 font-family:var(--mono);font-size:9px;color:var(--dim);margin:-8px 0 14px */
.foot {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
  margin: -8px 0 14px;
}
</style>
