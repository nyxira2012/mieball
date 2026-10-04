<template>
  <!-- 名片建号卡（1.1 A1 · 三态）：填卡 → 手机号被占（接管/重填）→ 短信验证进入。
       游客点报名/建局时弹出，成功后自动接着完成挂起动作（D3：用户看一步，系统拆两步）。
       草稿落本机：断网/中断后已填内容不丢（§5 出错条目）。 -->
  <view class="ss">
    <!-- ===== 态一：填名片 ===== -->
    <template v-if="mode === 'card'">
      <view class="t">{{ title }}</view>
      <view class="hint">填张名片就同时建号 · 以后永远免密，不用记密码</view>

      <AppField label="叫什么">
        <AppInput v-model="nickname" placeholder="常用球友名，如 海淀反手王（可跳过）" :maxlength="16" />
      </AppField>

      <AppField label="选个头像">
        <view class="preset-note">点一下秒选；跳过用默认图案（装扮页可细调）</view>
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
        <AppInput v-model="phone" type="number" placeholder="11 位手机号" :maxlength="11" />
        <view class="pnote">用于球局紧急通知、防鸽子和跨设备找回；同局球友会看到你的尾号 4 位</view>
      </AppField>

      <AppButton variant="pri" block :disabled="busy" @click="onSubmitCard">
        {{ busy ? '提交中…' : actionLabel }}
      </AppButton>
    </template>

    <!-- ===== 态二：手机号已被占用（4.5） ===== -->
    <template v-else-if="mode === 'occupied'">
      <view class="t">这个手机号已经有人用了</view>
      <view class="hint">手机号永远归手机的主人——短信验证是最终裁决，验证后立即进入那个账号</view>
      <view class="btns">
        <AppButton variant="ghost" class="flex1" @click="mode = 'card'">不是我的号？返回重填</AppButton>
        <AppButton variant="pri" class="flex1" :disabled="busy" @click="onTakeover">用短信验证，进入</AppButton>
      </view>
    </template>

    <!-- ===== 态三：短信验证（接管） ===== -->
    <template v-else>
      <view class="t">短信验证</view>
      <view class="hint">验证码已发至 {{ phone }}（找回/接管都走这里，手机在谁手里号就归谁）</view>
      <AppField label="6 位验证码">
        <view class="frow">
          <AppInput v-model="code" type="number" placeholder="6 位数字" :maxlength="6" class="flex1" />
          <AppButton variant="ghost" size="sm" :disabled="countdown > 0 || busy" @click="onResend">
            {{ countdown > 0 ? `${countdown}s` : '重新发送' }}
          </AppButton>
        </view>
      </AppField>
      <AppButton variant="pri" block :disabled="busy" @click="onVerify">{{ busy ? '验证中…' : '验证并进入' }}</AppButton>
      <view class="kefu">收不到码且发码不是你本人操作的 · 联系平台客服微信 mieball-kefu</view>
    </template>
  </view>
</template>

<script setup lang="ts">
/* 名片建号卡：表单态 + 占用态 + 短信态。动作全走 session store（深模块），
   本组件只管状态机与草稿；错误按 ApiError.code 分支提示。 */
import { computed, onUnmounted, ref, watch } from 'vue';
import type { PropType } from 'vue';
import AppButton from '@/components/ui/AppButton.vue';
import AppField from '@/components/ui/AppField.vue';
import AppInput from '@/components/ui/AppInput.vue';
import ChibiAvatar from '@/components/ui/ChibiAvatar.vue';
import { useGameStore } from '@/stores/game';
import { useLiveStore } from '@/stores/live';
import { useSessionStore } from '@/stores/session';
import { useUiStore } from '@/stores/ui';
import { ApiError, clearCardDraft, readCardDraft, writeCardDraft } from '@/api/http';
import type { ChibiConfig, PublishInput } from '@/api/types';

const props = defineProps({
  pendingJoin: { type: Object as PropType<{ gameId: number; bring: number }>, default: undefined },
  pendingLaunch: { type: Object as PropType<PublishInput>, default: undefined },
  /** 扫码签到（2.1·选项A）：游客在现场页点「我到了」→ 建号成功后自动签到进候场区 */
  pendingCheckin: { type: Object as PropType<{ gameId: number }>, default: undefined },
});

const session = useSessionStore();
const game = useGameStore();
const liveStore = useLiveStore();
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

