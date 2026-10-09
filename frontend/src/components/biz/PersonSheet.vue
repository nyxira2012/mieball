<template>
  <!-- 点人抽屉（temp/打球页原型 sh-person 逐字）：常规态 = 头像/战绩头 + 手柄钮（本人随时可、
       给他人需全权：换人/歇两轮/连战/退场）+ 设为/撤掉管理员（仅组织者可见）+ 战力档案链接；
       换人二段态 = 标题换「把 X 换成谁？」列对侧池（场上↔候场），点行即换；
       待确认片上的人换不动（2.3 §4.3 冻结含换人：入口与对侧池该行前置灰，后端 court_frozen 兜底）。 -->
  <AppSheet :visible="visible" @close="emit('close')">
    <template v-if="p">
      <!-- ---------- 常规态 ---------- -->
      <template v-if="!swap">
        <view class="ps-head">
          <view class="ps-av"><ChibiAvatar :chibi="p.chibi" :size="44" /></view>
          <view class="ps-meta">
            <view class="ps-nm"
              >{{ p.name
              }}<text
                v-if="liveStore.isAdmin(personId)"
                class="badge admin ps-admin"
                >管理员</text
              ></view
            >
            <view class="ps-elo"
              ><text class="elo-b">{{ fmtDupr1(p.dupr ?? GUEST_DUPR) }}</text> ·
              已打 {{ p.play }} 场<text v-if="p.shadow" class="ps-guest">
                · 访客（不计积分）</text
              ></view
            >
          </view>
        </view>
        <view class="ps-grid">
          <view
            v-if="canOperate"
            class="ps-act"
            :class="{ off: swapFrozen }"
            @click="onSwap"
            >换人</view
          >
          <view
            v-if="canOperate"
            class="ps-act"
            :class="{ 'on-rest': !!p.skip }"
            @click="liveStore.togglePerson(p.id, 'skip')"
            >{{ p.skip ? `再歇一轮 · 将跳 ${p.skip} 轮` : "休息一轮" }}</view
          >
          <view
            v-if="canOperate && !!p.skip"
            class="ps-act"
            @click="liveStore.togglePerson(p.id, 'unskip')"
            >取消休息</view
          >
          <view
            v-if="canOperate"
            class="ps-act"
            :class="{ 'on-fire': !!p.fire }"
            @click="liveStore.togglePerson(p.id, 'fire')"
            >{{ p.fire ? "连战中" : "连战" }}</view
          >
          <view v-if="canOperate" class="ps-act warn" @click="onLeave"
            >退场</view
          >
          <view
            v-if="isOrgViewer"
            class="ps-act"
            :class="{ 'on-admin': liveStore.isAdmin(personId) }"
            @click="onAdminToggle"
            >{{
              liveStore.isAdmin(personId) ? "撤掉管理员" : "设为管理员"
            }}</view
          >
        </view>
        <view class="ps-link" @click="emit('profile', p.id)"
          >查看 <text class="ice">战力档案</text> ›</view
        >
      </template>

      <!-- ---------- 换人二段态：列对侧池 ---------- -->
      <template v-else>
        <view class="ps-swap-t">{{
          personOnCourt ? `把 ${p.name} 换成谁？` : `用 ${p.name} 换谁下场？`
        }}</view>
        <view v-if="poolRows.length" class="ps-pool">
          <view
            v-for="r in poolRows"
            :key="r.id"
            class="ps-row"
            :class="{ off: r.frozen }"
            @click="onPick(r)"
          >
            <view class="row-av"
              ><ChibiAvatar :chibi="r.u.chibi" :size="32"
            /></view>
            <view class="row-info">
              <view class="row-nm"
                >{{ r.u.name
                }}<text v-if="r.u.shadow" class="badge guest">访客</text
                ><text v-if="r.frozen" class="row-frozen">待确认</text></view
              >
              <view class="row-meta"
                >已打 {{ r.u.play }} 场 · DUPR
                {{ fmtDupr1(r.u.dupr ?? GUEST_DUPR) }}</view
              >
            </view>
            <text class="row-go">换 ‹</text>
          </view>
        </view>
        <EmptyBox
          v-else
          :text="
            personOnCourt
              ? '候场没人可换 · 先拉人或带访客'
              : '场上没人可换 · 先自动排阵'
          "
        />
        <view class="ps-link" @click="emit('swap-mode', false)">返回</view>
      </template>
    </template>
  </AppSheet>
