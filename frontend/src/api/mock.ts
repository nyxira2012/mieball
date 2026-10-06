/* 极薄数据源层：原样导出 mock/data 的可变引用（alpha 的全局可变数据）。
   1.2 起局/意向真数据走 api/games.ts，本层只剩隔离线（账单/登记/记录/现场演示）吃的快照。 */
export {
  U,
  games,
  bills,
  slots,
  mockDemoUser,
  mockAreas,
  mockVenues,
  AREA_OPTS,
  MOCK_BASE_DATE_STR,
  communityMeta,
} from '../mock/data';
