/* 静态字典（无后端真值的展示常量）：时段词表 / 场馆建议名单 / 头像预设组。
   原住 mock/data.ts（随假人表一并退役迁出）——它们不是数据，是词表。 */
import type { ChibiConfig, Slot } from "@/api/types";

/* 时段词表（前端单一源，后端只存 key 串不校验；意向「打过」徽章读 intent.known 定值） */
export const slots: Slot[] = [
  { k: "wd", n: "工作日晚间", desc: "19:00 后" },
  { k: "ln", n: "工作日午休", desc: "12:00-14:00" },
  { k: "we-d", n: "周末白天", desc: "09:00-18:00" },
  { k: "we-n", n: "周末晚上", desc: "19:00 后" },
];

/** 场馆建议名单一源：LaunchSheet 地点 chips（「手输新场地」伪选项由 LaunchSheet 自加） */
export const venueSuggestions = [
  "中冠（佛子岭）",
  "星跃X（山姆）",
  "热浪（林里桥）",
  "李宁（体育园）",
  "三琪广场",
];

/** 头像预设组（1.1 D2；1.7 自 SignupSheet 迁出）：名片卡快选 + 微信占卡回来重建名片用
 *  （login.vue 读本机草稿时按下标取同一份配置，单一源防两处漂移） */
export const CHIBI_PRESETS: { c: ChibiConfig }[] = [
  { c: { skin: 0, hair: 0, hc: 0, shirt: 5, face: 0, acc: 0 } },
  { c: { skin: 1, hair: 5, hc: 0, shirt: 1, face: 1, acc: 2 } },
  { c: { skin: 0, hair: 2, hc: 5, shirt: 7, face: 3, acc: 1 } },
  { c: { skin: 0, hair: 1, hc: 2, shirt: 2, face: 0, acc: 0 } },
  { c: { skin: 1, hair: 4, hc: 3, shirt: 6, face: 2, acc: 0 } },
  { c: { skin: 2, hair: 0, hc: 1, shirt: 4, face: 1, acc: 1 } },
  { c: { skin: 0, hair: 3, hc: 4, shirt: 0, face: 3, acc: 0 } },
  { c: { skin: 1, hair: 1, hc: 5, shirt: 3, face: 0, acc: 1 } },
];

/** 手机号收集用途说明（1.1 §6 告知义务，1.8 批3 抽单一源）：收集动作在哪，
 *  说明跟到哪——名片卡与我的页补绑面板两消费方同文 */
export const PHONE_USE_NOTE =
  "用于球局紧急通知、防鸽子和跨设备找回；同局球友会看到你的尾号 4 位";
