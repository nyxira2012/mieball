<template>
  <!-- 名片建号卡（1.1 A1 三态 + 1.6 扩展）：填卡 → 手机号被占（三出口接管/重填）→ 短信/密码验证进入。
       游客点报名/建局/留意向时弹出（或从约球页游客入口直开），成功后自动接着完成挂起动作
       （D3：用户看一步，系统拆两步）。草稿落本机：断网/中断后已填内容不丢（§5 出错条目）。
       右上角【登录】全天候亮（1.6 §4.2）：点了落挂起快照进信号位、直达登录页，登完回来动作接着办。
       2026-10-13 环境收口（1.8 修订节）+ 同日修订二（用户裁决）：表单两环境同貌、只换按钮——
       微信内=一颗微信授权登录（快进，卡上填过的都算数）；浏览器=一颗确定（原有手填路）；
       微信键微信外一律不渲染（WechatButton 公共件同规）。 -->
  <view class="ss">
    <!-- ===== 态一：名片卡（表单同貌，按环境换钮） ===== -->
    <template v-if="mode === 'card'">
      <view class="trow">
        <view class="sheet-t">{{ title }}</view>
        <view class="login-link" @click="goLoginWithDraft">登录 ▸</view>
      </view>

      <!-- 表单两环境同貌（修订二）：栏名让位占位字；填过的都算数——
           微信内快进与浏览器手填同消费这张卡 -->
      <AppField>
        <AppInput
          v-model="nickname"
          placeholder="常用球友名，如 海淀反手王（可跳过）"
          :maxlength="16"
        />
      </AppField>

      <AppField label="选个头像">
        <view class="presets">
          <view
            v-for="(p, i) in CHIBI_PRESETS"
            :key="i"
            class="ptile"
            :class="{ on: picked === i }"
            @click="pick(i)"
          >
            <ChibiAvatar :chibi="p.c" :size="44" />
          </view>
        </view>
      </AppField>

      <AppField>
        <AppInput
          v-model="phone"
          type="number"
          placeholder="11 位手机号"
          :maxlength="11"
        />
        <!-- 用途说明原文单一源在 api/dict（1.8 批3：我的页补绑面板同消费） -->
        <view class="pnote">{{ PHONE_USE_NOTE }}</view>
      </AppField>

      <!-- 按环境换钮（修订二）：微信内·动作弹出=授权钮（快进建号，吃全卡字段）；
           浏览器/微信找回面（4.7 护栏：找回卡不快进）=手填确定钮 -->
      <view v-if="wxFastCard" class="wx-go">
        <WechatButton
          variant="pri"
          label="微信授权登录"
          @press="onWechatFast"
        />
      </view>
      <AppButton
        v-else
        variant="pri"
        block
        :disabled="busy"
        @click="onSubmitCard"
      >
        {{ busy ? "提交中…" : actionLabel }}
      </AppButton>
      <!-- 微信内底部出路小字：给不用微信登录的人（去手机浏览器走手填路） -->
      <view v-if="wxFastCard" class="wx-out"
        >不使用微信登录？使用手机浏览器打开本程序</view
      >
    </template>

    <!-- ===== 态二：手机号已被占用（1.6 §4.5 三证明出口） ===== -->
    <template v-else-if="mode === 'occupied'">
      <view class="sheet-t">这个手机号已经有人用了</view>
      <view class="sheet-hint"
        >手机号永远归手机的主人——任选一种方式证明号是你的，验过立即进入那个账号</view
      >
      <view class="exits">
        <AppButton variant="pri" block :disabled="busy" @click="onTakeover"
          >用短信验证，进入那个账号</AppButton
        >
        <AppButton variant="ghost" block @click="mode = 'pwd'"
          >用密码进入</AppButton
        >
        <!-- 微信验证进入（1.7 点亮）：正式绑才放行（接管级，与短信出口同待遇）；
             没绑/绑别处点了回来一句指路（后端文案）。微信外不渲染（WechatButton 环境门） -->
        <WechatButton
          label="微信验证进入"
          note="正式绑过的微信两下进门"
          @press="onWechat"
        />
        <view class="relink" @click="mode = 'card'">不是我的号？返回重填</view>
      </view>
    </template>

    <!-- ===== 态二·密码出口（§4.5 三出口之二）：密码接管，效果与短信接管一致 ===== -->
    <template v-else-if="mode === 'pwd'">
      <view class="sheet-t">用密码进入</view>
      <view class="sheet-hint"
        >输入 {{ phone }} 账号的密码——验过即接管，刚才的动作接着办</view
      >
      <AppField label="密码">
        <AppInput
          v-model="pwd"
          placeholder="这个账号的登录密码"
          :maxlength="40"
          password
        />
      </AppField>
      <AppButton variant="pri" block :disabled="busy" @click="onPwdRedeem">{{
        busy ? "验证中…" : "进入那个账号"
      }}</AppButton>
      <!-- 锁一刻钟只锁密码路（§4.9 边缘）：改走短信出口照常能进 -->
      <view v-if="pwdLocked" class="relink" @click="onTakeover"
        >密码路锁了一刻钟 · 改用短信验证 ▸</view
      >
      <view class="relink" @click="mode = 'occupied'">返回重选</view>
    </template>

    <!-- ===== 态三：短信验证（接管） ===== -->
    <template v-else>
      <view class="sheet-t">短信验证</view>
      <view class="sheet-hint"
        >验证码已发至
        {{ phone }}（找回/接管都走这里，手机在谁手里号就归谁）</view
      >
      <AppField label="6 位验证码">
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
      <AppButton variant="pri" block :disabled="busy" @click="onVerify">{{
        busy ? "验证中…" : "验证并进入"
      }}</AppButton>
      <view class="kefu"
        >收不到码且发码不是你本人操作的 · 联系群主或发到反馈群</view
      >
    </template>
  </view>
