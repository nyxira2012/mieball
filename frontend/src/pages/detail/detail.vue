<template>
  <!-- 球局详情（3.2 · 1.2 接线修订面）：数据 = loadDetail 的真局（store.current）；
       全部动作走 game store 与 SheetHost 弹层，toast 文案由 store 逐字负责。
       名单/人头/人均/状态全是后端定值（A4），加入入口读 joinable，退局窗口读 status+unlocked。
       非 tab 页：无 TabBar，仍挂全部宿主。 -->
  <PageShell>
    <!-- 子页统一返回行：全站 navigationStyle custom 关了系统导航，详情页是六页里唯一漏挂的
         （又常是微信分享卡落地页）——放 v-if 外，加载失败态也有出口；长页滚动吸附见 BackRow -->
    <BackRow />
    <view v-if="game" class="stag">
      <!-- 页头：kicker + 局名（首个 ' · ' 断行，其余保留） -->
      <view class="kicker"
        >Game #{{ game.id }} · {{ tDay }} ·
        {{ game.organizer.nickname }} 发起</view
      >
      <view class="brand">
        {{ brandA }}
        <text v-if="brandB" class="brand-line">{{ brandB }}</text>
      </view>

      <!-- hero：大时间 · 日段·时长·场馆 · kv 行 · 人均口径 · 分享行
           （散场后切实际：大时刻=开账刻，时长行=打到几点） -->
      <view class="hero">
        <view class="big">{{ tBig }}</view>
        <view class="sub hero-sub"
          >{{ tDay }} ·
          {{
            endedLive
              ? `打到 ${isoHm(game.endedAt as string)}`
              : `打 ${durText}`
          }}
          · {{ game.venueName }}</view
        >
        <view class="row">
          <view class="kv">
            <view class="k">名单</view>
            <view class="v">{{ rosterCount }}/{{ game.maxPlayers }}</view>
          </view>
          <!-- 5.1 剩坑/截止/场地是赛前口径：done 局收掉，保住 kv 网格 -->
          <view v-if="game.status !== 'done'" class="kv">
            <view class="k">剩坑</view>
            <view
              class="v"
              :style="{ color: game.slotsLeft ? 'var(--dim)' : 'var(--coral)' }"
              >{{ game.slotsLeft }}</view
            >
          </view>
          <view class="kv">
            <view class="k">{{ game.feeTotal != null ? "总价" : "费用" }}</view>
            <view class="v">{{
              game.feeTotal != null ? `¥${game.feeTotal}` : "未定"
            }}</view>
          </view>
          <!-- A4 人均口径：未出账=预估（标「约」）；已出账=实摊（bill 块后端定格数，
               顶层 per_head 仍是订场时按报名人数的预估，出账后弃用） -->
          <view v-if="perHeadTxt" class="kv">
            <view class="k">人均</view>
            <view class="v v-lemon">{{ perHeadTxt }}</view>
          </view>
          <!-- 1.3 §4.1：局页「我自己那份」与账单行同一个数（含朋友份、同样带小字） -->
          <view v-if="game.bill?.myShare != null" class="kv">
            <view class="k">我自己那份</view>
            <view class="v v-lemon">¥{{ game.bill.myShare }}</view>
            <view v-if="(game.bill?.myGuestCount ?? 0) > 0" class="kv-sub"
              >含带来的朋友 ×{{ game.bill?.myGuestCount }}</view
            >
          </view>
          <view v-if="game.status !== 'done'" class="kv">
            <view class="k">场地</view>
            <view
              class="v v-court"
              :style="{
                color: game.courts?.length ? 'var(--cream)' : 'var(--dim)',
              }"
            >
              {{ game.courts?.length ? game.courts.join("、") : "待定" }}
            </view>
          </view>
          <view v-if="game.status !== 'done'" class="kv">
            <view class="k">截止</view>
            <view class="v v-dl"
              >{{ isoDay(game.deadlineAt) }} {{ isoHm(game.deadlineAt) }}</view
            >
          </view>
          <view v-if="game.unlocked" class="kv">
            <view class="k">名单</view>
            <view class="v v-court">改约解锁 · 可退</view>
          </view>
        </view>
        <!-- 人均口径（后端定值：订场后按实际人数摊）/ 截止判局提示 -->
        <view v-if="perNote" class="sub hero-note">{{ perNote }}</view>
        <!-- 分享行（2026-10-12 三处统一后的主分享口，唯一发链处=详情页）：文案两态——
             赛前拉人「分享组局详情」、散场后晒账「分享战报详情」（ended 锚，与查看战报
             同一把尺）；散场后换柠檬主钮（这页此时的亮动作就是它），赛前描边安静不抢
             底部的加入/开始打球；有锁定 chip 时同行分享让位收窄 -->
        <view class="row act2">
          <AppButton
            :variant="game.ended ? 'pri' : 'ghost'"
            size="sm"
            class="share-btn"
            @click="onShare"
            >{{ game.ended ? "分享战报详情" : "分享组局详情" }}</AppButton
          >
          <AppChip v-if="game.status === 'locked' && !game.unlocked" kind="full"
            >已到截止 · 名单锁定</AppChip
          >
        </view>
      </view>

      <!-- steps 进度条：报名/候补/进行中/战报（status 线性推进） -->
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
      <SectionTitle
        :title="`名单 ${rosterCount}/${game.maxPlayers} · 组织者排头一个`"
      >
        <template v-if="rosterMore" #more>{{ rosterMore }}</template>
      </SectionTitle>
      <view class="grid-p">
        <template v-for="e in formalRows" :key="e.account.id">
          <view
            class="pcard"
            :class="{ me: e.account.id === meId }"
            @click="onPlayer(e.account.id)"
          >
            <view v-if="e.bring" class="tag">带 {{ e.bring }} 人</view>
            <view class="avatar"
              ><ChibiAvatar :chibi="e.account.chibi" :size="56"
            /></view>
            <view class="nm">{{ e.account.nickname }}</view>
          </view>
          <!-- 带的人：用带他的人的头像，名 = 名字前两字+的球友 -->
          <view
            v-for="i in e.bring || 0"
            :key="`${e.account.id}-b${i}`"
            class="pcard dim75"
          >
            <view class="tag">随行</view>
            <view class="avatar"
              ><ChibiAvatar :chibi="e.account.chibi" :size="56"
            /></view>
            <view class="nm">{{ e.account.nickname.slice(0, 2) }}的球友</view>
          </view>
        </template>
        <!-- 空降：扫码进场，有账号有点头像可跳档案 -->
        <view
          v-for="d in dropins"
          :key="`d${d.account.id}`"
          class="pcard"
          :class="{ me: d.account.id === meId }"
          @click="onPlayer(d.account.id)"
        >
          <view class="tag dropin">空降</view>
          <view class="avatar"
            ><ChibiAvatar :chibi="d.account.chibi" :size="56"
          /></view>
          <view class="nm">{{ d.account.nickname }}</view>
        </view>
        <!-- 加人位（双角色共用：同一个位置同一个形状，点开各办各的事）——参加者=加入/
             带人，组织者=邀请（翻意向列表拉人）。joinable 定值（截止后/进行中照常可加，
             已结束只读——4.14；组织者邀请同样截止前后都开放——现场换人常翻名单）。
             @click 必须绑具名方法：绑三元表达式会编译成「返回函数」而非调用，点了没反应 -->
        <view
          v-if="game.joinable && (!joined || org)"
          class="pcard join"
          @click="onSeat"
        >
          <view class="plus">＋</view>
          <view class="nm">{{ org ? "邀请 · 拉人" : "加入 · 带人" }}</view>
        </view>
      </view>

      <!-- 候补栏 -->
      <template v-if="waitlist.length">
        <SectionTitle title="候补栏">
          <template #more>有人退出即刻递补</template>
        </SectionTitle>
        <view class="grid-p">
          <view
            v-for="e in waitlist"
            :key="`w${e.account.id}`"
            class="pcard dim65"
          >
            <view class="avatar"
              ><ChibiAvatar :chibi="e.account.chibi" :size="56"
            /></view>
            <view class="nm">{{ e.account.nickname }}</view>
          </view>
        </view>
      </template>

      <!-- 底部动作区：加入/退局窗口与提示全按 status/unlocked 定值 -->
      <view class="actions">
        <AppButton
          v-if="!joined && game.joinable"
          variant="pri"
          class="grow"
          @click="onJoin"
        >
          ＋ 加入 · 可带人{{ full ? " · 进候补" : "" }}
        </AppButton>
        <AppButton
          v-if="joined && !org && canQuit"
          variant="ghost"
          class="grow"
          @click="onQuit"
          >退出局</AppButton
        >
        <AppChip
          v-if="joined && !org && !canQuit && game.status !== 'done'"
          class="mid"
          >已到截止 · 不能退出</AppChip
        >
        <!-- 订场登记入口（BookingSheet；这里把动作与文案接上）。
             显隐直读能力旗 my.canBook（闸旗同源：后端 booking_window_error 同一份，
             散场确认前随时可改——开打中加片/买水、到点未散场照改、pending 待处置也走此门）；
             done+未填价的补填形态走 canFillFee 入口（只有散场过的局留这一个口子）。
             2026-10-10 用户定稿：按钮独占一行、文案只按「有没有场地信息」二分，不带货
             （场地号/总价头部信息卡已有）：无场地=输入已预定场地（未锁/空锁/live 未登记
             同句——登记即锁）；有场地非 live=已订场待开局；live 中=加场/改总价。
             必打判定逻辑不动（面板内照旧）。
             2026-10-08 债清偿：此前拿派生 status 拼 open|locked|live，到点未散场的
             派生 done 把钮收走（后端窗其实开着）——四份窗口拷贝就此归一 -->
        <template v-if="!!game.my?.canBook">
          <AppButton
            variant="ghost"
            class="grow full-row sure-btn"
            @click="onBooking"
            >{{
              game.courts?.length
                ? game.status === "live"
                  ? "已订场 · 加场 / 改总价"
                  : "已订场待开局"
                : "输入已预定场地"
            }}</AppButton
          >
        </template>
        <!-- 补填费用（1.3 §4.5）：显隐直读 my.canFillFee（后端 fill_fee_error 同一份：
             散场过且从未填价才亮——到点未散场的派生 done 不亮，点了必 game_not_ended） -->
        <template v-if="!!game.my?.canFillFee">
          <AppButton variant="ghost" class="grow sure-btn" @click="onBookingFee"
            >补填费用 · 只填总价（免费填 0）</AppButton
          >
        </template>
        <template
          v-if="org && (game.status === 'open' || game.status === 'locked')"
        >
          <AppButton variant="ghost" class="grow" @click="onEdit"
            >改信息</AppButton
          >
          <AppButton variant="ghost" class="grow cancel-btn" @click="onCancel"
            >取消局</AppButton
          >
        </template>
      </view>

      <!-- 状态动作（2.5 附录A1：详情与卡片同一套规矩）。组织者——报名中未定必开给指引句
           （无按钮语义，后端 live_requires_forced 同闸）、已锁/已订场随时开始（goLive 内
           ensureLive 开账，幂等）、开着回现场，done/终态无按钮。「回现场」补一类：账已开
           且未散场（liveOpened ∧ ¬ended）——到点未散场的局派生已是 done 但流程没散场，
           组织者要能回去补散场确认，否则局挂死在吸收态（2026-10-08 债清偿）。正式成员——
           「进入现场」吃卡片同源判定 cardLiveEntry（账开 ∨ 必开两小时窗）；
           候补/未报名/游客无按钮（上场唯一路=现场扫码）。已散场的局（ended 锚存储事实）
           亮「查看战报」（2.6 §4.2）：能开详情的人都见（战报链接即门票，不加身份条件） -->
      <AppChip v-if="orgGuide" class="mt12">先锁定必打，才能开始打球</AppChip>
      <AppButton
        v-else-if="org && (game.status === 'open' || game.status === 'locked')"
        variant="burn"
        block
        class="mt12"
        @click="onLive"
        >▶ 开始打球</AppButton
      >
      <AppButton
        v-else-if="org && liveOngoing(game)"
        variant="burn"
        block
        class="mt12"
        @click="onLive"
        >▶ 回到现场</AppButton
      >
      <AppButton
        v-else-if="memberLiveEnter"
        variant="burn"
        block
        class="mt12"
        @click="onLive"
        >▶ 进入现场</AppButton
      >
      <AppButton
        v-else-if="game.ended"
        variant="burn"
        block
        class="mt12"
        @click="onRecap"
        >查看战报</AppButton
      >

      <!-- 规则牌（规则三件 + 候补/人均口径；score_rule 未知值不显示得分规则段——旧局容错） -->
      <NoteCard class="rules">
        <b>规则牌：</b>{{ game.scoring }} 分制（领先 2 分才算赢）<template
          v-if="ruleName"
        >
          · {{ ruleName }}</template
        >
        · {{ modeName }} · 满
        {{ game.maxPlayers }} 人进候补，有人退出即刻递补<template
          v-if="rulePerTxt"
        >
          · {{ rulePerTxt }}</template
        >。
      </NoteCard>
    </view>
    <!-- A2：等待提示 / 链接失效说明页（2.6 §4.6 统一句：链接场景不说「已结束」） -->
    <view v-else-if="loading" class="ph">{{
      slow ? "网络有点慢 · 再等等，或稍后再来" : "正在打开这局…"
    }}</view>
    <view v-else class="ph">{{ DEAD_LINK_MSG }}</view>
  </PageShell>
