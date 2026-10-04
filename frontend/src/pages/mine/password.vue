<template>
  <!-- 修改密码页（5.1 子页）：三个输入 + 保存。校验（原密非空 / 新密≥6 位 / 两次一致）与 toast 全在 user store。 -->
  <PageShell>
    <!-- 子页统一返回行（bills.vue 同形态） -->
    <view class="backrow" @click="goBack">◂ 返回</view>

    <view class="stag">
      <view class="kicker">Password</view>
      <view class="brand">密<text class="bem">码</text></view>
    </view>

    <NoteCard text="演示环境 · 任意原密码可通过" />

    <!-- AppInput 联合类型无 password（mock 无真实安全面），明文 text 输入即可 -->
    <AppField label="原密码">
      <AppInput v-model="oldP" placeholder="输入原密码" />
    </AppField>
    <AppField label="新密码">
      <AppInput v-model="p1" placeholder="至少 6 位" />
    </AppField>
    <AppField label="确认新密码">
      <AppInput v-model="p2" placeholder="再输一遍新密码" />
    </AppField>

    <AppButton variant="pri" block class="save" @click="save">保存</AppButton>
  </PageShell>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import PageShell from '@/components/biz/PageShell.vue';
import AppField from '@/components/ui/AppField.vue';
import AppInput from '@/components/ui/AppInput.vue';
import AppButton from '@/components/ui/AppButton.vue';
import NoteCard from '@/components/ui/NoteCard.vue';
import { useUserStore } from '@/stores/user';

const user = useUserStore();

const oldP = ref('');
const p1 = ref('');
const p2 = ref('');

/** 保存：按序拦截在 store（changePwd），本页只传值 */
function save(): void {
  user.changePwd(oldP.value, p1.value, p2.value);
}
function goBack(): void {
  uni.navigateBack();
}
</script>

<style lang="scss" scoped>
/* ---------- 子页统一返回行（mono 11px dim · :active lemon） ---------- */
.backrow {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--dim);
  padding: 8px 2px;
  cursor: pointer;
  display: inline-block;
}
.backrow:active {
  color: var(--lemon);
}

/* ---------- 头部 brand（bills.vue 同款） ---------- */
.brand {
  font-family: var(--disp);
  font-size: 34px;
  line-height: 1.04;
  margin: 6px 0 2px;
  font-weight: 700;
}
.brand .bem {
  font-style: normal;
  color: var(--lemon);
}

/* 保存钮上间距 */
.save {
  margin-top: 6px;
}
</style>
