/* 会话 store（1.1 账号域 + 1.6 密码钥匙的前端深模块）：身份生命周期全在这——
   启动认人 / 名片建号 / 短信找回与接管 / 密码登录与设改密 / 退出 / 注销 / 改名片。

   身份位单一源在 user store（me 对象原位换装：applyAccount/resetGuest），
   本 store 只管钥匙生命周期与账号档案镜像。组件层不直接碰 http/api，
   只消费本 store 的动作与状态。 */
import { computed, ref } from "vue";
import { defineStore } from "pinia";
import {
  apiDeactivate,
  apiLogout,
  apiMe,
  apiPasswordChange,
  apiPasswordLogin,
  apiPasswordRedeem,
  apiPasswordReset,
  apiPasswordSet,
  apiPhoneBind,
  apiPhoneBindSend,
  apiRedeem,
  apiSendCode,
  apiSignup,
  apiUpdateProfile,
  apiWechatLogin,
  apiWechatRedeem,
  type AccountView,
  type CardPayload,
  type SessionPayload,
  type SmsPurpose,
} from "@/api/auth";
import { clearCardDraft, deviceMarker, getToken, setToken } from "@/api/http";
import type { CardBg, ChibiConfig } from "@/api/types";
import { useUiStore } from "./ui";
import { useUserStore } from "./user";