</template>

<script setup lang="ts">
/* 名片建号卡：表单态 + 占用态（三出口）+ 密码态 + 短信态。动作全走 session store（深模块），
   本组件只管状态机与草稿；错误按 ApiError.code 分支提示。
   挂起动作续办单一源在 composables/pendingResume（登录页登回来那路也用它）。 */
import { computed, onUnmounted, ref, watch } from "vue";
import type { PropType } from "vue";
import AppButton from "@/components/ui/AppButton.vue";
import AppField from "@/components/ui/AppField.vue";
import AppInput from "@/components/ui/AppInput.vue";
import ChibiAvatar from "@/components/ui/ChibiAvatar.vue";
import WechatButton from "@/components/biz/WechatButton.vue";
import { useSessionStore } from "@/stores/session";
import { useUiStore } from "@/stores/ui";
import { runPendingResume } from "@/composables/pendingResume";
import { CHIBI_PRESETS, PHONE_USE_NOTE } from "@/api/dict";
import { cardPayloadOf, type CardPayload } from "@/api/auth";
import {
  ApiError,
  clearCardDraft,
  errText,
  readCardDraft,
  writeCardDraft,
} from "@/api/http";
import { useSmsCountdown } from "@/composables/useSmsCountdown";
import { phoneInputError, smsCodeError } from "@/utils/validate";
import { isWeChatBrowser, goWechatAuth } from "@/utils/wechat";
import { goLogin } from "@/utils/nav";
import type { ChibiConfig, PublishGameInput } from "@/api/types";

const props = defineProps({
  pendingJoin: {
    type: Object as PropType<{ gameId: number; bring: number }>,
    default: undefined,
  },
  pendingLaunch: {
    type: Object as PropType<PublishGameInput>,
    default: undefined,
  },
  /** 扫码签到（2.1·选项A）：游客在现场页点「我到了」→ 建号成功后自动签到进候场区 */
  pendingCheckin: {
    type: Object as PropType<{ gameId: number }>,
    default: undefined,
  },
  /** 留意向（1.2 4.13）：游客在意向表单点保存 → 建号成功自动落意向簿 */
  pendingIntent: {
    type: Object as PropType<{
      slots: string[];
      frequency: number;
      note: string;
    }>,
    default: undefined,
  },
});

const session = useSessionStore();
const ui = useUiStore();

/** pwd=占卡三出口之二（1.6 §4.5）：内联密码接管 */
const mode = ref<"card" | "occupied" | "pwd" | "sms">("card");
const nickname = ref("");
const phone = ref("");
const code = ref("");
const pwd = ref("");
/** password_locked 后亮「改用短信验证」出口：锁只锁密码路一刻钟，短信路照常（§4.9 边缘） */
const pwdLocked = ref(false);
/** 选中的预设下标；null=没选（跳过 → 服务端默认小人） */
const picked = ref<number | null>(null);
const busy = ref(false);
const { countdown, start: startCountdown } = useSmsCountdown();

const title = computed(() =>
  props.pendingJoin
    ? "填张名片，报名"
    : props.pendingLaunch
      ? "填张名片，建局"
      : props.pendingIntent
        ? "填张名片，留意向"
        : "填张名片",
);
const actionLabel = computed(() =>
  props.pendingJoin
    ? "确定报名"
    : props.pendingLaunch
      ? "确定建局"
      : props.pendingIntent
        ? "确定留下意向"
        : "确定",
);

