<template>
  <!-- 沙盒候场条（2.7 批3，复刻 QueueBar 长相手感——真局组件零改动）：下一场头像×4
       柠檬描边 + 我的轮次一句话 + 我到了 / ＋到场。我的状态句推演吃 engine 状态，
       轮数吃真局同一真值（utils/rotate 的 roundsToPlay 单一源）。
       参与卡身份随卡走（规格 4.4）：我到了亮着（幕一光圈锚 me-checkin）；
       ＋到场是代办工具——普通球员点了由 store 权限闸如实拦下（批4）；
       候场头像可点开点人抽屉（§4.4，批4） -->
  <view v-if="s" class="sb-qbar">
    <view class="sb-qmid">
      <view class="sb-qlabel">{{
        s.queue.length ? "下一场" : "全员都在场上"
      }}</view>
      <view class="sb-qavs">
        <!-- 候场头像可点（§4.4「点任何人的头像都开点人抽屉」；组织卡第七步
             「点候场里的凯文」的入口）：光圈亮整个候场排——提示语点名要封谁 -->
        <view
          v-for="id in nextN"
          :key="id"
          class="sb-qav"
          :class="{ 'sb-glow': sandbox.spot === 'queue-kevin' }"
          @click.stop="emit('person', id)"
        >
          <AvatarBadge :url="pOf(s, id).avatar" :size="26" />
        </view>
      </view>
    </view>
    <view class="sb-qme" :class="{ hot: myRound === 1 }">{{ meTxt }}</view>
    <view
      class="sb-qarrive"
      :class="{ 'sb-glow': sandbox.spot === 'me-checkin' }"
      @click.stop="emit('arrive')"
      >我到了</view
    >
    <view
      class="sb-qcheck"
      :class="{ 'sb-glow': sandbox.spot === 'checkin-btn' }"
      @click.stop="emit('checkin')"
      >＋ 到场</view
    >
  </view>
</template>

<script setup lang="ts">
import { computed } from "vue";
import AvatarBadge from "@/components/ui/AvatarBadge.vue";
import { useSandboxStore } from "@/stores/sandbox";
import { roundsToPlay } from "@/utils/rotate";
import { arrived, pOf } from "@/sandbox/engine";
import { COURT_SIZE } from "@/sandbox/data";

const emit = defineEmits<{
  (e: "arrive"): void;
  (e: "checkin"): void;
  (e: "person", id: number): void;
}>();

const sandbox = useSandboxStore();
const s = computed(() => sandbox.state);

/** 下 N 位头像（N=每片人数，单源 data.COURT_SIZE；engine fillIdle 同吃） */
const nextN = computed(() => (s.value?.queue ?? []).slice(0, COURT_SIZE));

/** 我的轮次：真局 myRound 同一真值（roundsToPlay 单一源，utils/rotate——
    「不发明第二套」这次落进代码）；不在队列 → null */
const myRound = computed<number | null>(() => {
  const st = s.value;
  const you = st?.players.find((p) => p.you);
  if (!st || !you) return null;
  const idx = st.queue.indexOf(you.id);
  if (idx < 0) return null;
  const empty = st.courts.filter((c) => !c.a.length && !c.b.length).length;
  return roundsToPlay(SIZE, empty, idx);
});

/** 我的状态一句话（真局同式）：队列里「还有 N 轮到我」（=1 强调）；
    已到场不在队列=场上「场上打拼中」；否则「还没签到」。到场判定吃 engine 谓词
    （沙盒域单一真值，别手写第二份） */
const meTxt = computed(() => {
  const st = s.value;
  const you = st?.players.find((p) => p.you);
  if (!st || !you) return "还没签到";
  if (myRound.value != null) return `还有 ${myRound.value} 轮到我`;
  return arrived(you) ? "场上打拼中" : "还没签到";
});
const SIZE = COURT_SIZE;
</script>

<style lang="scss" scoped>
/* 长相与真局 QueueBar 同族（tokens 同源），类名 sb- 前缀防串域 */
.sb-qbar {
  flex: none;
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(22, 22, 29, 0.95);
  backdrop-filter: blur(8px);
  border-top: 1px solid var(--line);
  padding: 10px 14px;
  z-index: 5;
}
.sb-qmid {
  flex: 1;
  min-width: 0;
}
.sb-qlabel {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.2em;
  color: var(--dim);
}
.sb-qavs {
  display: flex;
  margin-top: 4px;
}
.sb-qav {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--ink3);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--lemon); /* 下几位高亮 */
  margin-right: -6px;
  cursor: pointer;
}
.sb-qme {
  font-size: 12px;
  font-weight: 700;
  color: var(--lemon);
  white-space: nowrap;
}
/* 下一轮就到我：再强调一档 */
.sb-qme.hot {
  font-size: 13px;
  text-shadow: 0 0 12px rgba(255, 212, 0, 0.55);
}
/* 我到了：实心柠檬压过描边的代办钮（签到是球友进场的主动作，与真局同权重） */
.sb-qarrive {
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
.sb-qarrive:active {
  transform: scale(0.93);
}
/* ＋到场：代办工具位（描边档）；参与卡点了由 Stage 如实拦下 */
.sb-qcheck {
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
.sb-qcheck:active {
  transform: scale(0.93);
}
</style>
