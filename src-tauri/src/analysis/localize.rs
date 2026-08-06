// 声音方位估计 (Sound Localization)
//
// 完整实现 ILD + GCC-PHAT ITD 融合, 输出 [-90°, +90°] 水平方位角
//
// ILD (Interaural Level Difference):
//   左右声道 RMS 比 → dB → 经验映射到角度
//
// GCC-PHAT (Generalized Cross-Correlation with Phase Transform):
//   1. 左右声道分别 FFT
//   2. 互相关 = X_l * conj(X_r) / |X_l * conj(X_r)|  (PHAT 加权)
//   3. IFFT 得到 R(τ)
//   4. 在 [-max_lag, +max_lag] 范围内找峰值 τ
//   5. τ → 角度: angle = asin(τ * c / (d * sr)) ≈ asin(τ / max_lag)
//
// 融合: 加权平均 (ILD 权重 0.6, ITD 权重 0.4)

use rustfft::num_complex::Complex;
use rustfft::{Fft, FftPlanner};

/// 最大时延样本数 (对应 ±90°)
/// @48kHz, 人头宽度约 0.15m, 声速 343m/s
/// max_lag = 0.15 / 343 * 48000 ≈ 21 (取 23 留余量)
const MAX_LAG: usize = 23;

/// 方位估计器
pub struct Localizer {
    /// FFT plan (复数→复数, 用于 GCC-PHAT)
    fft: std::sync::Arc<Fft<f32>>,
    /// IFFT plan
    ifft: std::sync::Arc<Fft<f32>>,
    /// FFT size (建议 2048, 与 onset FFT 一致)
    fft_size: usize,
    /// 临时缓冲
    left_complex: Vec<Complex<f32>>,
    right_complex: Vec<Complex<f32>>,
    /// 互相关结果
    cross_correlation: Vec<Complex<f32>>,
}

impl Localizer {
    /// 创建方位估计器
    ///
    /// fft_size 必须是 2 的幂, 建议 2048
    pub fn new(fft_size: usize) -> Self {
        let mut planner = FftPlanner::<f32>::new();
        let fft = planner.plan_fft_forward(fft_size);
        let ifft = planner.plan_fft_inverse(fft_size);

        Self {
            fft,
            ifft,
            fft_size,
            left_complex: vec![Complex { re: 0.0, im: 0.0 }; fft_size],
            right_complex: vec![Complex { re: 0.0, im: 0.0 }; fft_size],
            cross_correlation: vec![Complex { re: 0.0, im: 0.0 }; fft_size],
        }
    }

    /// 估计声音方位
    ///
    /// 输入: 左右声道时域样本 (长度 >= fft_size)
    /// 输出: 水平方位角 [-90.0, +90.0], 负=左, 正=右, 0=正前
    pub fn localize(&mut self, left: &[f32], right: &[f32]) -> f32 {
        let angle_from_ild = self.estimate_ild(left, right);
        let angle_from_itd = self.estimate_gcc_phat_itd(left, right);

        // 加权融合 (ILD 更可靠)
        let mut angle = 0.6 * angle_from_ild + 0.4 * angle_from_itd;

        // 钳制到 [-90, 90]
        if angle > 90.0 {
            angle = 90.0;
        } else if angle < -90.0 {
            angle = -90.0;
        }

        angle
    }

    /// ILD 方位估计
    ///
    /// 基于左右声道 RMS 比值, 用 dB 差映射到角度
    fn estimate_ild(&self, left: &[f32], right: &[f32]) -> f32 {
        let left_rms = rms(left);
        let right_rms = rms(right);

        // 避免除零
        if left_rms < 1e-6 && right_rms < 1e-6 {
            return 0.0;
        }

        let left_rms = left_rms.max(1e-6);
        let right_rms = right_rms.max(1e-6);

        // dB 差: 正值表示左声道响 (声源在左 → 负角度)
        let ild_db = 20.0 * (left_rms / right_rms).log10();

        // 经验映射: 1 dB 差约 5°
        // ild_db > 0 (左 > 右) → 角度为负 (偏左)
        let angle = -ild_db * 5.0;

        // 钳制
        if angle > 90.0 {
            90.0
        } else if angle < -90.0 {
            -90.0
        } else {
            angle
        }
    }

