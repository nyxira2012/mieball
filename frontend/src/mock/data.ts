/* ---------- 数据（alpha:760-830 原样移植；改数据口径 = 改 alpha，不要在这里发明） ----------
   全部以可变引用导出：store 用 reactive()/ref() 包住同一份原始对象，
   mock / live 名册 / 榜单读写的是同一批对象（Vue reactive 对同一原始目标返回同一代理）。
   1.2 接线：games 种子改型 MockGame（5.1 隔离线快照冻结——账单/登记/记录/现场演示继续吃这份，
   字段不再生长）；局/意向真数据走 api/games.ts + stores/game。 */
import type { Bill, MockGame, Slot, User } from '@/api/types';

export const U: Record<string, User> = {
  me: { id: 0, name: '我', elo: 1518, play: 34, win: 19, month: 18, last5: ['W', 'L', 'W', 'W', 'L'], chibi: { skin: 1, hair: 5, hc: 0, shirt: 0, face: 1, acc: 2 }, cardBg: 'neon', recentStats: { win: 3, loss: 1, hours: 2, kcal: 800 } },
  wang: { id: 1, name: '朝阳反手王', elo: 1721, play: 88, win: 61, month: 38, last5: ['W', 'W', 'W', 'L', 'W'], liked: true, chibi: { skin: 0, hair: 2, hc: 0, shirt: 1, face: 3, acc: 0 }, cardBg: 'gold' },
  hai: { id: 2, name: '海淀吊小球', elo: 1688, play: 76, win: 50, month: -12, last5: ['L', 'W', 'L', 'L', 'W'], liked: true, chibi: { skin: 1, hair: 1, hc: 2, shirt: 5, face: 0, acc: 1 }, cardBg: 'cyber' },
  wu: { id: 3, name: '五道口钉子步', elo: 1655, play: 64, win: 41, month: 8, last5: ['W', 'L', 'W', 'W', 'L'], chibi: { skin: 2, hair: 0, hc: 1, shirt: 2, face: 0, acc: 0 } },
  gu: { id: 4, name: '国贸截击手', elo: 1602, play: 71, win: 43, month: -6, last5: ['L', 'L', 'W', 'L', 'W'], chibi: { skin: 0, hair: 3, hc: 4, shirt: 6, face: 1, acc: 0 } },
  li: { id: 5, name: '亮马河快攻', elo: 1574, play: 52, win: 29, month: 14, last5: ['W', 'W', 'L', 'W', 'W'], chibi: { skin: 1, hair: 0, hc: 0, shirt: 4, face: 0, acc: 2 } },
  shi: { id: 6, name: '石景山铁腰', elo: 1533, play: 59, win: 31, month: 5, last5: ['L', 'W', 'W', 'L', 'W'], chibi: { skin: 2, hair: 2, hc: 5, shirt: 7, face: 3, acc: 1 } },
  yang: { id: 7, name: '亦庄月亮球', elo: 1498, play: 41, win: 20, month: -9, last5: ['L', 'L', 'W', 'L', 'L'], chibi: { skin: 0, hair: 1, hc: 3, shirt: 3, face: 1, acc: 0 } },
  bei: { id: 8, name: '北苑小钢炮', elo: 1452, play: 38, win: 17, month: 11, last5: ['W', 'W', 'L', 'W', 'L'], chibi: { skin: 1, hair: 0, hc: 2, shirt: 1, face: 1, acc: 0 } },
  tong: { id: 9, name: '通州长胶姨', elo: 1404, play: 47, win: 19, month: -4, last5: ['L', 'W', 'L', 'W', 'L'], chibi: { skin: 0, hair: 3, hc: 1, shirt: 5, face: 0, acc: 1 } },
  zhang: { id: 12, name: '小张', elo: 1380, play: 6, win: 2, month: 0, last5: ['L', 'W', 'L', 'L', 'W'], chibi: { skin: 1, hair: 1, hc: 5, shirt: 3, face: 0, acc: 0 } },
  ken: { id: 11, name: '亮马河 Ken', elo: 1355, play: 12, win: 5, month: 2, last5: ['W', 'L', 'L', 'W', 'L'], chibi: { skin: 0, hair: 4, hc: 3, shirt: 6, face: 2, acc: 0 } },
  zhao: { id: 10, name: '赵姐的朋友', elo: 0, play: 0, win: 0, month: 0, shadow: true, chibi: { skin: 1, hair: 4, hc: 5, shirt: 0, face: 1, acc: 0 } },
};

