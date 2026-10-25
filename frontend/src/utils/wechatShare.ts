/* 微信网页分享卡：卡片拼句（纯函数）+ 登记编排（副作用，全程静默降级）。
   页面只管把现成数据喂进来，SDK 注入/签名/config 的时序与失败兜底全收在这。
   零 Vue import（utils 不碰框架，同 share.ts 先例）。 */
import { apiWechatJsapiSign } from "@/api/auth";
import type { GameStatus } from "@/api/types";
/* 排障留痕落本地黑匣子：手机端 wx.config / SDK 注入失败不经任何网络请求，后端
   日志完全看不见，黑匣子是唯一取证口（「我的」页一键导出即查） */
import { trackAct, trackErr } from "./blackbox";
import { isoDay, isoHm } from "./time";
import { isWeChatBrowser } from "./wechat";

/** 拼句原料：字段全部来自页面现成拿得到的信息（缺哪段省哪段，不另编） */
export interface ShareCardSrc {
  name: string;
  status: GameStatus;
  startAt?: string;
  venueName?: string;
  /** 报名/实到人头（组织者本人算在内；0 也照说，不另造句） */
  heads?: number;
  /** 已落账场数：done 局用；null=页面拿不到（详情页没有这个数，落兜底句） */
  matchCount?: number | null;
}

/** 发出去的卡片四件（微信 API 参数形状） */
export interface WechatShareCard {
  title: string;
  desc: string;
  link: string;
  imgUrl: string;
}

/** 方图地址段：路径部分永不变名（历史卡片引用的老地址永远有图，不会空白）；
    但微信按完整 URL 缓存缩略图——只换文件不换 URL，新发卡片仍拿旧图。
    所以换图内容时必须同步 bump 日期参数逼微信重抓，路径不动、只动 v。 */
const SHARE_CARD_PATH = "/share-card.png?v=20261024";

/** 「日期 钟点」段时间口吻单一源：网页版分享卡的收人句段与小程序转发卡标题
    共用（两端卡面同款写法） */
const dayHm = (startAt: string): string =>
  `${isoDay(startAt)} ${isoHm(startAt)}`;

/** 卡片描述句：未散场说收人要点、散场说场数、死局各说各的。
   pending（组织者眼里的待处置）与 terminated 同句——对非组织者它本就被 mask 成
   terminated，卡片不区分看客身份，一句到底。 */
export function cardDesc(src: ShareCardSrc): string {
  const { status } = src;
  if (status === "terminated" || status === "pending") return "这局已终止";
  if (status === "cancelled") return "这局已撤销";
  if (status === "done") {
    const n = src.matchCount ?? null;
    if (n == null) return "已散场 · 看看谁赢了"; // 拿不到场数的兜底句
    return n > 0 ? `${n} 场对局 · 看看谁赢了` : "已散场";
  }
  // open/locked/live（满员/已开打也照说收人句——卡片是定格门面，真相进详情看）
  const segs: string[] = [];
  if (src.startAt) segs.push(dayHm(src.startAt));
  if (src.venueName) segs.push(src.venueName);
  segs.push(`已报 ${src.heads ?? 0} 人`);
  return segs.join(" · ");
}

/** 卡片落点固定发详情链接（调用方传 gameShareUrl(id)），方图全站共用一张 */
export function buildShareCard(
  src: ShareCardSrc,
  link: string,
): WechatShareCard {
  return {
    title: src.name,
    desc: cardDesc(src),
    link,
    imgUrl:
      typeof location === "undefined"
        ? SHARE_CARD_PATH
        : location.origin + SHARE_CARD_PATH,
  };
}

/** 战报卡局名解析的 store 最小形状：只声明本 helper 用到的两件，
    store 作参数传入（utils 不碰框架，同 WxSdk 先例） */
export interface GameNameSource {
  findGame(id: number): { name: string; startAt?: string } | null | undefined;
  loadDetail(id: number): Promise<{ name: string; startAt?: string }>;
}

/** 转发卡用的局（名+开赛时间）解析：局簿 findGame 现成取 → 冷链查无 loadDetail
    补拉（name 与 startAt 同一次响应）→ 两处都拿不到退泛称「球局战报」不带时间
    （标题仍成立，不拦卡）。resolveGameName 是它的只取名薄壳（H5 登记卡老消费方） */
