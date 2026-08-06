// Profile 管理逻辑: 加载列表、编辑配置、保存配置、激活配置

import { ref } from 'vue';
import { invoke } from '@tauri-apps/api/core';
import type { ProfileListItem } from '@/types/profile';

export function useProfileManager() {
  const profiles = ref<ProfileListItem[]>([]);
  const activeProfileId = ref('default');
  const editingProfileId = ref<string | null>(null);
  const editingContent = ref('');
  const error = ref('');

  async function loadProfiles() {
    try {
      profiles.value = await invoke<ProfileListItem[]>('list_profiles');
      activeProfileId.value = await invoke<string>('get_active_profile');
      error.value = '';
    } catch (e) {
      error.value = String(e);
    }
  }

  async function editProfile(id: string) {
    try {
      editingProfileId.value = id;
      editingContent.value = await invoke<string>('get_profile', { id });
      error.value = '';
    } catch (e) {
      error.value = String(e);
    }
  }

  async function saveProfile() {
    if (!editingProfileId.value) return;
    try {
      await invoke('save_profile', {
        id: editingProfileId.value,
        content: editingContent.value,
      });
      error.value = '';
      await loadProfiles();
    } catch (e) {
      error.value = String(e);
    }
  }

  async function activateProfile(id: string) {
    try {
      await invoke('set_active_profile', { id });
      activeProfileId.value = id;
      error.value = '';
    } catch (e) {
      error.value = String(e);
    }
  }

  function cancelEdit() {
    editingProfileId.value = null;
    editingContent.value = '';
    error.value = '';
  }

  return {
    profiles,
    activeProfileId,
    editingProfileId,
    editingContent,
    error,
    loadProfiles,
    editProfile,
    saveProfile,
    activateProfile,
    cancelEdit,
  };
}
