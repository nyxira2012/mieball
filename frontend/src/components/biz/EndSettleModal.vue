<template>
  <!-- 本地结算窗（2.3 记分本地化重造）：开关/片/模式单一源=store.settleWindow（直读，
       一次一扇，页面不再透传 visible/courtId）。upload=上传结算（谁都能传，后端把关
       到场者）：比分起点吃本机账 localScores[courtId]（不再吃视图比分——服务端不记
       进行中比分）；overwrite=改分重落（全权闸在 store.overwriteSettle）：预填该片
       最新落账 match 的比分胜方（视图 matches 按 courtNo 找最新行）。
       两队名单吃视图 players（courtNo/courtSide）。±积分预演读视图 elo_preview 双分支
       （批1 起挂 playing 片：A 胜/B 胜两套数随画面给、与落账同一条公式路——预演即
       落账）：点胜方在两套现成数间切换，仍当场变不等网络；访客行带「不计积分」标识
       （1.4 §4 不落账不进榜）。球友可操作（上传权=任意到场者）：全权只读态与
       「请组织者或管理员确认」旁注已删。
       「暂不结算」=closeSettleWindow 保本地分接着打（P2-2，唯一非上传出口）；输入格
       纠偏 upload 模式当场写回本机账——暂不结算后场卡接着打的就是纠偏后的分。
       一步展示（结算一步到位）：上传成功窗不关、内容切「下一场对阵+候场名单」只读
       态（done 旗在 store 窗位），数据从落地后的最新视图取（刚发的片=courts 同片号
       行、候场=queue 映射昵称）；片没开出（人少兜底）摆差人句不硬造对阵；「好的」
       关闭、下一场到分开新窗直接顶掉展示窗。改分重落不转展示（它重写的是上一场，
       轮转不动），照旧落账关窗。
       比分格数字直录替 ±（2026-10-11 裁决：不逐分记的人 0:0 起步连点不友好；
       空=0、只拦非负整数不卡上限）。窗内「撤一分」已删（P2-1）：撤分唯一入口=场卡。
       z-110 fixed 居中；遮罩不可关（旧裁决仍成立——关窗会丢待上传的账；遮罩纯视觉
       背板无点击事件），非上传出口只有「暂不结算」。 -->
  <view class="mwrap" :class="{ on: win != null }">
    <view class="mmask" />
    <view class="modal">
      <!-- ── 一步展示态（上传成功后 store 窗位翻 done）── -->
      <template v-if="done">
        <view class="md-kick">NEXT · {{ courtName }}</view>
        <view class="md-title">下一场<text class="bem">已排好</text></view>
        <view v-if="courtPlaying" class="nx-court">
          <view class="nx-side">
            <text class="nx-t a">TEAM A</text>
            <text class="nx-n">{{ namesA }}</text>
          </view>
          <view class="nx-vs">VS</view>
          <view class="nx-side">
            <text class="nx-t b">TEAM B</text>
            <text class="nx-n">{{ namesB }}</text>
          </view>
        </view>
        <view v-else class="nx-idle">{{ idleTxt }}</view>
        <view class="nx-queue">
          <text class="nx-qt">候场</text>
          <text class="nx-qn">{{ queueNames || "全员都在场上" }}</text>
        </view>
        <view class="md-btns">
          <AppButton variant="pri" block @click="liveStore.closeSettleWindow()"
            >好的</AppButton
          >
        </view>
      </template>

      <!-- ── 表单态（上传 / 改分重落）── -->
      <template v-else>
        <view class="md-kick">{{ kick }}</view>
        <view class="md-title">
          {{ mode === "overwrite" ? "改分" : "上传"
          }}<text class="bem">{{
            mode === "overwrite" ? "重落" : "比分"
          }}</text>
        </view>
        <view v-if="mode === 'overwrite'" class="md-mode-tip"
          >把这场已落的账按新分重写 · 积分重算</view
        >

        <!-- 胜方点选：A 柠檬 / B 冰蓝；分低方选不中（§4.6） -->
        <view class="win-pick">
          <view
            class="wp a"
            :class="{ on: winA === true, off: !canA }"
            @click="pick('a')"
          >
            <view class="t">TEAM A</view>
            <view class="n">{{ namesA }}</view>
          </view>
          <view
            class="wp b"
            :class="{ on: winA === false, off: !canB }"
            @click="pick('b')"
          >
            <view class="t">TEAM B</view>
            <view class="n">{{ namesB }}</view>
          </view>
        </view>

        <!-- 大比分输入格：空视同 0、失焦归一 -->
        <view class="md-score">
          <input
            class="num a"
            :value="saText"
            type="number"
            @input="onScore('a', $event)"
            @blur="onBlurScore('a')"
          />
          <view class="c">:</view>
          <input
            class="num b"
            :value="sbText"
            type="number"
            @input="onScore('b', $event)"
            @blur="onBlurScore('b')"
          />
        </view>
        <view class="md-tools">
          <text class="edit">点比分格 · 直接输数字</text>
        </view>

        <!-- ±积分预览（胜队在前；平分未点胜方时不显示）；访客带「不计积分」标识 -->
        <view v-for="(r, i) in preview" :key="i" class="elo-row">
          <text class="nm"
            >{{ r.name
            }}<text v-if="r.guest" class="gtag">访客 · 不计积分</text></text
          >
          <text class="d" :class="r.up ? 'up' : 'dn'">{{
            r.up ? `+${r.d}` : `−${Math.abs(r.d)}`
          }}</text>
        </view>
        <view class="md-note">±积分为结算预演 · 确认后落账生效</view>

        <view class="md-btns">
          <AppButton
            variant="pri"
            block
            :disabled="!canConfirm"
            @click="onConfirm"
            >{{
              mode === "overwrite" ? "确认改分 · 重落这场" : "确认上传 · 落账"
            }}</AppButton
          >
          <view v-if="winA === null" class="md-full-tip"
            >平分不分胜负 · 先点胜方</view
          >
          <!-- 唯一非上传出口（P2-2）：关窗不丢本机账，回场卡接着打 -->
          <AppButton
            variant="ghost"
            block
            @click="liveStore.closeSettleWindow()"
            >暂不结算 · 接着打</AppButton
          >
        </view>
      </template>
    </view>
  </view>
