<template>
  <!-- 球局详情（3.2）· alpha.html:1400-1467 openDetail() 模板逐字对齐（P5a 静态结构 + P5b 操作接线）。
       数据按 url query 的 id 从 game store 取局；全部动作走 game/live store 与 SheetHost 弹层，
       toast 文案由 store 逐字负责，视图刷新靠响应式。非 tab 页：无 TabBar，仍挂全部宿主。 -->
  <PageShell>
    <view v-if="game" class="stag">
      <!-- alpha:1403-1407 页头：kicker + 局名（首个 ' · ' 断行，其余保留） -->
      <view class="kicker">Game #{{ game.id }} · {{ game.d }} · {{ game.organizer.name }} 发起</view>
      <view class="brand">
        {{ brandA }}
        <text v-if="brandB" class="brand-line">{{ brandB }}</text>
      </view>

      <!-- alpha:1408-1424 hero：大时间 · t·时长·loc · kv 行 · 说明/人均口径 · 分享行 -->
      <view class="hero">
        <view class="big">{{ tBig }}</view>
        <view class="sub hero-sub">{{ tDay }} · 打 {{ durText }} · {{ game.loc }}</view>
        <view class="row">
          <view class="kv">
            <view class="k">名单</view>
            <view class="v">{{ hs }}/{{ game.cap }}</view>
          </view>
          <!-- 5.1 剩坑/截止是赛前口径：done 局收掉，换「战报」kv 保住 kv 网格（终局内容在下方终局牌） -->
          <view v-if="game.status !== 'done'" class="kv">
            <view class="k">剩坑</view>
            <view class="v" :style="{ color: need ? 'var(--coral)' : 'var(--dim)' }">{{ need }}</view>
          </view>
          <view class="kv">
            <view class="k">{{ game.fee != null ? '总价' : '费用' }}</view>
            <view class="v">{{ game.fee != null ? `¥${game.fee}` : '未定' }}</view>
          </view>
          <view v-if="game.fee != null" class="kv">
            <view class="k">人均</view>
            <view class="v v-lemon">¥{{ ph }}</view>
          </view>
          <!-- 3.2 订场改版：场地号 kv——已订场亮号（到场馆照号找场），未订显示待定 -->
          <view v-if="game.status !== 'done'" class="kv">
            <view class="k">场地</view>
            <view class="v v-court" :style="{ color: game.booked?.length ? 'var(--cream)' : 'var(--dim)' }">
              {{ game.booked?.length ? game.booked.join('、') : '待定' }}
            </view>
          </view>
          <view v-if="game.status !== 'done'" class="kv">
            <view class="k">截止</view>
            <view class="v v-dl">{{ game.deadline }}</view>
          </view>
          <view v-if="reported && result" class="kv">
            <view class="k">战报</view>
            <view class="v" :class="result.myWin ? 'v-lemon' : 'v-coral'">{{ result.myWin ? '胜' : '负' }}</view>
          </view>
        </view>
        <!-- alpha:1421-1423：有说明或人未够最少时展示，人均口径三态（alpha:1406 splitNote 逐字）；
             3.3 费用未定局（fee=null）不显示人均口径 -->
        <view v-if="game.note || (hs < game.min && game.fee != null)" class="sub hero-note">
          {{ [game.note ? `说明：${game.note}` : '', game.fee != null ? splitNote : ''].filter(Boolean).join(' · ') }}
        </view>
        <view class="row act2">
          <!-- 5.1：done 局不渲染分享——shareGame 对组织者首享会模拟「小张加入」，终局名单不能被改写 -->
          <AppButton v-if="game.status !== 'done'" variant="ghost" size="sm" @click="onShare">⤴ 分享到群</AppButton>
          <AppButton
            v-if="org && !game.locked && game.status === 'open'"
            variant="ghost"
            size="sm"
            @click="onDeadline"
          >⏰ 到截止 · 判定</AppButton>
          <!-- 与 actions 行「已到截止 · 不能退出」chip 同口径：done 局锁定态不再是有效信息 -->
          <AppChip v-if="game.locked && game.status !== 'done'" kind="full">已到截止 · 名单锁定</AppChip>
        </view>
      </view>

      <!-- alpha:1425-1428 steps 进度条：status !== 'open' 时「报名/候补」点亮；
           5.1：live/done 点亮「进行中」，done 点亮「战报」（连接线随较晚段，status 线性推进） -->
      <view class="steps">
        <text class="s" :class="{ on: started }">报名</text>
        <view class="i" :class="{ on: started }" />
        <text class="s" :class="{ on: started }">候补</text>
        <view class="i" :class="{ on: played }" />
        <text class="s" :class="{ on: played }">进行中</text>
        <view class="i" :class="{ on: reported }" />
        <text class="s" :class="{ on: reported }">战报</text>
      </view>

      <!-- 5.1 §3「点击进入后看的是打球页的最终内容」（验收故事 3）：done 局在 steps 下补终局牌，
           否则「战报」段点亮却无内容、hero 还是赛前口径，点进来无终局可看。hero 简化版式（页内 scoped）；
           无 result 的 done 局不渲染（类型上 result 可缺省，mock 全量有值） -->
      <view v-if="reported && result" class="finale">
        <view class="score">{{ result.sa }} · {{ result.sb }}</view>
        <!-- 胜负小字：赢收着说（dim，大字比分已 lemon 庆祝）、输打出来（coral，与 GameCard res-l / 战报 kv 负色同口径） -->
        <view class="wl" :style="{ color: result.myWin ? 'var(--dim)' : 'var(--coral)' }">
          {{ result.myWin ? '你赢了这局' : '你输了这局' }}
        </view>
        <!-- 我的到场账（无 myLog 不渲染该行）：早退带出时刻，打满全场收尾 -->
        <view v-if="game.myLog" class="log">
          签到 {{ game.myLog.checkIn }}{{ game.myLog.checkOut ? ' · 早退 ' + game.myLog.checkOut : ' · 打满全场' }}
        </view>
      </view>

      <!-- alpha:1429-1444 名单：组织者排头一个 · 随行/带 N 人角标 · 随行展开成独立 pcard -->
      <SectionTitle :title="`名单 ${hs}/${game.cap} · 组织者排头一个`">
        <template v-if="game.wait.length" #more>候补 {{ game.wait.length }} 人</template>
      </SectionTitle>
      <view class="grid-p">
        <template v-for="e in game.joined" :key="e.u.id">
          <view class="pcard" :class="{ me: e.u.id === meId }" @click="onPlayer(e.u.id)">
            <view v-if="e.u.shadow" class="tag">随行</view>
            <view v-else-if="e.bring" class="tag">带 {{ e.bring }} 人</view>
            <view class="avatar"><ChibiAvatar :chibi="e.u.chibi" :size="56" /></view>
            <view class="nm">{{ e.u.name }}</view>
            <view class="elo">{{ e.u.shadow ? '—' : e.u.elo }}</view>
          </view>
          <!-- alpha:1436-1438 带的人：用带他的人的头像，名 = 名字前两字+的球友，elo 为 — -->
          <view v-for="i in e.bring || 0" :key="`${e.u.id}-b${i}`" class="pcard dim75">
            <view class="tag">随行</view>
            <view class="avatar"><ChibiAvatar :chibi="e.u.chibi" :size="56" /></view>
            <view class="nm">{{ e.u.name.slice(0, 2) }}的球友</view>
            <view class="elo">—</view>
          </view>
        </template>
        <!-- alpha:1439-1442 未加入时的虚线加入卡 -->
        <view v-if="!joined && game.status !== 'done'" class="pcard join" @click="onJoin">
          <view class="plus">＋</view>
          <view class="nm">加入 / 带人</view>
        </view>
      </view>

      <!-- alpha:1445-1447 候补栏 -->
      <template v-if="game.wait.length">
        <SectionTitle title="候补栏">
          <template #more>有人退出即刻递补</template>
        </SectionTitle>
        <view class="grid-p">
          <view v-for="e in game.wait" :key="`w${e.u.id}`" class="pcard dim65">
            <view class="avatar"><ChibiAvatar :chibi="e.u.chibi" :size="56" /></view>
            <view class="nm">{{ e.u.name }}</view>
          </view>
        </view>
      </template>

      <!-- alpha:1448-1450 组织者按钮行（仅 open 态）；3.2 订场改版：加场按钮取消（上限放宽走改局，候补转正在 editGame 内接手） -->
      <view v-if="org && game.status === 'open'" class="org-row">
        <AppButton variant="ghost" size="sm" @click="onInvite">＋ 邀请 · 翻意向列表拉人</AppButton>
      </view>

      <!-- alpha:1451-1464 底部动作区（joined/org/locked/sure/status 显隐逻辑逐字） -->
      <view class="actions">
        <AppButton v-if="!joined && game.status === 'open'" variant="pri" class="grow" @click="onJoin">
          ＋ 加入 · 可带人{{ full ? ' · 进候补' : '' }}
        </AppButton>
        <AppButton
          v-if="joined && !org && game.status === 'open' && !game.locked"
          variant="ghost"
          class="grow"
          @click="onQuit"
        >退出局</AppButton>
        <AppChip v-if="joined && !org && game.locked && game.status !== 'done'" class="mid">已到截止 · 不能退出</AppChip>
        <!-- 5.1：org 动作收紧为 open/ready——done 局不再出现锁定/改信息/取消（原 gating 仅排除 live）。
             3.2 订场改版：锁升级三态一入口——没锁（🔒 锁定必打 · 可登记订场）/ 空锁（手动锁，去登记场地）/
             订场锁（已订场 · 场地号 · 总价），点开都是 BookingSheet；截止后（ready）仍可改登记（换号/退片） -->
        <template v-if="org && (game.status === 'open' || game.status === 'ready')">
          <AppButton variant="ghost" class="grow sure-btn" @click="onBooking">{{
            game.booked?.length
              ? `🔒 已订场 · ${game.booked.join('、')} · ¥${game.fee}`
              : game.sure
                ? '🔒 已锁定必打 · 去登记场地'
                : '🔒 锁定必打 · 可登记订场'
          }}</AppButton>
        </template>
        <template v-if="org && (game.status === 'open' || game.status === 'ready')">
          <AppButton variant="ghost" @click="onEdit">改信息</AppButton>
          <AppButton variant="ghost" class="cancel-btn" @click="onCancel">取消局</AppButton>
        </template>
      </view>

      <!-- alpha:1465-1469 状态动作：live 回现场；open/ready 开始打球 -->
      <AppButton v-if="game.status === 'live'" variant="burn" block class="mt12" @click="onLive">▶ 回到现场</AppButton>
      <AppButton
        v-else-if="game.status === 'open' || game.status === 'ready'"
        variant="burn"
        block
        class="mt12"
        @click="onStart"
      >▶ 开始打球</AppButton>

      <!-- alpha:1466 规则牌（modeName/迟到规则/候补递补/人均摊法口径逐字）；
           3.3：费用未定局（fee=null）不显示人均摊法句；scoreRule 有值才显示得分规则段（旧局无此字段） -->
      <NoteCard class="rules">
        <b>规则牌：</b>{{ game.score }} 分制（领先 2 分才算赢）<template v-if="game.scoreRule"> · {{ game.scoreRule === 'rally' ? '每球得分制' : '发球得分制' }}</template> · {{ modeName }}{{ game.lateRule ? ' · 迟到排队尾等一轮' : '' }}
        · 满 {{ game.cap }} 人进候补，有人退出即刻递补<template v-if="game.fee != null"> · 人均＝总价 ¥{{ game.fee }} ÷ {{ perBase }}（{{ perNote }}）</template>。
      </NoteCard>
    </view>
    <!-- alpha 无此态（openDetail 有 guard）；直链/局被取消后的兜底，文案中性、非产品文案 -->
    <view v-else class="ph">该局不存在或已被撤下</view>
  </PageShell>
