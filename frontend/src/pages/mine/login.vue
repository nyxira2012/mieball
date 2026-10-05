<template>
  <!-- 「我是老球友」两步页（1.1 A1 / 4.4）：输手机号 → 输 6 位验证码。
       查无账号明确提示核对重输，绝不静默建空号；底部写死客服出口。 -->
  <PageShell>
    <BackRow />

    <view class="stag">
      <view class="kicker">Old Friend</view>
      <view class="brand">我是<text class="bem">老球友</text></view>
      <view class="sub">换了手机 / 微信重装过？手机号收条短信，全部战绩拿得回来</view>
    </view>

    <!-- ===== 第一步：手机号 ===== -->
    <template v-if="step === 'phone'">
      <AppField label="手机号">
        <AppInput v-model="phone" type="number" placeholder="报名时填的 11 位手机号" :maxlength="11" />
      </AppField>
      <view v-if="hint" class="err">{{ hint }}</view>
      <AppButton variant="pri" block :disabled="busy" @click="onNext">{{ busy ? '发送中…' : '下一步 · 收验证码' }}</AppButton>
    </template>

    <!-- ===== 第二步：验证码 ===== -->
    <template v-else>
      <AppField label="6 位短信验证码">
        <view class="frow">
          <AppInput v-model="code" type="number" placeholder="6 位数字" :maxlength="6" class="flex1" />
          <AppButton variant="ghost" size="sm" :disabled="countdown > 0 || busy" @click="onResend">
            {{ countdown > 0 ? `${countdown}s` : '重新发送' }}
          </AppButton>
        </view>
      </AppField>
      <view v-if="hint" class="err">{{ hint }}</view>
      <AppButton variant="pri" block :disabled="busy" @click="onVerify">{{ busy ? '验证中…' : '拿回我的战绩' }}</AppButton>
    </template>

    <!-- 客服出口写死在页底（1.1：不藏在登录后才能看的档案页） -->
    <view class="kefu">收不到码且发码不是你本人操作的 · 联系平台客服微信 mieball-kefu</view>
  </PageShell>
</template>

<script setup lang="ts">
/* 找回页：状态机 phone → sms，动作走 session store；错误按 ApiError.code 分流提示。 */
import { ref } from 'vue';
import PageShell from '@/components/biz/PageShell.vue';
import BackRow from '@/components/biz/BackRow.vue';
import AppField from '@/components/ui/AppField.vue';
import AppInput from '@/components/ui/AppInput.vue';
import AppButton from '@/components/ui/AppButton.vue';
import { useSessionStore } from '@/stores/session';
import { useUiStore } from '@/stores/ui';
import { ApiError, errText } from '@/api/http';
import { useSmsCountdown } from '@/composables/useSmsCountdown';
import { isValidPhone } from '@/utils/validate';

const session = useSessionStore();
const ui = useUiStore();
const { countdown, start: startCountdown } = useSmsCountdown();

const step = ref<'phone' | 'sms'>('phone');
const phone = ref('');
const code = ref('');
const hint = ref('');
const busy = ref(false);

async function onNext(): Promise<void> {
  hint.value = '';
  const p = phone.value.trim();
  if (!isValidPhone(p)) {
    hint.value = '请输入 11 位手机号';
    return;
  }
  busy.value = true;
  try {
    await session.requestCode(p, 'recovery');
    startCountdown();
    step.value = 'sms';
  } catch (e) {
    if (e instanceof ApiError && e.code === 'no_account') {
      hint.value = '这个手机号还没有账号，请核对后重输'; // 查无账号：不发码、不建空号（§4.4）
    } else {
      hint.value = errText(e);
    }
  } finally {
    busy.value = false;
  }
}

async function onResend(): Promise<void> {
  busy.value = true;
  try {
    await session.requestCode(phone.value.trim(), 'recovery');
    startCountdown();
    ui.toast('验证码已重发');
  } catch (e) {
    ui.toast(errText(e));
  } finally {
    busy.value = false;
  }
}

async function onVerify(): Promise<void> {
  hint.value = '';
  if (code.value.trim().length !== 6) {
    hint.value = '请输入 6 位验证码';
    return;
  }
  busy.value = true;
  try {
    await session.redeemCode(phone.value.trim(), code.value.trim(), 'recovery');
    ui.toast('欢迎回来 · 战绩都在');
    uni.navigateBack();
  } catch (e) {
    hint.value = errText(e);
  } finally {
    busy.value = false;
  }
}
</script>

<style lang="scss" scoped>
/* 头部 brand：版式走全局 .brand 类，只补 700 加粗 */
.brand {
  font-weight: 700;
}
.kicker {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--dim);
  letter-spacing: 2px;
  text-transform: uppercase;
}
.sub {
  font-size: 12px;
  color: var(--dim);
  margin: 8px 2px 20px;
  line-height: 1.6;
}

/* 错误/提示行（含查无账号的核对提示） */
.err {
  font-size: 12px;
  color: var(--coral);
  margin: 6px 2px 12px;
  line-height: 1.5;
}

.frow {
  display: flex;
  gap: 10px;
  align-items: center;
}
.flex1 {
  flex: 1;
}

.kefu {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  margin-top: 24px;
  text-align: center;
}
</style>
