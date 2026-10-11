<template>
  <!-- 战报子页（2.6 §4.2）：从打球记录 → 局详情「查看战报」点进，与散场当场门牌
       同貌——同一 LiveRecap 组件天然同貌。纯读：apiLiveView 直拉，不经 ensureLive
       开账流（回看不是续摊）；普通子页导航（系统返回可用），页上「完成」=返回来路。
       未散场给中性提示；拉不到先探局存在性（§4.6 句面诚实：live 404 两成因——
       局在但从没开过账不说「已被撤销」，真没有才死链句），都可返回，不白屏。 -->
  <PageShell bare>
    <!-- 加载灰块（A2）：沿现场页骨架长相，不白屏 -->
    <template v-if="booting">
      <view class="skel-wrap" aria-hidden="true">
        <view class="sk sk-t" />
        <view class="sk sk-card" />
        <view class="sk sk-card d1" />
        <view class="sk sk-bar" />
      </view>
    </template>

    <!-- 战报门牌（200 且已散场）：完成=返回来路，分享同现场门牌；door=page 不给
         去向提示行（从记录进来的，指路是绕圈话） -->
    <template v-else-if="view">
      <LiveRecap
        :view="view"
        door="page"
        @complete="goBack"
        @share="onShare"
        @meet="goMeet"
      />
    </template>

    <!-- 未散场（或局在但从没开过账）：战报还没定格，诚实句不冒充 -->
    <template v-else-if="notEnded">
      <view class="dead-wrap">
        <EmptyBox>
          <view>球局还没散场 · 战报等打完才有</view>
          <AppButton variant="ghost" size="sm" class="back-btn" @click="goBack"
            >返回</AppButton
          >
        </EmptyBox>
      </view>
    </template>

    <!-- 404/断网：死链态同款句 + 重试/返回（断网的解药是重试，真死局只剩返回） -->
    <template v-else>
      <view class="dead-wrap">
        <EmptyBox>
          <view>{{ DEAD_LINK_MSG }}</view>
          <view class="dl-btns">
            <AppButton
              variant="ghost"
              size="sm"
              class="flex1"
              @click="fetchView"
              >重试</AppButton
            >
            <AppButton variant="pri" size="sm" class="flex1" @click="goBack"
              >返回</AppButton
            >
          </view>
        </EmptyBox>
      </view>
    </template>
  </PageShell>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import PageShell from "@/components/biz/PageShell.vue";
import AppButton from "@/components/ui/AppButton.vue";
import EmptyBox from "@/components/ui/EmptyBox.vue";
import LiveRecap from "@/components/biz/LiveRecap.vue";
import { apiLiveView, toLiveView } from "@/api/live";
import { apiGameDetail } from "@/api/games";
import type { LiveView } from "@/api/types";
import { shareLink } from "@/utils/share";
import { liveShareUrl } from "@/utils/deeplink";
import { DEAD_LINK_MSG, RECAP_COPY_MSG } from "@/utils/recap";
import { goBackOrMeet, goMeet } from "@/utils/nav";

const view = ref<LiveView | null>(null);
const booting = ref(true);
/** 200 但未散场（或局在但从没开过账）：战报还没落，不亮 LiveRecap（§4.2） */
const notEnded = ref(false);
let gameId = 0;

/** 直拉定格视图（纯读，不走 ensureLive 开账流）：ended 才渲染门牌；
    拉不到（404/断网）不 toast——先探局存在性再定落点，探不到才落死链态 */
async function fetchView(): Promise<void> {
  if (!gameId) return;
  booting.value = true;
  notEnded.value = false;
  view.value = null;
  try {
    const v = toLiveView(await apiLiveView(gameId));
    if (v.ended) view.value = v;
    else notEnded.value = true;
  } catch {
    /* 探局存在性是为句面诚实（live 404 两成因）：局在但从没开过账时说「已被撤销」
       是说假话 → 探到局复用未散场中性页；探不到（game_not_found/断网）落死链态，
       重试钮即断网出口，不新增状态机 */
    try {
      await apiGameDetail(gameId);
      notEnded.value = true;
    } catch {
      /* 死链态兜底（下方模板分支） */
    }
  } finally {
    booting.value = false;
  }
}

onLoad((options) => {
  const raw = (options as Record<string, string | undefined> | undefined)?.id;
  const n = raw != null ? Number(raw) : NaN;
  gameId = Number.isFinite(n) ? n : 0;
  if (!gameId) {
    booting.value = false; // 无 id 不发请求，直接落死链态
    return;
  }
  void fetchView();
});

/** 完成＝退出这页回到来路（§4.2 普通子页；系统返回同效）；
    URL 被收藏/转发冷开时栈无底——兜底切约球页（nav 契约，BackRow 同款） */
function goBack(): void {
  goBackOrMeet();
}

/** 分享（§4.3 链接任何人可看）：链接落点=现场页回看态；兜底提示带知情小字 */
function onShare(): void {
  if (!view.value) return;
  void shareLink(liveShareUrl(gameId), "球局战报", undefined, RECAP_COPY_MSG);
}
</script>

<style lang="scss" scoped>
/* 骨架灰块：.skel-wrap/.sk 族全局类（base.scss 单一源，沿现场页长相） */

/* 提示页（未散场/死链）：自补壳层边距（同现场页 .empty-wrap 口径） */
.dead-wrap {
  padding: calc(env(safe-area-inset-top) + 60px) 18px;
}
.back-btn {
  margin-top: 16px;
}
.dl-btns {
  display: flex;
  gap: 10px;
  margin-top: 16px;
}
.flex1 {
  flex: 1;
}
</style>
