// Overlay 拖拽逻辑(从 Overlay.vue 提取)
//
// 在编辑模式下允许用户拖拽波纹组位置, 拖动结束时持久化到 settings.json

import { ref, type Ref } from 'vue';
import { invoke } from '@tauri-apps/api/core';
import type { Appearance } from '@/types/appearance';

export function useOverlayDrag(
  appearanceRef: Ref<Appearance>,
  editMode: Ref<boolean>,
) {
  const dragging = ref(false);
  const dragStart = ref({ x: 0, y: 0, posX: 0, posY: 0 });

  function onDragStart(e: MouseEvent) {
    if (!editMode.value) return;
    dragging.value = true;
    dragStart.value = {
      x: e.screenX,
      y: e.screenY,
      posX: appearanceRef.value.pos_x_percent,
      posY: appearanceRef.value.pos_y_percent,
    };
    e.preventDefault();
  }

  function onDragMove(e: MouseEvent) {
    if (!dragging.value) return;
    const dx = e.screenX - dragStart.value.x;
    const dy = e.screenY - dragStart.value.y;
    const newX = Math.max(
      0,
      Math.min(100, dragStart.value.posX + (dx / window.innerWidth) * 100),
    );
    const newY = Math.max(
      0,
      Math.min(100, dragStart.value.posY + (dy / window.innerHeight) * 100),
    );
    appearanceRef.value = {
      ...appearanceRef.value,
      pos_x_percent: newX,
      pos_y_percent: newY,
    };
  }

  async function onDragEnd() {
    if (!dragging.value) return;
    dragging.value = false;
    // 持久化新位置
    try {
      await invoke('save_appearance', { appearance: appearanceRef.value });
    } catch (e) {
      console.error('保存位置失败', e);
    }
  }

  return { dragging, onDragStart, onDragMove, onDragEnd };
}
