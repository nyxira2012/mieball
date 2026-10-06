<template>
  <!-- 出勤底账抽屉（§4.14）：每人几点到/几点走、访客谁带的、移出留痕——留给事后摊钱用。
       纯渲染 live.ledger 快照行（一人一行、不引用名册，被移出者行保留），散场前后都可查。 -->
  <AppSheet
    :visible="visible"
    title="出勤底账"
    hint="几点到 · 几点走 · 访客谁带的 · 移出留痕——摊钱有据"
    @close="emit('close')"
  >
    <template v-if="rows.length">
      <view v-for="r in rows" :key="r.id" class="lg-row">
        <view class="row-av">
          <ChibiAvatar :chibi="r.chibi" :size="30" />
        </view>
        <view class="info">
          <view class="nm"
            >{{ r.name
            }}<text v-if="r.dropin" class="badge dropin nm-badge">空降</text
            ><text v-if="r.removedAt" class="badge guest nm-badge">已移出</text
            ><text v-if="r.shadow && !r.removedAt" class="badge guest nm-badge"
              >访客</text
            ></view
          >
          <view class="meta">
            {{
              r.removedAt
                ? `已移出 · ${hm(r.removedAt)}`
                : r.guarantor
                  ? `${r.guarantor} 带的`
                  : r.dropin
                    ? "空降进场"
                    : ""
            }}</view
          >
        </view>
        <view class="times">
          <text class="t">到 {{ hm(r.arriveAt) }}</text>
          <text class="t">走 {{ hm(r.leftAt) }}</text>
        </view>
      </view>
    </template>
    <EmptyBox v-else text="还没有出勤记录" />
  </AppSheet>
</template>

<script setup lang="ts">
/* 底账抽屉（2.2 批4）：无本地态，读 live store 的 ledger 快照；头像借名册同 id 者
   （被移出者名册查不到 → byId 兜底空配置）。时刻 isoHm 北京墙钟（未落 = 「—」）。 */
import { computed } from "vue";
import AppSheet from "@/components/ui/AppSheet.vue";
import ChibiAvatar from "@/components/ui/ChibiAvatar.vue";
import EmptyBox from "@/components/ui/EmptyBox.vue";
import { useLiveStore } from "@/stores/live";
import { isoHm } from "@/utils/time";
import type { ChibiConfig, LedgerRow } from "@/api/types";

defineProps({
  visible: { type: Boolean, default: false },
});
const emit = defineEmits<{
  (e: "close"): void;
}>();

const liveStore = useLiveStore();
/** ISO → HH:mm，未落账「—」（组件内唯一兜底口，模板不再写三元） */
const hm = (iso?: string): string => (iso ? isoHm(iso) : "—");

/** 行视图一次解析好：底账行 + 名册头像（快照行不存 chibi——人可能被移出，名册是真源） */
const rows = computed<(LedgerRow & { chibi: ChibiConfig })[]>(() =>
  (liveStore.live?.ledger ?? []).map((r) => ({
    ...r,
    chibi: liveStore.byId(r.id).chibi,
  })),
);
</script>

<style lang="scss" scoped>
/* 行构造与 QueueSheet 同构（qs-row 换 tokens），只留本组件用到的 */
.lg-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border-radius: 12px;
  margin-bottom: 6px;
  border: 1px solid rgba(245, 241, 232, 0.08);
  background: var(--ink2);
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
.lg-row .info {
  flex: 1;
  min-width: 0;
}
.lg-row .nm {
  font-size: 13px;
  font-weight: 600;
}
.lg-row .meta {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
  letter-spacing: 0.08em;
  margin-top: 2px;
}
.times {
  flex: none;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 3px;
}
.times .t {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  letter-spacing: 0.06em;
}
/* 徽章位置 margin：形与色在 base.scss 全局家族（同 QueueSheet 口径） */
.badge.guest,
.nm-badge {
  margin-left: 6px;
}
</style>
