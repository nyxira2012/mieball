// #ifdef MP-WEIXIN
/* mpAuth —— 小程序端微信钥匙编排：wx.login 静默换 code（不跳授权确认页，
   一两秒直进）→ 复用 session 微信认人门走 mp 通道 → 三态就地消费。
   与 wechat.ts 的 H5 授权跳转路互斥：goWechatAuth 顶部条件编译分流至此，宿主零改动。
   整文件 #ifdef 包裹：H5 构建整段剔除，uni.login 不进网页包（零扰动硬要求）。 */
import { cardPayloadOf } from "@/api/auth";
import { ApiError, errText, readCardDraft } from "@/api/http";
import { runPendingResume } from "@/composables/pendingResume";
import { useSessionStore } from "@/stores/session";
import {
  TOAST_VISIBLE_MS,
  hasPending,
  useUiStore,
  type SignupPending,
} from "@/stores/ui";
import { LOGIN_PATH, goMeet } from "@/utils/nav";

export type MpLoginOpts = {
  /** 动作弹卡主钮出发（快进建号）：微信没绑过则后端直接开号 */
  fast?: boolean;
  /** 卡上手填昵称（手填优先于微信昵称） */
  nickname?: string;
  /** 卡上手机号——没人用建带号账号、撞占用后端拒 phone_taken */
  phone?: string;
  /** 卡上选的公共头像编号 */
  avatar?: string;
  /** 出发前进行到一半的动作（进门/建号成功后接着办） */
  pending?: SignupPending | null;
  /** 占卡「微信验证进入」（H5 语境 = 带 phone 且无 fast）：走 wechatRedeem 接管路 */
  redeemPhone?: string;
};

/** in-flight 旗：识别身份的一两秒里连点只认第一次，完成即复位 */
let inFlight = false;

export async function mpLogin(opts: MpLoginOpts): Promise<void> {
  if (inFlight) return;
  inFlight = true;
  const ui = useUiStore();
  const session = useSessionStore();
  try {
    const code = await new Promise<string>((resolve) => {
      uni.login({
        provider: "weixin",
        success: (r) => resolve(r.code || ""),
        fail: () => resolve(""),
      });
    });
    if (!code) {
      ui.toast("微信登录没成功，再试一次");
      return;
    }
    if (opts.redeemPhone) {
      // 占卡微信验证（接管级，mp 通道查小程序钥匙）：名片草稿是出发前
      // SignupSheet flush 进本机的，就地重建（login.vue cardFromDraft 的 mp 孪生）
      const card = cardFromDraft(opts.redeemPhone);
      await session.wechatRedeem(code, opts.redeemPhone, card, "mp");
      ui.toast("已进入你的账号");
      await landInPlace(opts.pending);
      return;
    }
    const r = await session.wechatLogin(code, {
      fast: opts.fast,
      nickname: opts.nickname,
      phone: opts.phone,
      avatar: opts.avatar,
      source: "mp",
    });
    if (r.status === "unbound") {
      // 小程序认不出 = 普通新人卡（action 来源，微信授权登录快进钮随卡），
      // 不走 H5 的 wechat-return 找回面——不指路短信验证回家
      ui.signupThen(opts.pending ?? {}, "action");
      return;
    }
    if (r.status === "created" && r.randomName && session.account) {
      // 随机名主人不知道自己叫什么：名字句让动作句先说（单槽 toast 后到顶掉，
      // 与 login.vue 回跳路同款排队节奏）
      const sayName = () =>
        ui.toast(`名单里你叫『${session.account?.name}』，随时可改`);
      if (hasPending(opts.pending ?? {}))
        setTimeout(sayName, TOAST_VISIBLE_MS + 200);
      else sayName();
    }
    await landInPlace(opts.pending);
  } catch (e) {
    if (e instanceof ApiError && e.code === "phone_taken") {
      // 快进带号撞占用：重开名片卡直落占卡三出口；占卡信号必须落在
      // signupThen 之后（openSheet 会清）。无整页跳转，卡就在眼前切占卡态，免 toast
      ui.signupThen(opts.pending ?? {}, "action");
      ui.signupOccupiedPhone = opts.phone ?? "";
      return;
    }
    if (e instanceof ApiError && e.code === "wechat_off") {
      // 通道未开点了才知道：落降级信号（名片卡撤快进钮、落手填确定——退建号
      // 老路，新球友照常能注册）+ 原句就地保证，不依赖后端文案
      ui.mpWechatOff = true;
      ui.toast("微信登录即将开通 · 资质到位后点亮");
      return;
    }
    ui.toast(errText(e));
  } finally {
    inFlight = false;
  }
}

/** 进门/建号成功收尾：续办挂起动作 → 关弹层；宿主是登录页时回上一页
    （「直接进入他原来的账号」的画面收尾——登录页各成功路都 navigateBack，
    静默登录无整页跳转，这里对齐；深链冷开登录页栈无底兜约球页） */
async function landInPlace(
  pending: SignupPending | null | undefined,
): Promise<void> {
  const ui = useUiStore();
  await runPendingResume(pending ?? {});
  ui.closeSheet();
  const pages = getCurrentPages();
  const top = pages[pages.length - 1] as { route?: string } | undefined;
  if (top?.route !== LOGIN_PATH.slice(1)) return;
  if (pages.length > 1) uni.navigateBack();
  else goMeet();
}

/** 占卡微信验证带的名片重建（明确填过的才覆盖）——草稿是出发前
    SignupSheet flush 进本机的（login.vue cardFromDraft 的 mp 孪生，无整页跳转卡仍在） */
function cardFromDraft(phone: string) {
  const draft = readCardDraft<{ nickname?: string; picked?: number | null }>();
  if (!draft) return undefined;
  return cardPayloadOf(phone, draft.nickname ?? "", draft.picked ?? null);
}
// #endif
