"""声音类型分类器 (对应 src-tauri/src/analysis/classify.rs).

基于频谱形状规则分类:
- 脚步 (footstep): 80-400Hz 能量占比 > 40%, 持续 < 200ms
- 枪声 (gunshot): 高频 2-12kHz 能量占比 > 30%, 持续 < 100ms
- 载具 (vehicle): 极低频 < 200Hz 占比 > 50%, 持续 > 500ms
- 通用 (generic): 不符合上述规则的瞬态事件

优化 (避免背景噪声误判):
- 增加绝对能量阈值: 总能量低于阈值时返回 NONE (不是 generic)
- 提高 gunshot 高频占比阈值 30% → 40%
- 提高 footstep 低频占比阈值 40% → 50%
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

import numpy as np

# Spectrum 类型别名 (与 fft.py 一致)
Spectrum = np.ndarray

# 总能量阈值: 低于此值认为是噪声, 不分类
# magnitude^2 的和, 实测背景噪声 total ≈ 0.1-1.0, 音乐瞬态 total > 10
# 调低一点 (从 2.0 → 0.5) 以便真实声音能触发
MIN_TOTAL_ENERGY: float = 0.5


class SoundType(str, Enum):
    FOOTSTEP = "footstep"
    GUNSHOT = "gunshot"
    VEHICLE = "vehicle"
    GENERIC = "generic"
    NONE = "none"  # 噪声/能量不足, 不输出


class _BandEnergy:
    __slots__ = ("total", "low", "high", "sub_bass")

    def __init__(self, total: float, low: float, high: float, sub_bass: float) -> None:
        self.total = total
        self.low = low
        self.high = high
        self.sub_bass = sub_bass


class Classifier:
    """频谱形状规则分类器."""

    def __init__(
        self,
        sample_rate: int,
        fft_size: int,
        min_total_energy: float = MIN_TOTAL_ENERGY,
    ) -> None:
        self.sample_rate = sample_rate
        self.fft_size = fft_size
        self.min_total_energy = min_total_energy
        self.last_event_ts: int = 0
        self.prev_band_energy: Optional[_BandEnergy] = None

    def classify(
        self,
        spectrum: np.ndarray,
        timestamp_ms: int,
        onset_duration_ms: int,
    ) -> SoundType:
        """分类.

        Args:
            spectrum: FFT 幅度谱 (1D float32).
            timestamp_ms: 当前事件时间戳 (ms).
            onset_duration_ms: onset 持续时间估算 (ms).

        Returns:
            SoundType 枚举. 能量不足时返回 NONE.
        """
        bands = self._compute_band_energy(spectrum)

        # 噪声门限: 总能量太低不分类
        if bands.total < self.min_total_energy:
            return SoundType.NONE

        # 脚步: 低频 (80-400Hz) 占比 > 50%, 持续 < 200ms
        low_ratio = bands.low / bands.total if bands.total > 1e-6 else 0.0
        if low_ratio > 0.5 and onset_duration_ms < 200:
            self.prev_band_energy = bands
            self.last_event_ts = timestamp_ms
            return SoundType.FOOTSTEP

        # 枪声: 高频 (2-12kHz) 占比 > 40%, 持续 < 100ms
        high_ratio = bands.high / bands.total if bands.total > 1e-6 else 0.0
        if high_ratio > 0.4 and onset_duration_ms < 100:
            self.prev_band_energy = bands
            self.last_event_ts = timestamp_ms
            return SoundType.GUNSHOT

        # 载具: 极低频 (< 200Hz) 占比 > 50%, 持续 > 500ms
        sub_bass_ratio = bands.sub_bass / bands.total if bands.total > 1e-6 else 0.0
        if sub_bass_ratio > 0.5 and onset_duration_ms > 500:
            self.prev_band_energy = bands
            self.last_event_ts = timestamp_ms
            return SoundType.VEHICLE

        # 其他 (有足够能量但不匹配特定模式)
        self.prev_band_energy = bands
        self.last_event_ts = timestamp_ms
        return SoundType.GENERIC

    def _compute_band_energy(self, spectrum: np.ndarray) -> _BandEnergy:
        """计算各频段能量."""
        bin_hz = self.sample_rate / self.fft_size

        low_start = _hz_to_bin(80.0, bin_hz)
        low_end = _hz_to_bin(400.0, bin_hz)
        high_start = _hz_to_bin(2000.0, bin_hz)
        high_end = _hz_to_bin(12000.0, bin_hz)
        sub_bass_end = _hz_to_bin(200.0, bin_hz)

        # 能量 = magnitude^2
        energy = spectrum.astype(np.float64) ** 2
        total = float(np.sum(energy))

        # 用切片求和 (比逐元素循环快得多)
        low = float(np.sum(energy[low_start:low_end]))
        high = float(np.sum(energy[high_start:high_end]))
        sub_bass = float(np.sum(energy[:sub_bass_end]))

        return _BandEnergy(total=total, low=low, high=high, sub_bass=sub_bass)


def _hz_to_bin(hz: float, bin_hz: float) -> int:
    return int(round(hz / bin_hz))
