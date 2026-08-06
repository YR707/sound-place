<script setup lang="ts">
// 控制面板主窗口
//
// 布局:
// - 顶部: 启动/停止捕获 + 启用/禁用覆盖 + 当前 profile
// - Tab 切换: Profile 管理 / 外观设置 / 帮助 / 关于
// - 首次启动: 全屏 RiskNotice 弹窗

import { ref, computed, onMounted } from 'vue';
import { invoke } from '@tauri-apps/api/core';
import RiskNotice from './RiskNotice.vue';
import AppearanceSettings from './AppearanceSettings.vue';
import HelpPage from './HelpPage.vue';
import AboutPage from './AboutPage.vue';
import ProfileList from '@/components/ProfileList.vue';
import ProfileEditor from '@/components/ProfileEditor.vue';
import { useProfileManager } from '@/composables/useProfileManager';
import { useCaptureControl } from '@/composables/useCaptureControl';

type Tab = 'profile' | 'appearance' | 'help' | 'about';

const riskAccepted = ref(false);
const activeTab = ref<Tab>('profile');
const globalError = ref('');

const {
  profiles,
  activeProfileId,
  editingProfileId,
  editingContent,
  error: profileError,
  loadProfiles,
  editProfile,
  saveProfile,
  activateProfile,
  cancelEdit,
} = useProfileManager();

const {
  capturing,
  overlayEnabled,
  error: captureError,
  startCapture,
  stopCapture,
  enableOverlay,
  disableOverlay,
  editPosition,
} = useCaptureControl();

// 合并错误显示: 全局错误优先, 其次 Profile 错误, 最后捕获错误
const errorMsg = computed(() =>
  globalError.value || profileError.value || captureError.value
);

onMounted(async () => {
  try {
    riskAccepted.value = await invoke<boolean>('is_risk_accepted');
    if (riskAccepted.value) {
      await loadProfiles();
    }
  } catch (e) {
    globalError.value = String(e);
  }
});

async function onRiskAccepted() {
  riskAccepted.value = true;
  await loadProfiles();
}
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
          <ProfileList
            :profiles="profiles"
            :active-profile-id="activeProfileId"
            @edit="editProfile"
            @activate="activateProfile"
          />
          <ProfileEditor
            v-if="editingProfileId"
            :profile-id="editingProfileId"
            :content="editingContent"
            :error="profileError"
            @update:content="editingContent = $event"
            @save="saveProfile"
            @cancel="cancelEdit"
          />
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
</style>
