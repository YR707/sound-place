"""声音方位估计 (对应 src-tauri/src/analysis/localize.rs).

ILD + GCC-PHAT ITD 融合, 输出 [-90°, +90°] 水平方位角.
"""

from __future__ import annotations

import numpy as np

# 最大时延样本数, 对应 ±90°
# @48kHz, 人头宽度约 0.15m, 声速 343m/s
# max_lag = 0.15 / 343 * 48000 ≈ 21 (取 23 留余量)
MAX_LAG: int = 23


class Localizer:
    """方位估计器 (ILD + GCC-PHAT ITD)."""

    def __init__(self, fft_size: int = 2048) -> None:
        self.fft_size = fft_size

    def localize(self, left: np.ndarray, right: np.ndarray) -> float:
        """估计声音方位.

        Args:
            left: 左声道时域样本 (长度 >= fft_size).
            right: 右声道时域样本 (长度 >= fft_size).

        Returns:
            水平方位角 [-90.0, +90.0], 负=左, 正=右, 0=正前.
        """
        angle_ild = self._estimate_ild(left, right)
        angle_itd = self._estimate_gcc_phat_itd(left, right)

        # 加权融合 (ILD 更可靠, 权重 0.6; ITD 权重 0.4)
        angle = 0.6 * angle_ild + 0.4 * angle_itd

        # 钳制到 [-90, 90]
        return float(max(-90.0, min(90.0, angle)))

    def _estimate_ild(self, left: np.ndarray, right: np.ndarray) -> float:
        """ILD 方位估计: 左右 RMS 比 → dB → 角度."""
        left_rms = _rms(left)
        right_rms = _rms(right)

        # 静音时返回 0
        if left_rms < 1e-6 and right_rms < 1e-6:
            return 0.0

        left_rms = max(left_rms, 1e-6)
        right_rms = max(right_rms, 1e-6)

        # dB 差: 正值表示左声道响 (声源在左 → 负角度)
        ild_db = 20.0 * np.log10(left_rms / right_rms)

        # 经验映射: 1 dB 差约 5°, ild_db > 0 (左 > 右) → 角度为负 (偏左)
        angle = -ild_db * 5.0
        return float(max(-90.0, min(90.0, angle)))

    def _estimate_gcc_phat_itd(self, left: np.ndarray, right: np.ndarray) -> float:
        """GCC-PHAT ITD 估计."""
        n = min(self.fft_size, min(len(left), len(right)))

        # 1. 填充到 fft_size (补零)
        left_padded = np.zeros(self.fft_size, dtype=np.float32)
        right_padded = np.zeros(self.fft_size, dtype=np.float32)
        left_padded[:n] = left[:n]
        right_padded[:n] = right[:n]

        # 2. 左右声道 FFT
        xl = np.fft.rfft(left_padded)
        xr = np.fft.rfft(right_padded)

        # 3. PHAT 加权互相关: R = X_l * conj(X_r) / |X_l * conj(X_r)|
        cross = xl * np.conj(xr)
        magnitude = np.maximum(np.abs(cross), 1e-6)
        cross_phat = cross / magnitude

        # 4. IFFT 得到时域互相关 (完整 FFT 长度)
        # irfft 输出长度默认 fft_size, 因为 cross_phat 是 rfft 频谱
        cross_time = np.fft.irfft(cross_phat, n=self.fft_size)

        # 5. 在 [-MAX_LAG, +MAX_LAG] 范围内找峰值
        max_val = 0.0
        max_lag = 0
        for lag in range(-MAX_LAG, MAX_LAG + 1):
            idx = (self.fft_size + lag) % self.fft_size if lag < 0 else lag
            val = float(cross_time[idx].real) if np.iscomplexobj(cross_time) else float(cross_time[idx])
            if val > max_val:
                max_val = val
                max_lag = lag

        # 6. 时延差 → 角度: angle = asin(lag / MAX_LAG) * 180 / π
        # itd > 0 (右声道先到) → 角度为正 (偏右)
        ratio = max_lag / MAX_LAG
        ratio_clamped = max(-1.0, min(1.0, ratio))
        angle = np.arcsin(ratio_clamped) * 180.0 / np.pi
        return float(angle)


def _rms(samples: np.ndarray) -> float:
    """计算均方根."""
    if len(samples) == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(samples.astype(np.float64)))))
