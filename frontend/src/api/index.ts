/* api 统一出口 —— stores / 页面一律从这里取数（后续接真后端只动 api/ 这一层）。
   mock 世界已退役（2026-10-10）：假人表/种子局/演示账单删除，静态词表迁 dict.ts。 */
export * from "./types";
export * from "./dict";
export * from "./accounts";
export * from "./games";
export * from "./live";
export * from "./bills";