</template>

<script setup lang="ts">
/* 球局详情（1.2 接线修订面）。数据源 = game store 的 loadDetail/current；
   分享 = 系统分享面板优先、复制链接兜底，微信内走右上角「···」转出已登记的
   自定义分享卡（见下方 watch 登记）；「到截止判定」手动按钮退役（懒判定归后端）。 */
import { computed, ref, watch } from "vue";
import { onLoad, onShow } from "@dcloudio/uni-app";
import PageShell from "@/components/biz/PageShell.vue";
import BackRow from "@/components/biz/BackRow.vue";
import AppButton from "@/components/ui/AppButton.vue";
import AppChip from "@/components/ui/AppChip.vue";
import ChibiAvatar from "@/components/ui/ChibiAvatar.vue";
import NoteCard from "@/components/ui/NoteCard.vue";
import { useGameStore } from "@/stores/game";
import { useUserStore } from "@/stores/user";
import { useUiStore } from "@/stores/ui";
import { apiLiveView } from "@/api/live";
import {
  cardLiveEntry,
  isOrg,
  liveOngoing,
  MODE_NAMES,
  SCORE_RULE_NAMES,
} from "@/utils/format";
import { durTxt, isoDay, isoHm } from "@/utils/time";
import { goLive, goRecap } from "@/utils/nav";
import { gameShareUrl } from "@/utils/deeplink";
import { shareLink } from "@/utils/share";
import { buildShareCard, registerWechatShare } from "@/utils/wechatShare";
import { DEAD_LINK_MSG } from "@/utils/recap";
import { useSlowHint } from "@/composables/useSlowHint";