const mode = ref<'card' | 'occupied' | 'sms'>('card');
const nickname = ref('');
const phone = ref('');
const code = ref('');
/** 选中的预设下标；null=没选（跳过 → 服务端默认小人） */
const picked = ref<number | null>(null);
const busy = ref(false);
const countdown = ref(0);
let timer: ReturnType<typeof setInterval> | null = null;

const title = computed(() => (props.pendingJoin ? '填张名片，报名' : props.pendingLaunch ? '填张名片，建局' : '填张名片'));
const actionLabel = computed(() => (props.pendingJoin ? '确定报名' : props.pendingLaunch ? '确定建局' : '确定'));

/* ---- 草稿：本机持久化（断网重进内容还在） ---- */
const draft = readCardDraft<{ nickname: string; phone: string; picked: number | null }>();
if (draft) {
  nickname.value = draft.nickname ?? '';
  phone.value = draft.phone ?? '';
  picked.value = draft.picked ?? null;
}
watch([nickname, phone, picked], () => {
  writeCardDraft({ nickname: nickname.value, phone: phone.value, picked: picked.value });
});

function pick(i: number): void {
  picked.value = picked.value === i ? null : i;
}

function startCountdown(): void {
  countdown.value = 60;
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

function errMsg(e: unknown): string {
  return e instanceof ApiError ? e.message : '出错了，请稍后再试';
}

/* ---- 提交名片 ---- */
async function onSubmitCard(): Promise<void> {
  const p = phone.value.trim();
  if (!/^1[3-9]\d{9}$/.test(p)) {
    ui.toast('请输入 11 位手机号');
    return;
  }
  busy.value = true;
  try {
    await session.signupWithCard({
      phone: p,
      nickname: nickname.value,
      nickname_set: !!nickname.value.trim(),
      chibi: picked.value != null ? PRESETS[picked.value].c : undefined,
      chibi_set: picked.value != null,
    });
    afterSuccess(props.pendingJoin ? '报名完成，已在名单中' : '账号建好了');
  } catch (e) {
    if (e instanceof ApiError && e.code === 'phone_taken') {
      mode.value = 'occupied';
    } else {
      ui.toast(errMsg(e));
    }
  } finally {
    busy.value = false;
  }
}

/* ---- 占用 → 接管 ---- */
async function onTakeover(): Promise<void> {
  busy.value = true;
  try {
    await session.requestCode(phone.value.trim(), 'takeover');
    startCountdown();
    mode.value = 'sms';
  } catch (e) {
    ui.toast(errMsg(e));
  } finally {
    busy.value = false;
  }
}

async function onResend(): Promise<void> {
  busy.value = true;
  try {
    await session.requestCode(phone.value.trim(), 'takeover');
    startCountdown();
    ui.toast('验证码已重发');
  } catch (e) {
    ui.toast(errMsg(e));
  } finally {
    busy.value = false;
  }
}

async function onVerify(): Promise<void> {
  if (code.value.trim().length !== 6) {
    ui.toast('请输入 6 位验证码');
    return;
  }
  busy.value = true;
  try {
    await session.redeemCode(phone.value.trim(), code.value.trim(), 'takeover', {
      phone: phone.value.trim(),
      nickname: nickname.value,
      nickname_set: !!nickname.value.trim(),
      chibi: picked.value != null ? PRESETS[picked.value].c : undefined,
      chibi_set: picked.value != null,
    });
    afterSuccess('已进入你的账号');
  } catch (e) {
    ui.toast(errMsg(e)); // sms_bad_code / sms_code_invalid 等文案由后端给全
  } finally {
    busy.value = false;
  }
}

/* ---- 成功收尾：清草稿 → 接着完成挂起动作（报名/建局/扫码签到）→ 关弹层 ---- */
function afterSuccess(msg: string): void {
  clearCardDraft();
  if (props.pendingJoin) {
    game.joinGame(props.pendingJoin.gameId, props.pendingJoin.bring);
  } else if (props.pendingLaunch) {
    game.publishGame(props.pendingLaunch);
    uni.switchTab({ url: '/pages/meet/meet' }); // 建局成功回约球页（与 LaunchSheet.publish 同径）
  } else if (props.pendingCheckin) {
    liveStore.arriveMe(props.pendingCheckin.gameId); // 2.1 选项A：建号即球友，自动「我到了」
  }
  ui.toast(msg);
  ui.closeSheet();
}
</script>

<style lang="scss" scoped>
/* 壳层标题/hint 与 JoinSheet/AccountSheet 同款 */
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
.btns {
  display: flex;
  gap: 10px;
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
