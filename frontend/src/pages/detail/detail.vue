<template>
  <!-- 球局详情（3.2）· alpha.html:1400-1467 openDetail() 模板逐字对齐（P5a 静态结构）。
       数据按 url query 的 id 从 game store 取局；所有按钮本阶段为占位 handler（P5b 接 store/弹层、
       P8 接现场页），不做路由跳转与 store 写操作。非 tab 页：无 TabBar，仍挂全部宿主。 -->
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
        <view class="sub hero-sub">{{ tDay }} · 打 {{ game.dur }} 小时 · {{ game.loc }}</view>
        <view class="row">
          <view class="kv">
            <view class="k">名单</view>
            <view class="v">{{ hs }}/{{ game.cap }}</view>
          </view>
          <view class="kv">
            <view class="k">剩坑</view>
            <view class="v" :style="{ color: need ? 'var(--coral)' : 'var(--dim)' }">{{ need }}</view>
          </view>
          <view class="kv">
            <view class="k">总价</view>
            <view class="v">¥{{ game.fee }}</view>
          </view>
          <view class="kv">
            <view class="k">人均</view>
            <view class="v v-lemon">¥{{ ph }}</view>
          </view>
          <view class="kv">
            <view class="k">截止</view>
            <view class="v v-dl">{{ game.deadline }}</view>
          </view>
        </view>
        <!-- alpha:1421-1423：有说明或人未够最少时展示，人均口径三态（alpha:1406 splitNote 逐字） -->
        <view v-if="game.note || hs < game.min" class="sub hero-note">
          {{ game.note ? `说明：${game.note} · ` : '' }}{{ splitNote }}
        </view>
        <view class="row act2">
          <AppButton variant="ghost" size="sm" @click="onShare">⤴ 分享到群</AppButton>
          <AppButton
            v-if="org && !game.locked && game.status === 'open'"
            variant="ghost"
            size="sm"
            @click="onDeadline"
          >⏰ 到截止 · 判定</AppButton>
          <AppChip v-if="game.locked" kind="full">已到截止 · 名单锁定</AppChip>
        </view>
      </view>

      <!-- alpha:1425-1428 steps 进度条：status !== 'open' 时「报名/候补」点亮 -->
      <view class="steps">
        <text class="s" :class="{ on: started }">报名</text>
        <view class="i" :class="{ on: started }" />
        <text class="s" :class="{ on: started }">候补</text>
        <view class="i" />
        <text class="s">进行中</text>
        <view class="i" />
        <text class="s">战报</text>
      </view>

      <!-- alpha:1429-1444 名单：组织者排头一个 · 随行/带 N 人角标 · 随行展开成独立 pcard -->
      <SectionTitle :title="`名单 ${hs}/${game.cap} · 组织者排头一个`">
        <template v-if="game.wait.length" #more>候补 {{ game.wait.length }} 人</template>
      </SectionTitle>
      <view class="grid-p">
        <template v-for="e in game.joined" :key="e.u.id">
          <view class="pcard" :class="{ me: e.u.id === 0 }">
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
        <view v-if="!joined" class="pcard join" @click="onJoin">
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

      <!-- alpha:1448-1450 组织者按钮行（仅 open 态） -->
      <view v-if="org && game.status === 'open'" class="org-row">
        <AppButton variant="ghost" size="sm" @click="onInvite">＋ 邀请 · 翻意向列表拉人</AppButton>
        <AppButton variant="ghost" size="sm" @click="onAddCourt">＋ 加场 · 上限 {{ game.cap }}→{{ game.cap + 2 }}</AppButton>
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
        <AppChip v-if="joined && !org && game.locked" class="mid">已到截止 · 不能退出</AppChip>
        <template v-if="org && game.status !== 'live'">
          <AppChip v-if="game.sure" class="mid sure-chip">🔒 已锁定必打 · 人数不足也照打</AppChip>
          <AppButton v-else variant="ghost" class="grow sure-btn" @click="onSure">🔒 锁定必打</AppButton>
        </template>
        <template v-if="org && game.status !== 'live'">
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

      <!-- alpha:1466 规则牌（modeName/迟到规则/候补递补/人均摊法口径逐字） -->
      <NoteCard class="rules">
        <b>规则牌：</b>{{ game.score }} 分制（领先 2 分才算赢）· {{ modeName }}{{ game.lateRule ? ' · 迟到排队尾等一轮' : '' }}
        · 满 {{ game.cap }} 人进候补，有人退出即刻递补 · 人均＝总价 ¥{{ game.fee }} ÷ {{ perBase }}（{{ perNote }}）。
      </NoteCard>
    </view>
    <!-- alpha 无此态（openDetail 有 guard）；直链/局被撤下时的兜底占位，非产品文案 -->
    <view v-else class="ph">GAME NOT FOUND</view>
  </PageShell>
