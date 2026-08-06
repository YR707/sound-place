<script setup lang="ts">
// 阶段 1：根据 window.__TAURI_INTERNALS__ 判断是 overlay 还是主窗口
// 通过查询字符串区分：?window=overlay
const isOverlay = new URLSearchParams(window.location.search).get("window") === "overlay";
</script>

<template>
  <router-view v-if="!isOverlay" />
  <!-- overlay 窗口将在阶段 1.4 通过 overlay.vue 加载 -->
</template>

<style>
* {
  box-sizing: border-box;
}
html,
body,
#app {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
    "Microsoft YaHei", sans-serif;
}
</style>
