<template>
  <view class="cs">
    <!-- ===== logout：5.1 弹窗「说清只是这台设备登出，数据都在」 ===== -->
    <template v-if="kind === 'logout'">
      <view class="t">退出登录？</view>
      <view class="hint">只是这台设备登出，数据都在云端 · 随时能再登回来</view>
      <view class="btns">
        <AppButton variant="ghost" class="flex1" @click="ui.closeSheet()">再想想</AppButton>
        <AppButton variant="burn" class="flex1" @click="onLogout">确定退出</AppButton>
      </view>
    </template>

    <!-- ===== delete：守卫态优先 —— 应付没结先去结清（5.1：还有应付没结先提示去结清） ===== -->
    <template v-else-if="dueTotal > 0">
      <view class="t">注销账号</view>
      <view class="hint">还有应付 ¥{{ dueTotal }} 未结清 · 注销前先去结清，账目两清再走不扯皮</view>
      <view class="btns">
        <AppButton variant="ghost" class="flex1" @click="ui.closeSheet()">再想想</AppButton>
        <AppButton variant="pri" class="flex1" @click="onGoSettle">去结清 ¥{{ dueTotal }}</AppButton>
      </view>
    </template>

    <!-- ===== delete 第一步：后果说明（形象 / 记录 / 账单 各自怎么处理） ===== -->
    <template v-else-if="step === 'explain'">
      <view class="t">注销账号</view>
      <view class="hint">走了就是真走了 · 先看清楚带走什么、留下什么</view>
      <view class="cons">
        <view v-for="c in CONSEQ" :key="c.k" class="cons-row">
          <text class="cons-k">{{ c.k }}</text>
          <text class="cons-v">{{ c.v }}</text>
        </view>
      </view>
      <view class="btns">
        <AppButton variant="ghost" class="flex1" @click="ui.closeSheet()">我再想想</AppButton>
        <AppButton variant="burn" class="flex1" @click="step = 'confirm'">已了解，继续</AppButton>
      </view>
    </template>

    <!-- ===== delete 第二步：二次确认（两步都过才执行） ===== -->
    <template v-else>
      <view class="t">确认注销？</view>
      <view class="hint">永久删除 · 不可恢复 · 最后一步</view>
      <view class="btns">
        <AppButton variant="ghost" class="flex1" @click="ui.closeSheet()">返回</AppButton>
        <AppButton variant="burn" class="flex1 del-btn" @click="onDelete">确认注销</AppButton>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
/* 账号弹层 AccountSheet（5.1 弹窗）：logout 单步 / delete 应付守卫 → 后果说明 → 二次确认。
   动作全在 user / bill store（toast 文案内聚）；守卫态优先于步骤，不改 period ref（守卫永远全量口径）。 */
import { computed, ref } from 'vue';
import type { PropType } from 'vue';
import AppButton from '@/components/ui/AppButton.vue';
import { useUserStore } from '@/stores/user';
import { useBillStore } from '@/stores/bill';
import { useUiStore } from '@/stores/ui';

defineProps({
  kind: { type: String as PropType<'logout' | 'delete'>, required: true },
});

const user = useUserStore();
const bill = useBillStore();
const ui = useUiStore();

/** delete 两步进度；守卫（due>0）优先于本步骤展示 */
const step = ref<'explain' | 'confirm'>('explain');

/** 应付总额：store 全量口径 totalSummary（不随 period ref 漂移，勿换成 summary） */
const dueTotal = computed(() => bill.totalSummary.due);

/** 后果清单（5.1：形象 / 记录 / 账单 各自怎么处理，逐字） */
const CONSEQ = [
  { k: '形象', v: '装扮与档案匿名化，别人再也看不到你' },
  { k: '打球记录', v: '成绩清零，不再计入战力榜与名单' },
  { k: '账单', v: '已结清的留档，未结清的先去结清' },
] as const;

/** 去结清：关弹层 → 账单页（导航由组件层承担，同 ConfirmSheet.goMeet 先例） */
function onGoSettle(): void {
  ui.closeSheet();
  uni.navigateTo({ url: '/pages/mine/bills' });
}

function onLogout(): void {
  user.logout();
  ui.closeSheet();
}

function onDelete(): void {
  user.deleteAccount();
  ui.closeSheet();
}
</script>

<style lang="scss" scoped>
/* 壳层 h3/.hint 同款（SheetHost 不传壳层 title，各弹层自带，同 ConfirmSheet） */
.t {
  font-family: var(--disp);
  font-size: 21px;
  margin-bottom: 4px;
}
.hint {
  font-size: 12px;
  color: var(--dim);
  margin-bottom: 16px;
}
/* 双钮排（ConfirmSheet 同款） */
.btns {
  display: flex;
  gap: 10px;
}
.flex1 {
  flex: 1;
}
/* 后果清单：每条一行小卡 */
.cons {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}
.cons-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  padding: 10px 12px;
  background: var(--ink3);
}
.cons-k {
  flex: none;
  font-size: 13px;
  font-weight: 700;
}
.cons-v {
  font-size: 12px;
  color: var(--dim);
}
/* 第二步确认钮：burn 底 + 珊瑚描边强化 */
.del-btn {
  border: 1px solid rgba(255, 90, 54, 0.6);
}
</style>
