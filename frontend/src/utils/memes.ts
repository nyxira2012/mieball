/* 梗句封面单一配置（2026-10-12 用户拍板：战报头主视觉=球友昵称+流行梗，单人梗）。
   模板槽位 {a} 填一名上过场的昵称；梗会过气——只改这里，一行一条。 */

export const MEMES = [
  "真是一场酣畅淋漓的战斗呢，{a}大人",
  "{a}，会赢的",
  "什么，我打{a}？！",
  "{a}打得对面梨花带雨",
  "我要打十个！by {a}：",
  "本场最佳：{a}（自封）",
  // 时事与网络热梗
  "坏了，今天真让{a}装到了",
  "天命人{a}，请重回匹克球场",
  "{a}：问就是今天球馆风向不对",
  // 动漫与二次元
  "{a}：领域展开！",
  "愿称{a}为最强！",
  "安西教练：{a}，球技是另外的价钱",
  "那一天，全场回想起了被{a}支配的恐惧",
  "真相只有一个：全靠{a}在带飞",
  // 韩剧与热门影视综艺
  "妍珍啊，今天又是看{a}打球的一天呢",
  "告诉老默，我想看{a}打球了",
  "{a}，哭也算时间哦",
  // 音乐与名场面
  "{a}在仰望，月亮之上",
] as const;

/** 零战报局兜底（没人可点名） */
export const MEME_FALLBACK = "真是一场酣畅淋漓的战斗";

/** 随机挑一条梗填一个名：重名去重、空白名剔除；纯随机不挑赢家——反差才好笑。
    返回名字本身（兜底句为 null）——消费方好给名字单独上色，不分段不拆句 */
export function pickMeme(names: string[]): {
  text: string;
  name: string | null;
} {
  const pool = [...new Set(names.map((n) => n.trim()).filter(Boolean))];
  if (!pool.length) return { text: MEME_FALLBACK, name: null };
  const tpl = MEMES[Math.floor(Math.random() * MEMES.length)]!;
  const name = pool[Math.floor(Math.random() * pool.length)]!;
  return { text: tpl.replace("{a}", name), name };
}
