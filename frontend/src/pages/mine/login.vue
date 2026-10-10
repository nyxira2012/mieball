<template>
  <!-- 登录页（1.6 A1 四钥匙明门）：双栏「收验证码」（默认，1.1 两步原样）｜「用密码」
       （手机号+密码直进，锁一刻钟只锁此路）；栏内带忘记密码三步（4.10 换锁）。
       微信位只给说明不放死按钮（4.12）；页底客服出口写死（6.1 修订口径：群主/反馈群）。 -->
  <PageShell>
    <BackRow />

    <view class="stag">
      <view class="kicker">Old Friend</view>
      <view class="brand">我是<text class="bem">老球友</text></view>
      <view class="sub"
        >换了手机 / 微信重装过？收条短信或用密码，名片报名战绩全拿回来</view
      >
    </view>

    <!-- 双栏切换（A1：两栏并列，验证码为默认） -->
    <view class="tabs">
      <view class="tab" :class="{ on: tab === 'code' }" @click="tab = 'code'"
        >收验证码</view
      >
      <view class="tab" :class="{ on: tab === 'pwd' }" @click="tab = 'pwd'"
        >用密码</view
      >
    </view>

    <!-- ===== 收验证码栏：手机号 → 6 位码（1.1 现状原样） ===== -->
    <template v-if="tab === 'code'">
      <template v-if="step === 'phone'">
        <AppField label="手机号">
          <AppInput
            v-model="phone"
            type="number"
            placeholder="报名时填的 11 位手机号"
            :maxlength="11"
          />
        </AppField>
        <view v-if="hint" class="err">{{ hint }}</view>
        <AppButton variant="pri" block :disabled="busy" @click="onNext">{{
          busy ? "发送中…" : "下一步 · 收验证码"
        }}</AppButton>
      </template>

      <template v-else>
        <AppField label="6 位短信验证码">
          <view class="frow">
            <AppInput
              v-model="code"
              type="number"
              placeholder="6 位数字"
              :maxlength="6"
              class="flex1"
            />
            <AppButton
              variant="ghost"
              size="sm"
              :disabled="countdown > 0 || busy"
              @click="onResend"
            >
              {{ countdown > 0 ? `${countdown}s` : "重新发送" }}
            </AppButton>
          </view>
        </AppField>
        <view v-if="hint" class="err">{{ hint }}</view>
        <AppButton variant="pri" block :disabled="busy" @click="onVerify">{{
          busy ? "验证中…" : "拿回我的战绩"
        }}</AppButton>
      </template>
    </template>

    <!-- ===== 用密码栏：手机号+密码直进（4.9）；连错 5 次只锁此路 15 分钟，短信路照常 ===== -->
    <template v-else-if="!forgot">
      <AppField label="手机号">
        <AppInput
          v-model="pwdPhone"
          type="number"
          placeholder="报名时填的 11 位手机号"
          :maxlength="11"
        />
      </AppField>
      <AppField label="密码">
        <AppInput
          v-model="pwd"
          placeholder="至少 6 位"
          :maxlength="40"
          password
        />
      </AppField>
      <view v-if="pwdHint" class="err">{{ pwdHint }}</view>
      <AppButton variant="pri" block :disabled="pwdBusy" @click="onPwdLogin">{{
        pwdBusy ? "验证中…" : "用密码进入"
      }}</AppButton>
      <view v-if="locked" class="linkish switch" @click="switchToCode"
        >等不及？切「收验证码」照常进 ▸</view
      >
      <view class="minor">
        <text class="linkish" @click="startForgot">忘记密码？</text>
      </view>
    </template>

    <!-- ===== 忘记密码三步（4.10 换锁）：手机号 → 收码 → 新密码两遍；成功即登录回栈 ===== -->
    <template v-else>
      <view class="fp-t">重设密码</view>
      <template v-if="forgot === 'phone'">
        <AppField label="手机号">
          <AppInput
            v-model="fpPhone"
            type="number"
            placeholder="报名时填的 11 位手机号"
            :maxlength="11"
          />
        </AppField>
        <view v-if="fpHint" class="err">{{ fpHint }}</view>
        <AppButton
          variant="pri"
          block
          :disabled="fpBusy"
          @click="onForgotSend"
          >{{ fpBusy ? "发送中…" : "下一步 · 收验证码" }}</AppButton
        >
      </template>

      <template v-else-if="forgot === 'code'">
        <AppField label="6 位短信验证码">
          <view class="frow">
            <AppInput
              v-model="fpCode"
              type="number"
              placeholder="6 位数字"
              :maxlength="6"
              class="flex1"
            />
            <AppButton
              variant="ghost"
              size="sm"
              :disabled="fpCountdown > 0 || fpBusy"
              @click="onForgotResend"
            >
              {{ fpCountdown > 0 ? `${fpCountdown}s` : "重新发送" }}
            </AppButton>
          </view>
        </AppField>
        <view v-if="fpHint" class="err">{{ fpHint }}</view>
        <AppButton variant="pri" block :disabled="fpBusy" @click="onForgotCode"
          >下一步 · 设新密码</AppButton
        >
      </template>

      <template v-else>
        <AppField label="新密码（至少 6 位）">
          <AppInput
            v-model="fpP1"
            placeholder="6 位以上，纯数字也行"
            :maxlength="40"
            password
          />
        </AppField>
        <AppField label="再输一遍确认">
          <AppInput
            v-model="fpP2"
            placeholder="两次要一致"
            :maxlength="40"
            password
          />
        </AppField>
        <view v-if="fpHint" class="err">{{ fpHint }}</view>
        <AppButton
          variant="pri"
          block
          :disabled="fpBusy"
          @click="onForgotReset"
          >{{ fpBusy ? "重设中…" : "重设并进入" }}</AppButton
        >
      </template>
      <view class="minor">
        <text class="linkish" @click="forgot = null">返回 · 用密码登录</text>
      </view>
    </template>

    <!-- 微信位（4.12）：给位不给死按钮，点了说明 -->
    <view class="wx-row" @click="onWechat">
      <text>微信一键登录</text>
      <text class="wx-note">即将开通</text>
    </view>

    <!-- 客服出口写死在页底（6.1 修订口径：群主=开发者本人，不虚构客服微信号） -->
    <view class="kefu">收不到验证码？联系群主或发到反馈群</view>
  </PageShell>
