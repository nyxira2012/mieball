<template>
  <!-- 签到抽屉（temp/打球页原型 sh-check 逐字 · 2.2 批2§4.3 代办枢纽）：
       段1 未到（「到场」= setCheck ok，迟到口径由 store 按开球时刻归一）
       · 段2 已到场（「代办早退」= setCheck left 落离场时刻——扫码幽灵同走这条，2.6 裁决；空降标/几点到的）
       · 段3 带访客（AppInput 称呼 + AppStepper 人数 + OptionChips 介绍人 + 带上场）
       · 段4 空降说明 NoteCard。动作直调 live store（toast 在 store）。 -->
  <AppSheet
    :visible="visible"
    title="签到 · 到场"
    hint="来没来、几点走，清清楚楚"
    @close="emit('close')"
  >
    <!-- ---------- 段1 未到 ---------- -->
    <view class="ck-sec">
      <view class="ck-t">还没到的</view>
      <template v-if="absents.length">
        <view v-for="row in absents" :key="row.id" class="ck-row">
          <view class="row-av"
            ><ChibiAvatar :chibi="row.chibi" :size="30"
          /></view>
          <view class="who">
            <view class="nm"
              >{{ row.name
              }}<text v-if="row.id === liveStore.myRowId()" class="me-badge"
                >我</text
              ><text
                v-if="liveStore.isAdmin(row.id)"
                class="badge admin nm-badge"
                >管理员</text
              ></view
            >
            <view class="st late">{{ lateTxt }}</view>
          </view>
          <view class="acts">
            <AppButton
              variant="pri"
              size="sm"
              @click="liveStore.setCheck(row.id, 'ok')"
              >到场</AppButton
            >
          </view>
        </view>
      </template>
      <EmptyBox v-else text="都到齐了" />
    </view>

    <!-- ---------- 段2 已到场（迟到/中途加入同列；早退后从本区消失） ---------- -->
    <view class="ck-sec">
      <view class="ck-t">已到场</view>
      <template v-if="arriveds.length">
        <view v-for="row in arriveds" :key="row.id" class="ck-row done">
          <view class="row-av"
            ><ChibiAvatar :chibi="row.chibi" :size="30"
          /></view>
          <view class="who">
            <view class="nm"
              >{{ row.name
              }}<text v-if="row.dropin" class="badge dropin nm-badge">空降</text
              ><text v-if="row.id === liveStore.myRowId()" class="me-badge"
                >我</text
              ><text
                v-if="liveStore.isAdmin(row.id)"
                class="badge admin nm-badge"
                >管理员</text
              ></view
            >
            <view class="st ok">{{
              row.arriveAt ? `已到 ${isoHm(row.arriveAt)} ✓` : "已到场 ✓"
            }}</view>
          </view>
          <view class="acts">
            <AppButton
              variant="ghost"
              size="sm"
              @click="liveStore.setCheck(row.id, 'left')"
              >标他先走了</AppButton
            >
          </view>
        </view>
      </template>
      <EmptyBox v-else text="还没有人到场" />
    </view>

    <!-- ---------- 段3 带访客 ---------- -->
    <view class="ck-sec">
      <view class="ck-t">带访客</view>
      <view class="ck-input">
        <AppInput v-model="gName" placeholder="访客称呼（可空，自动命名）" />
        <AppStepper v-model="gCount" :min="1" :max="6" />
      </view>
      <view class="set-row">
        <OptionChips
          :options="introOptions"
          :model-value="introId ?? undefined"
          @update:model-value="introId = $event as number"
        />
      </view>
      <AppButton
        variant="pri"
        block
        :disabled="!introOptions.length"
        @click="onBring"
        >带上场</AppButton
      >
    </view>

    <!-- ---------- 段4 空降说明 ---------- -->
    <NoteCard>
      <text class="nk-lead">空降的人不用学：</text>没报名的直接扫场上二维码 →
      填个称呼就进局——空降按正式球友计（2.2 修订⑦），积分照记、费用照常摊。
    </NoteCard>
  </AppSheet>
</template>

<script setup lang="ts">
/* 签到抽屉（2.2 §4.3 代办枢纽）：到场 = setCheck ok（迟到口径 store 按 startAt 归一、队尾、自动发牌）；
   代办早退 = setCheck left（清候场清场上+离场时刻；2.6 裁决移出名册已退役，防幽灵统一走这条）。
   带访客 = addGuests（1.3 切真：一次请求 count+称呼+担保人行 id，命名/挂账/队尾在后端）。
   介绍人 = 已到场非访客成员（选项值即名册行 id），默认「我」在册则选中。 */
