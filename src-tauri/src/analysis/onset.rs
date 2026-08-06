// 瞬态事件检测 (Onset Detection)
//
// 基于 Spectral Flux + HFC 两个特征检测瞬态事件(脚步/枪声)
//
// 算法:
// 1. Spectral Flux: 正频谱差之和, 反映能量上升
//    flux = Σ max(0, |X_t[k]| - |X_{t-1}[k]|)
// 2. HFC (High Frequency Content): 高频能量加权, 对打击声敏感
//    hfc = Σ k * |X_t[k]|
// 3. 自适应阈值: 滑动窗口(约 20 帧)计算中位数 + k×MAD
// 4. 去抖: 同一类型事件最小间隔 100ms (可由 profile 配置)

use std::collections::VecDeque;
use std::time::{SystemTime, UNIX_EPOCH};

use super::fft::Spectrum;

/// Onset 检测事件
#[derive(Clone, Debug)]
pub struct OnsetEvent {
    /// 强度 [0.0, 1.0]
    pub intensity: f32,
    /// 时间戳(毫秒)
    pub timestamp: u64,
}

/// Onset 检测器
pub struct OnsetDetector {
    /// 上一帧的频谱(用于计算 Spectral Flux)
    prev_spectrum: Option<Spectrum>,
    /// 滑动窗口存储最近 N 帧的 flux 值, 用于自适应阈值
    flux_history: VecDeque<f32>,
    /// 滑动窗口大小
    window_size: usize,
    /// 阈值倍数 k (阈值 = median + k * MAD)
    threshold_k: f32,
    /// 上次触发时间戳(毫秒), 用于去抖
    last_trigger_ts: u64,
    /// 最小事件间隔(毫秒)
    min_interval_ms: u64,
}

impl OnsetDetector {
    /// 创建默认配置的检测器
    pub fn new() -> Self {
        Self {
            prev_spectrum: None,
            flux_history: VecDeque::with_capacity(32),
            window_size: 20,
            threshold_k: 3.0,
            last_trigger_ts: 0,
            min_interval_ms: 100,
        }
    }

    /// 用 profile 参数构造
    pub fn with_config(threshold_k: f32, min_interval_ms: u32) -> Self {
        let mut d = Self::new();
        d.threshold_k = threshold_k;
        d.min_interval_ms = min_interval_ms as u64;
        d
    }

    /// 检测是否触发 onset
    ///
    /// 输入当前帧的频谱(左右声道任一, 通常用左声道或合并)
    pub fn detect(&mut self, spectrum: &Spectrum) -> Option<OnsetEvent> {
        let now_ms = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_millis() as u64)
            .unwrap_or(0);

        // 计算 Spectral Flux
        let flux = match &self.prev_spectrum {
            Some(prev) if prev.len() == spectrum.len() => {
                let mut sum = 0.0f32;
                for (cur, p) in spectrum.iter().zip(prev.iter()) {
                    let diff = cur - p;
                    if diff > 0.0 {
                        sum += diff;
                    }
                }
                sum
            }
            _ => 0.0,
        };

        // 计算 HFC (归一化)
        let hfc: f32 = spectrum
            .iter()
            .enumerate()
            .map(|(k, mag)| k as f32 * mag)
            .sum::<f32>()
            / spectrum.len().max(1) as f32;

        // 组合特征: flux + 0.3 * hfc (flux 为主, hfc 辅助)
        let combined = flux + 0.3 * hfc;

        // 更新历史
        self.flux_history.push_back(combined);
        if self.flux_history.len() > self.window_size {
            self.flux_history.pop_front();
        }

        // 更新 prev_spectrum
        self.prev_spectrum = Some(spectrum.clone());

        // 历史不足时无法判断阈值
        if self.flux_history.len() < 5 {
            return None;
        }

        // 计算自适应阈值: median + k * MAD
        let threshold = self.adaptive_threshold();
        if combined <= threshold {
            return None;
        }

        // 去抖
        if now_ms.saturating_sub(self.last_trigger_ts) < self.min_interval_ms {
            return None;
        }

        // 计算强度(归一化到 [0, 1])
        let intensity = ((combined - threshold) / (threshold + 1e-6)).clamp(0.0, 1.0);

        self.last_trigger_ts = now_ms;
        Some(OnsetEvent {
            intensity,
            timestamp: now_ms,
        })
    }

    /// 计算自适应阈值 = median + k * MAD
    fn adaptive_threshold(&self) -> f32 {
        let mut sorted: Vec<f32> = self.flux_history.iter().copied().collect();
        sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));

        let mid = sorted.len() / 2;
        let median = if sorted.len() % 2 == 0 {
            (sorted[mid - 1] + sorted[mid]) / 2.0
        } else {
            sorted[mid]
        };

        // MAD = Median Absolute Deviation
        let mut deviations: Vec<f32> = sorted.iter().map(|x| (x - median).abs()).collect();
        deviations.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        let mad_mid = deviations.len() / 2;
        let mad = if deviations.len() % 2 == 0 {
            (deviations[mad_mid - 1] + deviations[mad_mid]) / 2.0
        } else {
            deviations[mad_mid]
        };

        median + self.threshold_k * mad
    }
}

impl Default for OnsetDetector {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_no_onset_for_silence() {
        let mut detector = OnsetDetector::new();
        let spectrum = vec![0.0; 1024];
        // 静音不应触发
        for _ in 0..30 {
            assert!(detector.detect(&spectrum).is_none());
        }
    }

    #[test]
    fn test_detect_onset_on_energy_burst() {
        let mut detector = OnsetDetector::new();
        let silence = vec![0.0; 1024];

        // 先喂 20 帧静音建立基线
        for _ in 0..20 {
            detector.detect(&silence);
        }

        // 突然能量爆发
        let loud: Spectrum = (0..1024).map(|i| (i as f32 / 100.0).sin() * 10.0).collect();
        let event = detector.detect(&loud);
        assert!(event.is_some(), "应在能量爆发时触发 onset");
    }
}