/* ---- 卡形态（2026-10-13 修订二，用户裁决）：表单两环境同貌、只换按钮——
     微信内+动作弹出 → 一颗微信授权登录（快进建号，吃全卡字段：昵称/头像/手机号
     填了就算、没填走各自兜底）；浏览器/微信找回面（4.7 护栏：找回卡不快进）→
     名片表单+一颗确定（手填路）。微信键微信外不渲染（WechatButton 环境门） ---- */
const fromWechatReturn = computed(() => ui.signupCardFrom === "wechat-return");
const wxFastCard = computed(() => isWeChatBrowser() && !fromWechatReturn.value);

/* ---- 草稿：本机持久化（断网重进内容还在）。
     打字密集场景，300ms 防抖再落存储，卸载/提交前 flush 补一次，防丢语义不变 ---- */
const draft = readCardDraft<{
  nickname: string;
  phone: string;
  picked: number | null;
}>();
if (draft) {
  nickname.value = draft.nickname ?? "";
  phone.value = draft.phone ?? "";
  picked.value = draft.picked ?? null;
}
/* 修订二：快进带号撞占用回跳——login 页 phone_taken 分支落的一次性信号：
   重开卡直接落占卡三出口、phone 复位为撞的号（消费即清；openSheet 开新卡兜清） */
if (ui.signupOccupiedPhone) {
  phone.value = ui.signupOccupiedPhone;
  ui.signupOccupiedPhone = "";
  mode.value = "occupied";
}
let draftTimer: ReturnType<typeof setTimeout> | null = null;
let draftDirty = false;
function flushDraft(): void {
  if (draftTimer) {
    clearTimeout(draftTimer);
    draftTimer = null;
  }
  if (!draftDirty) return;
  draftDirty = false;
  writeCardDraft({
    nickname: nickname.value,
    phone: phone.value,
    picked: picked.value,
  });
}
watch([nickname, phone, picked], () => {
  draftDirty = true;
  if (draftTimer) clearTimeout(draftTimer);
  draftTimer = setTimeout(flushDraft, 300);
});
onUnmounted(flushDraft);

function pick(i: number): void {
  picked.value = picked.value === i ? null : i;
}

/** 名片草稿_payload（D5 合并用）：建号 / 短信接管 / 密码接管三路同形，收一处防漂移；
    旗标拼装与预设映射在 api/auth cardPayloadOf 单一源（与微信回跳重建路共用） */
function cardPayload(): CardPayload {
  return cardPayloadOf(phone.value.trim(), nickname.value, picked.value);
}

/** 挂起动作快照：goLoginWithDraft 落信号位与成功续办两处同用 */
function pendingSnapshot() {
  return {
    pendingJoin: props.pendingJoin,
    pendingLaunch: props.pendingLaunch,
    pendingCheckin: props.pendingCheckin,
    pendingIntent: props.pendingIntent,
  };
}

/* 右上角【登录】（1.6 §4.2 全天候明门）：先 flush 草稿（登完回来已填内容不丢），
   挂起动作快照落信号位，直达登录页。弹层会随宿主页 onHide 被关、本组件卸载——
   登录回来由登录页凭信号位快照代跑续办，不靠本组件存活。 */
function goLoginWithDraft(): void {
  flushDraft();
  ui.pendingAfterLogin = pendingSnapshot();
  goLogin();
}

/** 微信内「微信授权登录」（1.8 4.1 快进；修订二：卡上填过的都算数）——昵称/头像/
    手机号与手填路同一份 cardPayload 拼装（单一源）：号没人用直接建带号账号（微信
    同时正式绑）、被占由回跳收尾落占卡三出口（login.vue）。号填了但格式不对拦在
    出发前（toast），不静默丢——用户以为给了号。 */
function onWechatFast(): void {
  if (phone.value.trim()) {
    const perr = phoneInputError(phone.value);
    if (perr) {
      ui.toast(perr);
      return;
    }
  }
  const card = cardPayload();
  flushDraft();
  void goWechatAuth({
    fast: true,
    nickname: card.nickname?.trim() || undefined,
    chibi: card.chibi,
    phone: card.phone || undefined,
    pending: pendingSnapshot(),
  });
}

/* ---- 提交名片 ---- */
async function onSubmitCard(): Promise<void> {
  const perr = phoneInputError(phone.value);
  if (perr) {
    ui.toast(perr);
    return;
  }
  busy.value = true;
  try {
    await session.signupWithCard(cardPayload());
    afterSuccess(
      props.pendingJoin
        ? "报名完成，已在名单中"
        : props.pendingIntent
          ? "账号建好了 · 意向已留下"
          : "账号建好了",
    );
  } catch (e) {
    if (e instanceof ApiError && e.code === "phone_taken") {
      mode.value = "occupied";
    } else {
      ui.toast(errText(e));
    }
  } finally {
    busy.value = false;
  }
}

