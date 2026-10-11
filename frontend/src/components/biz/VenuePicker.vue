<template>
  <view class="venue-picker">
    <!-- 1. 常用 3 馆快捷按钮行 -->
    <view class="v-quick-row">
      <view
        v-for="v in topVenues"
        :key="v"
        class="v-btn"
        :class="{ on: modelValue === v }"
        @click="selectVenue(v)"
      >
        {{ v }}
      </view>
    </view>

    <!-- 2. 搜索 / 手输输入框 -->
    <view class="v-input-wrap">
      <AppInput
        :model-value="modelValue"
        placeholder="搜场地或手输新球馆"
        @update:model-value="onInput"
      />
      <text v-if="modelValue" class="v-clear" @click="clearVenue">✕</text>
    </view>

    <!-- 3. 内联候选胶囊：打字时浮现，无多余提示字，点击填入 -->
    <view v-if="matchedVenues.length" class="v-chips-row">
      <view
        v-for="mv in matchedVenues"
        :key="mv"
        class="v-chip"
        @click="selectVenue(mv)"
      >
        📍 {{ mv }}
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
/* 场地选择器 VenuePicker（自适应推荐与防软键盘遮挡单一源）：
   - 常用 3 馆置顶直选，0 弹键盘 0 遮挡；
   - 输入框支持自由手输与模糊搜索；
   - 候选胶囊内联浮现，点击即选。 */
import { computed, onMounted, ref } from "vue";
import AppInput from "@/components/ui/AppInput.vue";
import { getTopVenues, matchVenues } from "@/utils/venues";

const props = defineProps({
  modelValue: { type: String, default: "" },
});

const emit = defineEmits<{
  (e: "update:modelValue", val: string): void;
}>();

const topVenues = ref<string[]>([]);

onMounted(() => {
  topVenues.value = getTopVenues(3);
  if (!props.modelValue && topVenues.value.length > 0) {
    emit("update:modelValue", topVenues.value[0]);
  }
});

/** 候选匹配列表（打字且有匹配时内联展示，排除完全一致的值） */
const matchedVenues = computed(() => matchVenues(props.modelValue, 3));

function selectVenue(v: string): void {
  emit("update:modelValue", v);
}

function onInput(val: string): void {
  emit("update:modelValue", val);
}

function clearVenue(): void {
  emit("update:modelValue", "");
}
</script>

<style lang="scss" scoped>
.venue-picker {
  display: flex;
  flex-direction: column;
}
.v-quick-row {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
}
.v-btn {
  flex: 1;
  min-width: 0;
  padding: 8px 4px;
  border-radius: 10px;
  border: 1px solid rgba(245, 241, 232, 0.14);
  background: var(--ink);
  color: var(--dim);
  font-size: 12px;
  text-align: center;
  cursor: pointer;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
  transition: 0.15s;
}
.v-btn.on {
  background: var(--lemon);
  color: var(--ink);
  border-color: var(--lemon);
  font-weight: 700;
}
.v-input-wrap {
  position: relative;
}
.v-clear {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--dim);
  font-size: 12px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(245, 241, 232, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 2;
}
.v-chips-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.v-chip {
  padding: 5px 10px;
  border-radius: 8px;
  background: rgba(255, 212, 0, 0.12);
  border: 1px solid rgba(255, 212, 0, 0.35);
  color: var(--lemon);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: 0.15s;
}
.v-chip:active {
  background: var(--lemon);
  color: var(--ink);
}
</style>