</template>

<script setup lang="ts">
/* alpha.html:1400-1467 openDetail（P5a 静态化 + P5b 操作接线）；
   摊法口径引用 utils/format 的 perHead（alpha:884，带注释口径）。 */
import { computed, ref } from 'vue';
import { onLoad } from '@dcloudio/uni-app';
import PageShell from '@/components/biz/PageShell.vue';
import AppButton from '@/components/ui/AppButton.vue';
import AppChip from '@/components/ui/AppChip.vue';
import ChibiAvatar from '@/components/ui/ChibiAvatar.vue';
import NoteCard from '@/components/ui/NoteCard.vue';
import { useGameStore } from '@/stores/game';
import { useUserStore } from '@/stores/user';
import { useUiStore } from '@/stores/ui';
import { useLiveStore } from '@/stores/live';
import { heads, needOf, perHead, myEntry, isOrg, isForced } from '@/utils/format';
import { durTxt } from '@/utils/time';
import type { CourtMode } from '@/api/types';

const store = useGameStore();

/** 从 url query 接 id（onLoad options），按 id 查局（alpha:1402 games.find） */
const gameId = ref<number | null>(null);

onLoad((options) => {
  const raw = (options as Record<string, string | undefined> | undefined)?.id;
  const n = raw != null ? Number(raw) : NaN;
  gameId.value = Number.isFinite(n) ? n : null;
});

