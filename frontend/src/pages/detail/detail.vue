<template>
  <!-- 球局详情（3.2 · 1.2 接线修订面）：数据 = loadDetail 的真局（store.current）；
       全部动作走 game store 与 SheetHost 弹层，toast 文案由 store 逐字负责。
       名单/人头/人均/状态全是后端定值（A4），加入入口读 joinable，退局窗口读 status+unlocked。
       非 tab 页：无 TabBar，仍挂全部宿主。 -->
  <PageShell>
    <view v-if="game" class="stag">
      <!-- alpha:1403-1407 页头：kicker + 局名（首个 ' · ' 断行，其余保留） -->
      <view class="kicker">Game #{{ game.id }} · {{ tDay }} · {{ game.organizer.nickname }} 发起</view>
      <view class="brand">
        {{ brandA }}
        <text v-if="brandB" class="brand-line">{{ brandB }}</text>
      </view>

      <!-- alpha:1408-1424 hero：大时间 · 日段·时长·场馆 · kv 行 · 人均口径 · 分享行 -->
      <view class="hero">
        <view class="big">{{ tBig }}</view>
        <view class="sub hero-sub">{{ tDay }} · 打 {{ durText }} · {{ game.venueName }}</view>
        <view class="row">
          <view class="kv">
            <view class="k">名单</view>
            <view class="v">{{ game.heads }}/{{ game.maxPlayers }}</view>
          </view>
          <!-- 5.1 剩坑/截止/场地是赛前口径：done 局收掉，保住 kv 网格 -->
          <view v-if="game.status !== 'done'" class="kv">
            <view class="k">剩坑</view>
            <view class="v" :style="{ color: game.slotsLeft ? 'var(--dim)' : 'var(--coral)' }">{{ game.slotsLeft }}</view>
          </view>
          <view class="kv">
            <view class="k">{{ game.feeTotal != null ? '总价' : '费用' }}</view>
            <view class="v">{{ game.feeTotal != null ? `¥${game.feeTotal}` : '未定' }}</view>
          </view>
          <view v-if="game.perHead != null" class="kv">
            <view class="k">人均</view>
            <view class="v v-lemon">¥{{ game.perHead }}</view>
          </view>
          <view v-if="game.status !== 'done'" class="kv">
            <view class="k">场地</view>
            <view class="v v-court" :style="{ color: game.courts?.length ? 'var(--cream)' : 'var(--dim)' }">
              {{ game.courts?.length ? game.courts.join('、') : '待定' }}
            </view>
          </view>
          <view v-if="game.status !== 'done'" class="kv">
            <view class="k">截止</view>
            <view class="v v-dl">{{ isoDay(game.deadlineAt) }} {{ isoHm(game.deadlineAt) }}</view>
          </view>
          <view v-if="game.unlocked" class="kv">
            <view class="k">名单</view>
            <view class="v v-court">改约解锁 · 可退</view>
          </view>
        </view>
        <!-- 人均口径（后端定值：订场后按实际人数摊）/ 截止判局提示 -->
        <view v-if="perNote" class="sub hero-note">{{ perNote }}</view>
        <view class="row act2">
          <AppButton variant="ghost" size="sm" @click="onShare">⤴ 分享到群</AppButton>
          <AppChip v-if="game.status === 'locked' && !game.unlocked" kind="full">已到截止 · 名单锁定</AppChip>
        </view>
      </view>

      <!-- alpha:1425-1428 steps 进度条：报名/候补/进行中/战报（status 线性推进） -->
      <view class="steps">
        <text class="s" :class="{ on: started }">报名</text>
        <view class="i" :class="{ on: started }" />
        <text class="s" :class="{ on: started }">候补</text>
        <view class="i" :class="{ on: played }" />
        <text class="s" :class="{ on: played }">进行中</text>
        <view class="i" :class="{ on: reported }" />
        <text class="s" :class="{ on: reported }">战报</text>
      </view>

      <!-- 名单：formal 按报名先后（组织者排头）、候补按序跟后（后端 entries 保序）；
           带 N 人角标 + 随行展开成独立 pcard（带的人不单独有账号，随主人头像） -->
      <SectionTitle :title="`名单 ${game.heads}/${game.maxPlayers} · 组织者排头一个`">
        <template v-if="waitlist.length" #more>候补 {{ waitlist.length }} 人</template>
      </SectionTitle>
      <view class="grid-p">
        <template v-for="e in formalRows" :key="e.account.id">
          <view class="pcard" :class="{ me: e.account.id === meId }" @click="onPlayer(e.account.id)">
            <view v-if="e.bring" class="tag">带 {{ e.bring }} 人</view>
            <view class="avatar"><ChibiAvatar :chibi="e.account.chibi" :size="56" /></view>
            <view class="nm">{{ e.account.nickname }}</view>
          </view>
          <!-- 带的人：用带他的人的头像，名 = 名字前两字+的球友 -->
          <view v-for="i in e.bring || 0" :key="`${e.account.id}-b${i}`" class="pcard dim75">
            <view class="tag">随行</view>
            <view class="avatar"><ChibiAvatar :chibi="e.account.chibi" :size="56" /></view>
            <view class="nm">{{ e.account.nickname.slice(0, 2) }}的球友</view>
          </view>
        </template>
        <!-- 加入入口：joinable 定值（截止后/进行中照常可加，已结束只读——4.14） -->
        <view v-if="!joined && game.joinable" class="pcard join" @click="onJoin">
          <view class="plus">＋</view>
          <view class="nm">加入 / 带人</view>
        </view>
      </view>

      <!-- 候补栏 -->
      <template v-if="waitlist.length">
        <SectionTitle title="候补栏">
          <template #more>有人退出即刻递补</template>
        </SectionTitle>
        <view class="grid-p">
          <view v-for="e in waitlist" :key="`w${e.account.id}`" class="pcard dim65">
            <view class="avatar"><ChibiAvatar :chibi="e.account.chibi" :size="56" /></view>
            <view class="nm">{{ e.account.nickname }}</view>
          </view>
        </view>
      </template>

      <!-- 组织者按钮行：翻意向拉人（截止前后都开放——现场换人常翻名单） -->
      <view v-if="org && game.joinable" class="org-row">
        <AppButton variant="ghost" size="sm" @click="onInvite">＋ 邀请 · 翻意向列表拉人</AppButton>
      </view>

      <!-- 底部动作区：加入/退局窗口与提示全按 status/unlocked 定值 -->
      <view class="actions">
        <AppButton v-if="!joined && game.joinable" variant="pri" class="grow" @click="onJoin">
          ＋ 加入 · 可带人{{ full ? ' · 进候补' : '' }}
        </AppButton>
        <AppButton
          v-if="joined && !org && canQuit"
          variant="ghost"
          class="grow"
          @click="onQuit"
        >退出局</AppButton>
        <AppChip v-if="joined && !org && !canQuit && game.status !== 'done'" class="mid">已到截止 · 不能退出</AppChip>
        <!-- 锁升级三态一入口（BookingSheet 批5 重排面板；这里先把动作与文案接上） -->
        <template v-if="org && (game.status === 'open' || game.status === 'locked')">
          <AppButton variant="ghost" class="grow sure-btn" @click="onBooking">{{
            game.courts?.length
              ? `🔒 已订场 · ${game.courts.join('、')} · ¥${game.feeTotal}`
              : game.manualLock
                ? '🔒 已锁定必打 · 去登记场地'
                : '🔒 锁定必打 · 可登记订场'
          }}</AppButton>
        </template>
        <template v-if="org && (game.status === 'open' || game.status === 'locked')">
          <AppButton variant="ghost" @click="onEdit">改信息</AppButton>
          <AppButton variant="ghost" class="cancel-btn" @click="onCancel">取消局</AppButton>
        </template>
      </view>

      <!-- 状态动作：live 回现场；在办局开始打球 -->
      <AppButton v-if="game.status === 'live'" variant="burn" block class="mt12" @click="onLive">▶ 回到现场</AppButton>
      <AppButton
        v-else-if="game.joinable"
        variant="burn"
        block
        class="mt12"
        @click="onStart"
      >▶ 开始打球</AppButton>

      <!-- 规则牌（规则三件 + 候补/人均口径；score_rule 未知值不显示得分规则段——旧局容错） -->
      <NoteCard class="rules">
        <b>规则牌：</b>{{ game.scoring }} 分制（领先 2 分才算赢）<template v-if="ruleName"> · {{ ruleName }}</template> · {{ modeName }}
        · 满 {{ game.maxPlayers }} 人进候补，有人退出即刻递补<template v-if="game.perHead != null"> · 人均＝总价 ¥{{ game.feeTotal }} ÷ {{ game.heads }}（按实际人数摊）</template>。
      </NoteCard>
    </view>
    <!-- A2：等待提示 / 链接失效说明页（文案中性） -->
    <view v-else-if="loading" class="ph">{{ slow ? '网络有点慢 · 再等等，或稍后再来' : '正在打开这局…' }}</view>
    <view v-else class="ph">这个球局不存在或已被删除</view>
  </PageShell>
