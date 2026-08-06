<script setup lang="ts">
// 控制面板主窗口
//
// 布局:
// - 顶部: 启动/停止捕获 + 启用/禁用覆盖 + 当前 profile
// - Tab 切换: Profile 管理 / 外观设置 / 帮助 / 关于
// - 首次启动: 全屏 RiskNotice 弹窗

import { ref, onMounted } from 'vue';
import { invoke } from '@tauri-apps/api/core';
import RiskNotice from './RiskNotice.vue';
import AppearanceSettings from './AppearanceSettings.vue';
import HelpPage from './HelpPage.vue';
import AboutPage from './AboutPage.vue';
import type { ProfileListItem } from '@/types/profile';

type Tab = 'profile' | 'appearance' | 'help' | 'about';

const riskAccepted = ref(false);
const capturing = ref(false);
const overlayEnabled = ref(false);
const errorMsg = ref('');
const activeTab = ref<Tab>('profile');

// Profile 管理
const profiles = ref<ProfileListItem[]>([]);
const activeProfileId = ref('default');
const editingProfileId = ref<string | null>(null);
const editingContent = ref('');
const editingError = ref('');

async function loadProfiles() {
  try {
    profiles.value = await invoke<ProfileListItem[]>('list_profiles');
    activeProfileId.value = await invoke<string>('get_active_profile');
  } catch (e) {
    errorMsg.value = String(e);
  }
}

async function editProfile(id: string) {
  try {
    editingProfileId.value = id;
    editingContent.value = await invoke<string>('get_profile', { id });
    editingError.value = '';
  } catch (e) {
    editingError.value = String(e);
  }
}

async function saveProfile() {
  if (!editingProfileId.value) return;
  try {
    await invoke('save_profile', {
      id: editingProfileId.value,
      content: editingContent.value,
    });
    editingError.value = '';
    await loadProfiles();
  } catch (e) {
    editingError.value = String(e);
  }
}

async function activateProfile(id: string) {
  try {
    await invoke('set_active_profile', { id });
    activeProfileId.value = id;
  } catch (e) {
    errorMsg.value = String(e);
  }
}

// 控制
async function startCapture() {
  try {
    await invoke('start_capture');
    capturing.value = true;
    errorMsg.value = '';
  } catch (e) {
    errorMsg.value = String(e);
  }
}

async function stopCapture() {
  try {
    await invoke('stop_capture');
    capturing.value = false;
    errorMsg.value = '';
  } catch (e) {
    errorMsg.value = String(e);
  }
}

async function enableOverlay() {
  try {
    await invoke('enable_overlay');
    overlayEnabled.value = true;
    errorMsg.value = '';
  } catch (e) {
    errorMsg.value = String(e);
  }
}

async function disableOverlay() {
  try {
    await invoke('disable_overlay');
    overlayEnabled.value = false;
    errorMsg.value = '';
  } catch (e) {
    errorMsg.value = String(e);
  }
}

async function editPosition() {
  try {
    await invoke('enter_edit_mode');
  } catch (e) {
    errorMsg.value = String(e);
  }
}

onMounted(async () => {
  try {
    riskAccepted.value = await invoke<boolean>('is_risk_accepted');
    if (riskAccepted.value) {
      await loadProfiles();
    }
  } catch (e) {
    errorMsg.value = String(e);
  }
});

async function onRiskAccepted() {
  riskAccepted.value = true;
  await loadProfiles();
}

const riskClass = (risk: string) => {
  if (risk === 'high') return 'risk-high';
  if (risk === 'medium') return 'risk-medium';
  return 'risk-low';
};
</script>