export async function resolveShareGame(
  gameStore: GameNameSource,
  gameId: number,
): Promise<{ name: string; startAt?: string }> {
  const g = gameStore.findGame(gameId);
  if (g?.name) return g;
  try {
    return await gameStore.loadDetail(gameId);
  } catch {
    return { name: "球局战报" };
  }
}

/** 战报卡局名解析（recap 子页与现场散场门牌两个消费方，收口单一源）：
    局簿 findGame 现成取 → 冷链查无 loadDetail 补拉 → 两处都拿不到退「球局战报」
    泛称（不拦登记）。调用侧手里另有真局名（现场页 L.g）时自行优先，不走这里 */
export async function resolveGameName(
  gameStore: GameNameSource,
  gameId: number,
): Promise<string> {
  return (await resolveShareGame(gameStore, gameId)).name;
}

/* ---- 小程序转发卡三件（onShareAppMessage/onShareTimeline 的原料单一源） ---- */

/** 小程序转发卡标题：「局名 · 日期 钟点」（时间口吻与网页版分享卡同一段 dayHm）；
    startAt 缺席（泛称兜底路）只落局名。超长交给微信省略，不自己截断 */
export function shareTitle(name: string, startAt?: string): string {
  return startAt ? `${name} · ${dayHm(startAt)}` : name;
}

/** 转发卡落点（小程序 path 形态）：与 gameShareUrl 是同一条详情页路径契约的两个
    出口——后者拼 origin/# 的完整外发 URL（H5 卡/复制链接），这里不带 origin 供
    小程序 onShareAppMessage 的 path 用。三处转发统一落详情页（散场局点「查看
    战报」一跳即看）由此钉死 */
export const SHARE_PATH = (gameId: number): string =>
  `/pages/detail/detail?id=${gameId}`;

/** 转发卡方图（MP 包根的静态资源，全站统一的夜球场品牌方图）：小程序端
    imageUrl 按包内路径取图、不吃 query 版本参——网页版换图的 ?v 逼重抓规矩在
    SHARE_CARD_PATH 那边，两端口径各自成立 */
export const SHARE_IMAGE = "/share-card.png";

/** wx 极简本地形状（jweixin-1.6.0 全局对象）：只声明本模块用到的几件，够 vue-tsc 过 */
interface WxSdk {
  config(opts: {
    appId: string;
    timestamp: number;
    nonceStr: string;
    signature: string;
    jsApiList: string[];
  }): void;
  ready(fn: () => void): void;
  error(fn: (res: unknown) => void): void;
  updateAppMessageShareData(card: WechatShareCard): void;
  updateTimelineShareData(card: {
    title: string;
    link: string;
    imgUrl: string;
  }): void;
}

const JWEIXIN_SRC = "https://res.wx.qq.com/open/js/jweixin-1.6.0.js";
const JWEIXIN_TIMEOUT_MS = 10_000;

let jweixinPromise: Promise<WxSdk> | null = null;

/** 动态注入 jweixin（只在微信里才走到，全站一次）：script 标签挂在 head，
    10s 没到当失败；失败不缓存——下次登记再试一次，不成重试风暴 */
function loadJweixin(): Promise<WxSdk> {
  jweixinPromise ??= new Promise<WxSdk>((resolve, reject) => {
    const s = document.createElement("script");
    const timer = setTimeout(() => {
      trackErr("wx_sdk_load", "jweixin-timeout");
      reject(new Error("jweixin-timeout"));
    }, JWEIXIN_TIMEOUT_MS);
    s.onload = () => {
      clearTimeout(timer);
      /* uni-app H5 运行时把 window.wx 占成 uni 的别名（可写可配置、无 config
         方法），和 jweixin 撞名——加载后两者虽都被覆盖成 SDK，但取谁不能赌
         脚本覆盖顺序：优先拿专属的 jWeixin，退回 wx，且验过 config 是函数
         才算真 SDK（纯浏览器 H5 里 wx 可能根本不是分享 SDK） */
      const g = globalThis as unknown as { wx?: WxSdk; jWeixin?: WxSdk };
      const sdk = g.jWeixin ?? g.wx;
      if (sdk && typeof sdk.config === "function") resolve(sdk);
      else {
        trackErr("wx_sdk_load", "jweixin-missing");
        reject(new Error("jweixin-missing"));
      }
    };
    s.onerror = () => {
      clearTimeout(timer);
      trackErr("wx_sdk_load", "jweixin-load-fail");
      reject(new Error("jweixin-load-fail"));
    };
    s.src = JWEIXIN_SRC;
    document.head.appendChild(s);
  }).catch((e) => {
    jweixinPromise = null; // 失败不缓存（见上）
    throw e;
  });
  return jweixinPromise;
}

