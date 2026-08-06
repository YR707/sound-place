"""FFT 频谱分析 (对应 src-tauri/src/analysis/fft.rs).

使用 numpy.fft.rfft 替代 realfft, 预计算 Hann 窗.
FFT size 默认 2048, hop 默认 1024 (50% overlap).
"""

from __future__ import annotations

from typing import Union

import numpy as np

# 类型别名: 频谱数据 (只含正频率, 长度 = fft_size//2 + 1)
Spectrum = np.ndarray


class FftAnalyzer:
    """FFT 分析器, 预计算 Hann 窗, 可重复调用 analyze."""

    def __init__(self, fft_size: int = 2048) -> None:
        if fft_size <= 0 or (fft_size & (fft_size - 1)) != 0:
            raise ValueError(f"fft_size 必须是 2 的幂, 得到 {fft_size}")
        self.fft_size = fft_size
        # Hann 窗: hann[i] = 0.5 - 0.5 * cos(2π i / N)
        i = np.arange(fft_size, dtype=np.float32)
        self.window = 0.5 - 0.5 * np.cos(2.0 * np.pi * i / fft_size)

    def analyze(self, left: np.ndarray, right: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """分析左右声道, 返回 (左幅度谱, 右幅度谱)."""
        return self.analyze_single(left), self.analyze_single(right)

    def analyze_single(self, samples: np.ndarray) -> np.ndarray:
        """分析单个声道: 加窗 → rfft → 幅度谱."""
        n = min(self.fft_size, len(samples))
        windowed = np.zeros(self.fft_size, dtype=np.float32)
        windowed[:n] = samples[:n] * self.window[:n]
        # 实数 FFT, 输出长度 = fft_size//2 + 1
        spectrum_complex = np.fft.rfft(windowed)
        magnitude = np.abs(spectrum_complex)
        return magnitude.astype(np.float32)

    def bin_to_hz(self, bin_idx: int, sample_rate: int) -> float:
        """第 k 个频谱 bin 对应的频率 (Hz)."""
        return bin_idx * sample_rate / self.fft_size

    def hz_to_bin(self, hz: float, sample_rate: int) -> int:
        """频率 (Hz) 对应的 bin 索引."""
        return int(round(hz * self.fft_size / sample_rate))
