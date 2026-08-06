<script setup lang="ts">
// 阶段 1：最小控制面板，仅启用/禁用 overlay + 编辑模式切换
// 阶段 5 将扩展为完整面板

import { ref } from "vue";
import { invoke } from "@tauri-apps/api/core";

const overlayEnabled = ref(false);
const editMode = ref(false);
const errorMsg = ref("");

async function toggleOverlay() {
  errorMsg.value = "";
  try {
    if (overlayEnabled.value) {
      await invoke("disable_overlay");
      overlayEnabled.value = false;
      editMode.value = false;
    } else {
      await invoke("enable_overlay");
      overlayEnabled.value = true;
    }
  } catch (e) {
    errorMsg.value = String(e);
  }
}

async function toggleEditMode() {
  errorMsg.value = "";
  try {
    if (editMode.value) {
      await invoke("exit_edit_mode");
      editMode.value = false;
    } else {
      if (!overlayEnabled.value) {
        await invoke("enable_overlay");
        overlayEnabled.value = true;
      }
      await invoke("enter_edit_mode");
      editMode.value = true;
    }
  } catch (e) {
    errorMsg.value = String(e);
  }
}
</script>

<template>
  <div class="control-panel">
    <h1>SoundPlace 控制面板</h1>
    <p class="version">v0.1.0 - 阶段 1 PoC</p>

    <div class="status-card">
      <div class="status-row">
        <span>Overlay 状态:</span>
        <span :class="['status', overlayEnabled ? 'on' : 'off']">
          {{ overlayEnabled ? "已启用" : "未启用" }}
        </span>
      </div>
      <div class="status-row">
        <span>编辑模式:</span>
        <span :class="['status', editMode ? 'on' : 'off']">
          {{ editMode ? "编辑中" : "未编辑" }}
        </span>
      </div>
    </div>

    <div class="actions">
      <button @click="toggleOverlay" :class="['btn', overlayEnabled ? 'danger' : 'primary']">
        {{ overlayEnabled ? "禁用 Overlay" : "启用 Overlay" }}
      </button>
      <button
        @click="toggleEditMode"
        :disabled="!overlayEnabled && !editMode"
        :class="['btn', editMode ? 'danger' : 'secondary']"
      >
        {{ editMode ? "退出编辑" : "调整位置" }}
      </button>
    </div>

    <div v-if="errorMsg" class="error">
      {{ errorMsg }}
    </div>

    <div class="hint">
      <h3>验证清单（阶段 1）</h3>
      <ul>
        <li>点击「启用 Overlay」后屏幕中央应出现占位波纹条</li>
        <li>鼠标点击波纹区域应穿透到下层窗口</li>
        <li>点击「调整位置」后波纹组出现蓝色边框，可拖动</li>
        <li>点击「完成」退出编辑模式恢复透明</li>
      </ul>
    </div>
  </div>
</template>

<style>
body {
  background: #1e1e1e;
  color: #e0e0e0;
}

.control-panel {
  max-width: 600px;
  margin: 40px auto;
  padding: 24px;
}

h1 {
  margin: 0 0 4px 0;
  font-size: 24px;
  color: #44a4ff;
}

.version {
  margin: 0 0 24px 0;
  color: #888;
  font-size: 12px;
}

.status-card {
  background: #2a2a2a;
  border: 1px solid #3a3a3a;
  border-radius: 6px;
  padding: 16px;
  margin-bottom: 24px;
}

.status-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 14px;
}

.status {
  font-weight: bold;
}

.status.on {
  color: #4ade80;
}

.status.off {
  color: #888;
}

.actions {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

.btn {
  padding: 10px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  flex: 1;
  transition: opacity 0.2s;
}

.btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn.primary {
  background: #44a4ff;
  color: white;
}

.btn.secondary {
  background: #4a4a4a;
  color: white;
}

.btn.danger {
  background: #ff4444;
  color: white;
}

.error {
  background: rgba(255, 68, 68, 0.1);
  border: 1px solid #ff4444;
  color: #ff8888;
  padding: 12px;
  border-radius: 4px;
  margin-bottom: 24px;
  font-family: monospace;
  font-size: 12px;
}

.hint {
  background: #2a2a2a;
  border: 1px solid #3a3a3a;
  border-radius: 6px;
  padding: 16px;
  font-size: 13px;
  color: #aaa;
}

.hint h3 {
  margin: 0 0 8px 0;
  color: #e0e0e0;
  font-size: 14px;
}

.hint ul {
  margin: 0;
  padding-left: 20px;
}

.hint li {
  margin: 4px 0;
  line-height: 1.5;
}
</style>
