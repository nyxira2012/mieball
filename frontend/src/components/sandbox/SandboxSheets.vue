<template>
  <!-- 沙盒抽屉族（2.7 批4）：真局 CheckinSheet/PersonSheet/RulesSheet/SweepSheet 的
       沙盒复刻——行为一致+长相接近，数据全吃 sandbox store（真局组件零改动、深耦合
       live store 的写动作在这里换成 engine 动作）。开关单槽在 store.sheetKind
       （真局 liveSheet 同语义），权限随卡走的拦下与提示都在 store 闸单点。
       复刻取舍（规格没写的不加）：签到抽屉只教待签+带访客（人数/介绍人不进教学）、
       点人抽屉无战力档案（假人无档案 §4.4）、规则抽屉只教分制（轮换四件套教学局
       锁定只读）、散场清单行内只有取消（上传比分不教——组织卡走「本场完成」），
       收工账单做在本抽屉的 ended 态（规格 4.3 第十步）。 -->
  <view>
    <!-- ---------- 签到 · 到场（组织卡第三/四步） ---------- -->
    <AppSheet
      :visible="sandbox.sheetKind === 'checkin'"
      title="签到 · 到场"
      hint="来没来、几点走，清清楚楚"
      @close="sandbox.closeSheet()"
    >
      <view class="sb-cksec">
        <view class="sb-ckt">还没到的</view>
        <template v-if="absents.length">
          <view v-for="row in absents" :key="row.id" class="sb-ckrow dim">
            <view class="sb-rav"
              ><ChibiAvatar :chibi="row.chibi" :size="30"
            /></view>
            <view class="sb-who">
              <view class="sb-nm"
                >{{ row.name
                }}<text v-if="row.admin" class="badge admin nm-badge"
                  >管理员</text
                ></view
              >
              <view class="sb-st late">未到</view>
            </view>
            <view class="sb-acts">
              <AppButton
                variant="pri"
                size="sm"
                @click="sandbox.checkInRow(row.id)"
                >到场</AppButton
              >
            </view>
          </view>
        </template>
        <EmptyBox v-else text="都到齐了" />
      </view>

      <!-- 光圈锚 bring-guest（组织卡第 4 步）：套住整个带访客区块（标题+称呼+带上） -->
      <view
        class="sb-cksec"
        :class="{ 'sb-glow': sandbox.spot === 'bring-guest' }"
      >
        <view class="sb-ckt">带访客</view>
        <view class="sb-ckin">
          <AppInput v-model="gName" placeholder="访客称呼" />
        </view>
        <AppButton variant="pri" block @click="onBring">带上</AppButton>
      </view>

      <NoteCard>
        <text class="sb-nk">空降的人不用学：</text>没报名的直接扫场上二维码 →
        填个称呼就进局打球——费用照常摊。
      </NoteCard>
    </AppSheet>

    <!-- ---------- 点人（两卡通用：歇/连/退场/换人二段/设管理员） ---------- -->
    <AppSheet
      :visible="sandbox.sheetKind === 'person'"
      @close="sandbox.closeSheet()"
    >
      <template v-if="p">
        <!-- 常规态 -->
        <template v-if="!sandbox.personSwap">
          <view class="sb-pshead">
            <view class="sb-psav"
              ><ChibiAvatar :chibi="p.chibi" :size="44"
            /></view>
            <view class="sb-psmeta">
              <view class="sb-psnm"
                >{{ p.name }}<text v-if="p.you" class="sb-mebadge">我</text
                ><text v-if="p.admin" class="badge admin nm-badge"
                  >管理员</text
                ></view
              >
              <view v-if="p.guest" class="sb-pssub">访客 · 不计积分</view>
            </view>
          </view>
          <view class="sb-psgrid">
            <view class="sb-psact" @click="sandbox.setSwapMode(true)"
              >换人</view
            >
            <view
              class="sb-psact"
              :class="{ 'on-rest': !!p.skip }"
              @click="sandbox.tempo(p.id, 'skip')"
              >{{ p.skip ? `再歇一轮 · 将跳 ${p.skip} 轮` : "休息一轮" }}</view
            >
            <view
              v-if="!!p.skip"
              class="sb-psact"
              @click="sandbox.tempo(p.id, 'unskip')"
              >取消休息</view
            >
            <view
              class="sb-psact"
              :class="{ 'on-fire': !!p.fire }"
              @click="sandbox.tempo(p.id, 'fire')"
              >{{ p.fire ? "连战中" : "连战" }}</view
            >
            <view class="sb-psact warn" @click="sandbox.leavePerson(p.id)"
              >退场</view
            >
            <!-- 封管理员只给组织卡视角（真局 isOrgViewer 同位）：只对候场正式球友、
                 已封的不重复给钮——访客与场上的人不显（store 闸兜底） -->
            <view
              v-if="canAdmin"
              class="sb-psact"
              @click="sandbox.setAdmin(p.id)"
              >设为管理员</view
            >
          </view>
        </template>

        <!-- 换人二段态：列对侧池（场上↔候场） -->
        <template v-else>
          <view class="sb-swapt">{{
            onCourt ? `把 ${p.name} 换成谁？` : `用 ${p.name} 换谁下场？`
          }}</view>
          <view v-if="pool.length" class="sb-pool">
            <view
              v-for="r in pool"
              :key="r.id"
              class="sb-prow"
              @click="sandbox.swapWith(r.id)"
            >
              <view class="sb-rav"
                ><ChibiAvatar :chibi="r.chibi" :size="32"
              /></view>
              <view class="sb-who">
                <view class="sb-nm"
                  >{{ r.name
                  }}<text v-if="r.guest" class="badge guest nm-badge">访客</text
                  ><text v-if="r.you" class="sb-mebadge">我</text></view
                >
              </view>
              <text class="sb-pgo">换 ‹</text>
            </view>
          </view>
          <EmptyBox
            v-else
            :text="
              onCourt
                ? '候场没人可换 · 先拉人或带访客'
                : '场上没人可换 · 先自动排阵'
            "
          />
          <view class="sb-pslink" @click="sandbox.setSwapMode(false)"
            >返回</view
          >
        </template>
      </template>
    </AppSheet>

    <!-- ---------- 规则（组织卡第五步可改分制；参与卡只读可开） ---------- -->
    <AppSheet
      :visible="sandbox.sheetKind === 'rules'"
      title="现场规则调整"
      :hint="
        sandbox.isFull
          ? '点选即生效 · 在打对局照旧打完，下一场起按新规'
          : '只读查看 · 改规则请找组织者或管理员'
      "
      @close="sandbox.closeSheet()"
    >
      <!-- 只读三保险之一：罩层（参与卡点不动）；处理器/闸在 store（二三层） -->
      <view :class="{ 'sb-ro': !sandbox.isFull }">
        <AppField label="局分分制 · First To">
          <AppSeg
            :options="SCORE_OPTS"
            :model-value="s?.scoring ?? 11"
            @update:model-value="onScore"
          />
        </AppField>
      </view>
      <!-- 轮换四件套：教学局锁定（engine 口径固定 n2·签到顺序）——两卡都只读展示，
           不教改轮换（规格 4.3 只教分制；验收「轮换可预期」需要开它看「2 人下」） -->
      <view class="sb-ro">
        <AppField label="单双打 · 全场统一">
          <view class="sb-roval">双打</view>
        </AppField>
        <AppField label="谁下">
          <view class="sb-roval">{{ DOWN_NAMES[SANDBOX_GAME.down] }}</view>
        </AppField>
        <AppField label="怎么配 · 双打分队">
          <view class="sb-roval">{{
            PAIRING_NAMES[SANDBOX_GAME.pairing]
          }}</view>
        </AppField>
      </view>
    </AppSheet>

    <!-- ---------- 散场收工（组织卡第十步）：残局清单 → 全取消 → 二次确认 → 账单 ---------- -->
    <AppSheet
      :visible="sandbox.sheetKind === 'sweep'"
      title="散场收工"
      hint="还有没处理完的对局 · 逐片上传或取消后才能收工"
      @close="sandbox.closeSheet()"
    >
      <!-- ended 态：收工账单亮相（写死 ORG_FINAL_BILL——界面一个数不自算，§6） -->
      <template v-if="s?.ended">
        <view class="sb-bill">
          <view class="sb-billk">BILL · 收工账单</view>
          <view class="sb-billt">场地费 {{ ORG_FINAL_BILL.feeTotal }} 元</view>
          <view class="sb-billrow"
            >{{ ORG_FINAL_BILL.heads }} 人 · 每人
            {{ ORG_FINAL_BILL.perHead }}</view
          >
          <view class="sb-billnote"
            >「{{ guestName }}」是访客——他那
            {{ ORG_FINAL_BILL.perHead }} 记在你（担保人）名下，你付
            {{ ORG_FINAL_BILL.myShare }}</view
          >
          <view class="sb-billtail">{{ ORG_FINAL_BILL.tail }}</view>
        </view>
        <AppButton variant="pri" block @click="sandbox.closeSheet()"
          >收下 · 回现场</AppButton
        >
      </template>

      <template v-else>
        <template v-if="residues.length">
          <view v-for="r in residues" :key="r.no" class="sb-swrow">
            <view class="sb-swinfo">
              <view class="sb-swnm">{{ r.no }}号场</view>
              <view class="sb-swmeta">
                <text class="sb-swst">在打</text>
                <text class="sb-swsc">{{ r.sa }} : {{ r.sb }}</text>
              </view>
            </view>
            <view class="sb-swacts">
              <view class="sb-swact" @click="sandbox.sweepCancelCourt(r.no)"
                >取消</view
              >
            </view>
          </view>
          <AppButton
            variant="ghost"
            block
            class="sb-allcancel"
            @click="sandbox.sweepCancelAll()"
            >未完对局全部取消</AppButton
          >
        </template>
        <EmptyBox v-else text="残局已清 · 没有挂在账上的对局了" />

        <!-- 费用亮数行（照真局 SweepSheet：确认散场前数字先亮着） -->
        <view class="sb-swfee"
          >总价 {{ ORG_FINAL_BILL.feeTotal }} · {{ ORG_FINAL_BILL.heads }} 人 ·
          人均 {{ ORG_FINAL_BILL.perHead }}</view
        >

        <!-- 确认散场二次确认（A3）：确认槽做在抽屉内（沙盒无页面确认槽） -->
        <view v-if="endConfirm" class="sb-endcfm">
          <view class="sb-ecmsg">球局将收工封存，此操作不可撤销</view>
          <view class="sb-ecbtns">
            <AppButton variant="ghost" class="flex1" @click="endConfirm = false"
              >再想想</AppButton
            >
            <AppButton variant="burn" class="flex1" @click="onEnd"
              >确认</AppButton
            >
          </view>
        </view>
        <AppButton
          v-else
          variant="burn"
          block
          class="sb-endbtn"
          :disabled="residues.length > 0"
          @click="endConfirm = true"
          >{{
            residues.length ? "还有残局 · 散场不放行" : "确认散场"
          }}</AppButton
        >
      </template>
    </AppSheet>
  </view>