</template>

<script setup lang="ts">
/* 球局详情（alpha.html:1400-1467 · 1.2 接线修订面）。数据源 = game store 的 loadDetail/current；
   分享按钮只出 toast（分享卡片降级规格§6）；「到截止判定」手动按钮退役（懒判定归后端）。 */
import { computed, onUnmounted, ref } from 'vue';
import { onLoad, onShow } from '@dcloudio/uni-app';
import PageShell from '@/components/biz/PageShell.vue';
import AppButton from '@/components/ui/AppButton.vue';
import AppChip from '@/components/ui/AppChip.vue';
import ChibiAvatar from '@/components/ui/ChibiAvatar.vue';
import NoteCard from '@/components/ui/NoteCard.vue';
import { useGameStore } from '@/stores/game';
import { useUserStore } from '@/stores/user';
import { useUiStore } from '@/stores/ui';
import { isOrg, MODE_NAMES, SCORE_RULE_NAMES } from '@/utils/format';
import { isoDay, isoHm } from '@/utils/time';
import { goLive } from '@/utils/nav';

const store = useGameStore();
const ui = useUiStore();

const gameId = ref<number | null>(null);
const loading = ref(false);

onLoad((options) => {
  const raw = (options as Record<string, string | undefined> | undefined)?.id;
  const n = raw != null ? Number(raw) : NaN;
  gameId.value = Number.isFinite(n) ? n : null;
});

