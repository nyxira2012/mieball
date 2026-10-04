/* 极薄数据源层：原样导出 mock/data 的可变引用（alpha 的全局可变数据）。
   将来接真后端：重写本文件为接口实现（或替换实现），stores 与页面零改动。 */
export {
  U,
  games,
  bills,
  intents,
  myIntent,
  slots,
  mockDemoUser,
  mockAreas,
  AREA_OPTS,
  DEFAULT_MOCK_CHECKIN_COUNT,
  MOCK_BASE_DATE_STR,
  communityMeta,
} from '../mock/data';