</template>

<script setup lang="ts">
/* 本地结算窗呈现与联动（2.3 记分本地化；编排归 store）：本地态只有 winA/sa/sb——
   比分直录交互单一源在 composables/scoreEntry（开窗按模式预填、确认直调 store：
   uploadSettle/overwriteSettle 落账·关窗·toast 都在 store；清扫态 noRedeal
   随 settleWindow 透传）。上传成功窗转一步展示（done 旗在 store 窗位）：
   下一场对阵+候场名单从最新视图取，「好的」关闭——表单态交互零改。
   联动纯函数（followWinner/canPickWinner）单一源在 utils/rotate（store 转出口），
   测试落 live-store.test.ts。上传权=任意到场者（后端 _require_arrived 把关）：
   窗内无全权只读态；改分重落全权闸在 store.overwriteSettle（needFull）。 */
import { computed } from "vue";
import AppButton from "@/components/ui/AppButton.vue";
import {
  courtNoOf,
  followWinner,
  latestMatchOf,
  useLiveStore,
} from "@/stores/live";
import { courtDisplayName } from "@/utils/format";
import { courtSize, idleHint } from "@/utils/rotate";
import { useScoreEntry } from "@/composables/scoreEntry";
import type { LivePlayer } from "@/api/types";

const liveStore = useLiveStore();

/** 窗位单一源在 store（一次一扇；visible/courtId/mode/noRedeal 全由它驱动） */
const win = computed(() => liveStore.settleWindow);
const mode = computed(() => win.value?.mode ?? "upload");
/** 一步展示态：上传成功后窗不关、内容切「下一场对阵+候场名单」（数据吃落地后的
    最新视图——namesA/namesB/courtRow 按同一 courtId 取到的就是刚发的片与新人） */
const done = computed(() => !!win.value?.done);
/** 这片开出没有：没开出（人少兜底）摆差人句不硬造对阵 */
const courtPlaying = computed(() => courtRow.value?.status === "playing");
/** 候场名单（queue 序映射昵称；空队=全员都在场上，与队列抽屉空态同句） */
const queueNames = computed(() =>
  (liveStore.live?.queue ?? []).map((id) => liveStore.byId(id).name).join("、"),
);
const idleTxt = computed(() =>
  idleHint(
    liveStore.live?.queue.length ?? 0,
    courtSize(liveStore.live?.rules.singles ?? false),
  ),
);
const kick = computed(
  () =>
    `${mode.value === "overwrite" ? "REWRITE" : "SETTLE"} · ${courtName.value}`,
);

/** 当前结算窗这片在视图里的片号（courtNoOf(win.courtId) 三处共用单一源） */
const winCourtNo = computed(() => courtNoOf(win.value?.courtId ?? -1));

/** 这片的视图行（elo_preview 双支）与两队名单（视图单一源） */
const courtRow = computed(() =>
  liveStore.liveView?.courts.find((c) => c.courtNo === winCourtNo.value),
);
function sideRows(side: "a" | "b"): LivePlayer[] {
  const no = winCourtNo.value;
  return (
    liveStore.liveView?.players.filter(
      (p) => p.courtNo === no && p.courtSide === side,
    ) ?? []
  );
}

