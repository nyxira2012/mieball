<template>
  <view class="page-shell">
    <!-- ============ 排版类 ============ -->
    <view class="stag">
      <view class="kicker">Pickle · Dev</view>
      <view class="h-disp brand-demo">组件试衣间 <em>STYLE</em></view>
      <view class="sub">P1 · 自建组件库全变体陈列 · 仅开发用（P12 删）</view>
    </view>

    <!-- ============ 跑马灯 ============ -->
    <SectionTitle title="Ticker 跑马灯" more="26s 循环" />
    <Ticker :items="tickerItems" />

    <!-- ============ 按钮 ============ -->
    <SectionTitle title="Button 按钮" more="5 变体 × 2 尺寸" />
    <view class="row wrap">
      <AppButton>默认</AppButton>
      <AppButton variant="pri">主要</AppButton>
      <AppButton variant="burn">燃烧</AppButton>
      <AppButton variant="ghost">幽灵</AppButton>
    </view>
    <view class="row">
      <AppButton variant="pri" block>通栏主要（blk）</AppButton>
    </view>
    <view class="row wrap">
      <AppButton variant="pri" size="sm">小号 pri</AppButton>
      <AppButton variant="burn" size="sm">小号 burn</AppButton>
      <AppButton variant="ghost" size="sm">小号 ghost</AppButton>
      <AppButton size="sm" disabled>禁用态</AppButton>
    </view>

    <!-- ============ Chips ============ -->
    <SectionTitle title="Chip 状态胶囊" more="4 态" />
    <view class="row wrap">
      <AppChip text="剩 3 坑" />
      <AppChip kind="hot" text="即将开始" />
      <AppChip kind="full" text="满员候补" />
      <AppChip kind="ok" text="ELO 1518" />
    </view>

    <!-- ============ Roletag ============ -->
    <SectionTitle title="Roletag 角色标签" more="3 态" />
    <view class="row wrap">
      <AppChip kind="org" text="我发起" />
      <AppChip kind="inv" text="被邀请" />
      <AppChip kind="dim" text="已结束" />
    </view>

    <!-- ============ 段位徽章 / 近 5 场 ============ -->
    <SectionTitle title="TierBadge & Last5Dots" more="5 段 / W-L 点" />
    <view class="row wrap gap16">
      <view class="cell"><TierBadge tier="SS" /></view>
      <view class="cell"><TierBadge tier="S" /></view>
      <view class="cell"><TierBadge tier="A" /></view>
      <view class="cell"><TierBadge tier="B" /></view>
      <view class="cell"><TierBadge tier="C" /></view>
      <view class="cell"><Last5Dots :results="['W', 'L', 'W', 'W', 'L']" /></view>
    </view>

    <!-- ============ 头像 ============ -->
    <SectionTitle title="ChibiAvatar" more="4 发型 × 4 表情" />
    <view class="av-grid">
      <view v-for="(cfg, i) in gridChibis" :key="i" class="av-cell">
        <ChibiAvatar :chibi="cfg" :size="56" />
        <text class="av-cap">h{{ cfg.hair }}·f{{ cfg.face }}</text>
      </view>
    </view>
    <view class="sub" style="margin: 10px 2px 8px">配饰：0 无 / 1 眼镜 / 2 发带</view>
    <view class="av-grid">
      <view v-for="(cfg, i) in accChibis" :key="i" class="av-cell">
        <ChibiAvatar :chibi="cfg" :size="56" />
        <text class="av-cap">acc{{ cfg.acc }}</text>
      </view>
    </view>

    <SectionTitle title="AvatarStack 名单叠层" more="前 5 + +N" />
    <view class="row">
      <AvatarStack :avatars="stackChibis" :max="5" />
    </view>

    <!-- ============ 表单 ============ -->
    <SectionTitle title="Field / Input 表单" more="inp · textarea" />
    <AppField label="局名">
      <AppInput v-model="form.name" placeholder="不填则按「时间·地点」自动起名" />
    </AppField>
    <AppField label="说明">
      <AppInput v-model="form.note" type="textarea" :maxlength="80" placeholder="写点玩法、规矩、福利…" />
    </AppField>
    <view class="row2-demo">
      <AppField label="最少人数">
        <AppStepper v-model="form.min" :min="2" :max="15" />
      </AppField>
      <AppField label="最多人数">
        <AppStepper v-model="form.cap" :min="3" :max="16" />
      </AppField>
    </view>

    <!-- ============ Seg / Stepper 独立演示 ============ -->
    <SectionTitle title="Seg 分段选择" more="Elo / NTRP 样例" />
    <AppSeg v-model="segVal" :options="segOptions" />

    <SectionTitle title="Stepper 步进器" />
    <view class="row">
      <view style="width: 200px"><AppStepper v-model="stepVal" :min="0" :max="3" /></view>
      <text class="sub">带人 0-3</text>
    </view>

    <!-- ============ Toggle ============ -->
    <SectionTitle title="Toggle 开关行" />
    <AppToggle v-model="togVal" title="迟到自动排队尾" desc="开了之后迟到的人不会插队" />

    <!-- ============ OptionChips / FilterChips ============ -->
    <SectionTitle title="OptionChips 单选组" more="crow/cbtn" />
    <OptionChips v-model="crowVal" :options="['今晚 19:00', '周六 14:00', '下周三 20:00', '自定义…']" />

    <SectionTitle title="FilterChips 横滚筛选" more="fchips（可多选）" />
    <FilterChips v-model="fVals" multiple :options="['全部', '工体', '望京', '五棵松', '亮马河', '亦庄', '北苑']" />

    <!-- ============ Empty / NoteCard ============ -->
    <SectionTitle title="EmptyBox / NoteCard" />
    <EmptyBox text="这里还没有球局" />
    <view style="height: 14px" />
    <NoteCard>
      <text>人均按<b>当前人数</b>摊，截止时不足最少人数按最少摊。</text>
    </NoteCard>

    <!-- ============ 抽屉 / Toast / 撒花 触发演示 ============ -->
    <SectionTitle title="Sheet / Toast / Confetti" more="点按钮触发" />
    <view class="row wrap">
      <AppButton variant="pri" @click="sheetVisible = true">开抽屉</AppButton>
      <AppButton variant="burn" @click="fireToast">弹 Toast</AppButton>
      <AppButton variant="ghost" @click="cfRef?.burst(46)">撒花 46</AppButton>
    </view>

    <!-- 抽屉：本地 ref 控 props 演示（P3 由 SheetHost + ui store 接线） -->
    <AppSheet :visible="sheetVisible" title="演示抽屉" hint="grab / 黄描边 / 遮罩点击关闭" @close="sheetVisible = false">
      <view class="row wrap" style="margin-bottom: 12px">
        <AppChip kind="ok" text="槽位内容区" />
        <AppChip text="标题 + hint props" />
      </view>
      <AppButton block variant="ghost" @click="sheetVisible = false">关 闭</AppButton>
    </AppSheet>

    <AppToast :message="toastMsg" :visible="toastVisible" />
    <Confetti ref="cfRef" />
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import ChibiAvatar from '@/components/ui/ChibiAvatar.vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppChip from '@/components/ui/AppChip.vue'
import TierBadge from '@/components/ui/TierBadge.vue'
import Last5Dots from '@/components/ui/Last5Dots.vue'
import AvatarStack from '@/components/ui/AvatarStack.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppField from '@/components/ui/AppField.vue'
import AppStepper from '@/components/ui/AppStepper.vue'
import AppSeg from '@/components/ui/AppSeg.vue'
import OptionChips from '@/components/ui/OptionChips.vue'
import FilterChips from '@/components/ui/FilterChips.vue'
import AppToggle from '@/components/ui/AppToggle.vue'
import AppSheet from '@/components/ui/AppSheet.vue'
import AppToast from '@/components/ui/AppToast.vue'
import Confetti from '@/components/ui/Confetti.vue'
import Ticker from '@/components/ui/Ticker.vue'
import SectionTitle from '@/components/ui/SectionTitle.vue'
import EmptyBox from '@/components/ui/EmptyBox.vue'
import NoteCard from '@/components/ui/NoteCard.vue'
import type { ChibiConfig } from '@/utils/chibi'
import type { TickerItem } from '@/components/ui/Ticker.vue'

