"""Onset 检测 (对应 src-tauri/src/analysis/onset.rs).

Spectral Flux + HFC 组合, 自适应阈值 (median + k×MAD), 去抖.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Optional

import numpy as np

# Spectrum 类型别名 (与 fft.py 一致)
Spectrum = np.ndarray


class OnsetEvent:
    """Onset 检测事件."""

    __slots__ = ("intensity", "timestamp_ms")

    def __init__(self, intensity: float, timestamp_ms: int) -> None:
        self.intensity = float(intensity)
        self.timestamp_ms = int(timestamp_ms)


class OnsetDetector:
    """Onset 检测器."""

    def __init__(
        self,
        window_size: int = 20,
        threshold_k: float = 3.0,
        min_interval_ms: int = 100,
    ) -> None:
        self.prev_spectrum: Optional[np.ndarray] = None
        self.flux_history: deque[float] = deque(maxlen=window_size)
        self.window_size = window_size
        self.threshold_k = threshold_k
        self.last_trigger_ts: int = 0
        self.min_interval_ms = min_interval_ms

    def detect(self, spectrum: np.ndarray) -> Optional[OnsetEvent]:
        """检测当前帧是否触发 onset.

        Args:
            spectrum: FFT 幅度谱 (1D float32 数组).

        Returns:
            触发时返回 OnsetEvent, 否则 None.
        """
        now_ms = int(time.time() * 1000)

        # 1. Spectral Flux: 正频谱差之和
        if self.prev_spectrum is not None and len(self.prev_spectrum) == len(spectrum):
            diff = spectrum - self.prev_spectrum
            flux = float(np.sum(np.maximum(diff, 0.0)))
        else:
            flux = 0.0

        # 2. HFC (归一化): 高频加权能量
        k_axis = np.arange(len(spectrum), dtype=np.float32)
        hfc = float(np.sum(k_axis * spectrum) / max(len(spectrum), 1))

        # 3. 组合特征: flux + 0.3 * hfc
        combined = flux + 0.3 * hfc

        # 4. 更新历史
        self.flux_history.append(combined)
        self.prev_spectrum = spectrum.copy()

        # 历史不足, 无法判断阈值
        if len(self.flux_history) < 5:
            return None

        # 5. 自适应阈值: median + k * MAD
        threshold = self._adaptive_threshold()
        if combined <= threshold:
            return None

        # 6. 去抖
        if now_ms - self.last_trigger_ts < self.min_interval_ms:
            return None

        # 7. 计算强度 (归一化 [0, 1])
        intensity = max(0.0, min(1.0, (combined - threshold) / (threshold + 1e-6)))
        self.last_trigger_ts = now_ms
        return OnsetEvent(intensity=intensity, timestamp_ms=now_ms)

    def _adaptive_threshold(self) -> float:
        """median + k * MAD."""
        sorted_vals = np.sort(np.array(self.flux_history, dtype=np.float32))
        n = len(sorted_vals)
        mid = n // 2
        if n % 2 == 0:
            median = float((sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0)
        else:
            median = float(sorted_vals[mid])

        deviations = np.sort(np.abs(sorted_vals - median))
        if n % 2 == 0:
            mad = float((deviations[mid - 1] + deviations[mid]) / 2.0)
        else:
            mad = float(deviations[mid])

        return median + self.threshold_k * mad