<template>
  <div class="control-panel">
    <!-- 首次启动: 强制显示风险告知 -->
    <RiskNotice v-if="!riskAccepted" @accepted="onRiskAccepted" />

    <template v-else>
      <!-- 顶部控制栏 -->
      <div class="top-bar">
        <div class="capture-controls">
          <button
            class="btn"
            :class="{ active: capturing }"
            @click="capturing ? stopCapture() : startCapture()"
          >
            {{ capturing ? '停止捕获' : '启动捕获' }}
          </button>
          <button
            class="btn"
            :class="{ active: overlayEnabled }"
            @click="overlayEnabled ? disableOverlay() : enableOverlay()"
          >
            {{ overlayEnabled ? '禁用覆盖' : '启用覆盖' }}
          </button>
          <button class="btn" @click="editPosition" :disabled="!overlayEnabled">
            调整位置
          </button>
        </div>
        <div class="active-profile-info">
          当前 Profile: <strong>{{ activeProfileId }}</strong>
        </div>
      </div>

      <!-- 错误显示 -->
      <div v-if="errorMsg" class="error-bar">{{ errorMsg }}</div>

      <!-- Tab 导航 -->
      <div class="tabs">
        <button
          :class="{ active: activeTab === 'profile' }"
          @click="activeTab = 'profile'"
        >Profile 管理</button>
        <button
          :class="{ active: activeTab === 'appearance' }"
          @click="activeTab = 'appearance'"
        >外观设置</button>
        <button
          :class="{ active: activeTab === 'help' }"
          @click="activeTab = 'help'"
        >帮助</button>
        <button
          :class="{ active: activeTab === 'about' }"
          @click="activeTab = 'about'"
        >关于</button>
      </div>

      <!-- Tab 内容 -->
      <div class="tab-content">
        <!-- Profile 管理 -->
        <div v-if="activeTab === 'profile'" class="profile-tab">
          <div class="profile-list">
            <h4>Profiles</h4>
            <div
              v-for="p in profiles"
              :key="p.game_id"
              class="profile-item"
              :class="{ active: p.game_id === activeProfileId }"
            >
              <div class="profile-info">
                <div class="profile-name">{{ p.name }}</div>
                <div class="profile-id">{{ p.game_id }}</div>
                <span class="risk-tag" :class="riskClass(p.anticheat_risk)">
                  {{ p.anticheat_risk }}
                </span>
              </div>
              <div class="profile-actions">
                <button @click="editProfile(p.game_id)">编辑</button>
                <button
                  v-if="p.game_id !== activeProfileId"
                  @click="activateProfile(p.game_id)"
                >激活</button>
                <span v-else class="active-tag">已激活</span>
              </div>
            </div>
          </div>

          <div class="profile-editor" v-if="editingProfileId">
            <div class="editor-header">
              <h4>编辑: {{ editingProfileId }}.toml</h4>
              <button @click="saveProfile">保存</button>
            </div>
            <textarea v-model="editingContent" class="toml-editor"></textarea>
            <div v-if="editingError" class="error-bar">{{ editingError }}</div>
          </div>
        </div>

        <!-- 外观设置 -->
        <AppearanceSettings v-else-if="activeTab === 'appearance'" />

        <!-- 帮助 -->
        <HelpPage v-else-if="activeTab === 'help'" />

        <!-- 关于 -->
        <AboutPage v-else-if="activeTab === 'about'" />
      </div>
    </template>
  </div>
</template>

<style scoped>
.control-panel {
  min-height: 100vh;
  background: #1e1e1e;
  color: #ddd;
  display: flex;
  flex-direction: column;
  font-size: 14px;
}

.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #252525;
  border-bottom: 1px solid #333;
}

.capture-controls {
  display: flex;
  gap: 8px;
}

.btn {
  background: #2a2a2a;
  color: #ddd;
  border: 1px solid #444;
  padding: 6px 14px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}

.btn:hover:not(:disabled) {
  background: #333;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn.active {
  background: #44a4ff;
  color: white;
  border-color: #44a4ff;
}

.active-profile-info {
  font-size: 13px;
  color: #aaa;
}

.error-bar {
  background: #4a1f1f;
  color: #ff8888;
  padding: 8px 16px;
  border-bottom: 1px solid #5a2a2a;
  font-size: 12px;
}

.tabs {
  display: flex;
  background: #2a2a2a;
  border-bottom: 1px solid #333;
}

.tabs button {
  background: transparent;
  color: #aaa;
  border: none;
  padding: 10px 20px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  font-size: 13px;
}

.tabs button.active {
  color: #fff;
  border-bottom-color: #44a4ff;
}

.tab-content {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
}

.profile-tab {
  display: flex;
  gap: 16px;
  height: 100%;
}

.profile-list {
  width: 280px;
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
  border-radius: 4px;
  padding: 12px;
  overflow-y: auto;
}

.profile-list h4 {
  margin: 0 0 10px;
  color: #fff;
  font-size: 14px;
}

.profile-item {
  padding: 8px;
  margin-bottom: 6px;
  background: #222;
  border-radius: 3px;
  cursor: pointer;
  border: 1px solid transparent;
}

.profile-item.active {
  border-color: #44a4ff;
}

.profile-info {
  margin-bottom: 6px;
}

.profile-name {
  color: #fff;
  font-size: 13px;
}

.profile-id {
  color: #888;
  font-size: 11px;
  font-family: monospace;
}

.risk-tag {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 2px;
  font-size: 10px;
  margin-top: 2px;
}

.risk-high { background: #4a1f1f; color: #ef476f; }
.risk-medium { background: #4a401f; color: #ffd166; }
.risk-low { background: #1f4a2f; color: #06d6a0; }

.profile-actions {
  display: flex;
  gap: 6px;
}

.profile-actions button {
  background: #333;
  color: #ddd;
  border: 1px solid #444;
  padding: 3px 8px;
  border-radius: 2px;
  cursor: pointer;
  font-size: 11px;
}

.active-tag {
  color: #06d6a0;
  font-size: 11px;
}

.profile-editor {
  flex: 1;
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
  border-radius: 4px;
  padding: 12px;
  display: flex;
  flex-direction: column;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.editor-header h4 {
  margin: 0;
  color: #fff;
  font-size: 14px;
}

.editor-header button {
  background: #44a4ff;
  color: white;
  border: none;
  padding: 4px 12px;
  border-radius: 3px;
  cursor: pointer;
  font-size: 12px;
}

.toml-editor {
  flex: 1;
  background: #111;
  color: #ddd;
  border: 1px solid #333;
  border-radius: 3px;
  padding: 8px;
  font-family: 'Consolas', monospace;
  font-size: 12px;
  resize: none;
}
</style>
