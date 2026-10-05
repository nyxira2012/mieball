/* 球局 store（alpha:1107-1297 各动作 · alpha:1375-1398 发布/改局 · alpha:807-830 意向）
   硬约束：动作只改状态与返回/弹出文案 —— 不做路由跳转、不直接调 uni.*（导航由页面层做）。 */
import { computed, reactive, ref } from 'vue';
import { defineStore } from 'pinia';
import {
  U,
  delay,
  games as seedGames,
  intents as seedIntents,
  mockAreas,
  mockDemoUser,
  myIntent as seedMyIntent,
} from '@/api';
import type { MyIntent, PublishInput, TimeBucket } from '@/api/types';
import { autoGameName, heads, isOrg, isForced, myEntry } from '@/utils/format';
import { dayOff, gameTime } from '@/utils/time';
import { useUiStore } from './ui';
import { useUserStore } from './user';

export const useGameStore = defineStore('game', () => {
  /* 数据源：mock 的同一份可变引用（alpha:781 games / 814 myIntent / 815 intents）。
     reactive() 对同一原始对象返回同一代理 —— 与 user/live store、页面读到的完全同源。 */
  const games = reactive(seedGames);
  const intents = reactive(seedIntents);
  const myIntent = ref<MyIntent | null>(seedMyIntent);

  /* —— 5.1 我的页登记口径（单一源）：原先 mine.vue 双卡与 signup.vue 各持一份手写 filter，
     两处互指「同口径」却各自维护，口径漂移风险下沉到 store（消费方只做排序/筛选/展示） —— */

  /** 我的登记全集：我组织/已报名 且未终止（含 done —— 已结束局要在登记页看到签到行） */
  const mySignups = computed(() => games.filter((g) => !g.dead && (isOrg(g) || myEntry(g))));
  /** 签到口径：其中打完（done）且我的到场底账留了 checkIn 的局 */
  const myCheckins = computed(() => mySignups.value.filter((g) => g.status === 'done' && g.myLog?.checkIn));

  /** 加入 · 可带人（alpha:1127-1138 doJoin）：满员进候补；带的人也占坑 */
  function joinGame(id: number, bring = 0): string | null {
    const g = games.find((x) => x.id === id);
    if (!g) return null;
    if (!myEntry(g)) {
      const toWait = heads(g) >= g.cap;
      (toWait ? g.wait : g.joined).push({ u: U.me, bring });
      g.invitedMe = false;
      const msg = toWait
        ? '已进候补栏 · 有人退出即刻递补'
        : bring
          ? `已加入 · 带了 ${bring} 人（共占 ${1 + bring} 坑）`
          : '已加入 · 这局进了「我的局」';
      useUiStore().toast(msg);
      return msg;
    }
    return null; // alpha:1137 已加入 → 只关弹层进详情
  }

  /** 退出局（alpha:1148-1153 doQuit）：名额立刻释放，你带的人也一起退（候补同样清）。「我」运行时读 U.me.id */
  function quitGame(id: number): string | null {
    const g = games.find((x) => x.id === id);
    if (!g) return null;
    g.joined = g.joined.filter((e) => e.u.id !== U.me.id);
    g.wait = g.wait.filter((e) => e.u.id !== U.me.id);
    const msg = '已退出 · 名单里少了你';
    useUiStore().toast(msg);
    return msg;
  }

  /** 取消局（alpha:1164-1168）：局从列表整体撤下；已订场的提醒一句去场馆退订（钱已花在 app 外） */
  function cancelGame(id: number): string | null {
    const i = games.findIndex((x) => x.id === id);
    if (i < 0) return null;
    const booked = games[i].booked?.length;
    games.splice(i, 1);
    const msg = booked
      ? '局已撤下 · 已订场地记得去场馆退订，报名的球友「我的局」里同步消失'
      : '局已撤下 · 报名的球友「我的局」里同步消失';
    useUiStore().toast(msg);
    return msg;
  }

  /** 发布/改局共用的推导（alpha:1383-1387）：局名「日段 · 地点」自动起名、tb 时间桶（按真实日期算）、area 地区推断。
      3.3 改版：time 可能是「10.06 周一 19:00」三段精确式，tb 由 gameTime 解析出的日期推导。
      自动名与天数偏移的规则在 utils（autoGameName/dayOff），与 LaunchSheet 预览同源。 */
  function deriveGame(p: PublishInput): { name: string; day: string; tb: TimeBucket; area: string } {
    const name = p.name.trim() || autoGameName(p.time, p.venue);
    const day = p.time.split(' ')[0];
    const start = gameTime(p.time);
    const off = dayOff(start);
    const wd = start.getDay();
    const tb: TimeBucket = off <= 0 ? 'tonight' : off === 1 ? 'tomorrow' : wd === 0 || wd === 6 ? 'weekend' : 'week';
    const area = mockAreas.find((a) => p.venue.includes(a)) || '其他';
    return { name, day, tb, area };
  }

  /** 发布（alpha:1394-1397）：新局插到列表最前，我是名单头一个。费用表单已去 → 新局 fee=null（费用未定）；
      3.3 规则三件（分制/轮转/迟到）由表单直选落 score/mode/lateRule */
  function publishGame(p: PublishInput): string | null {
    const d = deriveGame(p);
    games.unshift({
      id: Date.now(), organizer: U.me, t: p.time, d: d.day, dur: p.dur, deadline: p.deadline,
      area: d.area, tb: d.tb, loc: p.venue, name: d.name, min: p.min, cap: p.cap, fee: null,
      joined: [{ u: U.me }], wait: [], status: 'open', score: p.score, mode: p.mode, scoreRule: p.scoreRule, lateRule: false,
    });
    const msg = '局已发布 · 名单头一个就是你，点局上的 ⤴ 分享到群里拉人';
    useUiStore().toast(msg);
    return msg;
  }

  /** 改信息（alpha:1388-1392）：名单不动，截止定死不改；费用与说明不在表单里 → 原 note 原样保留。
      3.2 订场改版：加场按钮取消，上限放宽（及一切令 heads<cap 的改动）由这里统一接手——
      候补按先后自动转正（原 addCourt alpha:1198-1206 的递补循环原样搬入）。 */
  function editGame(id: number, p: PublishInput): string | null {
    const ed = games.find((x) => x.id === id);
    if (!ed) return null;
    const d = deriveGame(p);
    Object.assign(ed, {
      name: d.name, t: p.time, dur: p.dur, loc: p.venue, min: p.min, cap: p.cap,
      score: p.score, mode: p.mode, scoreRule: p.scoreRule, d: d.day, area: d.area, tb: d.tb,
    });
    let moved = 0;
    while (ed.wait.length && heads(ed) < ed.cap) {
      const e = ed.wait.shift();
      if (e) { ed.joined.push(e); moved++; }
    }
    const left = ed.wait.length;
    const msg = moved
      ? left
        ? `局已改好 · 上限放宽，候补转正，仍剩 ${left} 人满员（建议下次再参加）`
        : '局已改好 · 上限放宽，候补已全部转正'
      : '局已改好 · 名单里的人看到的就是新信息';
    useUiStore().toast(msg);
    return msg;
  }

  /** 锁定必打 · 空锁（alpha:1171-1176）：不登记场地只上手动锁，最少人数要求作废。
      订场（bookCourt）是必打的另一入口，带场地号与总价；两者口径统一在 isForced。 */
  function sureGame(id: number): string | null {
    const g = games.find((x) => x.id === id);
    if (!g) return null;
    g.sure = true;
    const msg = '已锁定必打 · 到截止不再因人数不足终止，最少人数要求作废';
    useUiStore().toast(msg);
    return msg;
  }

  /** 订场登记（3.2 订场改版）：订场发生在 app 外（场馆/平台），这里登记结果——场地号 + 总价。
      场上有号即必打（isForced）；费用从未定落定为总价，人均按当前人数摊（最少保底作废）。
      可反复改：加片添号、退片删号改价，每次保存联动重算。 */
  function bookCourt(id: number, courts: string[], fee: number): string | null {
    const g = games.find((x) => x.id === id);
    if (!g || !courts.length) return null;
    g.booked = [...courts];
    g.fee = fee;
    const msg = `已订场 · ${courts.join('、')}（${courts.length} 片）· 这局必开，费用已落定`;
    useUiStore().toast(msg);
    return msg;
  }

  /** 清空订场登记（场地全退光）：局回到未订场原样——费用回「未定」；
      手动锁（sure）是组织者明确点的，不跟着松。 */
  function clearBooking(id: number): string | null {
    const g = games.find((x) => x.id === id);
    if (!g) return null;
    g.booked = undefined;
    g.fee = null;
    const msg = g.sure
      ? '订场登记已清空 · 手动锁定保留，这局仍必打'
      : '订场登记已清空 · 局回到未订场，费用未定，截止照常判人数';
    useUiStore().toast(msg);
    return msg;
  }

  /** 到截止判定（alpha:1177-1189 延伸）：低于最少且未必打（手动锁 OR 已订场，isForced）→
    自动终止（dead，组织者「我的局」可恢复）；否则名单锁定、参加者不能再退出。 */
  function hitDeadline(id: number): string | null {
    const g = games.find((x) => x.id === id);
    if (!g) return null;
    const h = heads(g);
    if (h < g.min && !isForced(g)) {
      g.dead = true;
      const msg = '到截止 · 人数不足，局自动终止（组织者「我的局」留有未成局，可恢复）';
      useUiStore().toast(msg);
      return msg;
    }
    g.locked = true;
    const msg = '到截止 · 名单锁定，参加者不能再退出';
    useUiStore().toast(msg);
    return msg;
  }

  /** 恢复未成局（alpha:1207-1212）：回到终止前状态，名单原样（已订场的局必打，走不到 dead，此路只属未订场局） */
  function restoreGame(id: number): string | null {
    const g = games.find((x) => x.id === id);
    if (!g) return null;
    g.dead = false;
    const msg = '局已恢复 · 名单原样回来，再决定必定开局还是撤局';
    useUiStore().toast(msg);
    return msg;
  }

  /** 邀请（alpha:1249-1263 doInvite）：局出现在对方「我的局」；3.2 秒模拟对方点一下就加入（满员进候补） */
  function inviteUser(uid: number, gid: number): string | null {
    const g = games.find((x) => x.id === gid);
    const u = useUserStore().findUser(uid); // alpha:1250 findUser（现场名册优先）
    if (!g || !u) return null;
    const msg = `已邀请 ${u.name} · 局已出现在 ta 的「我的局」`;
    useUiStore().toast(msg);
    delay(3200).then(() => { // alpha:1255-1262 演示模拟，文案逐字
      if (!g.joined.some((e) => e.u.id === uid)) (heads(g) >= g.cap ? g.wait : g.joined).push({ u });
      const it = intents.find((i) => i.u.id === uid);
      if (it) it.done = true;
      useUiStore().toast(`${u.name} 点了一下 · ${heads(g) >= g.cap && !g.joined.some((e) => e.u.id === uid) ? '进了「' + g.name.replace(/ ·.*/, '') + '」候补' : '加入了「' + g.name.replace(/ ·.*/, '') + '」'}`);
    });
    return msg;
  }

  /** 分享（alpha:1224-1237 shareGame）：toast；组织者首次分享 3 秒后模拟「小张从群里点进来 · 加入并带 1 人」 */
  const shared: Record<number, boolean> = {};
  function shareGame(id: number): string | null {
    const g = games.find((x) => x.id === id);
    if (!g) return null;
    const msg = '分享卡片已生成 · 转到微信群里拉人';
    useUiStore().toast(msg);
    if (isOrg(g) && !shared[id]) {
      shared[id] = true;
      delay(3000).then(() => {
        if (!g.joined.some((e) => e.u.id === mockDemoUser.id)) g.joined.push({ u: mockDemoUser, bring: 1 }); // alpha:1230
        useUiStore().toast(`${mockDemoUser.name} 从群里点进来 · 加入并带了 1 人`);
      });
    }
    return msg;
  }

  /** 留/改意向（alpha:1286-1292 saveIntent）：至少一个时段 */
  function saveIntent(slots: string[], freq: number): string | null {
    if (!slots.length) {
      const m = '至少选一个时段';
      useUiStore().toast(m);
      return m;
    }
    const had = !!myIntent.value;
    myIntent.value = { slots: [...slots], freq };
    const msg = had ? '意向已更新 · 想改随时改' : '意向已留下 · 组局的人凑人时会看见你';
    useUiStore().toast(msg);
    return msg;
  }

  /** 删意向（alpha:1293-1297 delIntent） */
  function delIntent(): string {
    myIntent.value = null;
    const msg = '意向已删 · 随时可以再留';
    useUiStore().toast(msg);
    return msg;
  }

  return {
    games, intents, myIntent, mySignups, myCheckins,
    joinGame, quitGame, cancelGame, publishGame, editGame, sureGame, bookCourt, clearBooking,
    hitDeadline, restoreGame, inviteUser, shareGame, saveIntent, delIntent,
  };
});