const store = useGameStore();
const ui = useUiStore();

const gameId = ref<number | null>(null);
const loading = ref(false);

onLoad((options) => {
  const raw = (options as Record<string, string | undefined> | undefined)?.id;
  const n = raw != null ? Number(raw) : NaN;
  gameId.value = Number.isFinite(n) ? n : null;
});

/* A2 加载：等待提示，超 2 秒提示网络问题（useSlowHint 单一源，meet 同款） */
const { slow } = useSlowHint(() => loading.value);

onShow(() => {
  if (gameId.value == null || loading.value) return;
  loading.value = true;
  store
    .loadDetail(gameId.value)
    .catch(() => undefined) // 404/断网 → 走下方说明页兜底
    .finally(() => {
      loading.value = false;
    });
});

const game = computed(() =>
  gameId.value != null && store.current?.id === gameId.value
    ? store.current
    : null,
);

/* ---- 名单派生（后端 entries 已按 formal 报名序 + 候补序排好） ---- */
const formalRows = computed(
  () => game.value?.entries?.filter((e) => e.standing === "formal") ?? [],
);
const waitlist = computed(
  () => game.value?.entries?.filter((e) => e.standing === "waitlist") ?? [],
);
/* 空降进场者（后端 detail 单独带出）：不报名不占坑，实到与摊钱都算一份，
   名单区跟在报名行后分列——只列报名行会把实到的人漏掉 */