/* ---- 占卡三出口之二：密码接管（§4.5）——效果与短信接管一致：
     名片覆盖冒填者档案、全设备钥匙连同旧密码作废、挂起动作接着办 ---- */
async function onPwdRedeem(): Promise<void> {
  if (!pwd.value) {
    ui.toast("请输入密码");
    return;
  }
  busy.value = true;
  try {
    await session.passwordRedeem(phone.value.trim(), pwd.value, cardPayload());
    afterSuccess("已进入你的账号");
  } catch (e) {
    // password_locked 的 message 自带剩余秒；password_wrong 自带剩余次数，透传即可
    if (e instanceof ApiError && e.code === "password_locked") {
      pwdLocked.value = true; // 锁内亮「改用短信验证」出口（短信路不受锁影响）
    }
    ui.toast(errText(e));
  } finally {
    busy.value = false;
  }
}

/** 占卡「微信验证进入」（1.7 §4.4/4.5）：与「登录」链接同款先存后跳——名片草稿
    flush 进本机（回来重建名片用）、挂起快照进转场包（回来接着办），整页跳微信。
    回来由登录页收尾：正式绑→接管进入；否则一句指路（后端文案），短信/密码出口照常。 */
function onWechat(): void {
  flushDraft();
  void goWechatAuth({
    phone: phone.value.trim(),
    pending: pendingSnapshot(),
  });
}

/* ---- 占用 → 接管 ---- */
async function onTakeover(): Promise<void> {
  busy.value = true;
  try {
    await session.requestCode(phone.value.trim(), "takeover");
    startCountdown();
    mode.value = "sms";
  } catch (e) {
    ui.toast(errText(e));
  } finally {
    busy.value = false;
  }
}

async function onResend(): Promise<void> {
  busy.value = true;
  try {
    await session.requestCode(phone.value.trim(), "takeover");
    startCountdown();
    ui.toast("验证码已重发");
  } catch (e) {
    ui.toast(errText(e));
  } finally {
    busy.value = false;
  }
}

async function onVerify(): Promise<void> {
  const cerr = smsCodeError(code.value);
  if (cerr) {
    ui.toast(cerr);
    return;
  }
  busy.value = true;
  try {
    await session.redeemCode(
      phone.value.trim(),
      code.value.trim(),
      "takeover",
      cardPayload(),
    );
    afterSuccess("已进入你的账号");
  } catch (e) {
    ui.toast(errText(e)); // sms_bad_code / sms_code_invalid 等文案由后端给全
  } finally {
    busy.value = false;
  }
}

/* ---- 成功收尾（建号/短信接管/密码接管共用）：清草稿 → 接着完成挂起动作 → 关弹层。
     续办单一源在 composables/pendingResume（登录页登回来那路同款） ---- */
function afterSuccess(msg: string): void {
  clearCardDraft();
  void runPendingResume(pendingSnapshot());
  ui.toast(msg);
  ui.closeSheet();
}
</script>

<style lang="scss" scoped>
/* 壳层标题/hint 走全局 .sheet-t/.sheet-hint（base.scss 收源） */
/* 标题行：右上角【登录】全天候亮（1.6 §4.2 替代 1.1 底部小字"我是老球友"） */
.trow {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}
.login-link {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--lemon);
  cursor: pointer;
}
.login-link:active {
  opacity: 0.7;
}

/* 占卡三出口（1.6 §4.5）：纵向排列，微信位与返回重填是轻量行 */
.exits {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 4px;
}
/* 微信内快进卡：授权钮紧跟标题行，底部出路小字给不用微信的人 */
.wx-go {
  margin-top: 20px;
}
.wx-out {
  font-size: 11px;
  color: var(--dim);
  text-align: center;
  line-height: 1.5;
  margin-top: 12px;
}
.relink {
  font-size: 12px;
  color: var(--dim);
  text-align: center;
  cursor: pointer;
  padding: 2px 0;
}
.relink:active {
  color: var(--lemon);
}

.flex1 {
  flex: 1;
}

/* 预设头像组：横向滚动一屏可选（1.1 A2 空状态） */
.presets {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding: 2px 0 6px;
}
.ptile {
  flex: none;
  width: 60px;
  height: 60px;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--ink3);
  cursor: pointer;
}
.ptile.on {
  border-color: var(--lemon);
  box-shadow: 0 0 0 1px var(--lemon);
}

/* 手机号用途说明（1.1 §6 告知义务） */
.pnote {
  font-size: 11px;
  color: var(--dim);
  margin-top: 6px;
  line-height: 1.5;
}

/* 短信态：码输入行 + 客服出口写死在底部（1.1 A1） */
.frow {
  display: flex;
  gap: 10px;
  align-items: center;
}
.kefu {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  margin-top: 12px;
  text-align: center;
}
</style>
