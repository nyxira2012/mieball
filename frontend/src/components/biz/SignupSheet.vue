<template>
  <!-- 名片建号卡（1.1 A1 三态 + 1.6 扩展）：填卡 → 手机号被占（三出口接管/重填）→ 短信/密码验证进入。
       游客点报名/建局/留意向时弹出（或从约球页游客入口直开），成功后自动接着完成挂起动作
       （D3：用户看一步，系统拆两步）。草稿落本机：断网/中断后已填内容不丢（§5 出错条目）。
       右上角【登录】全天候亮（1.6 §4.2，替代 1.1 底部"我是老球友"小字）：
       点了落挂起快照进信号位、直达登录页，登完回来动作接着办。 -->
  <view class="ss">
    <!-- ===== 态一：填名片 ===== -->
    <template v-if="mode === 'card'">
      <view class="trow">
        <view class="sheet-t">{{ title }}</view>
        <view class="login-link" @click="goLogin">登录 ▸</view>
      </view>
      <view class="sheet-hint"
        >填张名片就同时建号 · 以后永远免密，不用记密码</view
      >

      <AppField label="叫什么">
        <AppInput
          v-model="nickname"
          placeholder="常用球友名，如 海淀反手王（可跳过）"
          :maxlength="16"
        />
      </AppField>

      <AppField label="选个头像">
        <view class="preset-note">跳过就用默认图案 · 装扮页可细调</view>
        <view class="presets">
          <view
            v-for="(p, i) in PRESETS"
            :key="i"
            class="ptile"
            :class="{ on: picked === i }"
            @click="pick(i)"
          >
            <ChibiAvatar :chibi="p.c" :size="44" />
          </view>
        </view>
      </AppField>

      <AppField label="手机号">
        <AppInput
          v-model="phone"
          type="number"
          placeholder="11 位手机号"
          :maxlength="11"
        />
        <view class="pnote"
          >用于球局紧急通知、防鸽子和跨设备找回；同局球友会看到你的尾号 4
          位</view
        >
      </AppField>

      <AppButton variant="pri" block :disabled="busy" @click="onSubmitCard">
        {{ busy ? "提交中…" : actionLabel }}
      </AppButton>
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
        <!-- 微信位（1.6 §4.12）：给位不给死按钮，点了说明 -->
        <view class="wx-row" @click="onWechat">
          <text>微信验证进入</text>
          <text class="wx-note">即将开通</text>
        </view>
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
import { useSessionStore } from "@/stores/session";
import { useUiStore } from "@/stores/ui";
import { runPendingResume } from "@/composables/pendingResume";
import type { CardPayload } from "@/api/auth";
import {
  ApiError,
  clearCardDraft,
  errText,
  readCardDraft,
  writeCardDraft,
} from "@/api/http";
import { useSmsCountdown } from "@/composables/useSmsCountdown";
import { isValidPhone } from "@/utils/validate";
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

/** 预设头像组（D2）：提前搭配好的 Q 版小人，点一下即选；细调去装扮页 */
const PRESETS: { c: ChibiConfig }[] = [
  { c: { skin: 0, hair: 0, hc: 0, shirt: 5, face: 0, acc: 0 } },
  { c: { skin: 1, hair: 5, hc: 0, shirt: 1, face: 1, acc: 2 } },
  { c: { skin: 0, hair: 2, hc: 5, shirt: 7, face: 3, acc: 1 } },
  { c: { skin: 0, hair: 1, hc: 2, shirt: 2, face: 0, acc: 0 } },
  { c: { skin: 1, hair: 4, hc: 3, shirt: 6, face: 2, acc: 0 } },
  { c: { skin: 2, hair: 0, hc: 1, shirt: 4, face: 1, acc: 1 } },
  { c: { skin: 0, hair: 3, hc: 4, shirt: 0, face: 3, acc: 0 } },
  { c: { skin: 1, hair: 1, hc: 5, shirt: 3, face: 0, acc: 1 } },
];

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

/** 名片草稿_payload（D5 合并用）：建号 / 短信接管 / 密码接管三路同形，收一处防漂移 */
function cardPayload(): CardPayload {
  return {
    phone: phone.value.trim(),
    nickname: nickname.value,
    nickname_set: !!nickname.value.trim(),
    chibi: picked.value != null ? PRESETS[picked.value].c : undefined,
    chibi_set: picked.value != null,
  };
}

/** 挂起动作快照：goLogin 落信号位与成功续办两处同用 */
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
function goLogin(): void {
  flushDraft();
  ui.pendingAfterLogin = pendingSnapshot();
  uni.navigateTo({ url: "/pages/mine/login" });
}

/* ---- 提交名片 ---- */
async function onSubmitCard(): Promise<void> {
  if (!isValidPhone(phone.value.trim())) {
    ui.toast("请输入 11 位手机号");
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

/** 微信位（1.6 §4.12）：资质未到，点了只说明，不放死按钮 */
function onWechat(): void {
  ui.toast("微信登录即将开通 · 资质到位后点亮");
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
  if (code.value.trim().length !== 6) {
    ui.toast("请输入 6 位验证码");
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
.wx-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1px dashed var(--line);
  border-radius: var(--r-md);
  padding: 11px 14px;
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
.preset-note {
  font-size: 11px;
  color: var(--dim);
  margin-bottom: 8px;
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