const dropins = computed(() => game.value?.dropins ?? []);
/* 名单区右上小字：候补/空降各有才说 */
const rosterMore = computed(() =>
  [
    waitlist.value.length ? `候补 ${waitlist.value.length} 人` : "",
    dropins.value.length ? `空降 ${dropins.value.length} 人` : "",
  ]
    .filter(Boolean)
    .join(" · "),
);

const full = computed(() => !!game.value && game.value.slotsLeft <= 0);
const joined = computed(() => !!game.value?.my?.myEntry);
const org = computed(() => !!game.value && isOrg(game.value));
/* 2.5 附录A1：报名中且未定必开（未锁必打也未订场）谁都没有开账入口——组织者给指引句
   而非按钮。锁必打不动 status（games.lock 只翻 pending，截止前仍 open），后端开账闸认
   forced——open+forced 的组织者照样随时开始，指引句只压真正开不了账的局面 */
const orgGuide = computed(
  () =>
    !!game.value &&
    org.value &&
    game.value.status === "open" &&
    !game.value.forced,
);
/* 成员「进入现场」与约球页卡片同一判定源（同规矩同文案，验收红线：勿手写第二份）；
   组织者走上面三态另判，不与它混 */
const memberLiveEnter = computed(
  () => !!game.value && !org.value && !!cardLiveEntry(game.value).liveEnter,
);
/** 退局窗口：报名中随便退；锁定后仅改约解锁窗可退（4.4/4.6） */
const canQuit = computed(
  () => !!game.value && (game.value.status === "open" || game.value.unlocked),
);
const started = computed(() => !!game.value && game.value.status !== "open");
const played = computed(() => {
  const s = game.value?.status;
  return s === "live" || s === "done";
});
const reported = computed(() => game.value?.status === "done");