const game = computed(() => store.games.find((x) => x.id === gameId.value) ?? null);

/* ---- alpha:1403-1406 的局部量（heads/full/joined/org 均沿用 utils/format 口径） ---- */
const hs = computed(() => (game.value ? heads(game.value) : 0));
const need = computed(() => (game.value ? needOf(game.value) : 0));
const ph = computed(() => (game.value ? perHead(game.value) : 0));
const full = computed(() => !!game.value && hs.value >= game.value.cap);
const joined = computed(() => !!game.value && !!myEntry(game.value));
const org = computed(() => !!game.value && isOrg(game.value));
const started = computed(() => !!game.value && game.value.status !== 'open'); // alpha:1425-1428 steps 点亮条件
/* 5.1 steps 后两段：played=已开打（live 及终局 done）、reported=战报已出（done） */
const played = computed(() => {
  const s = game.value?.status;
  return s === 'live' || s === 'done';
});
const reported = computed(() => game.value?.status === 'done');
/* 5.1 终局内容（终局牌 + hero 战报 kv 的数据源） */
const result = computed(() => game.value?.result);

/* 3.3 打多久文案（拨盘 5 分步进会出现 115 分钟这类，整/半小时才用小时） */
const durText = computed(() => (game.value ? durTxt(game.value.dur) : ''));

