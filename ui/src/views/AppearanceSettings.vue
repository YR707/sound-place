<script setup lang="ts">
// 外观设置页
// 所有改动实时保存到 settings.json, 并通过 'appearance-changed' 事件通知 overlay 实时更新

import { ref, onMounted, watch } from 'vue';
import { invoke } from '@tauri-apps/api/core';
import { DEFAULT_APPEARANCE, type Appearance, type WaveStyle } from '@/types/appearance';

const appearance = ref<Appearance>({ ...DEFAULT_APPEARANCE });
const saving = ref(false);

onMounted(async () => {
  try {
    const saved = await invoke<Appearance>('get_appearance');
    appearance.value = saved;
  } catch (e) {
    console.error('加载外观失败', e);
  }
});

// 监听变化, 防抖保存
let saveTimer: number | null = null;
watch(appearance, () => {
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = window.setTimeout(async () => {
    saving.value = true;
    try {
      await invoke('save_appearance', { appearance: appearance.value });
    } catch (e) {
      console.error('保存外观失败', e);
    } finally {
      saving.value = false;
    }
  }, 300);
}, { deep: true });

async function reset() {
  try {
    const def = await invoke<Appearance>('reset_appearance');
    appearance.value = def;
  } catch (e) {
    console.error('重置失败', e);
  }
}
</script>

<template>
  <div class="appearance-settings">
    <div class="header-row">
      <h3>外观设置</h3>
      <span v-if="saving" class="saving-tip">保存中...</span>
      <button class="reset-btn" @click="reset">恢复默认</button>
    </div>

    <div class="settings-group">
      <h4>位置</h4>
      <label>
        X 位置: {{ appearance.pos_x_percent.toFixed(1) }}%
        <input type="range" min="0" max="100" step="0.5" v-model.number="appearance.pos_x_percent" />
      </label>
      <label>
        Y 位置: {{ appearance.pos_y_percent.toFixed(1) }}%
        <input type="range" min="0" max="100" step="0.5" v-model.number="appearance.pos_y_percent" />
      </label>
    </div>

    <div class="settings-group">
      <h4>波纹条</h4>
      <label>
        总长度: {{ appearance.wave_length }}px
        <input type="range" min="80" max="400" step="10" v-model.number="appearance.wave_length" />
      </label>
      <label>
        最大高度: {{ appearance.wave_max_height }}px
        <input type="range" min="20" max="120" step="5" v-model.number="appearance.wave_max_height" />
      </label>
      <label>
        厚度: {{ appearance.wave_thickness }}px
        <input type="range" min="1" max="8" step="1" v-model.number="appearance.wave_thickness" />
      </label>
      <label>
        透明度: {{ appearance.opacity.toFixed(2) }}
        <input type="range" min="0.1" max="1" step="0.05" v-model.number="appearance.opacity" />
      </label>
      <label>
        波纹样式:
        <select v-model="appearance.wave_style">
          <option value="smooth">平滑曲线</option>
          <option value="sawtooth">锯齿</option>
          <option value="step">阶梯</option>
        </select>
      </label>
      <label class="checkbox-row">
        <input type="checkbox" v-model="appearance.show_divider" />
        显示左右分界标记
      </label>
    </div>

    <div class="settings-group">
      <h4>颜色</h4>
      <label>
        脚步声
        <input type="color" v-model="appearance.color_footstep" />
      </label>
      <label>
        枪声
        <input type="color" v-model="appearance.color_gunshot" />
      </label>
      <label>
        载具声
        <input type="color" v-model="appearance.color_vehicle" />
      </label>
      <label>
        通用
        <input type="color" v-model="appearance.color_generic" />
      </label>
    </div>

    <div class="settings-group">
      <h4>动画</h4>
      <label>
        衰减时长: {{ appearance.decay_ms }}ms
        <input type="range" min="200" max="2000" step="50" v-model.number="appearance.decay_ms" />
      </label>
    </div>
  </div>
</template>

<style scoped>
.appearance-settings {
  color: #ddd;
  font-size: 14px;
}

.header-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

h3 {
  margin: 0;
  color: #fff;
  flex: 1;
}

.saving-tip {
  color: #888;
  font-size: 12px;
}

.reset-btn {
  background: #444;
  color: #ddd;
  border: 1px solid #555;
  padding: 4px 12px;
  border-radius: 3px;
  cursor: pointer;
  font-size: 12px;
}

.settings-group {
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
  border-radius: 4px;
  padding: 12px;
  margin-bottom: 12px;
}

.settings-group h4 {
  margin: 0 0 10px;
  color: #ff9d4d;
  font-size: 13px;
}

label {
  display: block;
  margin: 8px 0;
  font-size: 13px;
}

label input[type="range"] {
  display: block;
  width: 100%;
  margin-top: 4px;
}

label input[type="color"] {
  display: block;
  margin-top: 4px;
  width: 60px;
  height: 30px;
  border: 1px solid #444;
  background: transparent;
  cursor: pointer;
}

label select {
  margin-top: 4px;
  background: #2a2a2a;
  color: #ddd;
  border: 1px solid #444;
  padding: 4px;
  border-radius: 3px;
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.checkbox-row input {
  margin: 0;
  width: auto;
}
</style>