let configPromise: Promise<WxSdk> | null = null;

/** 注入 + 签名 + wx.config（成功才缓存）：签名地址 = href 去 hash——hash 路由
    SPA 全站同址，整趟会话只签一次；顺带天然落在 iOS 的「首次进入地址」口径上
    （iOS 不认 SPA 内变化的 href，只认落地首址）。签名/config 失败同样不缓存 */
function ensureWxReady(): Promise<WxSdk> {
  configPromise ??= (async () => {
    const wx = await loadJweixin();
    const sign = await apiWechatJsapiSign(location.href.split("#")[0]);
    await new Promise<void>((resolve, reject) => {
      wx.config({
        appId: sign.app_id,
        timestamp: sign.timestamp,
        nonceStr: sign.nonce_str,
        signature: sign.signature,
        jsApiList: ["updateAppMessageShareData", "updateTimelineShareData"],
      });
      wx.ready(resolve);
      wx.error((res) => {
        // 微信原话（invalid signature / invalid url domain / permission denied…）
        // 是分辨 config 失败种类的唯一线索，原样留进黑匣子再拒
        trackErr(
          "wx_config_fail",
          (res as { errMsg?: string })?.errMsg ?? String(res),
        );
        reject(new Error("wx-config-fail"));
      });
    });
    return wx;
  })().catch((e) => {
    configPromise = null;
    throw e;
  });
  return configPromise;
}

/** 上次成功登记的卡片指纹（JSON 串）：同内容不重登的账本，失败不记 */
let lastRegisteredFp: string | null = null;

/** 登记意图流水号：号在「页面意图诞生」（register 被调）那一刻领，写入前核——
    等待期间又来了更新的登记（同页 watch 连触发 / 跨页跳转），旧意图自己作废。
    「最新页面的意图赢」由此成为模块保证，页面不用自己传 token 对账 */
let intentSeq = 0;

/** 登记本页分享卡：收「怎么拼卡」（make）而不是拼好的卡——原料取数（拉场数/
    补局名）挪进 make 并行等，且 make 只在微信内才执行（done 局微信外不白拉
    战报视图）。不在微信直接返回（领号之前，非微信领号毫无意义）；在微信里
    config 就绪 + 卡拼好后，先核号再写：号不等了才作废旧意图，谁新谁赢——
    同页双拉谁后回谁写的「兜底句盖真句」就断在这。
    同内容不重登：卡片 JSON 指纹等于上次成功登记的指纹就直接返回——done 局详情
    onLoad+onShow 双拉、现场页轮询重建都会喂来一模一样的卡，SDK 侧重复登记纯浪费；
    指纹只在两个 update 都落地后才记，中途失败不记，下次照常重试。
    任何一步失败（make 抛错也算「这次原料没拿到，不登记」）catch 静默——转出去
    退微信默认样，不弹错不打扰；签名请求只在微信内才发，开发期零噪声。 */
export async function registerWechatShare(
  make: () => WechatShareCard | Promise<WechatShareCard>,
): Promise<void> {
  if (!isWeChatBrowser()) return;
  const mine = ++intentSeq;
  try {
    const [wx, card] = await Promise.all([ensureWxReady(), make()]);
    if (mine !== intentSeq) return; // 期间有更新的意图，本次作废
    const fp = JSON.stringify(card); // 卡片都经 buildShareCard 产出，键序固定，串即指纹
    if (fp === lastRegisteredFp) return;
    wx.updateAppMessageShareData(card);
    wx.updateTimelineShareData({
      title: card.title,
      link: card.link,
      imgUrl: card.imgUrl,
    });
    lastRegisteredFp = fp;
    // 登记成功记一笔：有这条而线上仍是裸链接，即可排除「没登记上」，矛头指向 link/img/权限
    trackAct("WX", "share_registered", true);
  } catch {
    /* 静默降级：签名失败由 http 层留痕，SDK/config 失败已在 reject 前落黑匣子 */
  }
}
