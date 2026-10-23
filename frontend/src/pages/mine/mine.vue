<template>
  <!-- 我的页（P10）· 5.1 重做：形象区（点形象进装扮页）/ 账单卡（全量三数）/ 记录双卡 / 账号区。
       旧「本期账本」卡、换装行、我的球局列表
       分别由账单页（bills）、装扮页（dress）、登记/记录页（signup/logs）接管。 -->
  <PageShell tab="mine">
    <!-- 头部：kicker + brand（「的」字黄色） -->
    <view class="stag">
      <view class="kicker">Player Card</view>
      <view class="brand">我<text class="bem">的</text>球场</view>
    </view>

    <!-- 头部形象区（5.1 页面设计）：点形象即进装扮页。名片铺我的卡背（'f' 档全幅，
         无卡背/访客素卡渐变兜底）、头像换圆章（me.avatarUrl 后端解析直出） -->
    <view class="mecard">
      <CardBackdrop :cid="me.back ?? null" mode="f" />
      <view class="av" @click="go('/pages/mine/dress')">
        <AvatarBadge :url="me.avatarUrl ?? null" :size="88" />
      </view>
      <view class="minfo">
        <view class="mname">{{ meName }}</view>
        <view class="mrecord">{{ record }}</view>
        <view class="mchips">
          <!-- DUPR 位：tierB 徽章 + DUPR 分 + 档名（chip ok） -->
          <AppChip kind="ok">
            <TierBadge :tier="meTier" /> DUPR <DuprScore :d="duprOf(me)" /> ·
            {{ meTier }}
          </AppChip>
          <!-- 尾号 chip（1.8 A1）：有号显真实尾号；无号（含游客）显「未绑手机」，
               不吃演示尾号（假尾号骗人，顺带修正） -->
          <AppChip>{{
            session.phoneTail ? `尾号 ···${session.phoneTail}` : "未绑手机"
          }}</AppChip>
          <!-- 档案卡 = 别人看到的完整档案（与打球页名单点击同支弹层，userId 0 = 我） -->
          <AppChip @click="onProfileCard">档案卡 ▸</AppChip>
          <!-- 装扮入口（与点头像同页） -->
          <AppChip @click="go('/pages/mine/dress')">装扮 ▸</AppChip>
        </view>
      </view>
    </view>

    <!-- 账单卡（5.1）：totalSummary 是 store 的全量口径——period 单例跨页存活，
         账单页切过筛选后 summary 会带着漂，主页卡/注销守卫不能消费它；
         整卡可点进账单页看期间筛选与逐笔（class/@click 透传到 BillSummaryCard 根） -->
    <SectionTitle title="账单" more="明细 ▸" @more="go('/pages/mine/bills')" />
    <BillSummaryCard
      class="bill-card"
      :due="bill.totalSummary.due"
      :paid="bill.totalSummary.paid"
      :receivable="bill.totalSummary.receivable"
      @click="go('/pages/mine/bills')"
    />

    <!-- 记录双卡（5.1 页面设计）：登记局数/打完局数读真局 myGames（后端按角色裁好；
         mock 时代的「签到时刻」无后端读取面，随演示快照退役改「打完」口径） -->
    <view class="duo">
      <view class="d-card" @click="go('/pages/mine/signup')">
        <view class="d-t">参加登记</view>
        <view class="d-s"
          >共 {{ game.mySignups.length }} 局 · 打完
          {{ game.myDone.length }} 局</view
        >
      </view>
      <view class="d-card" @click="go('/pages/mine/logs')">
        <view class="d-t">打球记录</view>
        <view class="d-s">累计 {{ me.play }} 场</view>
      </view>
    </view>

    <!-- 账号区（1.6 批3 · 1.8 修订）：手机号行两态（无号=「未绑定」安静行点开补绑面板，
         除此外零补绑提示）；密码区块按 has_password 分流设/改密（4.8/4.11）；
         微信行两态（已绑才显示）；游客给登录入口 -->
    <SectionTitle title="账号" />
    <view class="acc-links">
      <view v-if="session.isGuest" class="acc-link" @click="goLogin">
        登录 · 我是老球友（手机号找回） <text class="arr">▸</text>
      </view>
      <template v-else>
        <!-- 手机号行两态（1.8 A1）：有号静态照旧；无号安静常驻行（样式同「密码未设置」，
             不标红不推送）点开补绑面板 -->
        <view v-if="session.maskedPhone" class="acc-link static">
          <text>手机号 {{ session.maskedPhone }}</text>
          <text class="arr">账号的根</text>
        </view>
        <view v-else class="acc-link" @click="toggleBindPanel">
          <text>手机号未绑定 · 补上能收通知</text>
          <text class="arr">{{ bindPanel ? "▾" : "▸" }}</text>
        </view>
        <view
          class="acc-link"
          @click="
            togglePwdPanel(session.account?.has_password ? 'change' : 'set')
          "
        >
          <text>{{
            session.account?.has_password
              ? "密码已设置 · 修改密码"
              : "密码未设置 · 设置密码"
          }}</text>
          <text class="arr">{{ pwdPanel ? "▾" : "▸" }}</text>
        </view>
        <!-- 微信行两态（1.8 用户裁决）：已绑静态行；未绑不显示整行（「即将开通」退役） -->
        <view v-if="session.wechatBound" class="acc-link static">
          <text>微信已绑定</text>
        </view>
      </template>
      <!-- 复制诊断日志（6.1 §4.6）：v-if 外=游客也可见可点；纯本地复制，误点无副作用 -->
      <view class="acc-link" @click="onCopyDiag">
        复制诊断日志 <text class="arr">▸</text>
      </view>
    </view>
    <!-- 换号预防提示（A1）：无号（快进号）不显示；「平台客服」对齐 1.6 冻结原文 -->
    <view v-if="!session.isGuest && session.maskedPhone" class="acc-hint">
      手机号是你账号的根 · 换号先联系平台客服
    </view>

    <!-- 密码面板（4.8/4.11）：未设=发码(set_password)+新密码两遍一次提交；
         已设=旧密+新密两遍。成功 toast 文案单一源在 session store -->
    <view v-if="pwdPanel" class="pwd-panel">
      <template v-if="pwdPanel === 'set'">
        <AppField label="6 位短信验证码">
          <view class="frow">
            <AppInput
              v-model="setCode"
              type="number"
              placeholder="6 位数字"
              :maxlength="6"
              class="flex1"
            />
            <AppButton
              variant="ghost"
              size="sm"
              :disabled="setCountdown > 0 || setBusy"
              @click="onSetSend"
            >
              {{
                setCountdown > 0
                  ? `${setCountdown}s`
                  : setSent
                    ? "重新发送"
                    : "发送验证码"
              }}
            </AppButton>
          </view>
        </AppField>
        <AppField label="新密码（至少 6 位）">
          <AppInput
            v-model="setP1"
            placeholder="6 位以上，纯数字也行"
            :maxlength="40"
            password
          />
        </AppField>
        <AppField label="再输一遍确认">
          <AppInput
            v-model="setP2"
            placeholder="两次要一致"
            :maxlength="40"
            password
          />
        </AppField>
        <view v-if="setHint" class="pwd-err">{{ setHint }}</view>
        <AppButton
          variant="pri"
          block
          :disabled="setBusy"
          @click="onSetSubmit"
          >{{ setBusy ? "设置中…" : "设置密码" }}</AppButton
        >
      </template>
      <template v-else>
        <AppField label="旧密码">
          <AppInput
            v-model="oldPwd"
            placeholder="现在用的密码"
            :maxlength="40"
            password
          />
        </AppField>
        <AppField label="新密码（至少 6 位）">
          <AppInput
            v-model="chP1"
            placeholder="6 位以上，纯数字也行"
            :maxlength="40"
            password
          />
        </AppField>
        <AppField label="再输一遍确认">
          <AppInput
            v-model="chP2"
            placeholder="两次要一致"
            :maxlength="40"
            password
          />
        </AppField>
        <view v-if="chHint" class="pwd-err">{{ chHint }}</view>
        <AppButton
          variant="pri"
          block
          :disabled="chBusy"
          @click="onChangeSubmit"
          >{{ chBusy ? "修改中…" : "确认修改" }}</AppButton
        >
      </template>
    </view>
    <!-- 补绑面板（1.8 §4.4）：输号（用途说明与名片卡同文，api/dict 单一源）→ 收码 →
         输码确认。占用拒=后端指路话术全文上面板错误行 + 「去登录页」出口——
         只跳转不 logout 不清 token（收编靠登录页验证那一刻快进号会话还活着） -->
    <view v-if="bindPanel" class="pwd-panel">
      <AppField label="11 位手机号">
        <view class="frow">
          <AppInput
            v-model="bindPhone"
            type="number"
            placeholder="11 位手机号"
            :maxlength="11"
            class="flex1"
          />
          <AppButton
            variant="ghost"
            size="sm"
            :disabled="bindCountdown > 0 || bindBusy"
            @click="onBindSend"
          >
            {{
              bindCountdown > 0
                ? `${bindCountdown}s`
                : bindSent
                  ? "重新发送"
                  : "获取验证码"
            }}
          </AppButton>
        </view>
        <view class="bind-note">{{ PHONE_USE_NOTE }}</view>
      </AppField>
      <AppField label="6 位短信验证码">
        <AppInput
          v-model="bindCode"
          type="number"
          placeholder="6 位数字"
          :maxlength="6"
        />
      </AppField>
      <view v-if="bindHint" class="pwd-err">{{ bindHint }}</view>
      <view v-if="bindTaken" class="bind-go" @click="goLogin">去登录页 ▸</view>
      <AppButton
        variant="pri"
        block
        :disabled="bindBusy"
        @click="onBindConfirm"
        >{{ bindBusy ? "绑定中…" : "确认绑定" }}</AppButton
      >
    </view>
    <!-- 退出/注销账号：未登录不显示更符合逻辑 -->
    <view v-if="!session.isGuest" class="acc-row">
      <AppButton variant="ghost" size="sm" class="grow" @click="onLogout"
        >退出账号</AppButton
      >
      <AppButton
        variant="ghost"
        size="sm"
        class="grow danger"
        @click="onDeleteAcc"
        >注销账号</AppButton
      >
    </view>
  </PageShell>
