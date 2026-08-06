// 声音类型分类器
//
// 基于 FFT 频谱形状规则分类:
// - 脚步 (footstep): 80-400Hz 能量占比 > 40%, 持续 < 200ms
// - 枪声 (gunshot): 宽带瞬态 + 2-12kHz 高频能量 > 30%, 持续 < 100ms
// - 载具 (vehicle): 持续低频 (< 200Hz) + 谐波结构, 持续 > 500ms
// - 通用 (generic): 不符合上述规则的瞬态事件

use super::fft::Spectrum;

/// 声音类型
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum SoundType {
    Footstep,
    Gunshot,
    Vehicle,
    Generic,
}

impl SoundType {
    /// 转为字符串(用于前端)
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Footstep => "footstep",
            Self::Gunshot => "gunshot",
            Self::Vehicle => "vehicle",
            Self::Generic => "generic",
        }
    }
}

/// 频段能量分布
#[derive(Clone, Debug)]
struct BandEnergy {
    /// 总能量
    total: f32,
    /// 低频 (80-400Hz) 能量
    low: f32,
    /// 高频 (2-12kHz) 能量
    high: f32,
    /// 极低频 (< 200Hz) 能量
    sub_bass: f32,
}

/// 分类器
pub struct Classifier {
    /// 采样率(用于频率→bin 转换)
    sample_rate: u32,
    /// FFT size
    fft_size: usize,
    /// 上次事件时间戳(用于估算持续时间)
    last_event_ts: u64,
    /// 上一帧的频谱特征(用于检测谐波结构)
    prev_band_energy: Option<BandEnergy>,
}

impl Classifier {
    pub fn new(sample_rate: u32, fft_size: usize) -> Self {
        Self {
            sample_rate,
            fft_size,
            last_event_ts: 0,
            prev_band_energy: None,
        }
    }

    /// 分类
    ///
    /// spectrum: FFT 幅度谱
    /// timestamp_ms: 当前事件时间戳
    /// onset_duration_ms: onset 检测器报告的持续时间估算
    pub fn classify(
        &mut self,
        spectrum: &Spectrum,
        timestamp_ms: u64,
        onset_duration_ms: u32,
    ) -> SoundType {
        let bands = self.compute_band_energy(spectrum);

        // 脚步: 低频集中
        let low_ratio = if bands.total > 1e-6 {
            bands.low / bands.total
        } else {
            0.0
        };
        if low_ratio > 0.4 && onset_duration_ms < 200 {
            self.prev_band_energy = Some(bands);
            self.last_event_ts = timestamp_ms;
            return SoundType::Footstep;
        }

        // 枪声: 高频能量大 + 短瞬态
        let high_ratio = if bands.total > 1e-6 {
            bands.high / bands.total
        } else {
            0.0
        };
        if high_ratio > 0.3 && onset_duration_ms < 100 {
            self.prev_band_energy = Some(bands);
            self.last_event_ts = timestamp_ms;
            return SoundType::Gunshot;
        }

        // 载具: 持续低频 (这里用 onset_duration_ms 不准确, 实际应通过持续事件流判断)
        // 简化: 如果低频占比 > 50% 且持续时间 > 500ms, 视为载具
        let sub_bass_ratio = if bands.total > 1e-6 {
            bands.sub_bass / bands.total
        } else {
            0.0
        };
        if sub_bass_ratio > 0.5 && onset_duration_ms > 500 {
            self.prev_band_energy = Some(bands);
            self.last_event_ts = timestamp_ms;
            return SoundType::Vehicle;
        }

        // 其他
        self.prev_band_energy = Some(bands);
        self.last_event_ts = timestamp_ms;
        SoundType::Generic
    }

    /// 计算各频段能量
    fn compute_band_energy(&self, spectrum: &Spectrum) -> BandEnergy {
        let bin_hz = self.sample_rate as f32 / self.fft_size as f32;

        // 频段对应的 bin 范围
        let low_start = Self::hz_to_bin(80.0, bin_hz);
        let low_end = Self::hz_to_bin(400.0, bin_hz);
        let high_start = Self::hz_to_bin(2000.0, bin_hz);
        let high_end = Self::hz_to_bin(12000.0, bin_hz);
        let sub_bass_end = Self::hz_to_bin(200.0, bin_hz);

        let mut total = 0.0f32;
        let mut low = 0.0f32;
        let mut high = 0.0f32;
        let mut sub_bass = 0.0f32;

        for (k, mag) in spectrum.iter().enumerate() {
            let energy = mag * mag;
            total += energy;

            if k >= low_start && k < low_end {
                low += energy;
            }
            if k >= high_start && k < high_end {
                high += energy;
            }
            if k < sub_bass_end {
                sub_bass += energy;
            }
        }

        BandEnergy {
            total,
            low,
            high,
            sub_bass,
        }
    }

    /// 频率 → bin 索引
    fn hz_to_bin(hz: f32, bin_hz: f32) -> usize {
        (hz / bin_hz).round() as usize
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_classify_footstep() {
        let mut classifier = Classifier::new(48000, 2048);
        // 构造 200Hz 主导的频谱 (脚步特征)
        let mut spectrum = vec![0.0; 1025];
        let bin_200hz = (200.0 / (48000.0 / 2048.0)).round() as usize;
        for i in bin_200hz.saturating_sub(2)..bin_200hz + 3 {
            if i < spectrum.len() {
                spectrum[i] = 10.0;
            }
        }
        let result = classifier.classify(&spectrum, 0, 100);
        assert_eq!(result, SoundType::Footstep);
    }

    #[test]
    fn test_classify_gunshot() {
        let mut classifier = Classifier::new(48000, 2048);
        // 构造 5kHz 主导的频谱 (枪声特征)
        let mut spectrum = vec![0.0; 1025];
        let bin_5khz = (5000.0 / (48000.0 / 2048.0)).round() as usize;
        for i in bin_5khz.saturating_sub(2)..bin_5khz + 3 {
            if i < spectrum.len() {
                spectrum[i] = 10.0;
            }
        }
        let result = classifier.classify(&spectrum, 0, 50);
        assert_eq!(result, SoundType::Gunshot);
    }
}