import { computed, ref, watch } from "vue";
import AppSheet from "@/components/ui/AppSheet.vue";
import AppButton from "@/components/ui/AppButton.vue";
import AppInput from "@/components/ui/AppInput.vue";
import AppStepper from "@/components/ui/AppStepper.vue";
import OptionChips from "@/components/ui/OptionChips.vue";
import NoteCard from "@/components/ui/NoteCard.vue";
import EmptyBox from "@/components/ui/EmptyBox.vue";
import ChibiAvatar from "@/components/ui/ChibiAvatar.vue";
import { useLiveStore, isArrived } from "@/stores/live";
import { isoHm } from "@/utils/time";

defineProps({
  visible: { type: Boolean, default: false },
});
const emit = defineEmits<{ (e: "close"): void }>();

const liveStore = useLiveStore();

/** 未到的迟到分钟数：floor((now − 开场)/60000)，≤0 显示「未到」（2.1 §2 口径） */
const lateTxt = computed(() => {
  const g = liveStore.live?.g;
  if (!g) return "未到";
  const mins = Math.floor((Date.now() - new Date(g.startAt).getTime()) / 60000);
  return mins > 0 ? `已迟到 ${mins} 分钟` : "未到";
});

const absents = computed(() =>
  (liveStore.live?.roster ?? []).filter((p) => p.check === "absent"),
);
/** 已到场（谓词单一源 isArrived）：ok / 迟到 / 中途加入同列，早退后自动消失 */
const arriveds = computed(() =>
  (liveStore.live?.roster ?? []).filter((p) => isArrived(p.check)),
);

/* ---------- 带访客本地态：带上场后重置（名字清空、人数回 1） ---------- */
const gName = ref("");
const gCount = ref(1);
// 介绍人选中值（名册行 id）：myRowId 查无我为 null（不在名册），watch 会改选首位
const introId = ref<number | null>(liveStore.myRowId());

/** 介绍人候选：已到场（谓词 isArrived）的非访客成员；「我」在册默认选中，否则取首位 */
const introOptions = computed(() =>
  (liveStore.live?.roster ?? [])
    .filter((p) => isArrived(p.check) && !p.shadow)
    .map((p) => ({
      value: p.id,
      label: p.id === liveStore.myRowId() ? "介绍人 · 我" : p.name,
    })),
);
watch(
  introOptions,
  (opts) => {
    if (!opts.some((o) => o.value === introId.value))
      introId.value = opts[0]?.value ?? liveStore.myRowId();
  },
  { immediate: true },
);

function onBring(): void {
  // 介绍人选项值即名册行 id（watch 保证选中项总在候选里——按钮只在有候选时可点，
  // 此处判空仅类型收窄：无候选时不可达）——后端按它挂 guarantor
  if (introId.value == null) return;
  liveStore.addGuests(gCount.value, gName.value.trim(), introId.value);
  gName.value = "";
  gCount.value = 1;
}
</script>

<style lang="scss" scoped>
/* ---------- 原型 .ck-sec/.ck-t/.ck-row/.ck-input（逐字换 tokens） ---------- */
.ck-sec {
  margin-bottom: 16px;
}
.ck-t {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.2em;
  color: var(--dim);
  margin-bottom: 8px;
}
.ck-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid rgba(245, 241, 232, 0.1);
  border-radius: 12px;
  background: var(--ink2);
  margin-bottom: 6px;
}
.ck-row.done {
  opacity: 0.45;
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
.ck-row .who {
  flex: 1;
  min-width: 0;
}
.ck-row .nm {
  font-size: 13px;
  font-weight: 600;
}
.me-badge {
  display: inline-block;
  font-family: var(--mono);
  font-size: 9px;
  border: 1px solid rgba(255, 212, 0, 0.5);
  color: var(--lemon);
  border-radius: 6px;
  padding: 0 5px;
  margin-left: 6px;
  vertical-align: 1px;
}
/* 管理员/空降徽章：形与色在 base.scss 全局类；此处只补名字右侧的位置 margin */
.nm-badge {
  margin-left: 6px;
  vertical-align: 1px;
}
/* 行尾动作组：到场/代办早退竖排会撑高行，横排窄钮 */
.ck-row .acts {
  display: flex;
  gap: 6px;
  flex: none;
}
.ck-row .st {
  font-size: 10px;
  color: var(--dim);
  margin-top: 2px;
}
.ck-row .st.late {
  color: var(--coral);
}
.ck-row .st.ok {
  color: var(--ice);
}
.ck-input {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.set-row {
  margin-bottom: 12px;
}
.nk-lead {
  color: var(--lilac);
  font-weight: 600;
}
</style>