</template>

<script setup lang="ts">
/* 我的页（P10）· 5.1 我的页主页面：底账入口聚合（账单/登记/记录）+ 账号区。
   meName/战绩/ELO 段位口径保留，其余换装与账本逻辑退场。 */
import { computed, ref, watch } from "vue";
import { onShow } from "@dcloudio/uni-app";
import PageShell from "@/components/biz/PageShell.vue";
import AvatarBadge from "@/components/ui/AvatarBadge.vue";
import CardBackdrop from "@/components/ui/CardBackdrop.vue";
import AppChip from "@/components/ui/AppChip.vue";
import AppButton from "@/components/ui/AppButton.vue";
import AppField from "@/components/ui/AppField.vue";
import AppInput from "@/components/ui/AppInput.vue";
import TierBadge from "@/components/ui/TierBadge.vue";
import DuprScore from "@/components/ui/DuprScore.vue";
import SectionTitle from "@/components/ui/SectionTitle.vue";
import BillSummaryCard from "@/components/biz/BillSummaryCard.vue";
import { useGameStore } from "@/stores/game";
import { useUserStore } from "@/stores/user";
import { useSessionStore } from "@/stores/session";
import { useUiStore } from "@/stores/ui";
import { useBillStore } from "@/stores/bill";
import { exportText } from "@/utils/blackbox";
import { copyWithToast } from "@/utils/clipboard";
import { ApiError, errText } from "@/api/http";
import { PHONE_USE_NOTE } from "@/api/dict";
import { duprOf, duprTier } from "@/utils/elo";
import { useSmsCountdown } from "@/composables/useSmsCountdown";
import { newPwdError, phoneInputError, smsCodeError } from "@/utils/validate";
import { goLogin } from "@/utils/nav";