/* alpha:1410 大时间 = t 末段（时刻）；1411 小字 = 前段拼接（今晚/周六…/10.06 周一）。
   3.3 改版后 t 可能是三段式，按末段=时刻、前段拼接=日段拆。 */
const tBig = computed(() => {
  const p = game.value ? game.value.t.split(' ') : [];
  return p[p.length - 1] ?? '';
});
const tDay = computed(() => (game.value ? game.value.t.split(' ').slice(0, -1).join(' ') : ''));

/* alpha:1405 局名首个 ' · ' 断行（replace(' · ','<br>') 的等价拆分，其余 ' · ' 原样保留） */
const brandA = computed(() => {
  if (!game.value) return '';
  const i = game.value.name.indexOf(' · ');
  return i >= 0 ? game.value.name.slice(0, i) : game.value.name;
});
const brandB = computed(() => {
  if (!game.value) return '';
  const i = game.value.name.indexOf(' · ');
  return i >= 0 ? game.value.name.slice(i + 3) : '';
});

/* alpha:1406 人均口径副文案（三态；3.2 订场改版：必打=手动锁或已订场，走 isForced） */
const splitNote = computed(() => {
  const g = game.value;
  if (!g) return '';
  return isForced(g)
    ? '人均按当前人数摊（最少要求已作废）'
    : hs.value < g.min
      ? `不足最少 ${g.min} 人 · 人均按最少摊`
      : `人均按当前 ${hs.value} 人摊`;
});

/* alpha:1405 发牌模式名 */
const MODE_NAMES: Record<CourtMode, string> = { winner: '赢家留场', rotate: '纯粹轮转', balance: '均衡配对' };
const modeName = computed(() => (game.value ? MODE_NAMES[game.value.mode] : ''));

/* alpha:1466 规则牌人均分母与括注（Math.max(isForced?0:min,hs) 口径；3.2 订场改版换 isForced） */
const perBase = computed(() => (game.value ? Math.max(isForced(game.value) ? 0 : game.value.min, hs.value) : 0));
const perNote = computed(() => {
  const g = game.value;
  if (!g) return '';
  return isForced(g) ? '必打后按实际人数摊' : hs.value < g.min ? '不足最少按最少摊' : '按当前人数摊';
});

/* ---- 操作接线（P5b）：toast 均由 game store 动作内逐字文案负责；视图刷新靠 store 响应式
   （alpha:1136/1152/1168 等处的 renderHome/renderMeet/openDetail/go 由响应式 + 既有页面承担） ---- */