</template>

<script setup lang="ts">
/* 找回/登录页：双栏状态机，动作走 session store；错误按 ApiError.code 分流提示，
   其余 errText 原样透出（password_wrong/locked 的剩余次数与秒数已由后端文案带上）。 */
import { ref } from "vue";
import PageShell from "@/components/biz/PageShell.vue";
import BackRow from "@/components/biz/BackRow.vue";
import AppField from "@/components/ui/AppField.vue";
import AppInput from "@/components/ui/AppInput.vue";
import AppButton from "@/components/ui/AppButton.vue";
import { useSessionStore } from "@/stores/session";
import { useUiStore } from "@/stores/ui";
import { ApiError, errText } from "@/api/http";
import { useSmsCountdown } from "@/composables/useSmsCountdown";
import { isValidPhone, newPwdError } from "@/utils/validate";

const session = useSessionStore();
const ui = useUiStore();

/** 当前栏：code=收验证码（默认）｜pwd=用密码 */
const tab = ref<"code" | "pwd">("code");

/* —— 收验证码栏（1.1 两步原样）：状态机 phone → sms —— */
const step = ref<"phone" | "sms">("phone");
const phone = ref("");
const code = ref("");
const hint = ref("");
const busy = ref(false);
const { countdown, start: startCountdown } = useSmsCountdown();

async function onNext(): Promise<void> {
  hint.value = "";
  const p = phone.value.trim();
  if (!isValidPhone(p)) {
    hint.value = "请输入 11 位手机号";
    return;
  }
  busy.value = true;
  try {
    await session.requestCode(p, "recovery");
    startCountdown();
    step.value = "sms";
  } catch (e) {
    if (e instanceof ApiError && e.code === "no_account") {
      hint.value = "这个手机号还没有账号，请核对后重输"; // 查无账号：不发码、不建空号（§4.4）
    } else {
      hint.value = errText(e); // 日上限等文案自带客服出口
    }
  } finally {
    busy.value = false;
  }
}

async function onResend(): Promise<void> {
  busy.value = true;
  try {
    await session.requestCode(phone.value.trim(), "recovery");
    startCountdown();
    ui.toast("验证码已重发");
  } catch (e) {
    ui.toast(errText(e));
  } finally {
    busy.value = false;
  }
}

async function onVerify(): Promise<void> {
  hint.value = "";
  if (code.value.trim().length !== 6) {
    hint.value = "请输入 6 位验证码";
    return;
  }
  busy.value = true;
  try {
    await session.redeemCode(phone.value.trim(), code.value.trim(), "recovery");
    ui.toast("欢迎回来 · 战绩都在");
    uni.navigateBack();
  } catch (e) {
    hint.value = errText(e);
  } finally {
    busy.value = false;
  }
}

/* —— 用密码栏（4.9） —— */
const pwdPhone = ref("");
const pwd = ref("");
const pwdHint = ref("");
const pwdBusy = ref(false);
/** password_locked 后亮「切收验证码」出口：锁只锁密码路一刻钟，短信路照常（4.9 边缘） */
const locked = ref(false);