const user = useUserStore();
const game = useGameStore();
const session = useSessionStore();
const ui = useUiStore();
const bill = useBillStore();

/* 账单卡三数（1.3 批4）：全量口径后端定值，进页拉一次（游客空账；断网静默沿用上次）。
   登记双卡同页重拉 myGames（游客 no_identity 静默在 game store 单一出口） */
onShow(() => {
  bill.loadTotal().catch(() => undefined);
  game.loadMine().catch((e) => ui.toast(errText(e)));
});

/** 账号区行的手机号打码口径在 session store（maskedPhone 单一源，AccountSheet 同消费） */

/** 我（身份位单一源在 user store：游客占位 ↔ 登录账号原位换装，全站同步） */
const me = computed(() => user.me);
/** 游客态或占位名显示为「访客」，登录后显示真实名片昵称 */
const meName = computed(() => {
  if (session.isGuest) return "访客";
  return me.value.name === "我" || me.value.name === "访客"
    ? "访客"
    : me.value.name;
});
/** 战绩行：N 场 · N 胜 · 胜率 N%（0 场人话守卫） */
const record = computed(() =>
  me.value.play === 0
    ? "还没开张"
    : `${me.value.play} 场 · ${me.value.win} 胜 · 胜率 ${Math.round((me.value.win / me.value.play) * 100)}%`,
);
/** DUPR chip 的档名（utils/elo.ts duprTier；未填按 2.5 起步档） */
const meTier = computed(() => duprTier(duprOf(me.value)));

