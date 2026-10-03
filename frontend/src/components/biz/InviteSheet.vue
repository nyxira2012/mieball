<template>
  <!-- 邀请入局弹层（两形态，SheetHost 按 payload 分发）：
       · mode='to-game'（alpha.html:1213-1220 inviteFromGame）：局详情翻意向列表挑人邀请进该局；
       · mode='to-slot'（alpha.html:1239-1247 inviteSheet）：球员档案翻我发起的局挑一个邀请该用户。
       选中 → game.inviteUser(userId, gameId)（store 内含 toast 与 3.2 秒模拟加入，alpha:1249-1263 doInvite）→ 关弹层。 -->
  <view v-if="bodyOk" class="iv">
    <!-- ===== to-game：翻意向列表（alpha:1216-1220） ===== -->
    <template v-if="mode === 'to-game' && g">
      <!-- alpha:1216 h3：`邀请入「局短名」` -->
      <view class="t">邀请入「{{ g.name.replace(/ ·.*/, '') }}」</view>
      <!-- alpha:1217 hint -->
      <view class="hint">翻意向列表挑人 · 局会出现在 ta 的「我的局」里，点一下就加入</view>
      <!-- alpha:1218-1220 意向行（liked 优先 → 熟人优先）→ doInvite(uid, gid) -->
      <template v-if="sortedIntents.length">
        <view v-for="i in sortedIntents" :key="i.u.id" class="mrow" @click="onInvite(i.u.id, g.id)">
          <view class="mnm">
            <text v-if="i.u.liked" class="hearttag">♥</text>
            <view class="mav"><ChibiAvatar :chibi="i.u.chibi" :size="26" /></view>
            <text>{{ i.u.name }}</text>
            <text class="msub2 mright">{{ i.slots.map(slotName).join(' · ') }} · {{ freqName(i.freq) }}</text>
          </view>
        </view>
      </template>
      <!-- alpha:1220 空态 -->
      <EmptyBox v-else text="还没有人留意向" />
    </template>

    <!-- ===== to-slot：翻我发起的局（alpha:1243-1247） ===== -->
    <template v-else-if="mode === 'to-slot' && u">
      <!-- alpha:1243 h3：`邀请 ${u.name}` -->
      <view class="t">邀请 {{ u.name }}</view>
      <!-- alpha:1244 hint -->
      <view class="hint">选一个你发起的局 · 局会出现在 ta 的「我的局」里，点一下就加入</view>
      <!-- alpha:1245-1247 我发起的 open 且未成局 → doInvite(uid, g.id) -->
      <view v-for="mg in mineOpen" :key="mg.id" class="mrow" @click="onInviteSlot(mg.id)">
        <view class="mnm">
          <text>{{ mg.name }}</text>
          <text class="need mright">还差 {{ needOf(mg) }} 人</text>
        </view>
        <view class="msub2">{{ mg.t }} · {{ mg.loc }}</view>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
/* 邀请弹层 InviteSheet（alpha.html:1213-1220 inviteFromGame / 1239-1247 inviteSheet · P5b）。
   alpha:1241 mine 过滤（我发起 · open · 未成局）；alpha:1242 无局可邀 → toast + 打开发局表单（openLaunch），
   在 onMounted 等价实现（openSheet 换 payload 即完成「换内容」）。 */
import { computed, onMounted } from 'vue';
import type { PropType } from 'vue';
import ChibiAvatar from '@/components/ui/ChibiAvatar.vue';
import EmptyBox from '@/components/ui/EmptyBox.vue';
import { useGameStore } from '@/stores/game';
import { useUserStore } from '@/stores/user';
import { useUiStore } from '@/stores/ui';
import { freqName, isOrg, known, needOf, slotName } from '@/utils/format';
import type { Intent } from '@/api/types';

