<template>
  <!-- 组局表单：新建（无 gameId）/ 改局（带 gameId 复用同表单，编辑态截止只读）
       （alpha.html:1299-1398 openLaunch/lfMin/lfCap/publish · P6 填充）。
       TabBar 的 FAB 与「改信息」入口都走 ui.openSheet({type:'launch'})。 -->
  <SheetStub title="发起球局" phase="P6" :lines="[gameId != null ? `gameId: ${gameId}（改局）` : '新建']" />
</template>

<script setup lang="ts">
defineProps({
  gameId: { type: Number, default: undefined },
});
</script>
