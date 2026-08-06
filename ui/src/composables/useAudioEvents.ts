// 订阅后端 sound_event 事件, 维护活跃事件列表
//
// 活跃事件 = 在 decay_ms 时间窗口内的事件, 超过窗口的自动清理
// useWaveRenderer 从这里读取事件进行渲染

import { onMounted, onUnmounted, ref } from 'vue';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';
import type { SoundEvent } from '@/types/audio';

export function useAudioEvents(decayMs = 800) {
  const events = ref<SoundEvent[]>([]);
  let unlisten: UnlistenFn | null = null;
  let cleanupTimer: number | null = null;

  /** 清理超过 decayMs 的事件 */
  const cleanup = () => {
    const now = Date.now();
    events.value = events.value.filter(e => now - e.timestamp < decayMs);
  };

  onMounted(async () => {
    unlisten = await listen<SoundEvent>('sound_event', (event) => {
      events.value.push(event.payload);
    });

    // 每 100ms 清理一次过期事件
    cleanupTimer = window.setInterval(cleanup, 100);
  });

  onUnmounted(() => {
    if (unlisten) unlisten();
    if (cleanupTimer) clearInterval(cleanupTimer);
  });

  return { events };
}