/* A2 加载：等待提示，超 2 秒提示网络问题（仿 meet.vue slowTimer） */
const slow = ref(false);
let slowTimer: ReturnType<typeof setTimeout> | null = null;

onShow(() => {
  if (gameId.value == null || loading.value) return;
  loading.value = true;
  if (slowTimer) clearTimeout(slowTimer);
  slowTimer = setTimeout(() => (slow.value = true), 2000);
  store
    .loadDetail(gameId.value)
    .catch(() => undefined) // 404/断网 → 走下方说明页兜底
    .finally(() => {
      loading.value = false;
      if (slowTimer) clearTimeout(slowTimer);
      slow.value = false; // 复位毛刺：上一轮慢网点亮的 slow 不能带进下一轮加载
    });
});
onUnmounted(() => {
  if (slowTimer) clearTimeout(slowTimer);
});

const game = computed(() => (gameId.value != null && store.current?.id === gameId.value ? store.current : null));

/* ---- 名单派生（后端 entries 已按 formal 报名序 + 候补序排好） ---- */
const formalRows = computed(() => game.value?.entries?.filter((e) => e.standing === 'formal') ?? []);
const waitlist = computed(() => game.value?.entries?.filter((e) => e.standing === 'waitlist') ?? []);

const full = computed(() => !!game.value && game.value.slotsLeft <= 0);
const joined = computed(() => !!game.value?.my?.myEntry);
const org = computed(() => !!game.value && isOrg(game.value));
/** 退局窗口：报名中随便退；锁定后仅改约解锁窗可退（4.4/4.6） */
const canQuit = computed(() => !!game.value && (game.value.status === 'open' || game.value.unlocked));
const started = computed(() => !!game.value && game.value.status !== 'open');
const played = computed(() => {
  const s = game.value?.status;
  return s === 'live' || s === 'done';
});
const reported = computed(() => game.value?.status === 'done');

/* 3.3 打多久文案：endAt-startAt 现算（拨盘 5 分步进会出现 115 分钟这类；整/半小时才用小时） */
const durText = computed(() => {
  if (!game.value) return '';
  const mins = Math.max(
    0,
    Math.round((new Date(game.value.endAt).getTime() - new Date(game.value.startAt).getTime()) / 60000),
  );
  return mins % 30 === 0 ? `${mins / 60} 小时` : `${mins} 分钟`;
});

const tBig = computed(() => (game.value ? isoHm(game.value.startAt) : ''));
const tDay = computed(() => (game.value ? isoDay(game.value.startAt) : ''));

/* alpha:1405 局名首个 ' · ' 断行 */
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