/* —— 导航（uni 路由集中在页面层，store 不碰 uni.*；路由在模板处直读） —— */
function go(url: string): void {
  uni.navigateTo({ url });
}
/** 档案卡弹层 = 别人看到的完整档案卡（传入当前用户真实 id） */
function onProfileCard(): void {
  ui.openSheet({ type: "profile", userId: me.value.id });
}
/** 退出/注销走确认弹层（5.1 弹窗：两步/守卫逻辑在 AccountSheet） */
function onLogout(): void {
  if (session.isGuest) return;
  ui.openSheet({ type: "logout-confirm" });
}
function onDeleteAcc(): void {
  if (session.isGuest) return;
  ui.openSheet({ type: "delete-confirm" });
}
/** 复制诊断日志（6.1 §4.6）：黑匣子导出纯本地文本进剪贴板，不联网；文案口径 spec 附录 A3 */
function onCopyDiag(): void {
  copyWithToast(exportText(), "已复制，发给组织者就行");
}

/* —— 密码区块（1.6 §4.8/§4.11）：has_password 分流设/改密，面板在账号区内联展开 —— */

/** 本人完整手机号（发码往这发；完整号只给自己看，展示一律走 maskedPhone） */
function ownPhone(): string {
  return session.account?.phone ?? "";
}

const pwdPanel = ref<"set" | "change" | null>(null);

/** 行点击开合面板；换向时清另一路的残留输入 */
function togglePwdPanel(kind: "set" | "change"): void {
  if (pwdPanel.value === kind) {
    pwdPanel.value = null;
    return;
  }
  pwdPanel.value = kind;
  setCode.value = "";
  setP1.value = "";
  setP2.value = "";
  setHint.value = "";
  setSent.value = false;
  oldPwd.value = "";
  chP1.value = "";
  chP2.value = "";
  chHint.value = "";
}

/** 设密码（4.8）：发码到本人手机（set_password）→ 输码+新密码两遍一次提交。
    apiPasswordSet 只回 ok，成功后 init() 重拉本人视图翻 has_password */
const { countdown: setCountdown, start: startSetCountdown } = useSmsCountdown();
const setCode = ref("");
const setP1 = ref("");
const setP2 = ref("");
const setHint = ref("");
const setBusy = ref(false);
const setSent = ref(false);

async function onSetSend(): Promise<void> {
  if (!ownPhone()) {
    ui.toast("账号信息加载中，请稍后再试");
    return;
  }
  setBusy.value = true;
  try {
    await session.requestCode(ownPhone(), "set_password");
    setSent.value = true;
    startSetCountdown();
    ui.toast("验证码已发送");
  } catch (e) {
    ui.toast(errText(e));
  } finally {
    setBusy.value = false;
  }
}

async function onSetSubmit(): Promise<void> {
  setHint.value = "";
  const cerr = smsCodeError(setCode.value);
  if (cerr) {
    setHint.value = cerr;
    return;
  }
  const msg = newPwdError(setP1.value, setP2.value); // 前端先拦（≥6 位），后端真闸兜底
  if (msg) {
    setHint.value = msg;
    return;
  }
  setBusy.value = true;
  try {
    await session.setPassword(setCode.value.trim(), setP1.value); // toast 在 store
    pwdPanel.value = null;
    setCode.value = "";
    setP1.value = "";
    setP2.value = "";
    setSent.value = false;
    await session.init();
  } catch (e) {
    setHint.value = errText(e);
  } finally {
    setBusy.value = false;
  }
}

