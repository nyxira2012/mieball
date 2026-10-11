<template>
  <!-- 只读回看（2.3 §4.10）：散场后扫码/从记录点进——战报/名单/考勤（分权在后端读链，
       view 里 null 就不显），纯渲染零写动作（写了 store sealGate 也拒收「球局已结束」）。
       2026-10-12 UI 修订（2.6 §8）：海报头主视觉=梗句封面（MemeHeadline 吃上过场
       昵称随机定格，用户拍板）；「已结束」全页只说一遍（REPLAY + 已散场戳）；完成/
       分享为动作行正常按钮、只 emit 不执行——编排归页面；去向提示行只给现场门牌·
       这局的人（door prop）；知情小字随分享降级走不常驻（shareLink copyMsg）；
       名单行全场 ±分=eloTotals 加总落账行；页脚出路钮 emit meet。 -->
  <view class="recap-root">
    <view class="rp-banner">
      <view class="rp-kick">
        <text class="kick-txt">REPLAY</text>
        <text class="rp-stamp">已散场</text>
      </view>
      <view class="rp-hero">
        <MemeHeadline :names="playedNames" />
      </view>
      <view class="rp-meta">{{
        `${view.players.length} 人 · ${matchCount} 场 · ${isoHm(view.startedAt)} — ${isoHm(view.endedAt ?? "")}`
      }}</view>
      <view v-if="showHint" class="rp-hint">▸ {{ RECAP_HINT }}</view>
      <view class="rp-actions">
        <AppButton
          variant="ghost"
          size="sm"
          class="flex1"
          @click="emit('complete')"
          >完成</AppButton
        >
        <AppButton variant="pri" size="sm" class="flex1" @click="emit('share')"
          >分享</AppButton
        >
      </view>
    </view>

    <!-- 战报（全量：片号/场次/名单/比分/胜方/时刻；新到旧翻） -->
    <view class="rp-sec-t">战报</view>
    <template v-if="matchCount">
      <view v-for="(m, i) in matchesDesc" :key="i" class="rp-match">
        <view class="m-head">
          <text class="m-court">{{ m.courtNo }}号 · 第{{ m.seq }}场</text>
          <text class="m-time">{{ isoHm(m.endedAt) }}</text>
        </view>
        <view class="m-score">
          <view class="m-team" :class="{ win: m.winA }">
            <text class="side">A</text>
            <text class="names">{{ names(m.winners, m.losers, true) }}</text>
          </view>
          <view class="m-num" :class="{ a: m.winA }"
            >{{ m.sa }} : {{ m.sb }}</view
          >
          <view class="m-team right" :class="{ win: !m.winA }">
            <text class="names">{{ names(m.winners, m.losers, false) }}</text>
            <text class="side">B</text>
          </view>
        </view>
        <!-- 落账积分（eloRows 权威）：访客有展示值不落账，带标识 -->
        <view v-if="m.eloRows.length" class="m-elo">
          <view v-for="(r, j) in m.eloRows" :key="j" class="e-row">
            <text class="e-nm"
              >{{ r.name
              }}<text v-if="r.guest" class="gtag">访客 · 不计积分</text></text
            >
            <text class="e-d" :class="r.delta >= 0 ? 'up' : 'dn'">{{
              fmtDelta(r.delta)
            }}</text>
          </view>
        </view>
      </view>
    </template>
    <EmptyBox v-else text="这场没落下战报" />

    <!-- 名单（含访客挂谁名下；注册球员行尾全场 ±合计，没上过场/访客不显） -->
    <view class="rp-sec-t">名单</view>
    <view v-for="row in rosterRows" :key="row.p.id" class="rp-row">
      <view class="r-nm"
        >{{ row.p.name
        }}<text v-if="row.p.guest" class="gtag">访客 · 不计积分</text
        ><text v-if="row.p.dropin" class="gtag dropin">空降</text></view
      >
      <view class="r-meta">
        <text v-if="row.eloTxt" class="r-elo" :class="row.eloCls">{{
          row.eloTxt
        }}</text>
        <text v-if="row.meta">{{ row.meta }}</text>
      </view>
    </view>

    <!-- 考勤时刻（分权：组织者全见、本人见自己——其余 null 整段隐藏） -->
    <template v-if="attendRows.length">
      <view class="rp-sec-t">考勤时刻</view>
      <view v-for="r in attendRows" :key="r.id" class="rp-row">
        <view class="r-nm">{{ r.name }}</view>
        <view class="r-meta">
          <text class="t">到 {{ isoHmOrDash(r.arriveAt) }}</text>
          <text class="t">走 {{ isoHmOrDash(r.leftAt) }}</text>
        </view>
      </view>
    </template>

    <!-- 出路钮换旧「球局已结束 · 只读回看」（无信息量，kicker 已说清） -->
    <view class="rp-foot">
      <AppButton variant="pri" block @click="emit('meet')"
        >来约场球吧</AppButton
      >
    </view>
  </view>
