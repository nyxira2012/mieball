<template>
  <!-- 出勤底账抽屉（§4.14）：每人几点到/几点走、访客谁带的——留给事后摊钱用。
       行直接从最近视图 players 现推（真值单源，store 不另存平行树），散场前后都可查。 -->
  <AppSheet
    :visible="visible"
    title="出勤底账"
    hint="几点到 · 几点走 · 访客谁带的——摊钱有据"
    @close="emit('close')"
  >
    <template v-if="rows.length">
      <view v-for="r in rows" :key="r.id" class="lg-row">
        <view class="row-av">
          <AvatarBadge :url="r.avatarUrl" :size="30" />
        </view>
        <view class="info">
          <view class="nm"
            >{{ r.name
            }}<text v-if="r.dropin" class="badge dropin nm-badge">空降</text
            ><text v-if="r.shadow" class="badge guest nm-badge"
              >访客</text
            ></view
          >
          <view class="meta">
            {{
              r.guarantor ? `${r.guarantor} 带的` : r.dropin ? "空降进场" : ""
            }}
          </view>
        </view>
        <view class="times">
          <text class="t">到 {{ isoHmOrDash(r.arriveAt) }}</text>
          <text class="t">走 {{ isoHmOrDash(r.leftAt) }}</text>
        </view>
      </view>
    </template>
    <EmptyBox v-else text="还没有出勤记录" />
  </AppSheet>
</template>

<script setup lang="ts">
/* 底账抽屉（2.2 批4）：无本地态；头像借名册同 id 者（工具清单不铺卡背，A6 #12）。
   时刻 isoHm 北京墙钟（未落 = 「—」）。 */
import { computed } from "vue";
import AppSheet from "@/components/ui/AppSheet.vue";
import AvatarBadge from "@/components/ui/AvatarBadge.vue";
import EmptyBox from "@/components/ui/EmptyBox.vue";
import { useLiveStore } from "@/stores/live";
import { isoHmOrDash } from "@/utils/time";

defineProps({
  visible: { type: Boolean, default: false },
});
const emit = defineEmits<{
  (e: "close"): void;
}>();

const liveStore = useLiveStore();

/** 行视图一次解析好：视图行直推 + 担保人名（guarantorAccountId 对同视图 players
    解析，不在册回 undefined）+ 名册头像 */
const rows = computed(() =>
  (liveStore.liveView?.players ?? []).map((p) => ({
    id: p.id,
    name: p.name,
    shadow: p.guest || undefined,
    dropin: p.dropin || undefined,
    guarantor:
      p.guarantorAccountId != null
        ? liveStore.liveView?.players.find(
            (x) => x.accountId === p.guarantorAccountId,
          )?.name
        : undefined,
    arriveAt: p.arriveAt ?? undefined,
    leftAt: p.leftAt ?? undefined,
    // 头像借名册同 id 者（byId 兜底查无行 → AvatarBadge 公共款默认）
    avatarUrl: liveStore.byId(p.id).avatarUrl ?? null,
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
