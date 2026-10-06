/* 2.4 §4.2 推荐矩阵 + 理由句单一源（新模块）。
   纯函数三定值入参（单双打/可打人数/片数——人数口径=activePlayers、片数口径=courtCount），
   总账算好随时可取、非强制不替切、不弹窗。 */
import type { DownMode } from '@/api/types';

export type RotationAdvice =
  | { kind: 'none'; reason: string } // 不荐：先等人（差人卡 2.1 已有着落）
  | { kind: 'switch-singles'; reason: string } // 提示可点：点了即全场换单打（铺不满片、但人够按单打铺满）
  | { kind: 'down'; down: DownMode; reason: string };

/** 从上往下先命中为准（「铺满」按当前单双打：双打=片数×4、单打=片数×2）。
    理由句逐字用规格 §4.2 表——表内「同上」是表格缩写，抽屉里单行独立展示，展开为同上一行的整句。 */
export function recommend(singles: boolean, players: number, courts: number): RotationAdvice {
  const full = courts * (singles ? 2 : 4);
  if (singles) {
    if (players < full) return { kind: 'none', reason: '先等人' };
    if (players === full) return { kind: 'down', down: 'all', reason: '人人每轮都在场上' };
    if (players === full + 1) return { kind: 'down', down: 'loser', reason: '单打就两种，赢家留场最顺' };
    return { kind: 'down', down: 'all', reason: '轮得最快最公平' }; // 多出 ≥ 一整片（≥铺满数+2）
  }
  if (players < courts * 2) return { kind: 'none', reason: '先等人' }; // 连单打都铺不满
  if (players < full) return { kind: 'switch-singles', reason: '改了就能全员上场，不混格式' };
  if (players === full) return { kind: 'down', down: 'all', reason: '人人每轮都在场上' };
  if (players === full + 1) return { kind: 'down', down: 'n1', reason: '等的人下一场马上轮进来' };
  if (players === full + 2) return { kind: 'down', down: 'n2', reason: '候场周转顺，连庄天然被拆' };
  if (players === full + 3) return { kind: 'down', down: 'n3', reason: '候场周转顺，连庄天然被拆' };
  return { kind: 'down', down: 'all', reason: '队伍长了，全下轮得最快最公平' }; // 多出 ≥ 一整片（≥铺满数+4）
}