const courtName = computed(() =>
  courtDisplayName(
    liveStore.live?.courts.find((c) => c.id === win.value?.courtId)?.name ?? "",
  ),
);
const namesA = computed(() =>
  sideRows("a")
    .map((p) => p.name)
    .join(" / "),
);
const namesB = computed(() =>
  sideRows("b")
    .map((p) => p.name)
    .join(" / "),
);

/* 比分直录交互单一源（沙盒 SandboxSettle 同吃）。开窗预填按模式：overwrite 吃
   该片最新落账 match（latestMatchOf 单一源，场卡「上一场 · 改分」链接同一真值；
   该片还没落过账——正常开不到这个模式——回落 0:0 不预选）；upload 吃本机账、
   胜方预选=分高方。直录写回只在 upload 模式（改分只动本地，落账即覆盖） */
const {
  winA,
  saText,
  sbText,
  sa,
  sb,
  canA,
  canB,
  canConfirm,
  pick,
  onScore,
  onBlurScore,
} = useScoreEntry(
  win,
  () => {
    const w = win.value;
    if (w?.mode === "overwrite") {
      const m = latestMatchOf(liveStore.liveView, winCourtNo.value);
      return { sa: m?.sa ?? 0, sb: m?.sb ?? 0, winA: m ? m.winA : null };
    }
    const acc = liveStore.localScores[w?.courtId ?? -1];
    return {
      sa: acc?.sa ?? 0,
      sb: acc?.sb ?? 0,
      winA: followWinner(acc?.sa ?? 0, acc?.sb ?? 0),
    };
  },
  (sa2, sb2) => {
    const w = win.value;
    if (w?.mode === "upload") liveStore.setLocalScore(w.courtId, sa2, sb2);
  },
);

/** ±积分预演：读视图 elo_preview 双分支——后端 _elo_settle 同一条路算好随画面给
    （批1 起挂 playing 片，A 胜/B 胜各一套，胜队在前），预演=落账；点胜方只是切换分支 */
const preview = computed(() => {
  if (winA.value === null) return [];
  const rows = courtRow.value?.eloPreview?.[winA.value ? "a" : "b"] ?? [];
  return rows.map((r) => ({
    name: r.name,
    guest: r.guest,
    up: r.delta > 0,
    d: r.delta,
  }));
});

function onConfirm(): void {
  const w = win.value;
  if (!w || winA.value === null) return;
  if (w.mode === "overwrite")
    void liveStore.overwriteSettle(w.courtId, winA.value, sa.value, sb.value);
  else
    void liveStore.uploadSettle(
      w.courtId,
      winA.value,
      sa.value,
      sb.value,
      w.noRedeal,
    );
}
</script>

<style lang="scss" scoped>
/* z-110（AppSheet 90 之上；confetti 115 / toast 120 仍在其上）。原型用 class 切换 + transition
   （animations.scss 的 pop keyframes 可用，但原型本体即 transition 方案，逐字从原型） */
.mwrap {
  position: fixed;
  inset: 0;
  z-index: 110;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  pointer-events: none; /* 关窗态不挡页面；on 态整层可点（窗内操作；遮罩纯视觉不可关窗） */
}
.mwrap.on {
  pointer-events: auto;
}
.mmask {
  position: absolute;
  inset: 0;
  background: rgba(8, 8, 11, 0.72);
  backdrop-filter: blur(3px);
  /* 关窗态必须连 visibility 一起收：backdrop-filter 对 opacity:0 的元素照样生效，
     只切透明度会把整页常驻压糊（走查实录：mmask 漏收 → 全屏发糊） */
  opacity: 0;
  visibility: hidden;
  transition:
    opacity 0.22s,
    visibility 0.22s;
}
.mwrap.on .mmask {
  opacity: 1;
  visibility: visible;
}
.modal {
  position: relative;
  width: 82%;
  max-width: 330px;
  background: linear-gradient(180deg, var(--ink3), var(--ink2));
  border: 1px solid rgba(255, 212, 0, 0.25);
  border-radius: var(--r-lg);
  padding: 20px 16px 16px;
  transform: scale(0.94);
  opacity: 0;
  transition: 0.22s;
  pointer-events: none;
}
.mwrap.on .modal {
  transform: scale(1);
  opacity: 1;
  pointer-events: auto;
}
.md-kick {
  text-align: center;
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.34em;
  color: var(--dim);
  text-transform: uppercase;
}
.md-title {
  text-align: center;
  font-family: var(--disp);
  font-size: 24px;
  margin: 6px 0 14px;
}
.md-title .bem {
  color: var(--lemon);
}
/* overwrite 模式的后果句（upload 无此行）：贴在标题下、胜方点选上 */
.md-mode-tip {
  text-align: center;
  font-size: 11px;
  color: var(--dim);
  margin: -6px 0 12px;
}

