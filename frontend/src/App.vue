<template>
  <!--
    文件路径：frontend/src/App.vue
    作用说明：
    1. 作为前端根组件。
    2. 当前阶段只承载路由出口，不在这里堆叠业务逻辑。
  -->
  <RouterView />
</template>

<script setup>
import { RouterView } from "vue-router";
</script>
