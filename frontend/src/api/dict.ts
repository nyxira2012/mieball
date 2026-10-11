/* 静态字典（无后端真值的展示常量）：时段词表 / 场馆建议名单。
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