/** 交互演示模拟用户（分享后从群里加入的示例球友） */
export const mockDemoUser = U.zhang;

/** 业务商圈与地区选项（基础字典配置；1.2 起真局列表不再按地区筛，仅存量演示面使用） */
export const mockAreas = ['工体', '望京', '五棵松', '亮马河'];
export const AREA_OPTS = ['全部', ...mockAreas];

/** 场馆名单一源：LaunchSheet 地点 chips 与上面局 seeds 的 loc 同源
    （场馆改名只动这里；「手输新场地」伪选项由 LaunchSheet 自加） */
export const mockVenues = ['工体北路 · 京篮匹克球馆', '望京 · 花家地球馆', '五棵松 · 万事达球馆'];

/** 现场开局演示时默认前 N 位球友已到场（alpha:1482 口径） */
export const DEFAULT_MOCK_CHECKIN_COUNT = 9;

/** mock 环境基准日期（2026-10-04，用于账单等相对期间推算，将来接真实系统时钟） */
export const MOCK_BASE_DATE_STR = '2026-10-04';

/** 圈子元数据（meet 页日期行在用） */
export const communityMeta = {
  name: '北京匹克球圈',
};
/* 5.1 快照种子（MockGame）：organizer/joined 等口径注释见 types.ts MockGame。
   真局 1.2 起走后端；这份快照只喂账单/登记/记录/现场演示的隔离线消费面。 */
