<template>
  <view class="cs">
    <!-- ===== logout：说清只是这台设备登出，数据都在（服务端作废本机钥匙） ===== -->
    <template v-if="kind === 'logout'">
      <view class="t">退出登录？</view>
      <view class="hint">只是这台设备登出，数据都在云端 · 随时能再登回来</view>
      <view class="btns">
        <AppButton variant="ghost" class="flex1" @click="ui.closeSheet()">再想想</AppButton>
        <AppButton variant="burn" class="flex1" @click="onLogout">确定退出</AppButton>
      </view>
    </template>

    <!-- ===== delete：应付提示（提示去结清，不硬拦——别人的账不受你注销影响） ===== -->
    <template v-else-if="step === 'guard' && dueTotal > 0">
      <view class="t">注销账号</view>
      <view class="hint">还有应付 ¥{{ dueTotal }} 未结清 · 建议先结清再走，账目两清不扯皮</view>
      <view class="btns">
        <AppButton variant="ghost" class="flex1" @click="onGoSettle">去结清 ¥{{ dueTotal }}</AppButton>
        <AppButton variant="burn" class="flex1" @click="step = 'explain'">仍要注销</AppButton>
      </view>
    </template>

    <!-- ===== delete 第一步：后果说明（形象 / 记录 / 账单 各自怎么处理，1.1 口径） ===== -->
    <template v-else-if="step === 'explain'">
      <view class="t">注销账号</view>
      <view class="hint">档案匿名化、手机号释放 · 别人的比赛记录和积分不受影响</view>
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

    <!-- ===== delete 第二步：二次确认 ===== -->
    <template v-else-if="step === 'confirm'">
      <view class="t">确认注销？</view>
      <view class="hint">档案匿名化 · 手机号释放 · 不可恢复 · 最后一步还需短信验证本人</view>
      <view class="btns">
        <AppButton variant="ghost" class="flex1" @click="ui.closeSheet()">返回</AppButton>
        <AppButton variant="burn" class="flex1" @click="onEnterSms">短信验证，继续注销</AppButton>
      </view>
    </template>

    <!-- ===== delete 第三步：短信验证本人（4.6） ===== -->
    <template v-else>
      <view class="t">短信验证本人</view>
      <view class="hint">验证码将发至 {{ maskedPhone }} · 验证通过即完成注销</view>
      <AppField label="6 位验证码">
        <view class="frow">
          <AppInput v-model="code" type="number" placeholder="6 位数字" :maxlength="6" class="flex1" />
          <AppButton variant="ghost" size="sm" :disabled="countdown > 0 || busy" @click="onSendCode">
            {{ countdown > 0 ? `${countdown}s` : countdownSent ? '重新发送' : '发送验证码' }}
          </AppButton>
        </view>
      </AppField>
      <view class="btns">
        <AppButton variant="ghost" class="flex1" @click="ui.closeSheet()">返回</AppButton>
        <AppButton variant="burn" class="flex1 del-btn" :disabled="busy" @click="onDelete">
          {{ busy ? '注销中…' : '确认注销' }}
        </AppButton>
      </view>
      <view class="kefu">收不到码且发码不是你本人操作的 · 联系平台客服微信 mieball-kefu</view>
    </template>
  </view>
</template>

<script setup lang="ts">
/* 账号弹层 AccountSheet（1.1/5.1 对齐）：logout 单步 / delete 应付提示(不硬拦) → 后果说明
   → 二次确认 → 短信验证本人。动作全走 session store（深模块）；守卫态只提示不阻拦。 */
import { computed, onUnmounted, ref } from 'vue';
import type { PropType } from 'vue';
import AppButton from '@/components/ui/AppButton.vue';
import AppField from '@/components/ui/AppField.vue';
import AppInput from '@/components/ui/AppInput.vue';
import { useSessionStore } from '@/stores/session';
import { useBillStore } from '@/stores/bill';
import { useUiStore } from '@/stores/ui';
import { ApiError } from '@/api/http';

defineProps({
  kind: { type: String as PropType<'logout' | 'delete'>, required: true },
});

const session = useSessionStore();
const bill = useBillStore();
const ui = useUiStore();

/** delete 步进：guard(有应付才出现) → explain → confirm → sms；logout 不走步骤 */
const step = ref<'guard' | 'explain' | 'confirm' | 'sms'>('guard');

/** 应付总额：store 全量口径 totalSummary（不随 period ref 漂移，勿换成 summary） */
const dueTotal = computed(() => bill.totalSummary.due);

/** 本人手机号（注销验证码发这个号；完整号只给自己看） */
const ownPhone = computed(() => session.account?.phone ?? '');
const maskedPhone = computed(() => {
  const p = ownPhone.value;
  return p ? `${p.slice(0, 3)}****${p.slice(-4)}` : '本账号手机号';
});

const code = ref('');
const busy = ref(false);
const countdown = ref(0);
const countdownSent = ref(false);
let timer: ReturnType<typeof setInterval> | null = null;

/** 后果清单（1.1 §4.6：匿名化/封存/释放，非"永久删除"） */
const CONSEQ = [
  { k: '形象', v: '装扮与档案匿名化，各处显示「已注销球友」' },
  { k: '打球记录', v: '历史封存不再显示，别人的战绩和积分不受影响' },
  { k: '手机号', v: '释放，将来可用同一个号注册全新账号（历史不继承）' },
  { k: '账单', v: '已结清的留档；还有应付建议先结清' },
] as const;

function startCountdown(): void {
  countdown.value = 60;
  countdownSent.value = true;
  if (timer) clearInterval(timer);
  timer = setInterval(() => {
    countdown.value--;
    if (countdown.value <= 0 && timer) {
      clearInterval(timer);
      timer = null;
    }
  }, 1000);
}
onUnmounted(() => {
  if (timer) clearInterval(timer);
});

/** 去结清：关弹层 → 账单页（导航由组件层承担，同 ConfirmSheet.goMeet 先例） */
function onGoSettle(): void {
  ui.closeSheet();
  uni.navigateTo({ url: '/pages/mine/bills' });
}

function onEnterSms(): void {
  step.value = 'sms';
}

async function onSendCode(): Promise<void> {
  if (!ownPhone.value) {
    ui.toast('账号信息加载中，请稍后再试');
    return;
  }
  busy.value = true;
  try {
    await session.requestCode(ownPhone.value, 'deactivate');
    startCountdown();
    ui.toast('验证码已发送');
  } catch (e) {
    ui.toast(e instanceof ApiError ? e.message : '网络不给力，请稍后再试');
  } finally {
    busy.value = false;
  }
}

async function onLogout(): Promise<void> {
  ui.closeSheet();
  await session.logout();
}

async function onDelete(): Promise<void> {
  if (code.value.trim().length !== 6) {
    ui.toast('请输入 6 位验证码');
    return;
  }
  busy.value = true;
  try {
    await session.deactivateAccount(ownPhone.value, code.value.trim());
    ui.closeSheet();
  } catch (e) {
    ui.toast(e instanceof ApiError ? e.message : '网络不给力，请稍后再试');
  } finally {
    busy.value = false;
  }
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
  line-height: 1.5;
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
/* 短信步：码输入行 + 客服出口 */
.frow {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 14px;
}
.kefu {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  margin-top: 12px;
  text-align: center;
}
/* 确认注销钮：burn 底 + 珊瑚描边强化 */
.del-btn {
  border: 1px solid rgba(255, 90, 54, 0.6);
}
</style>
