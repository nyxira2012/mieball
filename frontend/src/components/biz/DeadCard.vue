<template>
  <!-- 未成局卡 · alpha.html:919-931 deadCard 对齐：
       terminated（未成局）：局到截止人数不足自动终止后，组织者「我的局」里留的记录（整体 opacity:.75），
         时间位固定「未成/局」两行；地点行 = 开打时刻 · 场馆 · 截止时 heads/min 人 · 低于最少自动终止；
         foot =「名单 N 人原样保留」chip + 恢复/撤局两个 tbtn。
       pending（待处置，4.9）：恢复后的局等组织者处置，foot 换成 锁定必打/撤局 两个处置出口，
         处置完局离开待处置区回正常列表。同族一卡两态（分派见 utils/format deadRowKind）。 -->
  <view class="gcard">
    <view class="gd">
      <view class="time">
        {{ pending ? '待处' : '未成' }}
        <text class="tt">{{ pending ? '置' : '局' }}</text>
      </view>
      <view class="meta">
        <view class="name">
          <text class="title-txt">{{ game.name }}</text>
          <AppChip kind="dim">{{ pending ? '待处置' : '未成局' }}</AppChip>
        </view>
        <view class="loc">
          <template v-if="pending">原定 {{ isoDay(game.startAt) }} {{ isoHm(game.startAt) }} · {{ game.venueName }} · 等你处置：锁必打或撤局后回正常列表</template>
          <template v-else>{{ isoDay(game.startAt) }} {{ isoHm(game.startAt) }} · {{ game.venueName }} · 截止时 {{ game.heads }}/{{ game.minPlayers }} 人 · 低于最少自动终止</template>
        </view>
        <view class="foot">
          <AppChip>名单 {{ game.heads }} 人原样保留</AppChip>
          <view class="sp" />
          <!-- pending 的「锁定必打」进订场面板（空锁二段确认 + 登记订场同一入口，4.7/4.9） -->
          <view v-if="pending" class="tbtn on-in" @click.stop="emit('lock')">🔒 锁定必打</view>
          <view v-else class="tbtn on-in" @click.stop="emit('restore')">↻ 恢复</view>
          <view class="tbtn on-no" @click.stop="emit('cancel')">撤局</view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
/* alpha.html:919-931 deadCard（P5a）；pending 态为 1.2 新增（4.9 待处置）。 */
import type { PropType } from 'vue'
import AppChip from '@/components/ui/AppChip.vue'
import type { Game } from '@/api/types'
import { isoDay, isoHm } from '@/utils/time'

defineProps({
  game: { type: Object as PropType<Game>, required: true },
  /** true = 恢复后的待处置态：锁必打/撤局两出口（4.9）；false = 未成局：恢复/撤局 */
  pending: { type: Boolean, default: false },
})
const emit = defineEmits<{ (e: 'restore'): void; (e: 'lock'): void; (e: 'cancel'): void }>()
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
/* 小操作按钮走全局 .tbtn/.tbtn.on-in/.tbtn.on-no（base.scss 收源） */
</style>
