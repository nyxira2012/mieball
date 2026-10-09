<template>
  <!-- 散场残局清单（2.3 §4.9 · 记分本地化）：散场先不放行——还有在打的片时逐片强制
       处理，每片两条路：上传比分（开本地结算窗，noRedeal=true 不排下一场）/ 取消
       （作废，后果确认在页面）；另有「未完对局全部取消」一键。全清后「确认散场」放行，
       二次确认在页面危险确认槽（A3）。清单吃 store.sweepResidues（视图真值，A4 不自算），
       行内比分吃本机账 localScores（记分本地化后服务端不记进行中比分）。每处理完一片
       响应视图落地、行随状态消失。z 序沿 AppSheet（80/90）——结算窗（EndSettleModal
       z-110）盖在它上面开窗。 -->
  <AppSheet
    :visible="visible"
    title="散场收工"
    hint="还有没处理完的对局 · 逐片上传或取消后才能收工"
    @close="emit('close')"
  >
    <template v-if="rows.length">
      <view v-for="r in rows" :key="r.courtNo" class="sw-row">
        <view class="sw-info">
          <view class="sw-nm">{{ r.name }}</view>
          <view class="sw-meta">
            <text class="st">在打</text>
            <text class="sc">{{ r.sa }} : {{ r.sb }}</text>
          </view>
        </view>
        <view class="sw-acts">
          <view class="sw-act pri" @click="upload(r.courtId)">上传比分</view>
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

    <!-- 费用亮数行（1.3 §4.5 修订②：散场确认看着屏幕亮出的数字收工——数字全吃
         视图 fee 块定值，组件不自算；费用未定亮「总价未定 · N 人」） -->
    <view v-if="feeLine" class="sw-fee">{{ feeLine }}</view>

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
/* 残局清单呈现（2.3 §4.9）：清单吃 store.sweepResidues（最近视图的非 idle 片）、
   行内比分吃本机账 localScores（无账亮 0:0）。行内动作两条：
   - 上传比分：直调 store.openSettleWindow(courtId, "upload", noRedeal=true)——
     无危险确认不走页面确认槽，开窗闸（一次一扇）在 store；
   - cancel/cancelAll/end 只 emit，编排与危险确认全在页面（A3）：cancel →
     askConfirm 后 cancelMatch(noRedeal)；cancelAll → askConfirm 后 sweepCancelAll；
     end → askConfirm「球局将收工封存」后 endGame。 */
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
  (e: "cancel", courtId: number): void;
  (e: "cancelAll"): void;
  (e: "end"): void;
}>();

const liveStore = useLiveStore();

/** 清扫态上传（§4.9-1 不排下一场不补位）：noRedeal=true 开窗，确认透传落账 */
function upload(courtId: number): void {
  liveStore.openSettleWindow(courtId, "upload", true);
}

/** 费用亮数行（1.3 §4.5 修订②）：总价定值 + 摊钱人头（后端账单口径）+ 人均；
    无视图/无 fee 块不亮（旧数据容错） */
const feeLine = computed(() => {
  const f = liveStore.liveView?.fee;
  if (!f) return "";
  return f.total != null
    ? `总价 ${f.total} · ${f.heads} 人 · 人均 ${f.perHead}`
    : `总价未定 · ${f.heads} 人`;
});

/** 清单行视图一次拼好：片名借本地片行（场地名本地挂），比分吃本机账 */
const rows = computed(() =>
  liveStore.sweepResidues.map((c) => ({
    courtNo: c.courtNo,
    courtId: c.courtId, // store 组装处预带（片号↔片序换算不下放组件）
    name:
      liveStore.live?.courts.find((x) => x.id === c.courtId)?.name ??
      `${c.courtNo}号`,
    sa: liveStore.localScores[c.courtId]?.sa ?? 0,
    sb: liveStore.localScores[c.courtId]?.sb ?? 0,
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
.sw-fee {
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
.end-btn {
  margin-top: 8px;
}
</style>