</template>

<script setup lang="ts">
/* 点人抽屉（2.1 §3-4；2.2 批1 权限分级 · 批3b 休息叠加）：休息/取消休息/连战/退场直调 live store
   （toast 在 store），换人与档案走 emit 由页面编排（swap 二段态、ProfileSheet 全局弹层）。
   休息可连按叠加（按钮示「将跳 N 轮」——skip 还没消耗，将跳非已跳），「取消休息」随时清 0（§4.10 修订⑨）；
   权限（§4.8/4.9/4.10）：换人/歇/连/退场本人随时可、给他人需全权（isFullPower 单一源在 store）；
   「设为/撤掉管理员」仅组织者可见（§4.6 禁止管理员再封管理员）。
   对侧池口径：人在场上 → 列候场队列；人在队列 → 列场上全员（cur + 各待开片）。 */
import { computed } from "vue";
import AppSheet from "@/components/ui/AppSheet.vue";
import ChibiAvatar from "@/components/ui/ChibiAvatar.vue";
import EmptyBox from "@/components/ui/EmptyBox.vue";
import { useLiveStore } from "@/stores/live";
import { courtOfPerson, pById } from "@/utils/rotate";
import { GUEST_DUPR, fmtDupr1 } from "@/utils/elo";

const props = defineProps({
  visible: { type: Boolean, default: false },
  personId: { type: Number, required: true },
  /** 换人二段态（标题换「把 X 换成谁？」） */
  swap: { type: Boolean, default: false },
});
const emit = defineEmits<{
  (e: "close"): void;
  (e: "profile", id: number): void;
  (e: "swap-mode", on: boolean): void;
  (e: "swap-target", id: number): void;
}>();

const liveStore = useLiveStore();

/** 点中的人（roster 真身查不到 = 抽屉失效，内容整体不渲染；byId 的「—」占位不适合这里） */
const p = computed(() =>
  liveStore.live?.roster.find((x) => x.id === props.personId),
);

/** 全权（组织者 ∨ 管理员）单一源在 store */
const full = computed(() => liveStore.isFullPower);
/** 封撤管理员入口只给组织者本人——视图身份旗直读（2026-10-08 起） */
const isOrgViewer = computed(() => liveStore.liveView?.isOrganizer ?? false);
/** 手柄钮（换人/歇/连/退场）：给自己随时可、给他人需全权——「自己」按名册行 id
    判（store.myRowId 单一源；行 id ≠ 账号 id，与 setCheck/togglePerson 守卫同键） */
const canOperate = computed(
  () => full.value || props.personId === liveStore.myRowId(),
);

/** 退场：setCheck left（清队列清场上 + toast 在 store），随后关抽屉 */
function onLeave(): void {
  liveStore.setCheck(props.personId, "left");
  emit("close");
}
/** 换人入口（§4.3 待确认片冻结前置灰；后端 court_frozen 兜底） */
function onSwap(): void {
  if (swapFrozen.value) return;
  emit("swap-mode", true);
}
/** 换人落子：靶在待确认片上时前置灰拦（§4.3 Q5 整片冻结含换人） */
function onPick(r: { id: number; frozen: boolean }): void {
  if (r.frozen) return;
  emit("swap-target", r.id);
}
/** 封/撤管理员（toast 与 feed 留痕在 store）；抽屉不关，徽章当场可见 */
function onAdminToggle(): void {
  if (liveStore.isAdmin(props.personId)) liveStore.unsetAdmin(props.personId);
  else liveStore.setAdmin(props.personId);
}

/** 人在的片是否待确认冻结中（§4.3：片上的人换不动——出口等确认窗处理完）；
    片位查 courtOfPerson 单一源（与 store.swapPlayers 出/入定向同谓词） */
