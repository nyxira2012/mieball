<template>
  <!-- 邀请入局弹层（两形态，SheetHost 按 payload 分发）：
       · mode='to-game'（alpha.html:1213-1220 inviteFromGame）：局详情翻意向列表挑人邀请进该局；
       · mode='to-slot'（alpha.html:1239-1247 inviteSheet）：球员档案翻我发起的局挑一个邀请该用户。
       选中 → game.inviteUser(gameId, accountId)（toast 在 store）→ 关弹层。
       1.2 调用点适配：意向吃真接口新形状（known 打过徽章/已邀标）；
       已邀靠后排序单一源=后端（未邀在前、已邀靠后，各自 updated_at 倒序），前端保持该序不重排。 -->
  <view v-if="bodyOk" class="iv">
    <!-- ===== to-game：翻意向列表（alpha:1216-1220） ===== -->
    <template v-if="mode === 'to-game' && g">
      <view class="sheet-t">邀请入「{{ g.name.replace(/ ·.*/, "") }}」</view>
      <view class="sheet-hint"
        >翻意向列表挑人 · 局会出现在 ta 的「我的局」里，点一下就加入</view
      >
      <!-- 后端已排未邀在前、已邀靠后（updated_at 倒序），前端保持该序；
           自己与已在本局的人不进挑人列表（见 script pickable，视角减法） -->
      <template v-if="pickable.length">
        <view
          v-for="i in pickable"
          :key="i.account.id"
          class="mrow"
          @click="onInvite(g.id, i.account.id)"
        >
          <view class="mnm">
            <view class="mav"
              ><ChibiAvatar :chibi="i.account.chibi" :size="26"
            /></view>
            <text>{{ i.account.nickname }}</text>
            <AppChip v-if="i.known" kind="dim">打过</AppChip>
            <AppChip v-if="i.invited" kind="full">已邀</AppChip>
            <text class="msub2 mright"
              >{{ i.slots.map(slotName).join(" · ") }} ·
              {{ freqName(i.frequency) }}</text
            >
          </view>
        </view>
      </template>
      <EmptyBox v-else :text="inviteEmptyText" />
    </template>

    <!-- ===== to-slot：翻我发起的局（alpha:1243-1247） ===== -->
    <template v-else-if="mode === 'to-slot' && u">
      <view class="sheet-t">邀请 {{ u.name }}</view>
      <view class="sheet-hint"
        >选一个你发起的局 · 局会出现在 ta 的「我的局」里，点一下就加入</view
      >
      <view
        v-for="mg in mineOpen"
        :key="mg.id"
        class="mrow"
        @click="onInvite(mg.id, props.userId!)"
      >
        <view class="mnm">
          <text>{{ mg.name }}</text>
          <text class="need mright">还差 {{ mg.slotsLeft }} 人</text>
        </view>
        <view class="msub2"
          >{{ isoDay(mg.startAt) }} {{ isoHm(mg.startAt) }} ·
          {{ mg.venueName }}</view
        >
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
/* 邀请弹层 InviteSheet（alpha.html:1213-1247 · P5b；1.2 调用点适配）。
   to-slot 无局可邀 → toast + 打开发局表单（openSheet 换 payload 即完成「换内容」）。 */
import { computed, onMounted, ref } from "vue";
import type { PropType } from "vue";
import AppChip from "@/components/ui/AppChip.vue";
import ChibiAvatar from "@/components/ui/ChibiAvatar.vue";
import EmptyBox from "@/components/ui/EmptyBox.vue";
import { useGameStore } from "@/stores/game";
import { useUserStore } from "@/stores/user";
import { useUiStore } from "@/stores/ui";
import { freqName, slotName } from "@/utils/format";
import { isoDay, isoHm } from "@/utils/time";
import { errText } from "@/api/http";

const props = defineProps({
  /** to-game=局详情翻意向列表拉人 / to-slot=球员档案选局邀请（SheetHost 分发契约） */
  mode: { type: String as PropType<"to-game" | "to-slot">, required: true },
  gameId: { type: Number, default: undefined },
  userId: { type: Number, default: undefined },
});

const game = useGameStore();
const userStore = useUserStore();
const ui = useUiStore();
const busy = ref(false);

/** to-game：链接直达的局走 store.current */
const g = computed(() =>
  props.gameId != null ? game.findGame(props.gameId) : null,
);
/** to-slot：alpha:1240 findUser */
const u = computed(() =>
  props.userId != null ? userStore.findUser(props.userId) : undefined,
);
/** 两形态的主体是否齐备（模板渲染守卫） */
const bodyOk = computed(() =>
  props.mode === "to-game" ? !!g.value : !!u.value,
);

/** to-slot：我发起 · 还在报名中的局 */
const mineOpen = computed(() =>
  game.myGames.filter((x) => !!x.my?.isOrganizer && x.status === "open"),
);

/** to-game 挑人：全量意向簿减去自己（给自己发邀请是胡闹）与已在本局的人
    （报名/候补再邀是空动作、还会错标「已邀」）——与约球页意向区同口径的视角减法 */
const pickable = computed(() => {
  const inGame = new Set((g.value?.entries ?? []).map((e) => e.account.id));
  return game.intents.filter(
    (i) => i.account.id !== userStore.me.id && !inGame.has(i.account.id),
  );
});
/** 空态两分：意向簿真空 / 有但全在局里——同一条出路（分享链接拉人），两句都说实话 */
const inviteEmptyText = computed(() =>
  game.intents.length
    ? "留意向的都已经在局里了 · 把链接分享出去拉新球友"
    : "还没有人留意向 · 把局链接分享出去拉人",
);

/** alpha:1242 无局可邀：toast + openLaunch（换发局表单弹层）——挂载即判定。
    to-game 打开即拉意向：面板吃 store.intents，但只有约球页 onShow 预载过，
    直达 detail（分享链接/刷新）时是空的，不拉会误显空态。 */
onMounted(() => {
  if (
    props.mode === "to-slot" &&
    props.userId != null &&
    !mineOpen.value.length
  ) {
    ui.toast("你还没发起过局 · 先发一个再邀请人");
    ui.openSheet({ type: "launch" });
    return;
  }
  if (props.mode === "to-game")
    game.loadIntents().catch((e) => ui.toast(errText(e)));
});

/** doInvite：成功关弹层（toast 在 store）；失败 toast 留在弹层可重试 */
async function onInvite(gid: number, uid: number): Promise<void> {
  if (busy.value) return;
  busy.value = true;
  try {
    await game.inviteUser(gid, uid);
    ui.closeSheet();
  } catch (e) {
    ui.toast(errText(e));
  } finally {
    busy.value = false;
  }
}
</script>

<style lang="scss" scoped>
/* 壳层标题/hint 走全局 .sheet-t/.sheet-hint（base.scss 收源） */
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
/* alpha:352-353 ♥ 徽标位沿用为徽章行距 */
.msub2 {
  font-size: 11px;
  color: var(--dim);
  margin-top: 3px;
}
/* alpha:1219/1246 行内右伸段（margin-left:auto） */
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
