<template>
  <!-- 只读回看（2.3 §4.10）：散场后扫码/从我的局点进看到的画面——战报（每片每场的
       比分与胜方）、名单（含访客挂谁名下）、考勤时刻（组织者与本人；分权在后端读链，
       view 里拿到 null 就不显示）。纯渲染：props 吃定格视图，零写按钮、零本地态——
       页面是翻旧账的，不是续摊的（写动作在 store sealGate 拒收「球局已结束」）。
       战报行积分吃 matches[].eloRows（§4.11-3 落账权威数，预览不一致时以它为准）。 -->
  <view class="recap-root">
    <!-- 「球局已结束」横幅：回看态第一眼 -->
    <view class="rp-banner">
      <view class="kicker">REPLAY · 已散场</view>
      <view class="rp-title"
        >{{ view.players.length }} 人 · {{ matchCount }} 场战报</view
      >
      <view class="rp-times">{{
        `${isoHm(view.startedAt)} 开打 · ${isoHm(view.endedAt ?? "")} 散场`
      }}</view>
    </view>

    <!-- 战报（matches 全量：片号/第几场/名单/比分/胜方/时刻/访客标识；新到旧翻） -->
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
        <!-- 落账积分（elo_rows 权威）：每人一行 ±delta；访客带标识有展示值不落账 -->
        <view v-if="m.eloRows.length" class="m-elo">
          <view v-for="(r, j) in m.eloRows" :key="j" class="e-row">
            <text class="e-nm"
              >{{ r.name
              }}<text v-if="r.guest" class="gtag">访客 · 不计积分</text></text
            >
            <text class="e-d" :class="r.delta >= 0 ? 'up' : 'dn'">{{
              r.delta >= 0 ? `+${r.delta}` : `−${Math.abs(r.delta)}`
            }}</text>
          </view>
        </view>
      </view>
    </template>
    <EmptyBox v-else text="这场没落下战报" />

    <!-- 名单（含访客挂谁名下） -->
    <view class="rp-sec-t">名单</view>
    <view v-for="p in view.players" :key="p.id" class="rp-row">
      <view class="r-nm"
        >{{ p.name }}<text v-if="p.guest" class="gtag">访客 · 不计积分</text
        ><text v-if="p.dropin" class="gtag dropin">空降</text></view
      >
      <view class="r-meta">{{ guarantorTxt(p) }}</view>
    </view>

    <!-- 考勤时刻（分权：组织者全见、本人见自己——其余人 view 里是 null，整段隐藏） -->
    <template v-if="attendRows.length">
      <view class="rp-sec-t">考勤时刻</view>
      <view v-for="r in attendRows" :key="r.id" class="rp-row">
        <view class="r-nm">{{ r.name }}</view>
        <view class="r-meta att">
          <text class="t">到 {{ isoHmOrDash(r.arriveAt) }}</text>
          <text class="t">走 {{ isoHmOrDash(r.leftAt) }}</text>
        </view>
      </view>
    </template>

    <view class="rp-foot">球局已结束 · 只读回看</view>
  </view>
</template>

<script setup lang="ts">
/* 回看视图纯渲染（2.3 §4.10）：props 吃 LiveView 定格视图（ensureLive endedAt 分流 /
   endGame 响应落地两路同源），无本地态无写动作。访客标识与预览行同款口径
   （MatchPerson.guest / EloRow.guest）；担保人按 guarantorAccountId 对回名册行解析。 */
import { computed } from "vue";
import EmptyBox from "@/components/ui/EmptyBox.vue";
import { isoHm, isoHmOrDash } from "@/utils/time";
import type { LivePlayer, LiveView, MatchPerson } from "@/api/types";

const props = defineProps({
  view: { type: Object as () => LiveView, required: true },
});

const matchCount = computed(() => props.view.matches.length);
/** 旧到新落账、回看新到旧翻（与 history/feed 的「新到旧」同一观感） */
const matchesDesc = computed(() => [...props.view.matches].reverse());

/** 一侧名单：胜方/败方从快照取（落账定格事实，join 名册反而要二次查） */
function names(
  winners: MatchPerson[],
  losers: MatchPerson[],
  winSide: boolean,
): string {
  const rows = winSide ? winners : losers;
  return rows.map((p) => p.name).join(" / ") || "—";
}

/** 访客挂谁名下（§4.10 名单含访客挂谁名下）；正式球友带出场状态句 */
function guarantorTxt(p: LivePlayer): string {
  if (p.guarantorAccountId != null) {
    const g = props.view.players.find(
      (x) => x.accountId === p.guarantorAccountId,
    );
    return g ? `${g.name} 带的访客` : "随行访客";
  }
  if (p.check === "absent") return "未到场";
  if (p.check === "left") return "早退";
  return "";
}

/** 考勤时刻区（有值才显示：view 分权后普通人拿不到别人的时刻） */
const attendRows = computed(() =>
  props.view.players.filter((p) => p.arriveAt || p.leftAt),
);
</script>

<style lang="scss" scoped>
/* 回看态整页滚动（PageShell bare 壳：自补顶距 + 让出公共导航高度） */
.recap-root {
  height: calc(100vh - var(--nav-total-h));
  overflow-y: auto;
  padding: calc(env(safe-area-inset-top) + 14px) 18px 24px;
}
.rp-banner {
  border: 1px solid rgba(255, 212, 0, 0.25);
  border-radius: var(--r-md);
  background: linear-gradient(160deg, var(--ink3), var(--ink2));
  padding: 14px 16px;
  margin-bottom: 18px;
}
.kicker {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.3em;
  text-transform: uppercase;
  color: var(--dim);
}
.rp-title {
  font-family: var(--disp);
  font-size: 22px;
  margin: 6px 0 2px;
}
.rp-times {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  letter-spacing: 0.08em;
}
.rp-sec-t {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--dim);
  margin: 16px 0 8px;
}
/* 战报卡：卡头（片号·场次+时刻）→ A/B 两队与大比分 → 落账积分行 */
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
/* 落账积分行（elo_rows）：访客行带「不计积分」标识、delta 照显（展示值） */
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
/* 名单/考勤行（LedgerSheet 行构同族，tokens 换过） */
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
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  letter-spacing: 0.06em;
  flex: none;
}
.r-meta.att {
  display: flex;
  gap: 10px;
}
/* 徽章（与 EndSettleModal 预览行同款 gtag 语言） */
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
  text-align: center;
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  letter-spacing: 0.14em;
  margin-top: 18px;
  opacity: 0.7;
}
</style>
