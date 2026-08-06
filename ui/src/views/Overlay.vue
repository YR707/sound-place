<script setup lang="ts">
// Overlay 窗口: 全屏透明覆盖, Canvas 绘制声音方位波纹
//
// 渲染流程:
// 1. useAudioEvents 订阅后端 sound_event, 维护活跃事件列表
// 2. useWaveRenderer 基于 events + appearance 用 Canvas 绘制波纹条
// 3. 编辑模式下可拖拽整体位置(阶段 5 提取为 useOverlayDrag + 持久化)

import { ref, onMounted, onUnmounted } from 'vue';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';
import { invoke } from '@tauri-apps/api/core';

import { useAudioEvents } from '@/composables/useAudioEvents';
import { useWaveRenderer } from '@/composables/useWaveRenderer';
import { DEFAULT_APPEARANCE, type Appearance } from '@/types/appearance';

// 编辑模式(控制面板通过 enter_edit_mode / exit_edit_mode 切换)
const editMode = ref(false);

// 外观设置(阶段 5 从后端加载, 阶段 3 先用默认值)
const appearance = ref<Appearance>({ ...DEFAULT_APPEARANCE });

// 拖拽状态
const posX = ref(appearance.value.pos_x_percent);
const posY = ref(appearance.value.pos_y_percent);
const dragging = ref(false);
const dragStart = ref({ x: 0, y: 0, posX: 0, posY: 0 });

// Canvas 引用
const canvasRef = ref<HTMLCanvasElement | null>(null);

// 订阅音频事件(decayMs 与 appearance.decay_ms 一致)
const { events } = useAudioEvents(appearance.value.decay_ms);

// 渲染器
useWaveRenderer(canvasRef, events, appearance);

let unlistenEditMode: UnlistenFn | null = null;
let unlistenAppearance: UnlistenFn | null = null;

onMounted(async () => {
  // 监听编辑模式切换
  unlistenEditMode = await listen<boolean>('edit-mode', (event) => {
    editMode.value = event.payload;
  });

  // 监听外观变化(阶段 5 AppearanceSettings 保存时触发)
  unlistenAppearance = await listen<Appearance>('appearance-changed', (event) => {
    appearance.value = event.payload;
    posX.value = event.payload.pos_x_percent;
    posY.value = event.payload.pos_y_percent;
  });

  // 阶段 5 实现后: 从后端加载持久化的 appearance
  // 阶段 3 先用默认值
  try {
    const saved = await invoke<Appearance>('get_appearance');
    appearance.value = saved;
    posX.value = saved.pos_x_percent;
    posY.value = saved.pos_y_percent;
  } catch {
    // 命令尚未实现(阶段 5 才有), 用默认值
  }
});

onUnmounted(() => {
  if (unlistenEditMode) unlistenEditMode();
  if (unlistenAppearance) unlistenAppearance();
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
  // 同步到 appearance(让渲染器跟随)
  appearance.value.pos_x_percent = posX.value;
  appearance.value.pos_y_percent = posY.value;
}

function onDragEnd() {
  if (!dragging.value) return;
  dragging.value = false;
  // 阶段 5: 调用 save_appearance 持久化位置
}

function exitEdit() {
  invoke('exit_edit_mode').catch(console.error);
}
</script>

<template>
  <div
    class="overlay-root"
    :style="{ left: posX + '%', top: posY + '%' }"
    @mousemove="onDragMove"
    @mouseup="onDragEnd"
  >
    <!-- 波纹 Canvas (全屏, 渲染器内部计算位置) -->
    <canvas ref="canvasRef" class="wave-canvas"></canvas>

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
  pointer-events: none;
}

.wave-canvas {
  display: block;
  /* Canvas 尺寸由 useWaveRenderer 根据窗口大小动态设置 */
  width: 100vw;
  height: 100vh;
  position: fixed;
  left: 0;
  top: 0;
  pointer-events: none;
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