const ui = useUiStore();
/** 响应式「我」id（1.1 会话接管 U.me 后联动） */
const meId = computed(() => useUserStore().me.id);
const liveStore = useLiveStore();

/** alpha:1418 shareGame（组织者首享 3 秒后模拟小张加入，store 内逐字） */
const onShare = () => {
  if (game.value) store.shareGame(game.value.id);
};
/** alpha:1419 hitDeadline（低于最少且未锁 → dead；否则 locked，两分支 toast 在 store） */
const onDeadline = () => {
  if (!game.value) return;
  const id = game.value.id;
  store.hitDeadline(id);
  // alpha:1183 dead 分支 go('meet')：未成局自动终止后落回约球页（组织者可恢复）
  if (store.games.find((g) => g.id === id)?.dead) uni.switchTab({ url: '/pages/meet/meet' });
};
/** alpha:1441/1452 joinSheet → JoinSheet 弹层 */
const onJoin = () => {
  if (game.value) ui.openSheet({ type: 'join', gameId: game.value.id });
};
/** alpha:1453 quitSheet → ConfirmSheet(kind=quit) */
const onQuit = () => {
  if (game.value) ui.openSheet({ type: 'quit-confirm', gameId: game.value.id });
};
/** 锁定必打 / 订场登记（3.2 三态一入口）：BookingSheet（空锁=原 alpha:1459 sureGame） */
const onBooking = () => {
  if (game.value) ui.openSheet({ type: 'booking', gameId: game.value.id });
};
/** alpha:1460 editSheet → openLaunch(id)：LaunchSheet 编辑态（P6 填充） */
const onEdit = () => {
  if (game.value) ui.openSheet({ type: 'launch', gameId: game.value.id });
};
/** alpha:1461 cancelSheet → ConfirmSheet(kind=cancel) */
const onCancel = () => {
  if (game.value) ui.openSheet({ type: 'cancel-confirm', gameId: game.value.id });
};
/** alpha:1449 inviteFromGame → InviteSheet(mode=to-game) */
const onInvite = () => {
  if (game.value) ui.openSheet({ type: 'invite-to-game', gameId: game.value.id });
};
/** alpha:1468 startLive：live store 初始化（status→live · 随行展开 · 发牌）→ 跳现场页 */
const onStart = () => {
  if (!game.value) return;
  liveStore.startLive(game.value.id);
  uni.navigateTo({ url: `/pages/live/live?id=${game.value.id}` });
};
/** alpha:1465 go('live')：已 live 的局回现场页 */
const onLive = () => {
  if (!game.value) return;
  uni.navigateTo({ url: `/pages/live/live?id=${game.value.id}` });
};
/** 名单球员卡 → 球员档案弹层（ProfileSheet 全产品共用；alpha 详情卡未挂 onclick，
   本迁移按 P9「现场队员/榜单都唤起」的共用口径在此接入） */
const onPlayer = (uid: number) => {
  ui.openSheet({ type: 'profile', userId: uid });
};
</script>

<style lang="scss" scoped>
/* 页面专属类（alpha:226-245 hero/kv/steps/grid-p/pcard/avatar + openDetail 内联样式）。
   品牌大字同 base.scss 的 h1.brand（alpha:84-87）——uni 模板不能用 h1，故页面自带同值类。 */
.brand {
  font-family: var(--disp);
  font-size: 34px;
  line-height: 1.04;
  margin: 6px 0 2px;
}
.brand .brand-line {
  display: block;
}