/** 改密码（4.11）：例行换钥匙，其他设备无感；旧密错只提示重输（后端不计锁） */
const oldPwd = ref("");
const chP1 = ref("");
const chP2 = ref("");
const chHint = ref("");
const chBusy = ref(false);

async function onChangeSubmit(): Promise<void> {
  chHint.value = "";
  if (!oldPwd.value) {
    chHint.value = "请输入旧密码";
    return;
  }
  const msg = newPwdError(chP1.value, chP2.value);
  if (msg) {
    chHint.value = msg;
    return;
  }
  chBusy.value = true;
  try {
    await session.changePassword(oldPwd.value, chP1.value); // toast 在 store
    pwdPanel.value = null;
    oldPwd.value = "";
    chP1.value = "";
    chP2.value = "";
  } catch (e) {
    chHint.value = errText(e);
  } finally {
    chBusy.value = false;
  }
}

/* —— 补绑手机号（1.8 §4.4）：安静行点开的两步面板（仿密码面板交互）。
    占用拒不 toast、走面板内错误行显后端指路话术全文；错误随再次发码/确认清掉 —— */

const bindPanel = ref(false);
const bindPhone = ref("");
const bindCode = ref("");
const bindHint = ref("");
/** phone_taken_redirect 才亮「去登录页」出口（其他错误只有话术行） */
const bindTaken = ref(false);
const bindBusy = ref(false);
const bindSent = ref(false);
const { countdown: bindCountdown, start: startBindCountdown } =
  useSmsCountdown();

/* 面板是登录态无号账号的私有面：身份或号码一变（收编换身份/退出变游客），
   展开态与输入/错误/占用指路全是上一具身份的残留——整块作废收起
   （倒计时 useSmsCountdown 自管，不用手动清） */
watch([() => session.isGuest, () => session.maskedPhone], () => {
  bindPanel.value = false;
  resetBindForm();
});

/** 输入/错误/占用指路/已发旗一次清空：开合、身份切换、绑定成功三路共用 */
function resetBindForm(): void {
  bindPhone.value = "";
  bindCode.value = "";
  bindHint.value = "";
  bindTaken.value = false;
  bindSent.value = false;
}

/** 占用拒才亮「去登录页」出口——发码与确认两路同吃这一把尺 */
function isTakenRedirect(e: unknown): boolean {
  return e instanceof ApiError && e.code === "phone_taken_redirect";
}

/** 行点击开合面板；开合都清残留输入（密码面板 toggle 同款） */
function toggleBindPanel(): void {
  bindPanel.value = !bindPanel.value;
  resetBindForm();
}

async function onBindSend(): Promise<void> {
  const perr = phoneInputError(bindPhone.value);
  if (perr) {
    ui.toast(perr);
    return;
  }
  bindBusy.value = true;
  try {
    await session.bindPhoneSend(bindPhone.value.trim());
    bindHint.value = "";
    bindTaken.value = false;
    bindSent.value = true;
    startBindCountdown();
    ui.toast("验证码已发送");
  } catch (e) {
    bindHint.value = errText(e);
    bindTaken.value = isTakenRedirect(e);
  } finally {
    bindBusy.value = false;
  }
}

async function onBindConfirm(): Promise<void> {
  bindHint.value = "";
  bindTaken.value = false;
  const perr = phoneInputError(bindPhone.value);
  if (perr) {
    bindHint.value = perr;
    return;
  }
  const cerr = smsCodeError(bindCode.value);
  if (cerr) {
    bindHint.value = cerr;
    return;
  }
  bindBusy.value = true;
  try {
    await session.bindPhoneConfirm(
      bindPhone.value.trim(),
      bindCode.value.trim(),
    ); // toast 在 store
    bindPanel.value = false;
    resetBindForm();
  } catch (e) {
    bindHint.value = errText(e);
    bindTaken.value = isTakenRedirect(e);
  } finally {
    bindBusy.value = false;
  }
}
</script>

