<template>
  <!-- 散场残局清单（2.3 §4.9）：散场先不放行——还有在打/待确认的片时逐片强制处理，
       每片三选一：确认这场比赛的比分（pending 片开确认窗定胜负）/ 提前结束（playing 片
       开同一扇窗）/ 取消（作废）；另有「未完对局全部取消」一键。全清后「确认散场」放行，
       二次确认在页面危险确认槽（A3）。清单吃 store.sweepResidues（视图真值，A4 不自算）：
       每处理完一片响应视图落地、行随状态消失。z 序沿 AppSheet（80/90）——确认窗
       （EndSettleModal z-110）盖在它上面开同一扇窗。 -->
  <AppSheet
    :visible="visible"
    title="散场收工"
    hint="还有没处理完的对局 · 逐片确认或取消后才能收工"
    @close="emit('close')"
  >
    <template v-if="rows.length">
      <view v-for="r in rows" :key="r.courtNo" class="sw-row">
        <view class="sw-info">
          <view class="sw-nm">{{ r.name }}</view>
          <view class="sw-meta">
            <text class="st" :class="r.status">{{
              r.status === "pending" ? "待确认" : "在打"
            }}</text>
            <text class="sc">{{ r.sa }} : {{ r.sb }}</text>
          </view>
        </view>
        <view class="sw-acts">
          <view
            v-if="r.status === 'pending'"
            class="sw-act pri"
            @click="emit('confirm', r.courtId)"
            >确认比分</view
          >
          <view v-else class="sw-act pri" @click="emit('early', r.courtId)"
            >提前结束</view
          >
          <view class="sw-act danger" @click="emit('cancel', r.courtId)"
            >取消</view
          >
        </view>
      </view>
      <AppButton
        variant="ghost"
        block
        class="all-cancel"
        @click="emit('cancelAll')"
        >未完对局全部取消</AppButton
      >
    </template>
    <EmptyBox v-else text="残局已清 · 没有挂在账上的对局了" />

    <AppButton
      variant="burn"
      block
      class="end-btn"
      :disabled="rows.length > 0"
      @click="emit('end')"
      >{{ rows.length ? "还有残局 · 散场不放行" : "确认散场" }}</AppButton
    >
  </AppSheet>
</template>

<script setup lang="ts">
/* 残局清单呈现（2.3 §4.9）：无本地态——清单吃 store.sweepResidues（最近视图的
   playing/pending 片），行内动作只 emit、编排与危险确认全在页面（A3）：
   confirm/early → 开确认窗（EndSettleModal 同一扇，清扫态确认 noRedeal）；
   cancel → 页面 askConfirm 后 cancelMatch(noRedeal)；cancelAll → askConfirm 后
   sweepCancelAll；end → 页面 askConfirm「球局将收工封存」后 endGame。 */
import { computed } from "vue";
import AppSheet from "@/components/ui/AppSheet.vue";
import AppButton from "@/components/ui/AppButton.vue";
import EmptyBox from "@/components/ui/EmptyBox.vue";
import { useLiveStore } from "@/stores/live";

defineProps({
  visible: { type: Boolean, default: false },
});
const emit = defineEmits<{
  (e: "close"): void;
  (e: "confirm", courtId: number): void;
  (e: "early", courtId: number): void;
  (e: "cancel", courtId: number): void;
  (e: "cancelAll"): void;
  (e: "end"): void;
}>();

const liveStore = useLiveStore();

/** 清单行视图一次拼好：片名借本地片行（场地名本地挂），比分/状态吃视图 */
const rows = computed(() =>
  liveStore.sweepResidues.map((c) => ({
    courtNo: c.courtNo,
    courtId: c.courtId, // store 组装处预带（片号↔片序换算不下放组件）
    name:
      liveStore.live?.courts.find((x) => x.id === c.courtId)?.name ??
      `${c.courtNo}号`,
    status: c.status,
    sa: c.scoreA,
    sb: c.scoreB,
  })),
);
</script>

<style lang="scss" scoped>
.sw-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  margin-bottom: 8px;
  border: 1px solid rgba(245, 241, 232, 0.08);
  background: var(--ink2);
}
.sw-info {
  flex: 1;
  min-width: 0;
}
.sw-nm {
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sw-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 3px;
}
.sw-meta .st {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.1em;
  color: var(--dim);
}
.sw-meta .st.pending {
  color: var(--lilac);
}
.sw-meta .sc {
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 700;
  color: var(--lemon);
}
.sw-acts {
  flex: none;
  display: flex;
  gap: 6px;
}
.sw-act {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.06em;
  border: 1px solid rgba(245, 241, 232, 0.16);
  border-radius: 9px;
  padding: 6px 9px;
  color: var(--cream);
  cursor: pointer;
  white-space: nowrap;
  transition: 0.15s;
}
.sw-act:active {
  transform: scale(0.94);
}
.sw-act.pri {
  color: var(--lemon);
  border-color: rgba(255, 212, 0, 0.4);
  background: rgba(255, 212, 0, 0.06);
}
.sw-act.danger {
  color: var(--coral);
  border-color: rgba(255, 90, 54, 0.4);
  background: rgba(255, 90, 54, 0.06);
}
.all-cancel {
  margin-top: 4px;
}
.end-btn {
  margin-top: 8px;
}
</style>