/* ---------- hero / kv / steps（alpha:226-230） ---------- */
.hero {
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  overflow: hidden;
  background: linear-gradient(165deg, var(--ink3) 30%, var(--ink2));
  padding: 20px;
  position: relative;
}
.hero .big {
  font-family: var(--disp);
  font-size: 52px;
  line-height: 1;
  color: var(--lemon);
}
.hero-sub {
  margin-top: 6px;
}
.hero .row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 14px;
}
.row.act2 {
  margin-top: 10px; /* alpha:1417 style="margin-top:10px" */
}
.kv {
  border: 1px solid rgba(245, 241, 232, 0.1);
  border-radius: 12px;
  padding: 8px 12px;
  min-width: 78px;
}
.kv .k {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.2em;
  color: var(--dim);
  text-transform: uppercase;
}
.kv .v {
  font-family: var(--disp);
  font-size: 17px;
  margin-top: 2px;
}
.kv .v.v-lemon {
  color: var(--lemon); /* alpha:1415 人均黄色 */
}
.kv .v.v-coral {
  color: var(--coral); /* 5.1 战报 kv 负色（胜=lemon 走 v-lemon） */
}
.kv .v.v-dl {
  font-size: 13px;
  line-height: 1.7; /* alpha:1416 截止小字 */
}
.kv .v.v-court {
  font-size: 13px;
  line-height: 1.7; /* 场地号小字（多个号如「3号、5号」不撑破 kv 网格） */
}
.sub.hero-note {
  margin-top: 10px;
  font-size: 12px; /* alpha:1422 说明行 */
}
.steps {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 16px 2px 4px;
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
}
.steps .i {
  flex: 1;
  height: 2px;
  background: rgba(245, 241, 232, 0.12);
  border-radius: 2px;
}
.steps .i.on {
  background: var(--lemon);
}
.steps .s.on {
  color: var(--lemon);
}

/* ---------- 终局牌（5.1 done 态）：hero 简化版式 —— 比分大字 + 胜负 + 我的到场账 ---------- */
.finale {
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  background: linear-gradient(165deg, var(--ink3) 30%, var(--ink2));
  padding: 16px 20px;
  margin-top: 14px; /* steps 条（margin-bottom 4px）与名单区之间的呼吸 */
}
.finale .score {
  font-family: var(--disp);
  font-size: 44px;
  line-height: 1;
  color: var(--lemon);
}
.finale .wl {
  margin-top: 5px;
  font-size: 12px;
}
.finale .log {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  margin-top: 8px;
  letter-spacing: 0.08em;
}

/* ---------- 球员网格（alpha:231-243） ---------- */
.grid-p {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(88px, 1fr));
  gap: 10px;
}
.pcard {
  border: 1px solid rgba(245, 241, 232, 0.1);
  border-radius: var(--r-md);
  background: var(--ink2);
  padding: 12px 8px 10px;
  text-align: center;
  position: relative;
  transition: transform 0.15s;
}
.pcard:active {
  transform: scale(0.94);
}
.pcard .nm {
  font-size: 12px;
  font-weight: 600;
  margin-top: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pcard .elo {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--lemon);
}
.pcard .tag {
  position: absolute;
  top: 7px;
  right: 7px;
  font-size: 9px;
  font-family: var(--mono);
  background: rgba(184, 169, 255, 0.16);
  color: var(--lilac);
  border-radius: 6px;
  padding: 2px 5px;
}
.pcard.me {
  border-color: rgba(255, 212, 0, 0.5);
}
.pcard.dim75 {
  opacity: 0.75; /* alpha:1437 带的人 */
}
.pcard.dim65 {
  opacity: 0.65; /* alpha:1447 候补 */
}
.avatar {
  width: 56px;
  height: 56px;
  margin: 0 auto;
}
.pcard.join {
  border-style: dashed; /* alpha:1440 虚线加入卡 */
  cursor: pointer;
}
.pcard.join .plus {
  font-size: 34px;
  color: var(--lemon);
  font-family: var(--disp);
  padding-top: 18px; /* alpha:1441 */
}

/* ---------- 按钮行与动作区（openDetail 内联样式） ---------- */
.org-row {
  display: flex;
  gap: 8px;
  margin-top: 10px; /* alpha:1448 */
  flex-wrap: wrap;
}
.actions {
  display: flex;
  gap: 10px;
  margin-top: 20px; /* alpha:1451 */
  flex-wrap: wrap;
}
.actions .grow {
  flex: 1;
}
.actions .mid {
  align-self: center;
}
.actions .sure-btn {
  color: var(--ice); /* alpha:1459 锁定必打按钮（三态锁共用入口，2026-10-04 订场改版） */
  border-color: rgba(111, 231, 255, 0.4);
}
.actions .cancel-btn {
  color: var(--coral); /* alpha:1461 取消局 */
  border-color: rgba(255, 90, 54, 0.4);
}
.mt12 {
  margin-top: 12px; /* alpha:1465-1466 burn 通栏钮 */
}
.rules {
  margin-top: 14px; /* alpha:1466 */
}

.ph {
  color: var(--dim);
  font-family: var(--mono);
  font-size: 12px;
  letter-spacing: 0.1em;
}
</style>