export const useSessionStore = defineStore("session", () => {
  const ui = useUiStore();

  /** guest=游客（含启动认人失败静默降级）；ready=已带有效钥匙 */
  const status = ref<"guest" | "ready" | "init">("init");
  const account = ref<AccountView | null>(null);
  /** 微信绑定凭条（1.7）：授权认人后攥在手里，下一个验明正身动作（建号/短信/密码）
      自动捎带上——绑成了后端回 wechat_bound，这里统一说「已绑上」并清凭条；
      验证失败不烧凭条（后端一次性，十分钟自然过期）。仅内存：整页跳转后由
      登录页回话重新落位（wechatLogin 回话里带）。 */
  const wechatBindToken = ref<string | null>(null);

  const isGuest = computed(() => status.value !== "ready");
  /** 名片尾号：无号（快进号/游客）→ null，页面尾号位显「未绑手机」——
      不回落演示尾号（1.8 A1：假尾号骗人，顺带修正） */
  const phoneTail = computed<string | null>(
    () => account.value?.phone_tail ?? null,
  );
  /** 本人手机号打码（139****1234）：我的页账号区与注销短信步共用展示口径；无账号 → null */
  const maskedPhone = computed<string | null>(() => {
    const p = account.value?.phone ?? "";
    return p ? `${p.slice(0, 3)}****${p.slice(-4)}` : null;
  });
  /** 微信绑没绑（AccountView 持久定值，1.8 批3）：我的页「微信已绑定」行两态唯一判定 */
  const wechatBound = computed(() => account.value?.wechat_bound ?? false);

  /* ---- 动作 ---- */

  /** 启动认人：有钥匙→换本人档案；没钥匙/钥匙失效/网络失败→游客，不报错（§B 认人） */
  async function init(): Promise<void> {
    if (!getToken()) {
      status.value = "guest";
      return;
    }
    try {
      const { account: view } = await apiMe();
      if (view) {
        applySelfView(view);
        status.value = "ready";
      } else {
        resetToGuest(); // 钥匙已作废（被接管/注销/退出）→ 静默降级游客
      }
    } catch {
      status.value = "guest"; // 网络问题不拦启动，按游客先进场
    }
  }

  /** 名片建号（4.2）：成功落钥匙+档案并清草稿；手机号被占抛 ApiError('phone_taken') 由弹层接。
      1.7：微信凭条在手则捎带——建号顺手绑（弱档），绑成了提示不说谎（没绑上不说） */
  async function signupWithCard(card: CardPayload): Promise<AccountView> {
    const res = await apiSignup(
      card,
      deviceMarker(),
      wechatBindToken.value ?? undefined,
    );
    return settleKeys(res, true);
  }

  /** 发验证码（60 秒冷却/一天上限等错误原样抛，弹层按 code 提示） */
  async function requestCode(
    phone: string,
    purpose: SmsPurpose,
  ): Promise<void> {
    await apiSendCode(phone, purpose);
  }

  /** 验证码换钥匙（4.4 找回 / 4.5 接管）：接管带名片做 D5 合并；
      1.7：微信凭条捎带——验明正身=正式绑的好时机（老账号自动接上，4.3） */
  async function redeemCode(
    phone: string,
    code: string,
    purpose: "recovery" | "takeover",
    card?: CardPayload,
  ): Promise<AccountView> {
    const res = await apiRedeem(
      phone,
      code,
      purpose,
      deviceMarker(),
      card,
      wechatBindToken.value ?? undefined,
    );
    return settleKeys(res, true);
  }

  /* ---- 微信钥匙（1.7 第四把）：认人门 + 占卡微信验证 ---- */

  /** 微信认人（4.1/4.2）：绑了直接进；没绑落凭条转名片/验证。凭条恒落位——
      绑着的微信想搬到别的账号，下一个验明正身凭它顶替换绑（4.5 下文）。
      1.8 快进支（opts.fast，动作弹卡主钮出发）：微信没绑过则后端直接开号
      （created：微信生而正式绑、无凭条、与建号同款清草稿）。这里不 toast：
      单槽 toast 会被续办动作原话立刻顶掉——randomName 交回调用方（login.vue）
      排队，动作句说完再报名字（4.1 结果 2）。 */
  async function wechatLogin(
    code: string,
    opts?: { fast?: boolean },
  ): Promise<{ status: "ok" | "unbound" | "created"; randomName: boolean }> {
    const res = await apiWechatLogin(code, deviceMarker(), opts?.fast);
    if (res.status === "created") {
      admitSession({ token: res.token, account: res.account }, true);
      // 名字句让动作句先说——单槽 toast 顶替，randomName 交调用方排队补报
      return { status: "created", randomName: res.nickname_random };
    }
    wechatBindToken.value = res.bind_token;
    if (res.status === "unbound")
      return { status: "unbound", randomName: false };
    admitSession({ token: res.token, account: res.account }, false);
    return { status: "ok", randomName: false };
  }

  /** 占卡「微信验证进入」（4.4/4.5）：正式绑才放行（接管级），指路文案后端给全；
      转场包里存过名片草稿的重建（明确填过的才覆盖，D5 同规） */
  async function wechatRedeem(
    code: string,
    phone: string,
    card?: CardPayload,
  ): Promise<AccountView> {
    const res = await apiWechatRedeem(code, phone, deviceMarker(), card);
    return admitSession(res, true);
  }

  /* ---- 密码钥匙（1.6 §4.8~§4.11）：三动作共用 admitSession 入会壳，失败 ApiError
     原样上抛、身份态不动（请求成功才落钥匙， reject 时一行未执行） ---- */

  /** 密码登录（4.9）/ 忘记密码重置（4.10）：换钥匙不清名片草稿——
      草稿是登录前挂起的报名/建局续办要用的工作面（A1 已填内容不丢）；
      1.7：微信凭条捎带（密码路也是验明正身，B1 两处都消费） */
  async function passwordLogin(
    phone: string,
    password: string,
  ): Promise<AccountView> {
    const res = await apiPasswordLogin(
      phone,
      password,
      deviceMarker(),
      wechatBindToken.value ?? undefined,
    );
    return settleKeys(res, false);
  }

  async function passwordReset(
    phone: string,
    code: string,
    password: string,
  ): Promise<AccountView> {
    const res = await apiPasswordReset(
      phone,
      code,
      password,
      deviceMarker(),
      wechatBindToken.value ?? undefined,
    );
    return settleKeys(res, false);
  }

  /** 占卡「用密码进入」（4.5 三出口之二）：密码接管，名片已并入账号 → 与 redeemCode 同款清草稿 */
  async function passwordRedeem(
    phone: string,
    password: string,
    card?: CardPayload,
  ): Promise<AccountView> {
    const res = await apiPasswordRedeem(
      phone,
      password,
      deviceMarker(),
      card,
      wechatBindToken.value ?? undefined,
    );
    return settleKeys(res, true);
  }

  /** 首设密码（4.8）：短信码或宽限窗验身后落锁；成功文案单一源在这 */
  async function setPassword(
    code: string | null,
    password: string,
  ): Promise<void> {
    await apiPasswordSet(code, password);
    ui.toast("密码已设置 · 以后可用密码登录");
  }

  /** 修改密码（4.11）：例行换钥匙——其他设备记忆不受影响，无感 */
  async function changePassword(oldPwd: string, newPwd: string): Promise<void> {
    await apiPasswordChange(oldPwd, newPwd);
    ui.toast("密码已修改 · 其他设备不用重新登录");
  }

  /* ---- 补绑手机号（1.8 §4.4）：快进号随时补上，必须收码验证。
      占用拒 phone_taken_redirect 原样上抛（指路话术后端单一源，面板内显示 +
      去登录页出口——指路不登出：收编靠 redeem 那刻快进号会话还活着） ---- */

  async function bindPhoneSend(phone: string): Promise<void> {
    await apiPhoneBindSend(phone);
  }

  /** 确认绑上：核销后用返回的最新本人视图原位换装（改名片同款），尾号/微信行立即翻真 */
  async function bindPhoneConfirm(phone: string, code: string): Promise<void> {
    const { account: view } = await apiPhoneBind(phone, code);
    applySelfView(view);
    ui.toast("手机号已绑定");
  }

  /** 退出登录（4.3/A3）：服务端作废本机钥匙 + 本机清记忆；网络失败也照样退出本机 */
  async function logout(): Promise<void> {
    try {
      await apiLogout();
    } catch {
      /* 服务端作废失败不拦退出：钥匙失效重于提示 */
    }
    resetToGuest();
    ui.toast("已退出本机登录 · 数据都在云端");
  }

  /** 注销（4.6）：短信验证本人后由后端匿名化+释放手机号+全钥匙失效 */
  async function deactivateAccount(phone: string, code: string): Promise<void> {
    await apiDeactivate(phone, code);
    resetToGuest();
    ui.toast("已注销 · 档案匿名化 · 手机号已释放");
  }

  /** 退出/注销共用回落：身份位复位游客占位（user store 单点） */
  function resetToGuest(): void {
    setToken(null);
    account.value = null;
    status.value = "guest";
    useUserStore().resetGuest();
  }

  /** 换钥匙入会壳：五路动作（建号/短信接管/密码登录·重置·接管）+ 微信认人共用同一
      落钥匙五连，请求成功才动身份态、reject 时一行未执行；是否清名片草稿由调用点
      显式裁定（只有 redeem 路清——登录/重置路的草稿是挂起续办的工作面，不能动）。
      1.7：绑成了才说「已绑上」（wechat_bound 后端定值，一个字不编）并清凭条 */
  function admitSession(res: SessionPayload, clearDraft: boolean): AccountView {
    setToken(res.token);
    applySelfView(res.account);
    status.value = "ready";
    if (res.wechat_bound) {
      ui.toast("微信号已绑上 · 下次微信一键直接进");
    }
    if (clearDraft) clearCardDraft();
    return res.account;
  }

  /** 本人视图原位换装：档案镜像位与全局身份位（user store me）同步——
      init/admitSession/改名片/补绑确认四路共用，换装要多带一步时只改这里 */
  function applySelfView(view: AccountView): void {
    account.value = view;
    useUserStore().applyAccount(view);
  }

  /** 捎带微信凭条的验明正身收尾（建号/短信/密码五路共用）：入会 + 成功即烧凭条
      （捎带过的凭条服务端已一次性核销，不清会死凭条乱捎；失败不动、留着重试）。
      不折进 admitSession——wechatLogin 的 unbound 路要保住凭条等下一个动作 */
  function settleKeys(res: SessionPayload, clearDraft: boolean): AccountView {
    const out = admitSession(res, clearDraft);
    wechatBindToken.value = null;
    return out;
  }

  /** 改名片（A3）：昵称/小人/卡背随时可改。游客态走本地演示保存（不接后端） */
  async function saveProfile(patch: {
    nickname?: string;
    chibi?: ChibiConfig;
    card_bg?: CardBg;
  }): Promise<string> {
    const n = (patch.nickname ?? "").trim();
    if (!n) {
      const m = "昵称不能为空";
      ui.toast(m);
      return m;
    }
    if (status.value !== "ready" || !account.value) {
      useUserStore().me.name = n; // 游客：演示态本地改名
      const msg = "已保存（演示态 · 登录后云端同步）";
      ui.toast(msg);
      return msg;
    }
    const { account: view } = await apiUpdateProfile({
      nickname: n,
      chibi: patch.chibi,
      card_bg: patch.card_bg,
    });
    applySelfView(view);
    const msg = "已保存 · 全局同步换新";
    ui.toast(msg);
    return msg;
  }

  return {
    status,
    account,
    isGuest,
    phoneTail,
    maskedPhone,
    wechatBound,
    wechatBindToken,
    init,
    signupWithCard,
    requestCode,
    redeemCode,
    wechatLogin,
    wechatRedeem,
    passwordLogin,
    passwordReset,
    passwordRedeem,
    setPassword,
    changePassword,
    bindPhoneSend,
    bindPhoneConfirm,
    logout,
    deactivateAccount,
    saveProfile,
  };
});
