"""Onset 检测 (对应 src-tauri/src/analysis/onset.rs).

Spectral Flux + HFC 组合, 自适应阈值 (median + k×MAD), 去抖.

优化 (针对实时捕获背景噪声过触发):
- 增加 min_absolute_flux 阈值: 背景噪声 flux < 1.0 时直接拒绝
- 提高 threshold_k 从 3.0 → 5.0 (更严格)
- 增加最小间隔 100ms → 150ms
- intensity 归一化用 max(threshold, min_absolute_flux) 避免除以小数放大噪声
"""

from __future__ import annotations

import time
from collections import deque
from typing import Optional

import numpy as np

# Spectrum 类型别名 (与 fft.py 一致)
Spectrum = np.ndarray

# 背景噪声的典型 flux 水平 (经验值, 低于此值认为是噪声)
# 实测: 静音时 flux ≈ 0, 系统空闲时 flux ≈ 0.1-0.5, 音乐瞬时 flux > 5
# 调低一点 (从 1.0 → 0.5) 以便真实声音能触发
MIN_ABSOLUTE_FLUX: float = 0.5


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
        window_size: int = 30,
        threshold_k: float = 5.0,
        min_interval_ms: int = 150,
        min_absolute_flux: float = MIN_ABSOLUTE_FLUX,
    ) -> None:
        self.prev_spectrum: Optional[np.ndarray] = None
        self.flux_history: deque[float] = deque(maxlen=window_size)
        self.window_size = window_size
        self.threshold_k = threshold_k
        self.last_trigger_ts: int = 0
        self.min_interval_ms = min_interval_ms
        self.min_absolute_flux = min_absolute_flux

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
        if len(self.flux_history) < 10:
            return None

        # 5. 自适应阈值: median + k * MAD
        threshold = self._adaptive_threshold()
        # 取自适应阈值和绝对阈值中的较大者
        effective_threshold = max(threshold, self.min_absolute_flux)
        if combined <= effective_threshold:
            return None

        # 6. 去抖
        if now_ms - self.last_trigger_ts < self.min_interval_ms:
            return None

        # 7. 计算强度 (归一化 [0, 1])
        # 用 effective_threshold 做分母, 避免 background 噪声放大
        intensity = max(0.0, min(1.0, (combined - effective_threshold) / (effective_threshold + 1e-6)))
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
