<template>
  <!-- 选卡屏（2.7 §4.1）：无局空态的替身——常驻横幅 + 两张体验卡 + 随便逛逛。
       数据全是本机自带（sandbox/data 名册小像），零联网零加载态（§4.1 禁止项）；
       进过即落 ✓（store.doneCards），✓ 卡可再点=带引导完整重放（§4.5） -->
  <view class="empty-wrap">
    <SandboxBanner />
    <view class="kicker kt14">Court</view>
    <view class="brand">现<text class="bem">场</text></view>

    <view class="cards">
      <view class="tcard" @click="pick('participate')">
        <view v-if="sandbox.doneCards.participate" class="ok">✓</view>
        <!-- 一局对局小画面：名册前四人的小像摆成两边＋比分（素材与教学同源） -->
        <view class="scene">
          <view class="side">
            <ChibiAvatar :chibi="PARTICIPATE_ROSTER[0]!.chibi" :size="24" />
            <ChibiAvatar :chibi="PARTICIPATE_ROSTER[1]!.chibi" :size="24" />
          </view>
          <text class="pts">11:9</text>
          <view class="side">
            <ChibiAvatar :chibi="PARTICIPATE_ROSTER[2]!.chibi" :size="24" />
            <ChibiAvatar :chibi="PARTICIPATE_ROSTER[3]!.chibi" :size="24" />
          </view>
        </view>
        <view class="t">{{ CARD_TITLES.participate.title }}</view>
        <view class="s">{{ CARD_TITLES.participate.sub }}</view>
      </view>

      <view class="tcard" @click="pick('organize')">
        <view v-if="sandbox.doneCards.organize" class="ok">✓</view>
        <!-- 开赛工具小画面：候场一列小像＋⚡（人够自动开，组织者操盘） -->
        <view class="scene">
          <view class="side">
            <ChibiAvatar :chibi="ORGANIZE_ROSTER[0]!.chibi" :size="24" />
            <ChibiAvatar :chibi="ORGANIZE_ROSTER[1]!.chibi" :size="24" />
            <ChibiAvatar :chibi="ORGANIZE_ROSTER[2]!.chibi" :size="24" />
          </view>
          <text class="pts">⚡</text>
        </view>
        <view class="t">{{ CARD_TITLES.organize.title }}</view>
        <view class="s">{{ CARD_TITLES.organize.sub }}</view>
      </view>
    </view>

    <view class="roam" @click="pick('freeroam')">随便逛逛 ▸</view>
  </view>
</template>

<script setup lang="ts">
/* 组件直调 store（项目惯例）：点卡=enter，教学模式切换由 live.vue 分支次序接管 */
import ChibiAvatar from "@/components/ui/ChibiAvatar.vue";
import SandboxBanner from "@/components/sandbox/SandboxBanner.vue";
import {
  CARD_TITLES,
  ORGANIZE_ROSTER,
  PARTICIPATE_ROSTER,
} from "@/sandbox/data";
import { useSandboxStore } from "@/stores/sandbox";

const sandbox = useSandboxStore();

function pick(kind: "participate" | "organize" | "freeroam"): void {
  sandbox.enter(kind);
}
</script>

<style lang="scss" scoped>
/* 无局空态版式基底（同 live.vue 空态段：bare 壳下自补边距） */
.empty-wrap {
  padding: calc(env(safe-area-inset-top) + 18px) 18px;
}
.kt14 {
  margin-top: 14px;
}

.cards {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}
.tcard {
  position: relative;
  flex: 1;
  border: 1px solid rgba(255, 212, 0, 0.28);
  border-radius: var(--r-lg);
  background: linear-gradient(180deg, var(--ink3), var(--ink2));
  padding: 16px 12px 14px;
}
/* ✓ 角标（进过即落）：右上角电光黄小圆 */
.tcard .ok {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--lemon);
  color: var(--ink);
  font-size: 12px;
  font-weight: 700;
}

/* 卡上小画面：对局/候场两排小像，不做装饰性的重图 */
.scene {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  border: 1px dashed rgba(245, 241, 232, 0.2);
  border-radius: var(--r-md);
  background: var(--ink2);
  padding: 10px 6px;
}
.scene .side {
  display: flex;
  gap: 6px;
}
.scene .pts {
  font-family: var(--mono);
  font-size: 13px;
  font-weight: 700;
  color: var(--lemon);
  letter-spacing: 0.08em;
}

.tcard .t {
  margin-top: 12px;
  font-size: 14px;
  font-weight: 700;
  color: var(--cream);
}
.tcard .s {
  margin-top: 5px;
  font-size: 11px;
  color: var(--dim);
}

/* 随便逛逛：小字行（不带引导的自由玩，§4.5） */
.roam {
  margin-top: 16px;
  text-align: center;
  font-size: 12px;
  color: var(--dim);
  padding: 8px;
}
</style>
