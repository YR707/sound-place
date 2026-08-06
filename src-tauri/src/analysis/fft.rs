// FFT 频谱分析
//
// 封装 realfft crate, 预计算 Hann 窗, 对左右声道分别做 FFT 输出幅度谱
// 设计:
// - FFT size = 2048 (约 42ms @48kHz), 频率分辨率约 23Hz
// - Hann 窗减少频谱泄漏
// - 跳跃长度 hop = 1024 (50% overlap), 平衡时间分辨率与计算量

use realfft::{RealFftPlanner, RealToComplex};
use rustfft::num_complex::Complex;

/// 单声道的频谱数据(只含正频率, 长度 = fft_size/2)
pub type Spectrum = Vec<f32>;

/// FFT 分析器
///
/// 预计算 Hann 窗与 FFT plan, 可重复调用 analyze
pub struct FftAnalyzer {
    fft_size: usize,
    /// Hann 窗, 长度 = fft_size
    window: Vec<f32>,
    /// realfft plan (实数 → 复数)
    r2c: RealToComplex<f32>,
    /// 临时缓冲: 加窗后的输入
    windowed_input: Vec<f32>,
    /// 临时缓冲: FFT 输出(复数)
    spectrum_complex: Vec<num_complex::Complex32>,
}

impl FftAnalyzer {
    /// 创建 FFT 分析器
    ///
    /// fft_size 必须是 2 的幂, 推荐 2048
    pub fn new(fft_size: usize) -> Self {
        let mut planner = RealFftPlanner::<f32>::new();
        let r2c = planner.prepare_fft_to_vec(fft_size);

        // 预计算 Hann 窗: hann[i] = 0.5 - 0.5 * cos(2πi/N)
        let window: Vec<f32> = (0..fft_size)
            .map(|i| {
                let t = i as f32 / fft_size as f32;
                0.5 - 0.5 * (2.0 * std::f32::consts::PI * t).cos()
            })
            .collect();

        Self {
            fft_size,
            window,
            r2c,
            windowed_input: vec![0.0; fft_size],
            spectrum_complex: vec![
                Complex {
                    re: 0.0,
                    im: 0.0
                };
                fft_size / 2 + 1
            ],
        }
    }

    /// 分析左右声道, 返回 (左幅度谱, 右幅度谱)
    ///
    /// 输入 samples 长度必须 >= fft_size, 只取前 fft_size 个样本
    pub fn analyze(&mut self, left: &[f32], right: &[f32]) -> (Spectrum, Spectrum) {
        let left_spectrum = self.analyze_single(left);
        let right_spectrum = self.analyze_single(right);
        (left_spectrum, right_spectrum)
    }

    /// 分析单个声道
    fn analyze_single(&mut self, samples: &[f32]) -> Spectrum {
        let n = self.fft_size.min(samples.len());

        // 1. 加窗
        for i in 0..n {
            self.windowed_input[i] = samples[i] * self.window[i];
        }
        // 补零(如果输入短于 fft_size)
        for i in n..self.fft_size {
            self.windowed_input[i] = 0.0;
        }

        // 2. FFT (实数 → 复数)
        self.r2c
            .process(&mut self.windowed_input, &mut self.spectrum_complex)
            .expect("FFT 失败");

        // 3. 计算幅度谱 |X[k]|
        self.spectrum_complex
            .iter()
            .map(|c| (c.re * c.re + c.im * c.im).sqrt())
            .collect()
    }

    /// 获取 FFT size
    pub fn fft_size(&self) -> usize {
        self.fft_size
    }

    /// 给定采样率, 计算第 k 个频谱 bin 对应的频率(Hz)
    pub fn bin_to_hz(&self, bin: usize, sample_rate: u32) -> f32 {
        bin as f32 * sample_rate as f32 / self.fft_size as f32
    }

    /// 给定频率(Hz), 计算对应的频谱 bin 索引
    pub fn hz_to_bin(&self, hz: f32, sample_rate: u32) -> usize {
        (hz * self.fft_size as f32 / sample_rate as f32).round() as usize
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_fft_size() {
        let analyzer = FftAnalyzer::new(2048);
        assert_eq!(analyzer.fft_size(), 2048);
    }

    #[test]
    fn test_analyze_sine_wave() {
        // 1kHz 正弦波 @48kHz
        let mut samples = vec![0.0; 2048];
        let freq = 1000.0;
        let sr = 48000.0;
        for i in 0..2048 {
            samples[i] = (2.0 * std::f32::consts::PI * freq * i as f32 / sr).sin();
        }

        let mut analyzer = FftAnalyzer::new(2048);
        let spectrum = analyzer.analyze_single(&samples);

        // 峰值应在 1000Hz 对应的 bin
        let peak_bin = spectrum
            .iter()
            .enumerate()
            .max_by(|a, b| a.1.partial_cmp(b.1).unwrap())
            .unwrap()
            .0;
        let peak_hz = analyzer.bin_to_hz(peak_bin, 48000);
        // 允许误差 ±50Hz (一个 bin 宽度约 23Hz)
        assert!(
            (peak_hz - 1000.0).abs() < 50.0,
            "峰值频率应在 1000Hz 附近, 实际 {peak_hz}Hz"
        );
    }
}
