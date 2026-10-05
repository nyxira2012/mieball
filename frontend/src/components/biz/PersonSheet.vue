<template>
  <!-- 点人抽屉（temp/打球页原型 sh-person 逐字）：常规态 = 头像/战绩头 + 四钮（换人[org]/歇两轮/连战/退场[org]）
       + 战力档案链接；换人二段态 = 标题换「把 X 换成谁？」列对侧池（场上↔候场），点行即换。 -->
  <AppSheet :visible="visible" @close="emit('close')">
    <template v-if="p">
      <!-- ---------- 常规态 ---------- -->
      <template v-if="!swap">
        <view class="ps-head">
          <view class="ps-av"><ChibiAvatar :chibi="p.chibi" :size="44" /></view>
          <view class="ps-meta">
            <view class="ps-nm">{{ p.name }}</view>
            <view class="ps-elo"><text class="elo-b">{{ p.elo || '新' }}</text> · 已打 {{ p.play }} 场<text v-if="p.shadow" class="ps-guest"> · 访客（积分半权重）</text></view>
          </view>
        </view>
        <view class="ps-grid">
          <view v-if="org" class="ps-act" @click="emit('swap-mode', true)">换人</view>
          <view class="ps-act" :class="{ 'on-rest': !!p.skip }" @click="liveStore.togglePerson(p.id, 'skip')">{{ p.skip ? '已歇两轮' : '歇两轮' }}</view>
          <view class="ps-act" :class="{ 'on-fire': !!p.fire }" @click="liveStore.togglePerson(p.id, 'fire')">{{ p.fire ? '连战中' : '连战' }}</view>
          <view v-if="org" class="ps-act warn" @click="onLeave">退场</view>
        </view>
        <view class="ps-link" @click="emit('profile', p.id)">查看 <text class="ice">战力档案</text> ›</view>
      </template>

      <!-- ---------- 换人二段态：列对侧池 ---------- -->
      <template v-else>
        <view class="ps-swap-t">把 {{ p.name }} 换成谁？</view>
        <view v-if="poolRows.length" class="ps-pool">
          <view v-for="r in poolRows" :key="r.id" class="ps-row" @click="emit('swap-target', r.id)">
            <view class="row-av"><ChibiAvatar :chibi="r.u.chibi" :size="32" /></view>
            <view class="row-info">
              <view class="row-nm">{{ r.u.name }}<text v-if="r.u.shadow" class="badge guest">访客</text></view>
              <view class="row-meta">已打 {{ r.u.play }} 场 · ELO {{ r.u.elo || '—' }}</view>
            </view>
            <text class="row-go">换 ‹</text>
          </view>
        </view>
        <EmptyBox v-else :text="personOnCourt ? '候场没人可换 · 先拉人或带访客' : '场上没人可换 · 先自动排阵'" />
        <view class="ps-link" @click="emit('swap-mode', false)">返回</view>
      </template>
    </template>
  </AppSheet>
</template>

<script setup lang="ts">
/* 点人抽屉（2.1 §3-4）：歇两轮/连战/退场直调 live store（toast 在 store），
   换人与档案走 emit 由页面编排（swap 二段态、ProfileSheet 全局弹层）。
   对侧池口径：人在场上 → 列候场队列；人在队列 → 列场上全员（cur + 各待开片）。 */
import { computed } from 'vue';
import AppSheet from '@/components/ui/AppSheet.vue';
import ChibiAvatar from '@/components/ui/ChibiAvatar.vue';
import EmptyBox from '@/components/ui/EmptyBox.vue';
import { useLiveStore } from '@/stores/live';
import { pById } from '@/utils/rotate';
import { isOrg } from '@/utils/format';

const props = defineProps({
  visible: { type: Boolean, default: false },
  personId: { type: Number, required: true },
  /** 换人二段态（标题换「把 X 换成谁？」） */
  swap: { type: Boolean, default: false },
});
const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'profile', id: number): void;
  (e: 'swap-mode', on: boolean): void;
  (e: 'swap-target', id: number): void;
}>();

const liveStore = useLiveStore();

/** 点中的人（roster 真身查不到 = 抽屉失效，内容整体不渲染；byId 的「—」占位不适合这里） */
const p = computed(() => liveStore.live?.roster.find((x) => x.id === props.personId));

/** 组织者判定（换人/退场仅组织者可操作，运行时读 U.me.id） */
const org = computed(() => (liveStore.live ? isOrg(liveStore.live.g) : false));

/** 退场：setCheck left（清队列清场上 + toast 在 store），随后关抽屉 */
function onLeave(): void {
  liveStore.setCheck(props.personId, 'left');
  emit('close');
}

/** 场上全员 id（cur A/B + 各待开片 A/B） */
const onCourtIds = computed<number[]>(() => {
  const l = liveStore.live;
  if (!l) return [];
  return [...(l.cur ? [...l.cur.A, ...l.cur.B] : []), ...l.courts.flatMap((c) => [...c.A, ...c.B])];
});
const personOnCourt = computed(() => onCourtIds.value.includes(props.personId));

/** 对侧池：person 在场上 → 列队列全员；person 在队列 → 列场上全员。
    过滤名册查不到的 id（建号换 id 后场上残留旧 id 的 mock 路径），不出「—」行。
    行数据 computed 一次解析好（模板逐字段 byId 是每行多次名册线性扫描）。 */
const poolRows = computed(() => {
  const l = liveStore.live;
  if (!l) return [];
  const ids = (personOnCourt.value ? l.queue : onCourtIds.value).filter((id) => !!pById(l, id));
  return ids.map((id) => ({ id, u: liveStore.byId(id) }));
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
.ps-act.warn {
  color: var(--coral);
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
/* 访客徽章：形与色在 base.scss 全局类；此处只补名字右侧的位置 margin */
.badge.guest {
  margin-left: 6px;
}
</style>
