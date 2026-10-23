<template>
  <!-- 完整候场队列抽屉（temp/打球页原型 sh-queue 逐字）：首 N 行 .next 高亮（预计序
     里排最前的下 N 位，N=每片人数，双打 4 / 单打 2——2.4 批2 size-aware），每行
     mono 小注（今晚 N 场 · DUPR 一位小数——吃名册行 tonight 战报派生真值，档案
     play 是生涯数不顶用）+ 右侧 tag（下一场 / 我还有 N 轮）；点行开点人抽屉（页面编排）。
     1.9 A6 #11：每行铺行主卡背（r 档窄条与榜单行同一配方，访客素行）；「下一场」
     高亮让位卡背——黄底撤掉，语义由黄边框+右侧「下一场」标签承担；抽屉头部
     不铺（工具面无个人印记）。 -->
  <AppSheet
    :visible="visible"
    title="候场队列"
    :hint="`下${nextN}位已排进下一场 · 点人可换人 / 歇两轮 / 连战 / 退场`"
    @close="emit('close')"
  >
    <template v-if="rows.length">
      <view
        v-for="(r, i) in rows"
        :key="r.id"
        class="qs-row"
        :class="{ next: i < nextN }"
        @click="emit('person', r.id)"
      >
        <CardBackdrop :cid="r.u.back ?? null" mode="r" />
        <view class="row-av"
          ><AvatarBadge :url="r.u.avatarUrl ?? null" :size="30"
        /></view>
        <view class="info">
          <view class="nm"
            >{{ r.u.name
            }}<text v-if="r.u.shadow" class="badge guest">访客</text
            ><text v-if="r.u.dropin" class="badge dropin nm-badge">空降</text
            ><text v-if="liveStore.isAdmin(r.id)" class="badge admin nm-badge"
              >管理员</text
            ></view
          >
          <view class="meta"
            >今晚 {{ r.u.tonight ?? 0 }} 场 · DUPR
            {{ fmtDupr1(duprOf(r.u)) }}</view
          >
        </view>
        <text
          v-if="r.id === userStore.me.id && myRound != null"
          class="tag tag-me"
          >还有 {{ myRound }} 轮</text
        >
        <text v-else-if="i < nextN" class="tag">下一场</text>
      </view>
    </template>
    <EmptyBox v-else text="全员都在场上" />
  </AppSheet>
</template>

<script setup lang="ts">
/* 队列抽屉（2.1 §3 · 2.4 批2 size-aware）：无本地态，读 live store 的 queue/myRound/rules；
   点行 emit person 由页面开点人抽屉。 */
import { computed } from "vue";
import AppSheet from "@/components/ui/AppSheet.vue";
import AvatarBadge from "@/components/ui/AvatarBadge.vue";
import CardBackdrop from "@/components/ui/CardBackdrop.vue";
import EmptyBox from "@/components/ui/EmptyBox.vue";
import { useLiveStore } from "@/stores/live";
import { useUserStore } from "@/stores/user";
import { courtSize } from "@/utils/rotate";
import { duprOf, fmtDupr1 } from "@/utils/elo";

defineProps({
  visible: { type: Boolean, default: false },
});
const emit = defineEmits<{
  (e: "close"): void;
  (e: "person", id: number): void;
}>();

const liveStore = useLiveStore();
const userStore = useUserStore();
/** 行数据 computed 一次解析好（模板逐字段 byId 是每行多次名册线性扫描） */
const rows = computed(() =>
  (liveStore.live?.queue ?? []).map((id) => ({ id, u: liveStore.byId(id) })),
);
/** 「下一场」高亮位数 = 每片人数（双打 4 / 单打 2，单一源在引擎） */
const nextN = computed(() => courtSize(liveStore.live?.rules.singles ?? false));
const myRound = computed(() => liveStore.myRound);
</script>

<style lang="scss" scoped>
/* ---------- 原型 .qs-row（逐字换 tokens）；宿主契约（CardBackdrop）：relative+hidden
   裁窄条出血、z-index:0 立层叠上下文垫负 z 卡底层（不立层会被行自己的 background 盖死） ---------- */
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
  position: relative;
  z-index: 0;
  overflow: hidden;
}
/* 「下一场」让位卡背（A6 #11）：黄底撤掉不与卡背抢对比度，高亮语义只剩黄边框
   （右侧「下一场」标签在模板里，与边框同色系承担另一半） */
.qs-row.next {
  border-color: rgba(255, 212, 0, 0.4);
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
.badge.guest,
.nm-badge {
  margin-left: 6px;
}
</style>
