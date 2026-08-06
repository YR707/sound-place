// 音频捕获与处理模块
//
// 子模块:
// - ring_buffer: 无锁 SPSC 环形缓冲（生产者=捕获线程, 消费者=分析线程）
// - capture: WASAPI loopback 捕获线程
// - session_filter: 进程白名单过滤（IAudioSessionEnumerator）

pub mod capture;
pub mod ring_buffer;
pub mod session_filter;

// 公开导出关键类型,供 analysis 模块使用
pub use ring_buffer::{AudioFrame, StereoFrame};