</template>

<script setup lang="ts">
/* 回看视图纯渲染（2.3 §4.10）：props 吃 LiveView 定格视图，零本地态零写动作；
   名单全场 ±分吃 utils/recap.eloTotals（落账行加总不重算）。 */
import { computed, type PropType } from "vue";
import AppButton from "@/components/ui/AppButton.vue";
import EmptyBox from "@/components/ui/EmptyBox.vue";
import MemeHeadline from "@/components/biz/MemeHeadline.vue";
import { isoHm, isoHmOrDash } from "@/utils/time";
import { RECAP_HINT, eloTotals } from "@/utils/recap";
import type { LivePlayer, LiveView, MatchPerson } from "@/api/types";

const props = defineProps({
  view: { type: Object as () => LiveView, required: true },
  /** 门牌：live=现场格（提示行只在这门给）、page=战报子页（从记录进来，指路绕圈不给） */
  door: { type: String as PropType<"live" | "page">, default: "live" },
});

/** 只上报意图不执行（complete 现场门牌=收摊/子页=返回）——编排归页面，这里零逻辑 */
const emit = defineEmits<{ complete: []; share: []; meet: [] }>();

const matchCount = computed(() => props.view.matches.length);
/** 旧到新落账、回看新到旧翻（与 history/feed 同一观感） */
const matchesDesc = computed(() => [...props.view.matches].reverse());

/** 去向提示行只给现场门牌·这局的人（is_my_game 后端定值，前端不自判） */
const showHint = computed(() => props.door === "live" && props.view.isMyGame);

/** 梗句候选=上过场的昵称（落账快照收名；去重与剔除归 pickMeme） */
const playedNames = computed(() =>
  props.view.matches.flatMap((m) =>
    [...m.winners, ...m.losers].map((p) => p.name),
  ),
);

/** 名单行拼装：状态句 + 全场 ±分（访客关联不了名册行——同名会串且不落账；没上过场查无） */
const rosterRows = computed(() => {
  const totals = eloTotals(props.view.matches);
  return props.view.players.map((p) => {
    const elo = p.accountId != null ? totals.get(p.accountId) : undefined;
    return {
      p,
      meta: guarantorTxt(p),
      eloTxt: elo !== undefined ? fmtDelta(elo) : "",
      eloCls: elo == null ? "" : elo > 0 ? "up" : elo < 0 ? "dn" : "",
    };
  });
});

/** ±分统一格式（战报行与名单行同一副面孔） */
function fmtDelta(d: number): string {
  return d > 0 ? `+${d}` : d < 0 ? `−${Math.abs(d)}` : "±0";
}

/** 一侧名单：胜方/败方从快照取（落账定格事实，join 名册反而要二次查） */
function names(
  winners: MatchPerson[],
  losers: MatchPerson[],
  winSide: boolean,
): string {
  const rows = winSide ? winners : losers;
  return rows.map((p) => p.name).join(" / ") || "—";
}

/** 访客挂谁名下（§4.10）；正式球友带出场状态句 */
function guarantorTxt(p: LivePlayer): string {
  if (p.guarantorAccountId != null) {
    const g = props.view.players.find(
      (x) => x.accountId === p.guarantorAccountId,
    );
    return g ? `${g.name} 带的访客` : "随行访客";
  }
  if (p.check === "absent") return "未到场";
  if (p.check === "left") return "先走了";
  return "";
}

const attendRows = computed(() =>
  props.view.players.filter((p) => p.arriveAt || p.leftAt),
);
</script>