<style lang="scss" scoped>
/* ---------- 头部 brand：版式走全局 .brand 类，此处只补 h1 的 UA 默认加粗 ---------- */
.brand {
  font-weight: 700;
}

/* ---------- mecard ---------- */
/* 宿主契约（CardBackdrop）：relative+hidden 裁圆角出血；z-index:0 立层叠上下文，
   让负 z-index 的卡底层垫在卡底渐变之上、文字之下。渐变即素卡兜底（访客/无卡背） */
.mecard {
  position: relative;
  z-index: 0;
  overflow: hidden;
  display: flex;
  gap: 16px;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  padding: 18px;
  background: linear-gradient(150deg, var(--ink3), var(--ink2));
}
.mecard .av {
  width: 88px;
  height: 88px;
  flex: none;
  cursor: pointer;
  transition: transform 0.2s;
}
.mecard .av:active {
  transform: scale(0.92) rotate(-6deg);
}
.minfo {
  flex: 1;
  min-width: 0;
}
.mname {
  font-size: 20px;
  font-weight: 800;
}
.mrecord {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--dim);
  margin: 3px 0 8px;
}
/* chips 行（4 枚起换行兜底） */
.mchips {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

/* ---------- 账单卡（三数版式与配色内聚在 BillSummaryCard，此处只挂点击态） ---------- */
.bill-card {
  cursor: pointer;
}
.bill-card:active {
  border-color: rgba(255, 212, 0, 0.4);
}

/* ---------- 记录双卡（5.1：参加登记 / 打球记录，mecard 简化版式） ---------- */
.duo {
  display: flex;
  gap: 10px;
  margin-top: 14px;
}
.d-card {
  flex: 1;
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  padding: 14px 16px;
  background: linear-gradient(150deg, var(--ink3), var(--ink2));
  cursor: pointer;
}
.d-card:active {
  border-color: rgba(255, 212, 0, 0.4);
}
.d-t {
  font-size: 15px;
  font-weight: 800;
}
.d-s {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  margin-top: 4px;
}

/* ---------- 账号区（5.1：行式入口 + 退出/注销） ---------- */
.acc-links {
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  overflow: hidden;
  background: var(--ink2);
  margin-bottom: 14px;
}
.acc-link {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 13px 16px;
  font-size: 13px;
  cursor: pointer;
}
.acc-link + .acc-link {
  border-top: 1px solid var(--line);
}
.acc-link .arr {
  font-family: var(--mono);
  color: var(--dim);
}
.acc-link:active {
  color: var(--lemon);
}
/* 静态信息行（手机号/微信授权）：不可点，压掉 active 变色 */
.acc-link.static {
  cursor: default;
}
.acc-link.static:active {
  color: inherit;
}
/* 换号预防提示（A1） */
.acc-hint {
  font-size: 11px;
  color: var(--dim);
  margin: -6px 2px 14px;
  line-height: 1.5;
}
/* 密码面板：与 acc-links 同框风格 */
.pwd-panel {
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  background: var(--ink2);
  padding: 14px 16px 16px;
  margin-bottom: 14px;
}
.pwd-err {
  font-size: 12px;
  color: var(--coral);
  margin: 2px 2px 12px;
  line-height: 1.5;
}
/* 补绑面板（1.8）：用途说明与名片卡同文（api/dict 单一源）；去登录页出口随指路话术亮 */
.bind-note {
  font-size: 11px;
  color: var(--dim);
  margin-top: 6px;
  line-height: 1.5;
}
.bind-go {
  font-size: 12px;
  color: var(--lemon);
  margin: -6px 2px 12px;
  cursor: pointer;
}
.frow {
  display: flex;
  gap: 10px;
  align-items: center;
}
.flex1 {
  flex: 1;
}
.acc-row {
  display: flex;
  gap: 10px;
}
.acc-row .grow {
  flex: 1;
}
/* 注销 = 珊瑚描边强化（同 detail.vue .cancel-btn 口径；双类选择器压过 AppButton 内部 .btn-ghost） */
.acc-row .danger {
  color: var(--coral);
  border-color: rgba(255, 90, 54, 0.4);
}
</style>
