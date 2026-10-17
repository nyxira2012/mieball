/* 微信网页分享卡：卡片拼句（纯函数）+ 登记编排（副作用，全程静默降级）。
   页面只管把现成数据喂进来，SDK 注入/签名/config 的时序与失败兜底全收在这。
   零 Vue import（utils 不碰框架，同 share.ts 先例）。 */
import { apiWechatJsapiSign } from "@/api/auth";
import type { GameStatus } from "@/api/types";
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

/** 方图固定地址段：放本站根、地址不改名——换图只换内容同路径覆盖，旧卡不会变空白 */
const SHARE_CARD_PATH = "/share-card.png";

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
  if (src.startAt) segs.push(`${isoDay(src.startAt)} ${isoHm(src.startAt)}`);
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
  findGame(id: number): { name: string } | null | undefined;
  loadDetail(id: number): Promise<{ name: string }>;
}

/** 战报卡局名解析（recap 子页与现场散场门牌两个消费方，收口单一源）：
    局簿 findGame 现成取 → 冷链查无 loadDetail 补拉 → 两处都拿不到退「球局战报」
    泛称（不拦登记）。调用侧手里另有真局名（现场页 L.g）时自行优先，不走这里 */
export async function resolveGameName(
  gameStore: GameNameSource,
  gameId: number,
): Promise<string> {
  const cached = gameStore.findGame(gameId)?.name;
  if (cached) return cached;
  try {
    return (await gameStore.loadDetail(gameId)).name;
  } catch {
    return "球局战报";
  }
}

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
    const timer = setTimeout(
      () => reject(new Error("jweixin-timeout")),
      JWEIXIN_TIMEOUT_MS,
    );
    s.onload = () => {
      clearTimeout(timer);
      /* uni-app H5 运行时把 window.wx 占成 uni 的别名（可写可配置、无 config
         方法），和 jweixin 撞名——加载后两者虽都被覆盖成 SDK，但取谁不能赌
         脚本覆盖顺序：优先拿专属的 jWeixin，退回 wx，且验过 config 是函数
         才算真 SDK（纯浏览器 H5 里 wx 可能根本不是分享 SDK） */
      const g = globalThis as unknown as { wx?: WxSdk; jWeixin?: WxSdk };
      const sdk = g.jWeixin ?? g.wx;
      if (sdk && typeof sdk.config === "function") resolve(sdk);
      else reject(new Error("jweixin-missing"));
    };
    s.onerror = () => {
      clearTimeout(timer);
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
      wx.error(() => reject(new Error("wx-config-fail")));
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

/** 登记本页分享卡：不在微信直接返回；在微信里 config 就绪后两个 update 一起调
    （朋友卡全四件、朋友圈卡只 title/link/imgUrl——朋友圈没有描述行，微信的规矩）。
    同内容不重登：卡片 JSON 指纹等于上次成功登记的指纹就直接返回——done 局详情
    onLoad+onShow 双拉、现场页轮询重建都会喂来一模一样的卡，SDK 侧重复登记纯浪费；
    指纹只在两个 update 都落地后才记，中途失败不记，下次照常重试。
    任何一步失败 catch 静默——转出去退微信默认样，不弹错不打扰；签名请求只在
    微信内才发，开发期零噪声。 */
export async function registerWechatShare(
  card: WechatShareCard,
): Promise<void> {
  if (!isWeChatBrowser()) return;
  const fp = JSON.stringify(card); // 卡片都经 buildShareCard 产出，键序固定，串即指纹
  if (fp === lastRegisteredFp) return;
  try {
    const wx = await ensureWxReady();
    wx.updateAppMessageShareData(card);
    wx.updateTimelineShareData({
      title: card.title,
      link: card.link,
      imgUrl: card.imgUrl,
    });
    lastRegisteredFp = fp;
  } catch {
    /* 静默降级（埋点在 http 层，够排障） */
  }
}