</template>

<script setup lang="ts">
/* alpha.html:1400-1467 openDetail 静态化（P5a）；
   摊法口径引用 utils/format 的 perHead（alpha:884，带注释口径）。 */
import { computed, ref } from 'vue';
import { onLoad } from '@dcloudio/uni-app';
import PageShell from '@/components/biz/PageShell.vue';
import AppButton from '@/components/ui/AppButton.vue';
import AppChip from '@/components/ui/AppChip.vue';
import ChibiAvatar from '@/components/ui/ChibiAvatar.vue';
import NoteCard from '@/components/ui/NoteCard.vue';
import SectionTitle from '@/components/ui/SectionTitle.vue';
import { useGameStore } from '@/stores/game';
import { heads, needOf, perHead, myEntry, isOrg } from '@/utils/format';
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

/* alpha:1410 大时间 = t 第二段（时刻）；1411 小字 = t 第一段（今晚/周六…） */
const tBig = computed(() => (game.value ? (game.value.t.split(' ')[1] ?? '') : ''));
const tDay = computed(() => (game.value ? (game.value.t.split(' ')[0] ?? '') : ''));

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

/* alpha:1406 人均口径副文案（三态逐字） */
const splitNote = computed(() => {
  const g = game.value;
  if (!g) return '';
  return g.sure
    ? '人均按当前人数摊（最少要求已作废）'
    : hs.value < g.min
      ? `不足最少 ${g.min} 人 · 人均按最少摊`
      : `人均按当前 ${hs.value} 人摊`;
});

/* alpha:1405 发牌模式名 */
const MODE_NAMES: Record<CourtMode, string> = { winner: '赢家留场', rotate: '纯粹轮转', balance: '均衡配对' };
const modeName = computed(() => (game.value ? MODE_NAMES[game.value.mode] : ''));

/* alpha:1466 规则牌人均分母与括注（Math.max(g.sure?0:g.min,hs) 逐字口径） */
const perBase = computed(() => (game.value ? Math.max(game.value.sure ? 0 : game.value.min, hs.value) : 0));
const perNote = computed(() => {
  const g = game.value;
  if (!g) return '';
  return g.sure ? '必定开局后按实际人数摊' : hs.value < g.min ? '不足最少按最少摊' : '按当前人数摊';
});

/* ---- 操作占位（静态阶段不写 store / 不做路由）：P5b 接 game store 动作与 SheetHost 弹层 ---- */
const onShare = () => {};    /* P5b: store.shareGame(game.id)（alpha:1418 shareGame） */
const onDeadline = () => {}; /* P5b: store.hitDeadline(game.id)（alpha:1419 hitDeadline） */
const onJoin = () => {};     /* P5b: ui.openSheet({type:'join',gameId})（alpha:1441/1452 joinSheet） */
const onQuit = () => {};     /* P5b: ui.openSheet({type:'quit-confirm',gameId})（alpha:1453 quitSheet） */
const onSure = () => {};     /* P5b: store.sureGame(game.id)（alpha:1459 sureGame） */
const onEdit = () => {};     /* P5b: ui.openSheet({type:'launch',gameId})（alpha:1460 editSheet） */
const onCancel = () => {};   /* P5b: ui.openSheet({type:'cancel-confirm',gameId})（alpha:1461 cancelSheet） */
const onInvite = () => {};   /* P5b: ui.openSheet({type:'invite-to-game',gameId})（alpha:1449 inviteFromGame） */
const onAddCourt = () => {}; /* P5b: ui.openSheet({type:'add-court',gameId})（alpha:1450 addCourtSheet） */
const onStart = () => {};    /* P8: live store startLive（alpha:1468 startLive） */
const onLive = () => {};     /* P8: uni.navigateTo → live 页（alpha:1465 go('live')） */
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
.kv .v.v-dl {
  font-size: 13px;
  line-height: 1.7; /* alpha:1416 截止小字 */
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
.actions .sure-chip {
  color: var(--ice); /* alpha:1458 ice 描边锁定徽章 */
  border-color: rgba(111, 231, 255, 0.45);
}
.actions .sure-btn {
  color: var(--ice); /* alpha:1459 锁定必打按钮 */
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