const props = defineProps({
  /** to-game=局详情翻意向列表拉人 / to-slot=球员档案选局邀请（SheetHost 分发契约） */
  mode: { type: String as PropType<'to-game' | 'to-slot'>, required: true },
  gameId: { type: Number, default: undefined },
  userId: { type: Number, default: undefined },
});

const game = useGameStore();
const userStore = useUserStore();
const ui = useUiStore();

/** to-game：alpha:1214 games.find */
const g = computed(() => game.games.find((x) => x.id === props.gameId) ?? null);
/** to-slot：alpha:1240 findUser */
const u = computed(() => (props.userId != null ? userStore.findUser(props.userId) : undefined));
/** 两形态的主体是否齐备（模板渲染守卫） */
const bodyOk = computed(() => (props.mode === 'to-game' ? !!g.value : !!u.value));

/** to-slot：alpha:1241 mine = 我发起 · open · 未成局（isOrg 同 utils/format 口径） */
const mineOpen = computed(() => game.games.filter((x) => isOrg(x) && x.status === 'open' && !x.dead));

/** to-game：alpha:1215 sorted（喜欢的人优先 → 熟人优先，逐字口径） */
const sortedIntents = computed<Intent[]>(() =>
  [...game.intents].sort(
    (a, b) => (b.u.liked ? 1 : 0) - (a.u.liked ? 1 : 0) || (known(b.u) ? 1 : 0) - (known(a.u) ? 1 : 0),
  ),
);

/** alpha:1242 无局可邀：toast + openLaunch（换发局表单弹层）——挂载即判定，等价 alpha 的同步 return 分支 */
onMounted(() => {
  if (props.mode === 'to-slot' && props.userId != null && !mineOpen.value.length) {
    ui.toast('你还没发起过局 · 先发一个再邀请人');
    ui.openSheet({ type: 'launch' });
  }
});

/** alpha:1249-1253 doInvite：store.inviteUser（toast + 3.2s 模拟加入）→ closeSheet */
function onInvite(uid: number, gid: number): void {
  game.inviteUser(uid, gid);
  ui.closeSheet();
}
/** to-slot 行点击：带上档案目标 userId（alpha:1245 onclick="doInvite(${uid},${g.id})"） */
function onInviteSlot(gid: number): void {
  if (props.userId == null) return;
  onInvite(props.userId, gid);
}
</script>

<style lang="scss" scoped>
/* alpha:558-561 壳层 h3/.hint 同款（SheetHost 不传壳层 title，各弹层自带，同 ProfileSheet） */
.t {
  font-family: var(--disp);
  font-size: 21px;
  margin-bottom: 4px;
}
.hint {
  font-size: 12px;
  color: var(--dim);
  margin-bottom: 16px;
}
/* alpha:347-348 意向/选局行 */
.mrow {
  border: 1px solid rgba(245, 241, 232, 0.12);
  border-radius: var(--r-md);
  background: var(--ink2);
  padding: 13px 14px;
  margin-bottom: 10px;
}
/* alpha:349 */
.mnm {
  font-size: 14px;
  font-weight: 700;
  display: flex;
  gap: 8px;
  align-items: center;
}
/* alpha:350 小头像（miniav 的 26px 圆形容器，ChibiAvatar 填充） */
.mav {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  overflow: hidden;
  flex: none;
  background: var(--ink3);
}
/* alpha:352-353 ♥ 徽标 */
.hearttag {
  font-family: var(--mono);
  font-size: 9px;
  background: rgba(255, 90, 54, 0.16);
  color: var(--coral);
  padding: 2px 7px;
  border-radius: 6px;
  flex: none;
}
/* alpha:354 */
.msub2 {
  font-size: 11px;
  color: var(--dim);
  margin-top: 3px;
}
/* alpha:1219/1246 行内右伸段（margin-left:auto；to-slot 的还差 N 人另带 mono 10px 柠檬色） */
.mright {
  margin-left: auto;
  margin-top: 0;
  text-align: right;
}
.need {
  margin-left: auto;
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 400;
  color: var(--lemon);
}
</style>
