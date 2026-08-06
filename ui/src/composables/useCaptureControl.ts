// 捕获控制与 Overlay 控制逻辑

import { ref } from 'vue';
import { invoke } from '@tauri-apps/api/core';

export function useCaptureControl() {
  const capturing = ref(false);
  const overlayEnabled = ref(false);
  const error = ref('');

  async function startCapture() {
    try {
      await invoke('start_capture');
      capturing.value = true;
      error.value = '';
    } catch (e) {
      error.value = String(e);
    }
  }

  async function stopCapture() {
    try {
      await invoke('stop_capture');
      capturing.value = false;
      error.value = '';
    } catch (e) {
      error.value = String(e);
    }
  }

  async function enableOverlay() {
    try {
      await invoke('enable_overlay');
      overlayEnabled.value = true;
      error.value = '';
    } catch (e) {
      error.value = String(e);
    }
  }

  async function disableOverlay() {
    try {
      await invoke('disable_overlay');
      overlayEnabled.value = false;
      error.value = '';
    } catch (e) {
      error.value = String(e);
    }
  }

  async function editPosition() {
    try {
      await invoke('enter_edit_mode');
      error.value = '';
    } catch (e) {
      error.value = String(e);
    }
  }

  return {
    capturing,
    overlayEnabled,
    error,
    startCapture,
    stopCapture,
    enableOverlay,
    disableOverlay,
    editPosition,
  };
}