    /// GCC-PHAT ITD 方位估计
    ///
    /// 通过 PHAT 加权互相关估计时延差, 再映射到角度
    fn estimate_gcc_phat_itd(&mut self, left: &[f32], right: &[f32]) -> f32 {
        let n = self.fft_size.min(left.len().min(right.len()));

        // 1. 左右声道填入复数缓冲并 FFT
        for i in 0..n {
            self.left_complex[i] = Complex {
                re: left[i],
                im: 0.0,
            };
            self.right_complex[i] = Complex {
                re: right[i],
                im: 0.0,
            };
        }
        // 补零
        for i in n..self.fft_size {
            self.left_complex[i] = Complex { re: 0.0, im: 0.0 };
            self.right_complex[i] = Complex { re: 0.0, im: 0.0 };
        }

        self.fft.process(&mut self.left_complex).unwrap_or(());
        self.fft.process(&mut self.right_complex).unwrap_or(());

        // 2. PHAT 加权互相关: R = X_l * conj(X_r) / |X_l * conj(X_r)|
        for i in 0..self.fft_size {
            let xl = self.left_complex[i];
            let xr_conj = self.right_complex[i].conj();
            let product = xl * xr_conj;
            let magnitude = product.norm().max(1e-6);
            self.cross_correlation[i] = product.scale(1.0 / magnitude);
        }

        // 3. IFFT 得到时域互相关
        self.ifft.process(&mut self.cross_correlation).unwrap_or(());

        // 4. 在 [-MAX_LAG, +MAX_LAG] 范围内找峰值
        let mut max_val = 0.0f32;
        let mut max_lag = 0i32;

        for lag in -(MAX_LAG as i32)..=(MAX_LAG as i32) {
            let idx = if lag < 0 {
                self.fft_size - (-lag) as usize
            } else {
                lag as usize
            };
            let val = self.cross_correlation[idx].re;
            if val > max_val {
                max_val = val;
                max_lag = lag;
            }
        }

        // 5. 时延差 → 角度
        // itd > 0 (右声道先到) → 角度为正 (偏右)
        // angle = asin(lag / MAX_LAG) * 180 / π
        let ratio = max_lag as f32 / MAX_LAG as f32;
        let ratio_clamped = ratio.clamp(-1.0, 1.0);
        let angle = ratio_clamped.asin() * 180.0 / std::f32::consts::PI;

        angle
    }
}

/// 计算均方根
fn rms(samples: &[f32]) -> f32 {
    if samples.is_empty() {
        return 0.0;
    }
    let sum_sq: f32 = samples.iter().map(|s| s * s).sum();
    (sum_sq / samples.len() as f32).sqrt()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_localizer_creation() {
        let _ = Localizer::new(2048);
    }

    #[test]
    fn test_center_localization() {
        // 左右相同 → 应该接近 0°
        let mut loc = Localizer::new(2048);
        let samples: Vec<f32> = (0..2048)
            .map(|i| (2.0 * std::f32::consts::PI * 1000.0 * i as f32 / 48000.0).sin())
            .collect();
        let angle = loc.localize(&samples, &samples);
        assert!(
            angle.abs() < 15.0,
            "左右相同应定位在 0° 附近, 实际 {angle}°"
        );
    }

    #[test]
    fn test_left_localization() {
        // 左声道明显大于右 → 应定位在左侧 (负角度)
        let mut loc = Localizer::new(2048);
        let left: Vec<f32> = (0..2048)
            .map(|i| (2.0 * std::f32::consts::PI * 1000.0 * i as f32 / 48000.0).sin() * 1.0)
            .collect();
        let right: Vec<f32> = vec![0.0; 2048];
        let angle = loc.localize(&left, &right);
        assert!(
            angle < -10.0,
            "左声道响应定位在左侧 (负角度), 实际 {angle}°"
        );
    }
}
