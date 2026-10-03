<template>
  <!-- 球员档案弹层（全产品共用：榜单/意向卡/现场队员/我的头像都唤起）。
       alpha.html:1891-1929 openProfile · P9 填充。 -->
  <SheetStub title="球员档案" phase="P9" :lines="[`userId: ${userId}`]" />
</template>

<script setup lang="ts">
defineProps({
  userId: { type: Number, required: true },
});
</script>
