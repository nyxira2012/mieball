<template>
  <!-- 块三置底候场条（temp/打球页原型 .queuebar 逐字）：下一场头像×4 柠檬描边叠压 +
       我的轮次一句话 + ＋到场钮。点队列区开完整队列抽屉，＋到场开签到抽屉（页面编排）。 -->
  <view v-if="L" class="queuebar">
    <view class="q-mid" @click="emit('queue')">
      <view class="q-label">{{ L.queue.length ? '下一场' : '全员都在场上' }}</view>
      <view class="q-avs">
        <view v-for="id in next4" :key="id" class="q-av next">
          <ChibiAvatar :chibi="byId(id).chibi" :size="26" />
        </view>
      </view>
    </view>
    <view class="q-me" :class="{ hot: myRound === 1 }" @click="emit('queue')">{{ meTxt }}</view>
    <view class="q-check" @click.stop="emit('checkin')">＋ 到场</view>
  </view>
</template>

<script setup lang="ts">
/* 置底候场条（2.1 §3）：无 props，读 live store；emit queue/checkin 由页面开对应抽屉。
   我的轮次三态：队列里「还有 N 轮到我」（=1 加粗强调）/ 场上「场上打拼中」/ 未签到「还没签到」。 */
import { computed } from 'vue';
import ChibiAvatar from '@/components/ui/ChibiAvatar.vue';
import { useLiveStore, isArrived } from '@/stores/live';
import { U } from '@/api';

const emit = defineEmits<{ (e: 'queue'): void; (e: 'checkin'): void }>();

const liveStore = useLiveStore();
const L = computed(() => liveStore.live);
const byId = (id: number) => liveStore.byId(id);

/** 下四位头像（不足则全量；全员都在场上时 q-label 已换文案、头像区空） */
const next4 = computed(() => (L.value?.queue ?? []).slice(0, 4));

/** 我的状态一句话：myRound 非空在队列；在册且已签到（谓词单一源 isArrived）但不在队列 = 场上；否则还没签到 */
const myRound = computed(() => liveStore.myRound);
const meTxt = computed(() => {
  if (myRound.value != null) return `还有 ${myRound.value} 轮到我`;
  const me = L.value ? liveStore.byId(U.me.id) : undefined;
  return me && isArrived(me.check) ? '场上打拼中' : '还没签到';
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