/* 人均口径提示：费用未定时提示截止判局；费用落定即按实际人数摊（4.7） */
const perNote = computed(() => {
  const g = game.value;
  if (!g) return '';
  if (g.feeTotal != null) return `费用已落定 · 人均按当前 ${g.heads} 人摊`;
  if (g.heads < g.minPlayers && !g.forced) return `还差 ${g.minPlayers - g.heads} 人到最少 · 截止人数不足且未锁必打会自动终止`;
  return '';
});

/* 规则牌：mode 必有；得分规则仅认识 rally/serve（旧局/未知值不显示） */
const modeName = computed(() => (game.value ? MODE_NAMES[game.value.rotation] : ''));
const ruleName = computed(() => {
  const r = game.value?.scoreRule;
  return r === 'rally' || r === 'serve' ? SCORE_RULE_NAMES[r] : '';
});

/** 响应式「我」id（名单行高亮） */
const meId = computed(() => useUserStore().me.id);

/** 分享 = 纯 toast（分享卡片降级，规格§6；演示模拟已随假局退役） */
const onShare = () => {
  ui.toast('分享卡片已生成 · 转到微信群里拉人');
};
/** joinSheet → JoinSheet 弹层 */
const onJoin = () => {
  if (game.value) ui.openSheet({ type: 'join', gameId: game.value.id });
};
/** quitSheet → ConfirmSheet(kind=quit) */
const onQuit = () => {
  if (game.value) ui.openSheet({ type: 'quit-confirm', gameId: game.value.id });
};
/** 锁定必打 / 订场登记（三态一入口 BookingSheet） */
const onBooking = () => {
  if (game.value) ui.openSheet({ type: 'booking', gameId: game.value.id });
};
/** editSheet → openLaunch(id)：LaunchSheet 编辑态 */
const onEdit = () => {
  if (game.value) ui.openSheet({ type: 'launch', gameId: game.value.id });
};
/** cancelSheet → ConfirmSheet(kind=cancel) */
const onCancel = () => {
  if (game.value) ui.openSheet({ type: 'cancel-confirm', gameId: game.value.id });
};
/** inviteFromGame → InviteSheet(mode=to-game) */
const onInvite = () => {
  if (game.value) ui.openSheet({ type: 'invite-to-game', gameId: game.value.id });
};
/** 开始打球 → 现场页（goLive 内 ensureLive 统一守门） */
const onStart = () => {
  if (game.value) goLive(game.value.id);
};
const onLive = () => {
  if (game.value) goLive(game.value.id);
};
/** 名单球员卡 → 球友名片弹层（真局成员可能不在 mock U，档案页自兜底） */
const onPlayer = (uid: number) => {
  ui.openSheet({ type: 'profile', userId: uid });
};
</script>

<style lang="scss" scoped>
/* 页面专属类（alpha:226-245 hero/kv/steps/grid-p/pcard/avatar + openDetail 内联样式）。 */

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
  color: var(--lemon);
}
.kv .v.v-dl {
  font-size: 13px;
  line-height: 1.7;
}
.kv .v.v-court {
  font-size: 13px;
  line-height: 1.7;
}
.sub.hero-note {
  margin-top: 10px;
  font-size: 12px;
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
  opacity: 0.75;
}
.pcard.dim65 {
  opacity: 0.65;
}
.avatar {
  width: 56px;
  height: 56px;
  margin: 0 auto;
}
.pcard.join {
  border-style: dashed;
  cursor: pointer;
}
.pcard.join .plus {
  font-size: 34px;
  color: var(--lemon);
  font-family: var(--disp);
  padding-top: 18px;
}

/* ---------- 按钮行与动作区（openDetail 内联样式） ---------- */
.org-row {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  flex-wrap: wrap;
}
.actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
  flex-wrap: wrap;
}
.actions .grow {
  flex: 1;
}
.actions .mid {
  align-self: center;
}
.actions .sure-btn {
  color: var(--ice);
  border-color: rgba(111, 231, 255, 0.4);
}
.actions .cancel-btn {
  color: var(--coral);
  border-color: rgba(255, 90, 54, 0.4);
}
.mt12 {
  margin-top: 12px;
}
.rules {
  margin-top: 14px;
}

.ph {
  color: var(--dim);
  font-family: var(--mono);
  font-size: 12px;
  letter-spacing: 0.1em;
}
</style>