async function onPwdLogin(): Promise<void> {
  pwdHint.value = "";
  locked.value = false;
  const p = pwdPhone.value.trim();
  if (!isValidPhone(p)) {
    pwdHint.value = "请输入 11 位手机号";
    return;
  }
  if (!pwd.value) {
    pwdHint.value = "请输入密码";
    return;
  }
  pwdBusy.value = true;
  try {
    await session.passwordLogin(p, pwd.value);
    ui.toast("欢迎回来 · 战绩都在");
    uni.navigateBack();
  } catch (e) {
    if (e instanceof ApiError && e.code === "password_locked") {
      pwdHint.value = errText(e); // message 自带剩余秒与「可先用短信」指引
      locked.value = true;
    } else if (e instanceof ApiError && e.code === "password_not_set") {
      // 该号没设过密码：顺手切「收验证码」栏，手机号带过去省重输
      switchToCode();
      ui.toast(errText(e));
    } else {
      pwdHint.value = errText(e); // password_wrong 的 message 自带剩余次数
    }
  } finally {
    pwdBusy.value = false;
  }
}

/** 锁内出口：切验证码栏并带上已输手机号 */
function switchToCode(): void {
  phone.value = pwdPhone.value.trim();
  step.value = "phone";
  tab.value = "code";
}

/* —— 忘记密码三步（4.10 换锁）：手机号 → 收码(reset_password) → 新密码两遍 —— */
const forgot = ref<"phone" | "code" | "newpwd" | null>(null);
const fpPhone = ref("");
const fpCode = ref("");
const fpP1 = ref("");
const fpP2 = ref("");
const fpHint = ref("");
const fpBusy = ref(false);
const { countdown: fpCountdown, start: fpStart } = useSmsCountdown();

function startForgot(): void {
  fpPhone.value = pwdPhone.value.trim(); // 已输的手机号带过来
  fpCode.value = "";
  fpP1.value = "";
  fpP2.value = "";
  fpHint.value = "";
  forgot.value = "phone";
}

async function onForgotSend(): Promise<void> {
  fpHint.value = "";
  const p = fpPhone.value.trim();
  if (!isValidPhone(p)) {
    fpHint.value = "请输入 11 位手机号";
    return;
  }
  fpBusy.value = true;
  try {
    await session.requestCode(p, "reset_password");
    fpStart();
    forgot.value = "code";
  } catch (e) {
    fpHint.value = errText(e); // 查无账号核对重输（不发码、不建空号）
  } finally {
    fpBusy.value = false;
  }
}

async function onForgotResend(): Promise<void> {
  fpBusy.value = true;
  try {
    await session.requestCode(fpPhone.value.trim(), "reset_password");
    fpStart();
    ui.toast("验证码已重发");
  } catch (e) {
    ui.toast(errText(e));
  } finally {
    fpBusy.value = false;
  }
}

function onForgotCode(): void {
  fpHint.value = "";
  if (fpCode.value.trim().length !== 6) {
    fpHint.value = "请输入 6 位验证码";
    return;
  }
  forgot.value = "newpwd";
}

async function onForgotReset(): Promise<void> {
  fpHint.value = "";
  const msg = newPwdError(fpP1.value, fpP2.value); // 5 位前端先拦，后端真闸兜底
  if (msg) {
    fpHint.value = msg;
    return;
  }
  fpBusy.value = true;
  try {
    await session.passwordReset(
      fpPhone.value.trim(),
      fpCode.value.trim(),
      fpP1.value,
    );
    // 换锁提示（A2）：全设备钥匙作废只留这台，人话一句
    ui.toast("已重置 · 为防旧钥匙作怪，其他设备下次要重新登录一次");
    uni.navigateBack();
  } catch (e) {
    fpHint.value = errText(e);
  } finally {
    fpBusy.value = false;
  }
}

/** 微信位（4.12）：资质未到，点了只说明，不放死按钮 */
function onWechat(): void {
  ui.toast("微信登录即将开通 · 资质到位后点亮");
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

/* 双栏 tab（A1 两栏并列） */
.tabs {
  display: flex;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  overflow: hidden;
  margin-bottom: 18px;
  background: var(--ink2);
}
.tab {
  flex: 1;
  text-align: center;
  padding: 10px 0;
  font-size: 13px;
  color: var(--dim);
  cursor: pointer;
}
.tab + .tab {
  border-left: 1px solid var(--line);
}
.tab.on {
  color: var(--lemon);
  background: var(--ink3);
  font-weight: 700;
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

/* 栏内次级动作（忘记密码 / 返回 / 锁内切栏） */
.minor {
  margin-top: 16px;
  text-align: center;
}
.linkish {
  font-size: 12px;
  color: var(--dim);
  cursor: pointer;
}
.linkish:active {
  color: var(--lemon);
}
.linkish.switch {
  display: block;
  text-align: center;
  margin-top: 10px;
  color: var(--lemon);
}

/* 忘记密码小标题 */
.fp-t {
  font-size: 13px;
  font-weight: 700;
  margin: 2px 2px 14px;
}

/* 微信位（4.12）：占位说明行，点了 toast */
.wx-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1px dashed var(--line);
  border-radius: var(--r-md);
  padding: 12px 14px;
  margin-top: 22px;
  font-size: 13px;
  cursor: pointer;
}
.wx-row:active {
  border-color: rgba(255, 212, 0, 0.4);
}
.wx-note {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
}

.kefu {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  margin-top: 24px;
  text-align: center;
}
</style>
