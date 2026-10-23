/* 静态字典（无后端真值的展示常量）：时段词表 / 场馆建议名单 / 公共头像编号组。
   原住 mock/data.ts（随假人表一并退役迁出）——它们不是数据，是词表。 */
import type { Slot } from "@/api/types";

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

/** 注册卡公共头像编号组（册子公共款头像恰 6 件；下标即名片草稿 picked 值）：
 *  编号语义归后端册子，这里只锁「第 N 款是哪件」的下标映射，供注册卡拼素材路径
 *  （/cosmetics/{cid}.webp 约定）与 cardPayloadOf 下标→编号换算共用 */
export const PUBLIC_AVATARS = [
  "a-p1",
  "a-p2",
  "a-p3",
  "a-p4",
  "a-p5",
  "a-p6",
] as const;

/** 手机号收集用途说明（1.1 §6 告知义务，1.8 批3 抽单一源；2026-10-13 改口）：
 *  收集动作在哪，说明跟到哪——名片卡与我的页补绑面板两消费方同文 */
export const PHONE_USE_NOTE =
  "用于球局紧急通知、防鸽子和跨设备找回；尾号4位球友可见";