</template>

<script setup lang="ts">
/* 四扇抽屉一文件（规格「一个文件多弹层或拆子组件，批内自定」——四扇共享 store 单槽，
   拆开反而要把 sheetKind 判定抄四遍）。动作全直调 store（编排/权限闸在 store，
   组件只呈现——同 CourtMatchCard 构）。本地态只有签到称呼预填与散场二次确认。 */
import { computed, ref, watch } from "vue";
import AppSheet from "@/components/ui/AppSheet.vue";
import AppButton from "@/components/ui/AppButton.vue";
import AppInput from "@/components/ui/AppInput.vue";
import AppField from "@/components/ui/AppField.vue";
import AppSeg from "@/components/ui/AppSeg.vue";
import EmptyBox from "@/components/ui/EmptyBox.vue";
import NoteCard from "@/components/ui/NoteCard.vue";
import ChibiAvatar from "@/components/ui/ChibiAvatar.vue";
import { useSandboxStore } from "@/stores/sandbox";
import { arrived, pOf, type SandPlayer } from "@/sandbox/engine";
import { DOWN_NAMES, PAIRING_NAMES, SCORE_OPTS } from "@/utils/format";
import { ORG_FINAL_BILL, SANDBOX_GAME } from "@/sandbox/data";

const sandbox = useSandboxStore();
const s = computed(() => sandbox.state);

