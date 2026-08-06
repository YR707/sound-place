// 声音分析模块
//
// 职责: 从 ring buffer 读取音频帧 → FFT → onset 检测 → 方位估计 → 分类 → emit 事件
//
// 子模块:
// - fft: realfft 封装 + Hann 窗, 输出左右声道幅度谱
// - onset: Spectral Flux + HFC 瞬态检测
// - localize: ILD + GCC-PHAT ITD 融合, 输出 [-90°, +90°] 水平方位角
// - classify: 频谱形状规则分类 (脚步/枪声/载具/通用)
// - worker: 分析线程, 串联以上模块并 emit sound_event 到前端

pub mod classify;
pub mod fft;
pub mod localize;
pub mod onset;
pub mod worker;

use serde::Serialize;

/// 声音事件 payload, emit 到前端
#[derive(Clone, Debug, Serialize)]
pub struct SoundEvent {
    /// 水平方位角 [-90.0, +90.0], 负=左, 正=右, 0=正前
    pub angle: f32,
    /// 强度 [0.0, 1.0]
    pub intensity: f32,
    /// 声音类型 "footstep" | "gunshot" | "vehicle" | "generic"
    pub sound_type: String,
    /// 时间戳(毫秒, 用于前端动画)
    pub timestamp: u64,
}
