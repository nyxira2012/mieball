<template>
  <!-- 块三置底候场条（temp/打球页原型 .queuebar 逐字）：下一场头像×4 柠檬描边叠压 +
       我的轮次一句话 + 「我到了」自签到钮 + 「代人签到」钮（2026-10-17 用户裁决改名，
       原文「＋ 到场」——点它开代办签到抽屉，语义是替还没到的人办到场）。
       点队列区开完整队列抽屉，我到了走自签到链（页面编排）。
       「下一场 · 预计序」：队列是后端按排位算好的快照（无人手动换人时排前几位的
       即下一场上场人选，手动换人后以现场为准）；歇/连战角标吃名册行 skip/fire。 -->
  <view v-if="L" class="queuebar">
    <view class="q-mid" @click="emit('queue')">
      <view class="q-label">{{
        L.queue.length ? "下一场 · 预计序" : "全员都在场上"
      }}</view>
      <view class="q-avs">
        <view
          v-for="id in nextN"
          :key="id"
          class="q-av next"
          :class="{ dropin: byId(id).dropin }"
        >
          <text v-if="byId(id).fire" class="badge fire q-tag">连</text>
          <text v-else-if="byId(id).skip" class="badge rest q-tag">歇</text>
          <ChibiAvatar :chibi="byId(id).chibi" :size="26" />
        </view>
      </view>
    </view>
    <view class="q-me" :class="{ hot: myRound === 1 }" @click="emit('queue')">{{
      meTxt
    }}</view>
    <view class="q-arrive" @click.stop="emit('arrive')">我到了</view>
    <view class="q-check" @click.stop="emit('checkin')">代人签到</view>
  </view>
</template>

<script setup lang="ts">
/* 置底候场条（2.1 §3 · 2.4 批2 size-aware）：无 props，读 live store；emit queue/arrive/checkin
   由页面开对应抽屉/走自签到。下一场头像数=每片人数（courtSize：双打 4 / 单打 2，单一源在引擎）。
   我的轮次三态：队列里「还有 N 轮到我」（=1 加粗强调）/ 场上「场上打拼中」/ 未签到「还没签到」。 */
import { computed } from "vue";
import ChibiAvatar from "@/components/ui/ChibiAvatar.vue";
import { useLiveStore, isArrived } from "@/stores/live";
import { courtSize } from "@/utils/rotate";

const emit = defineEmits<{
  (e: "queue"): void;
  (e: "arrive"): void;
  (e: "checkin"): void;
}>();

const liveStore = useLiveStore();
const L = computed(() => liveStore.live);
const byId = (id: number) => liveStore.byId(id);

/** 下 N 位头像（N=每片人数；不足则全量，全员都在场上时 q-label 已换文案、头像区空） */
const nextN = computed(() =>
  (L.value?.queue ?? []).slice(0, courtSize(L.value?.rules.singles ?? false)),
);

/** 我的状态一句话：myRound 非空在队列；在册且已签到（谓词单一源 isArrived）但不在队列 = 场上；否则还没签到。
    名册行 id 与账号 id 是两套自增（见 live store myRowId 的口径注）——此处必须经
    myRowId() 换算，裸账号 id 撞车才对、撞不上就永远误显「还没签到」（2026-10-17 走查修复） */
const myRound = computed(() => liveStore.myRound);
const meTxt = computed(() => {
  if (myRound.value != null) return `还有 ${myRound.value} 轮到我`;
  const me = L.value ? liveStore.byId(liveStore.myRowId() ?? -1) : undefined;
  return me && isArrived(me.check) ? "场上打拼中" : "还没签到";
});
</script>

<style lang="scss" scoped>
/* ---------- 原型 .queuebar（逐字换 tokens） ---------- */
.queuebar {
  flex: none;
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(22, 22, 29, 0.95);
  backdrop-filter: blur(8px);
  border-top: 1px solid var(--line);
  padding: 10px 14px calc(10px + env(safe-area-inset-bottom, 0px));
  cursor: pointer;
  z-index: 5;
}
.q-mid {
  flex: 1;
  min-width: 0;
}
.q-label {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.2em;
  color: var(--dim);
}
.q-avs {
  display: flex;
  margin-top: 4px;
}
.q-av {
  position: relative; /* 歇/连战角标的定位锚 */
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--ink3);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid transparent;
  margin-right: -6px;
}
.q-av.next {
  border-color: var(--lemon); /* 下几位高亮 */
}
/* 空降者头像换冰青描边（§4.4 全场看得到；无名字位，色环即标记） */
.q-av.dropin {
  border-color: var(--ice);
}
/* 歇/连战角标（§4.7 预计序上谁歇谁连战一眼可辨）：形与色吃全局 .badge，这里只
   定位到头像右上角、压住叠压边（单字不遮脸） */
.q-tag {
  position: absolute;
  top: -5px;
  right: -3px;
  z-index: 1;
}
.q-me {
  font-size: 12px;
  font-weight: 700;
  color: var(--lemon);
  white-space: nowrap;
}
/* 下一轮就到我：再强调一档（本色辉光 + 放大半号） */
.q-me.hot {
  font-size: 13px;
  text-shadow: 0 0 12px rgba(255, 212, 0, 0.55);
}
/* 「我到了」自签到钮（A1 自己那行的醒目签到键）：实心柠檬压过描边的代办钮——
   签到是球友进场的主动作；对已签到者不隐藏，点了吃 arriveMe 现有「你已经在场了」句 */
.q-arrive {
  flex: none;
  background: var(--lemon);
  color: #1b1b1d;
  font-size: 12px;
  font-weight: 700;
  font-family: var(--sans);
  border-radius: 12px;
  padding: 9px 13px;
  cursor: pointer;
  transition: 0.15s;
}
.q-arrive:active {
  transform: scale(0.93);
}
.q-check {
  flex: none;
  border: 1px solid rgba(255, 212, 0, 0.35);
  background: rgba(255, 212, 0, 0.08);
  color: var(--lemon);
  font-size: 12px;
  font-weight: 700;
  font-family: var(--sans);
  border-radius: 12px;
  padding: 9px 13px;
  cursor: pointer;
  transition: 0.15s;
}
.q-check:active {
  transform: scale(0.93);
}
</style>