/* ---------- 签到代办：待签=未到的正式球友（访客走「带访客」表单，data.ts 契约） ---------- */
const absents = computed(() =>
  (s.value?.players ?? []).filter((p) => p.check === "none" && !p.guest),
);
/** 称呼预填「朋友」可改（规格 4.3 第四步）；带上后回预填，称呼可再改再带 */
const gName = ref("朋友");
function onBring(): void {
  sandbox.bringGuest(gName.value);
  gName.value = "朋友";
}

/* ---------- 点人抽屉 ---------- */
const p = computed<SandPlayer | null>(
  () => s.value?.players.find((x) => x.id === sandbox.personId) ?? null,
);
const onCourt = computed(() => {
  const pp = p.value;
  const st = s.value;
  if (!pp || !st) return false;
  return st.courts.some((c) => c.a.includes(pp.id) || c.b.includes(pp.id));
});
/** 封管理员渲染闸（store 闸兜底）：组织卡 + 候场正式球友 + 未封过 */
const canAdmin = computed(() => {
  const pp = p.value;
  const st = s.value;
  return (
    sandbox.isFull &&
    !!pp &&
    !pp.guest &&
    !pp.admin &&
    !!st &&
    st.queue.includes(pp.id)
  );
});
/** 换人对侧池：人在场上列候场队；人在队/未到列场上全员（真局 poolRows 同口径） */
const pool = computed<SandPlayer[]>(() => {
  const st = s.value;
  const pp = p.value;
  if (!st || !pp) return [];
  const ids = onCourt.value
    ? st.queue
    : st.courts.flatMap((c) => [...c.a, ...c.b]);
  return ids.map((id) => pOf(st, id));
});