/* ---------- 胜方二选一 ---------- */
.win-pick {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.wp {
  flex: 1;
  text-align: center;
  border: 1px solid rgba(245, 241, 232, 0.16);
  border-radius: 13px;
  background: var(--ink);
  padding: 10px 4px;
  cursor: pointer;
  transition: 0.15s;
  min-width: 0;
}
.wp .t {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.18em;
  color: var(--dim);
}
.wp .n {
  font-size: 12px;
  font-weight: 700;
  margin-top: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.wp.on {
  border-color: var(--lemon);
  background: rgba(255, 212, 0, 0.08);
}
.wp.on .t {
  color: var(--lemon);
}
.wp.b.on {
  border-color: var(--ice);
  background: rgba(111, 231, 255, 0.08);
}
.wp.b.on .t {
  color: var(--ice);
}
/* 分低方选不中（§4.6）：置灰不可点，预选高亮仍可见 */
.wp.off {
  opacity: 0.45;
  pointer-events: none;
}

/* ---------- 大比分输入格 ---------- */
.md-score {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  margin: 4px 0 10px;
}
/* 显式定高必须：uni-input 内层 wrapper 恒为宿主内容区 100%，宿主无高有值即塌 0
   （AppInput 同坑注） */
.md-score .num {
  width: 88px;
  height: 68px;
  border: 1px solid rgba(245, 241, 232, 0.16);
  border-radius: 13px;
  background: var(--ink);
  text-align: center;
  font-family: var(--disp);
  font-size: 40px;
  color: var(--cream);
}
.md-score .num.a {
  color: var(--lemon);
}
.md-score .num.b {
  color: var(--ice);
}
.md-score .c {
  font-family: var(--disp);
  font-size: 22px;
  color: var(--coral);
}
/* 比分注 */
.md-tools {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
}
.edit {
  font-size: 11px;
  color: var(--dim);
}

/* ---------- ±积分预览行 ---------- */
.elo-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid rgba(245, 241, 232, 0.08);
  border-radius: 12px;
  background: var(--ink2);
  margin-bottom: 6px;
}
.elo-row .nm {
  flex: 1;
  font-size: 12px;
  font-weight: 600;
}
.elo-row .gtag {
  margin-left: 6px;
  font-family: var(--mono);
  font-size: 9px;
  font-weight: 400;
  color: var(--lilac);
}
.elo-row .d {
  font-family: var(--mono);
  font-size: 13px;
  font-weight: 700;
}
.elo-row .d.up {
  color: var(--lemon);
}
.elo-row .d.dn {
  color: var(--coral);
}
.md-note {
  text-align: center;
  font-size: 10px;
  color: var(--dim);
  margin: 8px 0 12px;
}

/* ---------- 一步展示（上传成功后的只读态） ---------- */
.nx-court {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.nx-side {
  flex: 1;
  min-width: 0;
  text-align: center;
  border: 1px solid rgba(245, 241, 232, 0.16);
  border-radius: 13px;
  background: var(--ink);
  padding: 10px 6px;
}
.nx-t {
  display: block;
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.18em;
}
.nx-t.a {
  color: var(--lemon);
}
.nx-t.b {
  color: var(--ice);
}
.nx-n {
  display: block;
  font-size: 12px;
  font-weight: 700;
  margin-top: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.nx-vs {
  flex: none;
  font-family: var(--disp);
  font-size: 18px;
  color: var(--coral);
}
/* 片没开出（人少兜底）：一句差人卡同款句交代，不硬摆对阵 */
.nx-idle {
  text-align: center;
  font-size: 13px;
  font-weight: 600;
  padding: 16px 0;
  margin-bottom: 12px;
  border: 1px dashed rgba(245, 241, 232, 0.2);
  border-radius: 13px;
}
.nx-queue {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 9px 10px;
  border: 1px solid rgba(245, 241, 232, 0.08);
  border-radius: 12px;
  background: var(--ink2);
  margin-bottom: 12px;
}
.nx-qt {
  flex: none;
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.18em;
  color: var(--dim);
}
.nx-qn {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  font-weight: 600;
}

/* ---------- 按钮 ---------- */
.md-btns {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.md-full-tip {
  text-align: center;
  font-size: 11px;
  color: var(--dim);
}
</style>
