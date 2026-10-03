<template>
  <!-- 未成局卡 · alpha.html:919-931 deadCard() 逐字对齐（P5a）：
       局到截止人数不足自动终止后，组织者「我的局」里留的记录（整体 opacity:.75）。
       时间位固定「未成/局」两行；地点行 = 原 t · loc · 截止时 heads/min 人 · 低于最少自动终止；
       foot =「名单 N 人原样保留」chip + 恢复/撤局两个 tbtn。
       静态阶段只 emit：P5b 接 game.restoreGame / cancelSheet（alpha:927-928）。 -->
  <view class="gcard">
    <view class="gd">
      <view class="time">
        未成
        <text class="tt">局</text>
      </view>
      <view class="meta">
        <view class="name">
          <text class="title-txt">{{ game.name }}</text>
          <AppChip kind="dim">未成局</AppChip>
        </view>
        <view class="loc">{{ game.t }} · {{ game.loc }} · 截止时 {{ hs }}/{{ game.min }} 人 · 低于最少自动终止</view>
        <view class="foot">
          <AppChip>名单 {{ hs }} 人原样保留</AppChip>
          <view class="sp" />
          <view class="tbtn on-in" @click.stop="emit('restore')">↻ 恢复</view>
          <view class="tbtn on-no" @click.stop="emit('cancel')">撤局</view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
/* alpha.html:919-931 deadCard（P5a） */
import { computed } from 'vue'
import type { PropType } from 'vue'
import AppChip from '@/components/ui/AppChip.vue'
import type { Game } from '@/api/types'
import { heads } from '@/utils/format'

const props = defineProps({
  game: { type: Object as PropType<Game>, required: true },
})
const emit = defineEmits<{ (e: 'restore'): void; (e: 'cancel'): void }>()

const hs = computed(() => heads(props.game))
</script>

<style lang="scss" scoped>
/* gcard 家族样式与 GameCard.vue 同源（alpha:104-118 副本 + alpha:920 opacity:.75）；
   chip 归 AppChip。 */
.gcard {
  position: relative;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: linear-gradient(160deg, var(--ink3), var(--ink2));
  padding: 16px 16px 14px;
  margin-bottom: 12px;
  height: 108px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: center;
  overflow: hidden;
  opacity: 0.75; /* alpha:920 style="opacity:.75"（不可点击，无 pointer 光标与 :active） */
}
.gd {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}
.time {
  font-family: var(--disp);
  font-size: 30px;
  line-height: 0.95;
  color: var(--lemon);
  min-width: 64px;
  flex: none;
}
.time .tt {
  display: block;
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  letter-spacing: 0.2em;
  margin-top: 4px;
}
.meta {
  flex: 1;
  min-width: 0;
}
.name {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 2px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  line-height: 1.2;
}
.title-txt {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.loc {
  font-size: 12px;
  color: var(--dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.3;
}
.foot {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  flex-wrap: nowrap;
  overflow: hidden;
}
.sp {
  flex: 1;
}
/* 小操作按钮（alpha:339-343 .tbtn + on-in/on-no 变体） */
.tbtn {
  padding: 7px 12px;
  border-radius: 10px;
  border: 1px solid rgba(245, 241, 232, 0.16);
  background: none;
  color: var(--dim);
  font-size: 12px;
  font-weight: 700;
  transition: 0.15s;
  font-family: var(--sans);
  cursor: pointer;
  flex: none;
}
.tbtn:active {
  transform: scale(0.93);
}
.tbtn.on-in {
  background: var(--lemon);
  color: var(--ink);
  border-color: var(--lemon);
}
.tbtn.on-no {
  border-color: var(--coral);
  color: var(--coral);
  background: rgba(255, 90, 54, 0.08);
}
</style>