/* ---------- 规则抽屉 ---------- */
function onScore(v: string | number): void {
  sandbox.setScoring(Number(v)); // 闸在 store（只读罩层是第一保险）
}

/* ---------- 散场抽屉 ---------- */
/** 残局=在打片（A/B 有人）；行内比分吃本机账（无账 0:0，真局同源） */
const residues = computed(() =>
  (s.value?.courts ?? [])
    .filter((c) => c.a.length || c.b.length)
    .map((c) => ({
      no: c.no,
      sa: sandbox.localScores[c.no]?.sa ?? 0,
      sb: sandbox.localScores[c.no]?.sb ?? 0,
    })),
);
const endConfirm = ref(false);
watch(
  () => sandbox.sheetKind,
  (k) => {
    if (k !== "sweep") endConfirm.value = false; // 关抽屉收确认态，重开回到清单
  },
);
function onEnd(): void {
  if (sandbox.endGame()) endConfirm.value = false;
}
const guestName = computed(
  () => s.value?.players.find((p) => p.guest)?.name ?? "朋友",
);
</script>

<style lang="scss" scoped>
/* 类名全带 sb- 前缀防串域；形与色逐字换 tokens 自真局四抽屉（复刻） */
.flex1 {
  flex: 1;
}
.nm-badge {
  margin-left: 6px;
  vertical-align: 1px;
}

/* ---------- 签到代办（CheckinSheet .ck-sec 族） ---------- */
.sb-cksec {
  margin-bottom: 16px;
}
.sb-ckt {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.2em;
  color: var(--dim);
  margin-bottom: 8px;
}
.sb-ckrow {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid rgba(245, 241, 232, 0.1);
  border-radius: 12px;
  background: var(--ink2);
  margin-bottom: 6px;
}
/* 待签行暗显（规格 4.3「凯文在待签列表里暗显」——还没到的人压一档） */
.sb-ckrow.dim {
  opacity: 0.6;
}
.sb-rav {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: var(--ink3);
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}
.sb-who {
  flex: 1;
  min-width: 0;
}
.sb-nm {
  font-size: 13px;
  font-weight: 600;
}
.sb-st {
  font-size: 10px;
  color: var(--dim);
  margin-top: 2px;
}
.sb-st.late {
  color: var(--coral);
}
.sb-acts {
  display: flex;
  gap: 6px;
  flex: none;
}
.sb-ckin {
  margin-bottom: 12px;
}
.sb-nk {
  color: var(--lilac);
  font-weight: 600;
}