function onFrozenCourt(id: number): boolean {
  const l = liveStore.live;
  const c = l ? courtOfPerson(l, id) : undefined;
  return !!c && liveStore.isPending(c.id);
}
/** 点中的人在待确认片上：换人入口前置灰 */
const swapFrozen = computed(() => onFrozenCourt(props.personId));

/** 场上全员 id（各片 A/B 并起来——2.4 批2 起无 cur，多片各打各的） */
const onCourtIds = computed<number[]>(() => {
  const l = liveStore.live;
  if (!l) return [];
  return l.courts.flatMap((c) => [...c.A, ...c.B]);
});
const personOnCourt = computed(() => onCourtIds.value.includes(props.personId));

/** 对侧池：person 在场上 → 列候场队全员；person 在队 → 列各片场上全员。
    过滤名册查不到的 id（建号换 id 后场上残留旧 id 的 mock 路径），不出「—」行。
    行数据 computed 一次解析好（模板逐字段 byId 是每行多次名册线性扫描）；
    frozen=靶在待确认片上（§4.3 换人冻结，行前置灰拦点） */
const poolRows = computed(() => {
  const l = liveStore.live;
  if (!l) return [];
  const ids = (personOnCourt.value ? l.queue : onCourtIds.value).filter(
    (id) => !!pById(l, id),
  );
  return ids.map((id) => ({
    id,
    u: liveStore.byId(id),
    frozen: onFrozenCourt(id),
  }));
});
</script>

<style lang="scss" scoped>
/* ---------- 原型 .ps-head/.ps-grid/.ps-act/.ps-link（逐字换 tokens） ---------- */
.ps-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.ps-av {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: var(--ink2);
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}
.ps-nm {
  font-size: 15px;
  font-weight: 700;
}
.ps-elo {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  letter-spacing: 0.1em;
  margin-top: 3px;
}
.ps-elo .elo-b {
  color: var(--lemon);
  font-size: 13px;
}
.ps-guest {
  color: var(--lilac);
}
.ps-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.ps-act {
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
.ps-act:active {
  transform: scale(0.95);
  border-color: var(--lemon);
}
.ps-act.on-rest {
  border-color: var(--ice);
  color: var(--ice);
}
.ps-act.on-fire {
  border-color: var(--coral);
  color: var(--coral);
}
.ps-act.on-admin {
  border-color: var(--lemon);
  color: var(--lemon);
}
.ps-act.warn {
  color: var(--coral);
}
/* 待确认片冻结前置灰（§4.3）：入口可见但点不动，出口在确认窗 */
.ps-act.off {
  opacity: 0.4;
  pointer-events: none;
}
.ps-admin {
  margin-left: 6px;
  vertical-align: 1px;
}
.ps-link {
  text-align: center;
  font-size: 12px;
  color: var(--dim);
  margin-top: 12px;
  cursor: pointer;
}
.ps-link .ice {
  color: var(--ice);
  font-weight: 600;
}

/* ---------- 换人二段态 ---------- */
.ps-swap-t {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 14px;
}
.ps-pool {
  max-height: 46vh;
  overflow-y: auto;
}
.ps-row {
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
.ps-row:active {
  border-color: var(--lemon);
}
.row-av {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: var(--ink3);
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}
.row-info {
  flex: 1;
  min-width: 0;
}
.row-nm {
  font-size: 13px;
  font-weight: 600;
}
.row-meta {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
  letter-spacing: 0.08em;
  margin-top: 2px;
}
.row-go {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--lemon);
}
/* 待确认片上的人换不动（§4.3）：行置灰拦点 + 名旁小标 */
.ps-row.off {
  opacity: 0.4;
  pointer-events: none;
}
.row-frozen {
  margin-left: 6px;
  font-family: var(--mono);
  font-size: 9px;
  color: var(--coral);
}
/* 访客徽章：形与色在 base.scss 全局类；此处只补名字右侧的位置 margin */
.badge.guest {
  margin-left: 6px;
}
</style>