export const games: MockGame[] = [
  { id: 101, organizer: U.wang, t: '今晚 19:00', d: '今天', tb: 'tonight', area: '工体', dur: 2, deadline: '今天 17:00',
    loc: '工体北路 · 京篮匹克球馆 · 3 片', name: '周四夜战', min: 8, cap: 12, fee: 720, note: '老搭子局 · 新朋友走候补',
    joined: [{ u: U.wang }, { u: U.hai, bring: 2 }, { u: U.wu }, { u: U.gu }, { u: U.li }, { u: U.me }, { u: U.shi }, { u: U.yang }, { u: U.bei }, { u: U.tong }, { u: U.zhao }], wait: [],
    status: 'live', locked: true, score: 11, mode: 'winner', lateRule: true },
  { id: 102, organizer: U.me, t: '周六 14:00', d: '10.07', tb: 'weekend', area: '望京', dur: 2, deadline: '周五 20:00',
    loc: '望京 · 花家地球馆 · 2 片', name: '周末午后局', min: 4, cap: 8, fee: 480, booked: ['3号', '5号'], note: '新手友好 · 打完一起晚饭',
    joined: [{ u: U.me }, { u: U.li, bring: 1 }, { u: U.bei }], wait: [], status: 'open', score: 11, mode: 'balance', lateRule: false },
  { id: 103, organizer: U.wu, t: '下周三 20:00', d: '10.09', tb: 'week', area: '五棵松', dur: 2, deadline: '周二 18:00',
    loc: '五棵松 · 万事达球馆 · 1 片', name: '夜光单挑夜', min: 4, cap: 6, fee: 180, note: '单挑为主 · 输了换人',
    joined: [{ u: U.wu }, { u: U.yang }], wait: [], status: 'open', score: 15, mode: 'rotate', lateRule: true },
  { id: 104, organizer: U.hai, t: '周日 19:00', d: '10.06', tb: 'weekend', area: '工体', dur: 2, deadline: '周六 12:00',
    loc: '工体北路 · 京篮匹克球馆 · 2 片', name: '夜光混搭局', min: 8, cap: 12, fee: 720, note: '水平混搭 · 均衡配对',
    joined: [{ u: U.li, bring: 1 }, { u: U.yang }], wait: [], status: 'open', score: 11, mode: 'balance', lateRule: false },
  { id: 105, organizer: U.ken, t: '周六 10:00', d: '10.07', tb: 'weekend', area: '亮马河', dur: 2, deadline: '周五 18:00',
    loc: '亮马河 · 滨河球场 · 2 片', name: '周末白天随便打打', min: 4, cap: 4, fee: 160, note: '河边随便打打 · 不较真',
    joined: [{ u: U.tong }], wait: [], status: 'open', score: 11, mode: 'rotate', lateRule: false },
  { id: 106, organizer: U.wang, t: '周三 20:00', d: '10.08', tb: 'week', area: '五棵松', dur: 2, deadline: '周二 20:00',
    loc: '五棵松 · 万事达球馆 · 1 片', name: '周三夜光局', min: 4, cap: 8, fee: 400, note: '攒固定搭子',
    joined: [{ u: U.wang }, { u: U.wu }], wait: [], status: 'open', score: 11, mode: 'balance', lateRule: false, invitedMe: true },
  { id: 107, organizer: U.shi, t: '今晚 21:00', d: '今天', tb: 'tonight', area: '望京', dur: 1, deadline: '今晚 19:00',
    loc: '望京 · 花家地球馆 · 1 片', name: '加时夜战 · 临时凑', min: 4, cap: 6, fee: 300, note: '临时凑 · 来就能打',
    joined: [{ u: U.shi }, { u: U.gu }], wait: [], status: 'open', score: 11, mode: 'balance', lateRule: true },
  /* 5.1 已结束局（done 一等球局）：result=最终比分 · myLog=我的到场底账（签到/早退）。
     必填字段与进行中局同构，局卡/详情/摊账链路整链复用；日期按今天=2026-10-04（周日）回推校准星期。 */
  { id: 93, organizer: U.wu, t: '周五 20:00', d: '9.25', tb: 'week', area: '五棵松', dur: 2, deadline: '周五 18:00',
    loc: '五棵松 · 万事达球馆 · 1 片', name: '周五夜战', min: 4, cap: 6, fee: 164,
    joined: [{ u: U.wu }, { u: U.me }, { u: U.yang }, { u: U.bei }], wait: [], status: 'done',
    score: 21, mode: 'rotate', lateRule: true, result: { sa: 19, sb: 21, myWin: false }, myLog: { checkIn: '19:55' } },
  { id: 94, organizer: U.me, t: '周六 19:00', d: '9.12', tb: 'weekend', area: '工体', dur: 2, deadline: '周六 12:00',
    loc: '工体北路 · 京篮匹克球馆 · 2 片', name: '周六混搭局', min: 8, cap: 12, fee: 720,
    joined: [{ u: U.me }, { u: U.hai }, { u: U.li }, { u: U.wang }, { u: U.wu }, { u: U.gu }, { u: U.shi }, { u: U.yang }], wait: [], status: 'done',
    score: 21, mode: 'balance', lateRule: false, result: { sa: 21, sb: 19, myWin: true } },
  { id: 95, organizer: U.ken, t: '周日 10:00', d: '9.20', tb: 'weekend', area: '亮马河', dur: 2, deadline: '周六 18:00',
    loc: '亮马河 · 滨河球场 · 2 片', name: '周日晨练局', min: 4, cap: 4, fee: 160,
    joined: [{ u: U.ken }, { u: U.me }, { u: U.tong }, { u: U.shi }], wait: [], status: 'done',
    score: 21, mode: 'rotate', lateRule: false, result: { sa: 15, sb: 21, myWin: false }, myLog: { checkIn: '09:52' } },
  { id: 96, organizer: U.wang, t: '周六 19:00', d: '9.26', tb: 'weekend', area: '工体', dur: 2, deadline: '周六 17:00',
    loc: '工体北路 · 京篮匹克球馆 · 3 片', name: '周六夜战', min: 8, cap: 12, fee: 720,
    joined: [{ u: U.wang }, { u: U.hai }, { u: U.wu }, { u: U.gu }, { u: U.li }, { u: U.me }, { u: U.shi }, { u: U.yang }, { u: U.bei }], wait: [], status: 'done',
    score: 21, mode: 'winner', lateRule: true, locked: true, result: { sa: 21, sb: 17, myWin: true }, myLog: { checkIn: '19:02', checkOut: '21:30' } },
  { id: 97, organizer: U.me, t: '周四 14:00', d: '10.01', tb: 'week', area: '望京', dur: 2, deadline: '周三 20:00',
    loc: '望京 · 花家地球馆 · 2 片', name: '午后加场局', min: 4, cap: 8, fee: 200,
    joined: [{ u: U.me }, { u: U.li, bring: 1 }, { u: U.bei }], wait: [], status: 'done',
    score: 21, mode: 'balance', lateRule: false, result: { sa: 21, sb: 15, myWin: true }, myLog: { checkIn: '13:58' } },
  { id: 98, organizer: U.hai, t: '周五 20:00', d: '10.02', tb: 'week', area: '五棵松', dur: 2, deadline: '周五 18:00',
    loc: '五棵松 · 万事达球馆 · 1 片', name: '周五夜光局', min: 4, cap: 6, fee: 180,
    joined: [{ u: U.hai }, { u: U.me }, { u: U.wu }, { u: U.tong }], wait: [], status: 'done',
    score: 21, mode: 'rotate', lateRule: true, result: { sa: 17, sb: 21, myWin: false }, myLog: { checkIn: '20:01' } },
];
/* alpha:805 let live=null —— 现场进行中状态，归 stores/live.ts */

