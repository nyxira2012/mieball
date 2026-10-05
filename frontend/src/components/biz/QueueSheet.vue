<template>
  <!-- 完整候场队列抽屉（temp/打球页原型 sh-queue 逐字）：首 4 行 .next 高亮（已排进下一场），
       每行 mono 小注（已打/ ELO）+ 右侧 tag（下一场 / 我还有 N 轮）；点行开点人抽屉（页面编排）。 -->
  <AppSheet :visible="visible" title="候场队列" hint="下四位已排进下一场 · 点人可换人 / 歇两轮 / 连战 / 退场" @close="emit('close')">
    <template v-if="rows.length">
      <view
        v-for="(r, i) in rows"
        :key="r.id"
        class="qs-row"
        :class="{ next: i < 4 }"
        @click="emit('person', r.id)"
      >
        <view class="row-av"><ChibiAvatar :chibi="r.u.chibi" :size="30" /></view>
        <view class="info">
          <view class="nm">{{ r.u.name }}<text v-if="r.u.shadow" class="badge guest">访客</text></view>
          <view class="meta">已打 {{ r.u.play }} 场 · ELO {{ r.u.elo || '—' }}</view>
        </view>
        <text v-if="r.id === U.me.id && myRound != null" class="tag tag-me">还有 {{ myRound }} 轮</text>
        <text v-else-if="i < 4" class="tag">下一场</text>
      </view>
    </template>
    <EmptyBox v-else text="全员都在场上" />
  </AppSheet>
</template>

<script setup lang="ts">
/* 队列抽屉（2.1 §3）：无本地态，读 live store 的 queue/myRound；点行 emit person 由页面开点人抽屉。 */
import { computed } from 'vue';
import AppSheet from '@/components/ui/AppSheet.vue';
import ChibiAvatar from '@/components/ui/ChibiAvatar.vue';
import EmptyBox from '@/components/ui/EmptyBox.vue';
import { useLiveStore } from '@/stores/live';
import { U } from '@/api';

defineProps({
  visible: { type: Boolean, default: false },
});
const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'person', id: number): void;
}>();

const liveStore = useLiveStore();
/** 行数据 computed 一次解析好（模板逐字段 byId 是每行多次名册线性扫描） */
const rows = computed(() => (liveStore.live?.queue ?? []).map((id) => ({ id, u: liveStore.byId(id) })));
const myRound = computed(() => liveStore.myRound);
</script>

<style lang="scss" scoped>
/* ---------- 原型 .qs-row（逐字换 tokens） ---------- */
.qs-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border-radius: 12px;
  margin-bottom: 6px;
  border: 1px solid rgba(245, 241, 232, 0.08);
  background: var(--ink2);
  cursor: pointer;
}
.qs-row.next {
  border-color: rgba(255, 212, 0, 0.4);
  background: rgba(255, 212, 0, 0.05);
}
.row-av {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--ink3);
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}
.qs-row .info {
  flex: 1;
  min-width: 0;
}
.qs-row .nm {
  font-size: 13px;
  font-weight: 600;
}
.qs-row .meta {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
  letter-spacing: 0.08em;
  margin-top: 2px;
}
.qs-row .tag {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.15em;
  color: var(--lemon);
  flex: none;
}
.qs-row .tag-me {
  color: var(--ice);
}
/* 访客徽章：形与色在 base.scss 全局类；此处只补名字右侧的位置 margin */
.badge.guest {
  margin-left: 6px;
}
</style>
