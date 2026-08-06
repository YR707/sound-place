"""分析工作线程 (对应 src-tauri/src/analysis/worker.rs).

消费 ring buffer → 触发 onset → 定位 → 分类 → 打印.

优化:
- 角度滑动平均 (window=5), 减少跳动
- 跳过 SoundType.NONE (噪声门限)
- 实时 CLI 可视化: 角度刻度条 + 强度条
"""

from __future__ import annotations

import sys
import threading
import time
from collections import deque
from typing import Optional

import numpy as np

from .classify import Classifier, SoundType
from .fft import FftAnalyzer
from .localize import Localizer
from .onset import OnsetDetector, OnsetEvent
from .ring_buffer import RingBuffer


# 角度滑动平均窗口大小 (越大越平滑, 但延迟也越大)
ANGLE_SMOOTH_WINDOW: int = 5


class AnalysisWorker:
    """分析线程."""

    def __init__(
        self,
        ring_buffer: RingBuffer,
        fft_size: int = 2048,
        hop_size: int = 1024,
        sample_rate: int = 48000,
        process_names: Optional[list[str]] = None,
        enable_visualization: bool = True,
    ) -> None:
        self.ring_buffer = ring_buffer
        self.fft_size = fft_size
        self.hop_size = hop_size
        self.sample_rate = sample_rate
        # Python 版本不实现进程过滤
        self.process_names = process_names or []
        self.enable_visualization = enable_visualization

        self._stop_flag = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # 分析器实例
        self.fft_analyzer = FftAnalyzer(fft_size)
        self.onset_detector = OnsetDetector()
        self.localizer = Localizer(fft_size)
        self.classifier = Classifier(sample_rate, fft_size)

        # 角度滑动平均缓冲
        self._angle_history: deque[float] = deque(maxlen=ANGLE_SMOOTH_WINDOW)

        # 统计
        self._event_count: int = 0
        self._last_event_str: str = ""

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("分析线程已在运行")
        self._stop_flag.clear()
        self._thread = threading.Thread(
            target=self._analysis_loop,
            name="soundplace-analysis",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_flag.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _analysis_loop(self) -> None:
        # 累积样本缓冲
        left_buf = np.zeros(0, dtype=np.float32)
        right_buf = np.zeros(0, dtype=np.float32)

        # 持续声音模式: 当 onset 不触发但能量足够时, 也输出方位
        # 用于音乐/持续背景音的方位显示
        last_continuous_emit_ts: int = 0
        CONTINUOUS_EMIT_INTERVAL_MS = 500  # 持续模式每 500ms 输出一次

        while not self._stop_flag.is_set():
            # 从 ring buffer 取数据
            available = self.ring_buffer.available()
            if available == 0:
                time.sleep(0.005)
                continue

            left, right = self.ring_buffer.pop_batch(available)
            left_buf = np.concatenate([left_buf, left])
            right_buf = np.concatenate([right_buf, right])

            # 每凑齐 hop_size 帧做一次分析 (50% overlap)
            while len(left_buf) >= self.fft_size:
                frame_left = left_buf[: self.fft_size]
                frame_right = right_buf[: self.fft_size]

                # FFT 分析
                left_spectrum, right_spectrum = self.fft_analyzer.analyze(frame_left, frame_right)

                # 计算能量 (用于持续模式)
                rms_left = float(np.sqrt(np.mean(frame_left ** 2)))
                rms_right = float(np.sqrt(np.mean(frame_right ** 2)))
                rms_max = max(rms_left, rms_right)

                # Onset 检测 (用左声道频谱)
                onset = self.onset_detector.detect(left_spectrum)

                if onset is not None:
                    # 方位估计
                    raw_angle = self.localizer.localize(frame_left, frame_right)

                    # 角度滑动平均
                    self._angle_history.append(raw_angle)
                    smoothed_angle = float(np.mean(self._angle_history))

                    # 分类
                    duration_ms = 50
                    sound_type = self.classifier.classify(
                        left_spectrum, onset.timestamp_ms, duration_ms
                    )

                    # 跳过噪声
                    if sound_type != SoundType.NONE:
                        self._emit_event(onset, smoothed_angle, sound_type)

                elif rms_max > 0.01:
                    # 持续声音模式: 能量足够但未触发 onset (如持续音乐)
                    # 降低输出频率避免刷屏
                    now_ms = int(time.time() * 1000)
                    if now_ms - last_continuous_emit_ts > CONTINUOUS_EMIT_INTERVAL_MS:
                        raw_angle = self.localizer.localize(frame_left, frame_right)
                        self._angle_history.append(raw_angle)
                        smoothed_angle = float(np.mean(self._angle_history))

                        # 持续声音用 GENERIC 类型, intensity 基于 rms
                        intensity = min(1.0, rms_max * 5.0)  # 归一化
                        cont_event = OnsetEvent(
                            intensity=intensity,
                            timestamp_ms=now_ms,
                        )
                        self._emit_event(cont_event, smoothed_angle, SoundType.GENERIC)
                        last_continuous_emit_ts = now_ms

                # 推进 hop_size
                left_buf = left_buf[self.hop_size :]
                right_buf = right_buf[self.hop_size :]

    def _emit_event(self, onset: OnsetEvent, angle: float, sound_type: SoundType) -> None:
        """打印事件 + 可视化."""
        self._event_count += 1

        # 文字方向
        direction = "中"
        if angle < -15:
            direction = f"左 {abs(angle):.0f}°"
        elif angle > 15:
            direction = f"右 {angle:.0f}°"

        event_str = (
            f"[sound] #{self._event_count:4d} type={sound_type.value:8s} "
            f"angle={angle:+6.1f}° ({direction}) "
            f"intensity={onset.intensity:.2f}"
        )
        self._last_event_str = event_str
        print(event_str)

        # 实时 CLI 可视化
        if self.enable_visualization:
            self._render_visualization(angle, onset.intensity, sound_type)

    def _render_visualization(self, angle: float, intensity: float, sound_type: SoundType) -> None:
        """渲染 CLI 可视化: 角度刻度条 + 强度条.

        格式:
        ```
        -90°  -45°   0°  +45°  +90°
          |    |    ▼    |    |
                    ████ ← (强度条)
        ```
        """
        # 角度刻度条 (41 个字符宽, 代表 -90° 到 +90°)
        width = 41
        center = width // 2  # 索引 20 = 0°

        # 角度 → 位置 (-90° = 0, 0° = 20, +90° = 40)
        pos = int(round((angle + 90) / 180 * (width - 1)))
        pos = max(0, min(width - 1, pos))

        # 构建刻度条
        bar = [' '] * width
        # 刻度位置: -90, -45, 0, +45, +90
        for tick_angle in [-90, -45, 0, 45, 90]:
            tick_pos = int(round((tick_angle + 90) / 180 * (width - 1)))
            bar[tick_pos] = '|'
        # 中心标记
        bar[center] = '·'
        # 当前角度位置
        bar[pos] = '▼'

        # 强度条 (10 个字符)
        intensity_width = 10
        filled = int(round(intensity * intensity_width))
        filled = max(0, min(intensity_width, filled))
        intensity_bar = '█' * filled + '░' * (intensity_width - filled)

        # 类型颜色 (ANSI)
        type_color = {
            SoundType.FOOTSTEP: '\033[33m',  # 黄
            SoundType.GUNSHOT: '\033[31m',   # 红
            SoundType.VEHICLE: '\033[34m',   # 蓝
            SoundType.GENERIC: '\033[37m',   # 白
            SoundType.NONE: '\033[90m',      # 灰
        }.get(sound_type, '\033[37m')
        reset = '\033[0m'

        # 类型标签
        type_label = {
            SoundType.FOOTSTEP: '👣 FOOTSTEP',
            SoundType.GUNSHOT:  '💥 GUNSHOT',
            SoundType.VEHICLE:  '🚗 VEHICLE',
            SoundType.GENERIC:  '◆ GENERIC',
            SoundType.NONE:     '· NONE',
        }.get(sound_type, sound_type.value)

        # 输出 (用 \r 不换行, 实时刷新)
        sys.stdout.write('\r\033[K')  # 清行
        sys.stdout.write(
            f"{type_color}{type_label:12s}{reset} "
            f"{''.join(bar)} "
            f"{intensity_bar} "
            f"{intensity*100:5.1f}%"
        )
        sys.stdout.write('\n')  # 换行保留历史
        sys.stdout.flush()
