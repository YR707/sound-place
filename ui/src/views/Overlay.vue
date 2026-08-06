<script setup lang="ts">
// 阶段 1.4：占位波纹条 + 编辑模式拖拽手柄
// 实际音频事件驱动绘制将在阶段 3 实现

import { ref, onMounted, onUnmounted } from "vue";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { invoke } from "@tauri-apps/api/core";
import { getCurrentWebview } from "@tauri-apps/api/webview";

// 编辑模式（控制面板通过 enter_edit_mode / exit_edit_mode 切换）
const editMode = ref(false);

// 波纹组位置（百分比，0-100）
const posX = ref(50);
const posY = ref(50);

// 拖拽状态
const dragging = ref(false);
const dragStart = ref({ x: 0, y: 0, posX: 0, posY: 0 });

// 占位：模拟一个事件峰值（阶段 3 将替换为真实事件）
const placeholderPeak = ref({ left: 0.5, right: 0.5, intensity: 0.0 });

let unlistenEditMode: UnlistenFn | null = null;

onMounted(async () => {
  // 监听编辑模式切换
  unlistenEditMode = await listen<boolean>("edit-mode", (event) => {
    editMode.value = event.payload;
  });

  // 设置 overlay 窗口为全屏覆盖（占满屏幕）
  const win = await getCurrentWebview();
  // 阶段 1：仅占位，不做位置计算
  void win;
});

onUnmounted(() => {
  if (unlistenEditMode) unlistenEditMode();
});

// 拖拽处理
function onDragStart(e: MouseEvent) {
  if (!editMode.value) return;
  dragging.value = true;
  dragStart.value = {
    x: e.screenX,
    y: e.screenY,
    posX: posX.value,
    posY: posY.value,
  };
  e.preventDefault();
}

function onDragMove(e: MouseEvent) {
  if (!dragging.value) return;
  const dx = e.screenX - dragStart.value.x;
  const dy = e.screenY - dragStart.value.y;
  posX.value = Math.max(0, Math.min(100, dragStart.value.posX + (dx / window.innerWidth) * 100));
  posY.value = Math.max(0, Math.min(100, dragStart.value.posY + (dy / window.innerHeight) * 100));
}

function onDragEnd() {
  if (!dragging.value) return;
  dragging.value = false;
  // 退出编辑模式时保存（阶段 5 接入 settings.json 持久化）
}

// 退出编辑模式按钮
function exitEdit() {
  invoke("exit_edit_mode").catch(console.error);
}
</script>

<template>
  <div
    class="overlay-root"
    :style="{
      left: posX + '%',
      top: posY + '%',
    }"
    @mousemove="onDragMove"
    @mouseup="onDragEnd"
  >
    <!-- 左侧波纹条占位 -->
    <canvas class="wave-canvas left" width="200" height="50"></canvas>

    <!-- 中心分界标记 -->
    <div class="divider"></div>

    <!-- 右侧波纹条占位 -->
    <canvas class="wave-canvas right" width="200" height="50"></canvas>

    <!-- 编辑模式拖拽手柄 -->
    <div v-if="editMode" class="edit-frame" @mousedown="onDragStart">
      <div class="drag-handle">⠿</div>
      <button class="exit-edit-btn" @click="exitEdit">完成</button>
      <div class="position-display">
        X: {{ posX.toFixed(1) }}% Y: {{ posY.toFixed(1) }}%
      </div>
    </div>
  </div>
</template>

<style>
html,
body,
#app {
  margin: 0;
  padding: 0;
  background: transparent;
  overflow: hidden;
  user-select: none;
}

.overlay-root {
  position: absolute;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  gap: 8px;
  pointer-events: none;
}

.wave-canvas {
  display: block;
  background: rgba(0, 0, 0, 0.01);
  /* 阶段 1 占位：用边框让 canvas 可见 */
  border: 1px dashed rgba(255, 255, 255, 0.2);
}

.divider {
  width: 2px;
  height: 30px;
  background: rgba(255, 255, 255, 0.4);
}

.edit-frame {
  position: absolute;
  top: -40px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  background: rgba(0, 0, 0, 0.7);
  border: 1px solid #44a4ff;
  border-radius: 4px;
  pointer-events: auto;
  cursor: move;
  font-size: 12px;
  color: white;
}

.drag-handle {
  cursor: grab;
  font-size: 16px;
  line-height: 1;
}

.exit-edit-btn {
  background: #44a4ff;
  color: white;
  border: none;
  padding: 2px 8px;
  border-radius: 3px;
  cursor: pointer;
  font-size: 11px;
}

.position-display {
  font-family: monospace;
  color: #aaa;
}
</style>
