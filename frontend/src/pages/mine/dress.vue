<template>
  <!-- 装扮页（5.1 子页）：预览大图（可切「别人看到的档案卡」效果）+ 分类装扮件 + 卡背背景 + 昵称保存。
       换件/背景即点即换（me 是 store 同源引用，全局同步换新）；昵称本地草稿，显式保存才落。 -->
  <PageShell>
    <!-- 子页统一返回行（BackRow） -->
    <BackRow />

    <view class="stag">
      <view class="kicker">Dress Up</view>
      <view class="brand">装<text class="bem">扮</text></view>
    </view>

    <!-- 预览两态：我的预览 / 别人看到的完整档案卡（与打球页名单点击同一份 ProfileSheet） -->
    <AppSeg v-model="view" :options="VIEW_OPTS" />

    <view class="preview">
      <ChibiAvatar :chibi="me.chibi" :size="140" />
    </view>
    <view v-if="isCard" class="cardwrap">
      <ProfileSheet :user-id="0" />
    </view>

    <!-- 分类装扮件（5.1「分类装扮件…即点即换即见」）：逐部件一行，变体号 chips 即点即换 -->
    <view class="parts">
      <view v-for="part in DRESS_PARTS" :key="part" class="part-row">
        <text class="part-name">{{ PART_NAMES[part] }}</text>
        <view class="variants">
          <AppChip
            v-for="i in DRESS_RANGES[part]"
            :key="i - 1"
            :kind="curVariant(part) === i - 1 ? 'ok' : 'default'"
            @click="user.setVariant(part, i - 1)"
          >{{ i - 1 }}</AppChip>
        </view>
      </view>

      <!-- 卡背背景（5.1）：换完战力页 MyPowerCard 卡背全局联动 -->
      <view class="part-row">
        <text class="part-name">卡背背景</text>
        <view class="variants">
          <AppChip
            v-for="b in CARD_BGS"
            :key="b.v"
            :kind="me.cardBg === b.v ? 'ok' : 'default'"
            @click="user.setCardBg(b.v)"
          >{{ b.n }}</AppChip>
        </view>
      </view>
    </view>

    <!-- 昵称：初值取当前名，本地草稿不即时写 store，保存才落（toast 在 store） -->
    <AppField label="昵称">
      <AppInput v-model="nameDraft" placeholder="怎么称呼你" />
    </AppField>

    <!-- 手机号（1.1 A1 档案页）：完整号只有本人可见 + 唯一钥匙提示；手机号不可自行换（人工） -->
    <AppField v-if="session.account?.phone" label="手机号">
      <view class="phonerow">
        <text class="phone">{{ session.account.phone }}</text>
        <text class="phint">唯一钥匙 · 换号先联系平台客服</text>
      </view>
    </AppField>

    <AppButton variant="pri" block class="save" @click="onSave">保存</AppButton>

    <!-- 5.1「未来可能付费（如头像）」预告 -->
    <NoteCard class="note" text="头像与背景未来可能上架付费装扮 · 当前全部免费" />
  </PageShell>
</template>

<script setup lang="ts">
/* 装扮页（5.1 子页）：我的脸面。数据/动作全在 user store（setVariant 即点即换、saveProfile toast 内聚），
   本页只做选择接线与预览展示。 */
import { computed, ref } from 'vue';
import PageShell from '@/components/biz/PageShell.vue';
import BackRow from '@/components/biz/BackRow.vue';
import ChibiAvatar from '@/components/ui/ChibiAvatar.vue';
import AppSeg from '@/components/ui/AppSeg.vue';
import AppChip from '@/components/ui/AppChip.vue';
import AppField from '@/components/ui/AppField.vue';
import AppInput from '@/components/ui/AppInput.vue';
import AppButton from '@/components/ui/AppButton.vue';
import NoteCard from '@/components/ui/NoteCard.vue';
import ProfileSheet from '@/components/biz/ProfileSheet.vue';
import { useUserStore } from '@/stores/user';
import { DRESS_PARTS, DRESS_RANGES, PART_NAMES, type DressPart } from '@/utils/chibi';
import { useSessionStore } from '@/stores/session';
import type { CardBg } from '@/api/types';

const user = useUserStore();
const session = useSessionStore();
/** 我 = store 同一份可变引用，换件/背景/改名全产品同步 */
const me = computed(() => user.me);

/** 保存：登录态走后端（昵称+当前小人+卡背一次落云），游客回落本地演示保存（session 内分流） */
function onSave(): void {
  void session.saveProfile({ nickname: nameDraft.value, chibi: { ...me.value.chibi }, card_bg: me.value.cardBg });
}

/* 预览两态（string|number 对齐 AppSeg v-model 联合类型，IntentFormSheet ifFreq 同法） */
const view = ref<string | number>('me');
const VIEW_OPTS = [
  { value: 'me', label: '我的预览' },
  { value: 'card', label: '档案卡效果' },
];
const isCard = computed(() => view.value === 'card');

/** 部件当前变体号（chibi 字段可缺省，缺省按 0） */
function curVariant(part: DressPart): number {
  return me.value.chibi[part] ?? 0;
}

/** 卡背背景全集（CardBg 四值，alpha:1844 bg-*；n 为 chips 展示名） */
const CARD_BGS: { v: CardBg; n: string }[] = [
  { v: 'neon', n: '霓虹' },
  { v: 'gold', n: '鎏金' },
  { v: 'cyber', n: '赛博' },
  { v: 'aurora', n: '极光' },
];

/** 昵称草稿 */
const nameDraft = ref(me.value.name);
</script>

<style lang="scss" scoped>
/* ---------- 头部 brand：版式走全局 .brand 类，只补 700 加粗（bills 同款） ---------- */
.brand {
  font-weight: 700;
}

/* ---------- 预览区大卡：140px 小人居中，卡面造型与 mecard 同族 ---------- */
.preview {
  margin-top: 14px;
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  background: linear-gradient(150deg, var(--ink3), var(--ink2));
  padding: 22px 0;
  display: flex;
  justify-content: center;
}
/* 档案卡效果：ProfileSheet 内嵌展示（内容自带标题/分数/意向行） */
.cardwrap {
  margin-top: 10px;
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  background: var(--ink2);
  padding: 16px;
}

/* ---------- 装扮件行：左部件名（10px mono dim）+ 右变体 chips ---------- */
.parts {
  margin-top: 16px;
}
.part-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 2px;
  border-bottom: 1px solid rgba(245, 241, 232, 0.07);
}
.part-row:first-child {
  border-top: 1px solid rgba(245, 241, 232, 0.07);
}
.part-name {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.18em;
  color: var(--dim);
  min-width: 60px;
  flex: none;
}
.variants {
  flex: 1;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

/* 昵称区与保存钮间距 */
.save {
  margin-top: 6px;
}
.note {
  margin-top: 14px;
}

/* 手机号行（1.1 档案页：本人可见完整号 + 唯一钥匙提示） */
.phonerow {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px 0;
}
.phone {
  font-family: var(--mono);
  font-size: 14px;
  letter-spacing: 1px;
}
.phint {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
}
</style>
