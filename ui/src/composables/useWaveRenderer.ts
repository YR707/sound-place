// Canvas 波纹渲染
//
// 设计:
// - 左右两条水平波纹条, 紧贴准星
// - 峰值水平位置 = 角度映射(-90° → 左条最左端, 0° → 准星处, +90° → 右条最右端)
// - 峰值高度 = 强度 × wave_max_height
// - 颜色 = 声音类型对应颜色
// - 衰减动画: 从峰值向两端扩散, alpha 随时间衰减
// - 仅在有事件时重绘(空闲时停止 RAF 节省 CPU)

import { onMounted, onUnmounted, ref, watch, type Ref } from 'vue';
import type { SoundEvent } from '@/types/audio';
import type { Appearance } from '@/types/appearance';

/** 根据 sound_type 获取颜色 */
function getColor(soundType: SoundEvent['sound_type'], appearance: Appearance): string {
  switch (soundType) {
    case 'footstep': return appearance.color_footstep;
    case 'gunshot': return appearance.color_gunshot;
    case 'vehicle': return appearance.color_vehicle;
    case 'generic': return appearance.color_generic;
    default: return appearance.color_generic;
  }
}

export function useWaveRenderer(
  canvasRef: Ref<HTMLCanvasElement | null>,
  eventsRef: Ref<SoundEvent[]>,
  appearanceRef: Ref<Appearance>,
) {
  let rafId: number | null = null;
  let ctx: CanvasRenderingContext2D | null = null;

  /** 设置 Canvas 分辨率匹配显示器 */
  const resizeCanvas = () => {
    const canvas = canvasRef.value;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx = canvas.getContext('2d');
    if (ctx) ctx.scale(dpr, dpr);
  };

  /** 渲染一帧 */
  const render = () => {
    const canvas = canvasRef.value;
    if (!canvas || !ctx) return;

    const appearance = appearanceRef.value;
    const events = eventsRef.value;
    const now = Date.now();

    // 清空
    const rect = canvas.getBoundingClientRect();
    ctx.clearRect(0, 0, rect.width, rect.height);

    // 中心点(屏幕中心或外观指定的位置)
    const cx = (appearance.pos_x_percent / 100) * rect.width;
    const cy = (appearance.pos_y_percent / 100) * rect.height;

    // 波纹条参数
    const halfLen = appearance.wave_length / 2;
    const maxH = appearance.wave_max_height;
    const thickness = appearance.wave_thickness;

    // 绘制左右基线(可选,仅作视觉参考)
    if (appearance.show_divider) {
      ctx.strokeStyle = `rgba(255, 255, 255, 0.2)`;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(cx - halfLen, cy);
      ctx.lineTo(cx + halfLen, cy);
      ctx.stroke();
      // 中心准星
      ctx.beginPath();
      ctx.moveTo(cx, cy - 8);
      ctx.lineTo(cx, cy + 8);
      ctx.stroke();
    }

    // 渲染每个事件
    for (const event of events) {
      const age = now - event.timestamp;
      if (age < 0 || age > appearance.decay_ms) continue;

      // 衰减系数
      const alpha = 1.0 - (age / appearance.decay_ms);
      const color = getColor(event.sound_type, appearance);

      // 峰值位置: 角度映射
      // -90° → cx - halfLen, 0° → cx, +90° → cx + halfLen
      const peakX = cx + (event.angle / 90) * halfLen;
      const peakH = event.intensity * maxH * alpha;

      // 渲染波纹: 以 peakX 为中心向两端扩散
      ctx.strokeStyle = color;
      ctx.globalAlpha = alpha * appearance.opacity;
      ctx.lineWidth = thickness;
      ctx.lineCap = 'round';

      ctx.beginPath();
      if (appearance.wave_style === 'smooth') {
        // 平滑曲线: 从 peakX 向两端衰减高度
        const spread = halfLen * 0.5 * alpha;
        ctx.moveTo(peakX - spread, cy);
        ctx.quadraticCurveTo(peakX, cy - peakH, peakX + spread, cy);
      } else if (appearance.wave_style === 'sawtooth') {
        // 锯齿
        const spread = halfLen * 0.4 * alpha;
        ctx.moveTo(peakX - spread, cy);
        ctx.lineTo(peakX, cy - peakH);
        ctx.lineTo(peakX + spread, cy);
      } else {
        // 阶梯
        const spread = halfLen * 0.4 * alpha;
        ctx.moveTo(peakX - spread, cy);
        ctx.lineTo(peakX - spread * 0.3, cy - peakH);
        ctx.lineTo(peakX + spread * 0.3, cy - peakH);
        ctx.lineTo(peakX + spread, cy);
      }
      ctx.stroke();
    }

    ctx.globalAlpha = 1.0;

    // 决定下一帧是否继续
    const hasActiveEvents = events.some(
      e => now - e.timestamp < appearance.decay_ms,
    );
    if (hasActiveEvents) {
      rafId = requestAnimationFrame(render);
    } else {
      rafId = null;
    }
  };

  /** 事件列表变化时触发渲染 */
  const startRender = () => {
    if (rafId === null) {
      rafId = requestAnimationFrame(render);
    }
  };

  onMounted(() => {
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
    // 监听事件列表变化
    watch(eventsRef, startRender, { deep: true });
  });

  onUnmounted(() => {
    if (rafId !== null) cancelAnimationFrame(rafId);
    window.removeEventListener('resize', resizeCanvas);
  });

  return { resizeCanvas };
}