/* ---------- 点人抽屉（PersonSheet .ps- 族） ---------- */
.sb-pshead {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.sb-psav {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: var(--ink2);
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}
.sb-psnm {
  font-size: 15px;
  font-weight: 700;
}
.sb-mebadge {
  display: inline-block;
  font-family: var(--mono);
  font-size: 9px;
  border: 1px solid rgba(255, 212, 0, 0.5);
  color: var(--lemon);
  border-radius: 6px;
  padding: 0 5px;
  margin-left: 6px;
  vertical-align: 1px;
}
.sb-pssub {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--lilac);
  letter-spacing: 0.1em;
  margin-top: 3px;
}
.sb-psgrid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.sb-psact {
  border: 1px solid rgba(245, 241, 232, 0.16);
  border-radius: 13px;
  background: var(--ink2);
  color: var(--cream);
  font-size: 13px;
  font-weight: 600;
  padding: 13px 0;
  text-align: center;
  cursor: pointer;
  transition: 0.15s;
}
.sb-psact:active {
  transform: scale(0.95);
  border-color: var(--lemon);
}
.sb-psact.on-rest {
  border-color: var(--ice);
  color: var(--ice);
}
.sb-psact.on-fire {
  border-color: var(--coral);
  color: var(--coral);
}
.sb-psact.warn {
  color: var(--coral);
}
.sb-pslink {
  text-align: center;
  font-size: 12px;
  color: var(--dim);
  margin-top: 12px;
  cursor: pointer;
}
/* 换人二段态 */
.sb-swapt {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 14px;
}
.sb-pool {
  max-height: 46vh;
  overflow-y: auto;
}
.sb-prow {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid rgba(245, 241, 232, 0.1);
  border-radius: 12px;
  background: var(--ink2);
  margin-bottom: 6px;
  cursor: pointer;
}
.sb-prow:active {
  border-color: var(--lemon);
}
.sb-pgo {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--lemon);
}

/* ---------- 规则抽屉：只读罩层（RulesSheet .ro 同款）与只读值 ---------- */
.sb-ro {
  opacity: 0.45;
  pointer-events: none;
}
.sb-roval {
  display: inline-block;
  padding: 9px 14px;
  border-radius: 12px;
  border: 1px solid rgba(245, 241, 232, 0.14);
  background: var(--ink);
  color: var(--cream);
  font-size: 13px;
  font-weight: 700;
}

/* ---------- 散场抽屉（SweepSheet .sw- 族） ---------- */
.sb-swrow {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  margin-bottom: 8px;
  border: 1px solid rgba(245, 241, 232, 0.08);
  background: var(--ink2);
}
.sb-swinfo {
  flex: 1;
  min-width: 0;
}
.sb-swnm {
  font-size: 13px;
  font-weight: 600;
}
.sb-swmeta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 3px;
}
.sb-swst {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.1em;
  color: var(--dim);
}
.sb-swsc {
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 700;
  color: var(--lemon);
}
.sb-swacts {
  flex: none;
}
.sb-swact {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.06em;
  border: 1px solid rgba(255, 90, 54, 0.4);
  border-radius: 9px;
  padding: 6px 9px;
  color: var(--coral);
  background: rgba(255, 90, 54, 0.06);
  cursor: pointer;
  white-space: nowrap;
  transition: 0.15s;
}
.sb-swact:active {
  transform: scale(0.94);
}
.sb-allcancel {
  margin-top: 4px;
}
.sb-swfee {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(255, 212, 0, 0.25);
  background: rgba(255, 212, 0, 0.06);
  font-family: var(--mono);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-align: center;
  color: var(--lemon);
}
/* 二次确认（A3）：后果句 + 双纽（真局页面确认槽同构，收进抽屉内） */
.sb-endcfm {
  margin-top: 10px;
}
.sb-ecmsg {
  font-size: 13px;
  font-weight: 600;
  text-align: center;
  margin-bottom: 10px;
}
.sb-ecbtns {
  display: flex;
  gap: 10px;
}
.sb-endbtn {
  margin-top: 8px;
}

/* 收工账单（ended 态）：账目三行 + 担保注 + 指路尾 */
.sb-bill {
  border: 1px solid rgba(255, 212, 0, 0.25);
  border-radius: var(--r-md);
  background: rgba(255, 212, 0, 0.05);
  padding: 14px;
  margin-bottom: 12px;
  text-align: center;
}
.sb-billk {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.3em;
  color: var(--dim);
  text-transform: uppercase;
}
.sb-billt {
  font-family: var(--disp);
  font-size: 26px;
  color: var(--lemon);
  margin: 8px 0 4px;
}
.sb-billrow {
  font-size: 13px;
  font-weight: 600;
}
.sb-billnote {
  font-size: 12px;
  color: var(--cream);
  line-height: 1.6;
  margin-top: 8px;
}
.sb-billtail {
  font-size: 11px;
  color: var(--dim);
  margin-top: 10px;
}
</style>