/* 3.3 打多久文案：endAt-startAt 现算（拨盘 5 分步进会出现 115 分钟这类；整/半小时才用小时） */
const durText = computed(() => {
  if (!game.value) return "";
  const mins = Math.max(
    0,
    Math.round(
      (new Date(game.value.endAt).getTime() -
        new Date(game.value.startAt).getTime()) /
        60000,
    ),
  );
  return durTxt(mins / 60);
});

/* 散场后的局亮实际口径：开账/散场时刻是打出来的真值，排场的 start_at/end_at
   只是计划——hero 大时刻切实际开账，时长行换「打到几点」 */
const endedLive = computed(() => {
  const g = game.value;
  return !!(g?.ended && g.liveStartedAt && g.endedAt);
});

const tBig = computed(() =>
  game.value
    ? isoHm(
        endedLive.value
          ? (game.value.liveStartedAt as string)
          : game.value.startAt,
      )
    : "",
);
const tDay = computed(() => (game.value ? isoDay(game.value.startAt) : ""));

/* 名单人数：开过账的局吃名册实到（空降/现场带人都在册），否则报名口径 */
const rosterCount = computed(
  () => game.value?.liveHeads ?? game.value?.heads ?? 0,
);

/* 微信分享卡登记：局一到手就登记，onShow 重拉详情 → watch 重触发=重登记
   （信息更新跟着换卡面）。环境判定收在 registerWechatShare 入口、make 只在
   微信内才执行——微信外整段跳过，done 局连战报视图都不白拉。done 局详情页
   手里没有场数——make 里拉一次战报视图取 matches 数，拉不到（没开过账就
   终止的局等）落「已散场 · 看看谁赢了」兜底句。取数放进 make：登记意图
   诞生即领号，onLoad+onShow 双拉并发时慢回的旧意图由模块作废，兜底句盖
   不掉真句 */
watch(
  game,
  (g) => {
    if (!g) return;
    void registerWechatShare(async () => {
      let matchCount: number | null = null;
      if (g.status === "done") {
        try {
          matchCount = (await apiLiveView(g.id)).matches.length;
        } catch {
          matchCount = null;
        }
      }
      return buildShareCard(
        {
          name: g.name,
          status: g.status,
          startAt: g.startAt,
          venueName: g.venueName,
          heads: rosterCount.value,
          matchCount,
        },
        gameShareUrl(g.id),
      );
    });
  },
  { immediate: true },
);

/* 局名首个 ' · ' 断行 */
const brandA = computed(() => {
  if (!game.value) return "";
  const i = game.value.name.indexOf(" · ");
  return i >= 0 ? game.value.name.slice(0, i) : game.value.name;
});
const brandB = computed(() => {
  if (!game.value) return "";
  const i = game.value.name.indexOf(" · ");
  return i >= 0 ? game.value.name.slice(i + 3) : "";
});

/* 人均亮数（A4：预估与实摊要分得清）：未出账=按当前名单预估标「约」；
   已出账切 bill 块实摊定值（后端定格，界面不自算） */
const perHeadTxt = computed(() => {
  const g = game.value;
  if (!g) return "";
  if (g.bill) return `¥${g.bill.perHead}`;
  return g.perHead != null ? `约 ¥${g.perHead}` : "";
});

/* 规则牌人均句：未出账=按报名人数预估；已出账切摊钱名单实数（空降/随行都
   计入）——顶层 heads 是报名口径不含空降，出账后两处人头不同源会打架 */
const rulePerTxt = computed(() => {
  const g = game.value;
  if (!g || g.perHead == null) return "";
  if (g.bill)
    return `人均＝总价 ¥${g.feeTotal} ÷ ${g.bill.heads}（按摊钱名单实摊）`;
  return `人均＝总价 ¥${g.feeTotal} ÷ ${g.heads}（按实际人数摊）`;
});