/* ---- 跑马灯样例（结构同 alpha:938-939，b 前缀 + 正文 + 珊瑚 ●） ---- */
const tickerItems: TickerItem[] = [
  { tag: 'NOW', text: '周四夜战进行中' },
  { tag: 'ELO', text: '反手王卫冕 1421' },
  { tag: 'INTENT', text: '意向池里攒下一局' },
  { tag: 'SHARE', text: '局卡一键转群拉人' },
]

/* ---- 头像网格：4 发型(碗盖/丸子/刺头/长发) × 4 表情(微笑/开心/墨镜/专注) ---- */
const gridChibis: ChibiConfig[] = []
for (let face = 0; face < 4; face++) {
  for (let hair = 0; hair < 4; hair++) {
    gridChibis.push({ skin: (hair + face) % 4, hair, hc: hair, shirt: (hair * 2 + face) % 8, face, acc: 0 })
  }
}
/* 配饰 0/1/2 */
const accChibis: ChibiConfig[] = [
  { skin: 0, hair: 0, hc: 0, shirt: 0, face: 0, acc: 0 },
  { skin: 1, hair: 1, hc: 2, shirt: 2, face: 0, acc: 1 },
  { skin: 2, hair: 5, hc: 0, shirt: 4, face: 1, acc: 2 },
]
/* 叠层样例：8 人，展示 前5 + +3 */
const stackChibis: ChibiConfig[] = Array.from({ length: 8 }, (_, i) => ({
  skin: i % 4,
  hair: i % 6,
  hc: (i * 2) % 6,
  shirt: i % 8,
  face: i % 4,
  acc: i % 3,
}))