/* 5.1 账单（2026-10-04 修订）：逐笔底账，date 倒序，gameId 全部指向上面存活的 done 局。
   member 行 amt = 所连局 perHead，payee = 该局组织者（待付行写明欠谁）；
   org 行 amt = 别人摊费合计，payers = 数据侧给好的按人明细（不含我自己）。 */
export const bills: Bill[] = [
  { id: 1, gameId: 98, gname: '周五夜光局', date: '10.02', amt: 45, status: 'due', role: 'member', payee: U.hai },
  { id: 2, gameId: 97, gname: '午后加场局', date: '10.01', amt: 150, status: 'receivable', role: 'org',
    payers: [ { u: U.li, amt: 100, settled: false }, { u: U.bei, amt: 50, settled: true } ] },
  { id: 3, gameId: 96, gname: '周六夜战', date: '9.26', amt: 80, status: 'paid', role: 'member', payee: U.wang },
  { id: 4, gameId: 93, gname: '周五夜战', date: '9.25', amt: 41, status: 'due', role: 'member', payee: U.wu },
  { id: 5, gameId: 95, gname: '周日晨练局', date: '9.20', amt: 40, status: 'paid', role: 'member', payee: U.ken },
  { id: 6, gameId: 94, gname: '周六混搭局', date: '9.12', amt: 630, status: 'receivable', role: 'org',
    payers: [ { u: U.hai, amt: 90, settled: true }, { u: U.li, amt: 90, settled: false }, { u: U.wang, amt: 90, settled: true },
              { u: U.wu, amt: 90, settled: false }, { u: U.gu, amt: 90, settled: true }, { u: U.shi, amt: 90, settled: true }, { u: U.yang, amt: 90, settled: true } ] },
];

/* 时段词表（前端单一源，后端只存 key 串不校验；1.2 起同波段 match 数退役——
   意向「打过」徽章改读 intent.known 定值，批4 裁决②） */
export const slots: Slot[] = [
  { k: 'wd', n: '工作日晚间', desc: '19:00 后' },
  { k: 'ln', n: '工作日午休', desc: '12:00-14:00' },
  { k: 'we-d', n: '周末白天', desc: '09:00-18:00' },
  { k: 'we-n', n: '周末晚上', desc: '19:00 后' },
];