/* 人均口径提示：已出账切实摊说明；未出账费用已定=按当前人数预估（原句保持兼容）；
   费用未定时提示截止判局（4.7） */
const perNote = computed(() => {
  const g = game.value;
  if (!g) return "";
  if (g.bill) return "费用已出账 · 人均为实摊（按摊钱名单）";
  if (g.feeTotal != null) return `费用已落定 · 人均按当前 ${g.heads} 人摊`;
  if (g.heads < g.minPlayers && !g.forced)
    return `还差 ${g.minPlayers - g.heads} 人到最少 · 截止人数不足且未锁必打会自动终止`;
  return "";
});

/* 规则牌：mode 必有；得分规则仅认识 rally/serve（旧局/未知值不显示） */
const modeName = computed(() =>
  game.value ? MODE_NAMES[game.value.rotation] : "",
);
const ruleName = computed(() => {
  const r = game.value?.scoreRule;
  return r === "rally" || r === "serve" ? SCORE_RULE_NAMES[r] : "";
});

/** 响应式「我」id（名单行高亮） */
const meId = computed(() => useUserStore().me.id);

/** 分享（2026-10-12 三处统一：详情页/战报子页/现场散场门牌都发这一条详情链接，
    兜底提示走 shareLink 默认句——微信内的默认句多带「发卡片点右上角」指路；
    系统面板→复制兜底的降级链在 utils/share 单一源） */
const onShare = () => {
  if (!game.value) return; // 按钮只在 game 态渲染，这里防异步窗口错位
  void shareLink(gameShareUrl(game.value.id), game.value.name);
};
/** 查看战报（2.6 §4.2）：已散场的局亮（ended 锚存储事实），点进战报子页 */
const onRecap = () => {
  if (game.value) goRecap(game.value.id);
};
const onJoin = () => {
  if (game.value) ui.openSheet({ type: "join", gameId: game.value.id });
};
/** 加人位双角色分流：组织者开邀请抽屉、其他人开报名抽屉 */
const onSeat = () => (org.value ? onInvite() : onJoin());
const onQuit = () => {
  if (game.value) ui.openSheet({ type: "quit-confirm", gameId: game.value.id });
};
/** 锁定必打 / 订场登记（三态一入口 BookingSheet） */
const onBooking = () => {
  if (game.value) ui.openSheet({ type: "booking", gameId: game.value.id });
};
/** 补填费用（1.3 §4.5 补填形态：只填总价 + 出账确认步） */
const onBookingFee = () => {
  if (game.value)
    ui.openSheet({ type: "booking", gameId: game.value.id, feeOnly: true });
};
const onEdit = () => {
  if (game.value) ui.openSheet({ type: "launch", gameId: game.value.id });
};
const onCancel = () => {
  if (game.value)
    ui.openSheet({ type: "cancel-confirm", gameId: game.value.id });
};
const onInvite = () => {
  if (game.value)
    ui.openSheet({ type: "invite-to-game", gameId: game.value.id });
};
/** 开始打球/回现场 → 现场页（goLive 内 ensureLive 统一守门；开始与回现场同一路） */
const onLive = () => {
  if (game.value) goLive(game.value.id);
};
/** 名单球员卡 → 球友名片弹层 */
const onPlayer = (uid: number) => {
  ui.openSheet({ type: "profile", userId: uid });
};
</script>

<style lang="scss" scoped>
/* ---------- hero / kv / steps ---------- */
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
  margin-top: 10px;
}
/* 分享钮占满行（有锁定 chip 时让位收窄）；文案两态见模板注释 */
.share-btn {
  flex: 1;
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
/* 「我自己那份」小字（4.1 同款：含带来的朋友 ×N） */
.kv .kv-sub {
  font-size: 9px;
  color: var(--dim);
  margin-top: 2px;
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

/* ---------- 球员网格 ---------- */
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
/* 空降角标：与战报名单同款柠檬强调，和「随行」紫标区分 */
.pcard .tag.dropin {
  background: rgba(255, 212, 0, 0.14);
  color: var(--lemon);
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

/* ---------- 动作区（组织者按钮行 .org-row 已并入加人位） ---------- */
.actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
  flex-wrap: wrap;
}
.actions .grow {
  flex: 1;
}
/* 独占一行（订场入口）：长状态文案不再被同排挤到折行 */
.actions .full-row {
  flex-basis: 100%;
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
