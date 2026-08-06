"""分析工作线程 (对应 src-tauri/src/analysis/worker.rs).

消费 ring buffer → 触发 onset → 定位 → 分类 → 打印.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import numpy as np

from .classify import Classifier, SoundType
from .fft import FftAnalyzer
from .localize import Localizer
from .onset import OnsetDetector, OnsetEvent
from .ring_buffer import RingBuffer


class AnalysisWorker:
    """分析线程."""

    def __init__(
        self,
        ring_buffer: RingBuffer,
        fft_size: int = 2048,
        hop_size: int = 1024,
        sample_rate: int = 48000,
        process_names: Optional[list[str]] = None,
    ) -> None:
        self.ring_buffer = ring_buffer
        self.fft_size = fft_size
        self.hop_size = hop_size
        self.sample_rate = sample_rate
        # Python 版本不实现进程过滤 (pycaw 已捕获到特定进程的 session)
        self.process_names = process_names or []

        self._stop_flag = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # 分析器实例
        self.fft_analyzer = FftAnalyzer(fft_size)
        self.onset_detector = OnsetDetector()
        self.localizer = Localizer(fft_size)
        self.classifier = Classifier(sample_rate, fft_size)

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

                # Onset 检测 (用左声道频谱)
                onset = self.onset_detector.detect(left_spectrum)

                if onset is not None:
                    # 方位估计
                    angle = self.localizer.localize(frame_left, frame_right)

                    # 分类 (用 onset 的时间戳作为持续时间的粗估, 这里用 50ms)
                    duration_ms = 50
                    sound_type = self.classifier.classify(
                        left_spectrum, onset.timestamp_ms, duration_ms
                    )

                    self._emit_event(onset, angle, sound_type)

                # 推进 hop_size
                left_buf = left_buf[self.hop_size :]
                right_buf = right_buf[self.hop_size :]

    def _emit_event(self, onset: OnsetEvent, angle: float, sound_type: SoundType) -> None:
        """打印事件 (Python 版本没有 Tauri emit, 用 stdout)."""
        direction = "中"
        if angle < -15:
            direction = f"左 {abs(angle):.0f}°"
        elif angle > 15:
            direction = f"右 {angle:.0f}°"

        print(
            f"[sound] type={sound_type.value:8s} "
            f"angle={angle:+6.1f}° ({direction}) "
            f"intensity={onset.intensity:.2f}"
        )