<style lang="scss" scoped>
/* 回看态整页滚动（PageShell bare 壳：自补顶距 + 让出公共导航高度）；
   dvh 口径同 live 页（100vh 与 fixed 导航在手机动态工具栏下错位，旧内核回退 100vh 行） */
.recap-root {
  height: calc(100vh - var(--nav-total-h));
  height: calc(100dvh - var(--nav-total-h));
  overflow-y: auto;
  padding: calc(env(safe-area-inset-top) + 14px) 18px 24px;
}
/* 海报头（梗句封面做主视觉——MemeHeadline 随机定格；记分横幅顶线 + 斜纹纸纹打底，
   右上歪斜橡皮戳「已散场」——定格旧账的签名件） */
.rp-banner {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(255, 212, 0, 0.22);
  border-radius: var(--r-md);
  background:
    repeating-linear-gradient(
      135deg,
      rgba(255, 212, 0, 0.035) 0 1px,
      transparent 1px 14px
    ),
    linear-gradient(160deg, var(--ink3), var(--ink2));
  box-shadow: inset 0 2px 0 rgba(255, 212, 0, 0.4);
  padding: 14px 16px;
  margin-bottom: 18px;
}
.rp-kick {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.kick-txt {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.34em;
  text-transform: uppercase;
  color: var(--dim);
}
.rp-stamp {
  transform: rotate(-6deg);
  border: 1.5px solid rgba(255, 212, 0, 0.85);
  border-radius: 7px;
  padding: 3px 8px 3px 10px;
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  color: var(--lemon);
  box-shadow:
    0 0 0 3px rgba(255, 212, 0, 0.1),
    inset 0 0 10px rgba(255, 212, 0, 0.08);
}
.rp-hero {
  margin: 12px 0 8px;
}
.rp-meta {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  letter-spacing: 0.08em;
}
.rp-hint {
  display: inline-block;
  margin-top: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(255, 212, 0, 0.1);
  font-size: 11px;
  font-weight: 600;
  color: var(--lemon);
}
.rp-actions {
  display: flex;
  gap: 10px;
  margin-top: 14px;
}
.flex1 {
  flex: 1;
}
.rp-sec-t {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--dim);
  margin: 16px 0 8px;
}
.rp-match {
  border: 1px solid rgba(245, 241, 232, 0.08);
  border-radius: 12px;
  background: var(--ink2);
  padding: 10px 12px;
  margin-bottom: 8px;
}
.m-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.m-court {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  color: var(--lemon);
}
.m-time {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
}
.m-score {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 8px 0 4px;
}
.m-team {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  opacity: 0.75;
}
.m-team.right {
  justify-content: flex-end;
}
.m-team.win {
  opacity: 1;
}
.m-team .side {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
  flex: none;
}
.m-team .names {
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.m-team.win .names {
  color: var(--lemon);
}
.m-num {
  flex: none;
  font-family: var(--disp);
  font-size: 24px;
  color: var(--cream);
}
.m-num.a {
  color: var(--lemon);
}
.m-elo {
  border-top: 1px dashed rgba(245, 241, 232, 0.12);
  margin-top: 6px;
  padding-top: 6px;
}
.e-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2px 0;
}
.e-nm {
  font-size: 11px;
  color: var(--cream);
}
.e-d {
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 700;
}
.e-d.up {
  color: var(--lemon);
}
.e-d.dn {
  color: var(--coral);
}
.rp-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 9px 10px;
  border-radius: 12px;
  margin-bottom: 6px;
  border: 1px solid rgba(245, 241, 232, 0.08);
  background: var(--ink2);
}
.r-nm {
  font-size: 13px;
  font-weight: 600;
  min-width: 0;
}
.r-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: none;
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  letter-spacing: 0.06em;
}
.r-elo {
  font-size: 11px;
  font-weight: 700;
  color: var(--dim);
}
.r-elo.up {
  color: var(--lemon);
}
.r-elo.dn {
  color: var(--coral);
}
.gtag {
  margin-left: 6px;
  font-family: var(--mono);
  font-size: 9px;
  font-weight: 400;
  color: var(--lilac);
}
.gtag.dropin {
  color: var(--ice);
}
.rp-foot {
  margin: 22px 4px 6px;
}
</style>