/* ---- 表单演示状态 ---- */
const form = ref({ name: '', note: '', min: 4, cap: 8 })
const segVal = ref<string | number>('elo')
const segOptions = [
  { value: 'elo', label: 'ELO', sub: '默认分制' },
  { value: 'ntrp', label: 'NTRP', sub: '水平分级' },
]
const stepVal = ref(0)
const togVal = ref(true)
const crowVal = ref<string | number>('今晚 19:00')
const fVals = ref<Array<string | number>>(['全部'])

/* ---- 抽屉 / Toast / 撒花 演示（本地 ref 控 props；P3 换 ui store 接线） ---- */
const sheetVisible = ref(false)
const toastMsg = ref('')
const toastVisible = ref(false)
let toastTimer: ReturnType<typeof setTimeout> | null = null
const fireToast = () => {
  toastMsg.value = '已复制局卡 · 去群里喊人吧'
  toastVisible.value = true
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toastVisible.value = false), 2200) // 同 alpha:835 2.2s 自动收起
}
const cfRef = ref<InstanceType<typeof Confetti> | null>(null)
</script>

<style lang="scss" scoped>
/* 页面容器 padding 同 alpha:75-76 .page（safe-area 顶距 + nav-h 底距） */
.page-shell {
  padding: calc(env(safe-area-inset-top) + 14px) 18px calc(var(--nav-h) + env(safe-area-inset-bottom) + 86px);
  min-height: 100vh;
  box-sizing: border-box;
}
.brand-demo {
  font-family: var(--disp);
  font-size: 34px;
  line-height: 1.04;
  margin: 6px 0 2px;
}
.brand-demo em {
  font-style: normal;
  color: var(--lemon);
}
.row {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 12px;
}
.row.wrap {
  flex-wrap: wrap;
}
.gap16 {
  gap: 16px;
}
.cell {
  display: inline-flex;
  align-items: center;
}
.av-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 12px;
}
.av-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.av-cap {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
  letter-spacing: 0.1em;
}
.row2-demo {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
</style>
