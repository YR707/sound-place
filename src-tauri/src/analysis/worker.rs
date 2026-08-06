// 分析 worker 线程
//
// 职责:
// 1. 从 ring buffer 消费音频帧
// 2. 调用 SessionFilter 判断是否处理(集成阶段 2 遗留)
// 3. FFT 分析
// 4. Onset 检测
// 5. 触发时: 方位估计 + 分类
// 6. 构造 SoundEvent + emit 到前端
//
// 线程模型沿用 CaptureThread 模式: stop_flag + JoinHandle

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread::{self, JoinHandle};
use std::time::Duration;

use log::{error, info, warn};
use tauri::{AppHandle, Emitter};

use crate::audio::ring_buffer::{available_frames, dequeue_batch, FrameConsumer, StereoFrame};
use crate::audio::session_filter::SessionFilter;

use super::classify::{Classifier, SoundType};
use super::fft::FftAnalyzer;
use super::localize::Localizer;
use super::onset::OnsetDetector;
use super::SoundEvent;

/// 默认 FFT size
const DEFAULT_FFT_SIZE: usize = 2048;
/// hop size (每次读取的帧数)
const DEFAULT_HOP_SIZE: usize = 1024;
/// 采样率
const SAMPLE_RATE: u32 = 48000;

/// 分析线程控制块
pub struct AnalysisWorker {
    stop_flag: Arc<AtomicBool>,
    handle: Option<JoinHandle<()>>,
}

impl AnalysisWorker {
    /// 启动分析线程
    ///
    /// consumer: 环形缓冲的消费者端
    /// app: Tauri AppHandle (用于 emit 事件)
    /// process_names: 进程白名单(空表示不过滤)
    pub fn start(
        consumer: FrameConsumer,
        app: AppHandle,
        process_names: Vec<String>,
    ) -> Result<Self, String> {
        let stop_flag = Arc::new(AtomicBool::new(false));
        let stop_for_thread = stop_flag.clone();

        let handle = thread::Builder::new()
            .name("soundplace-analysis".to_string())
            .spawn(move || {
                if let Err(e) = analysis_loop(&stop_for_thread, consumer, &app, process_names) {
                    error!("分析线程异常退出: {e}");
                }
            })
            .map_err(|e| format!("启动分析线程失败: {e}"))?;

        Ok(Self {
            stop_flag,
            handle: Some(handle),
        })
    }

    /// 停止分析线程并等待退出
    pub fn stop(mut self) -> Result<(), String> {
        self.stop_flag.store(true, Ordering::SeqCst);
        if let Some(handle) = self.handle.take() {
            handle
                .join()
                .map_err(|_| "分析线程 join 失败".to_string())?;
        }
        Ok(())
    }
}

/// 分析线程主循环
fn analysis_loop(
    stop_flag: &Arc<AtomicBool>,
    mut consumer: FrameConsumer,
    app: &AppHandle,
    process_names: Vec<String>,
) -> Result<(), String> {
    // 初始化各模块
    let mut fft_analyzer = FftAnalyzer::new(DEFAULT_FFT_SIZE);
    let mut onset_detector = OnsetDetector::new();
    let mut localizer = Localizer::new(DEFAULT_FFT_SIZE);
    let mut classifier = Classifier::new(SAMPLE_RATE, DEFAULT_FFT_SIZE);
    let session_filter = SessionFilter::new(&process_names);

    // 累积缓冲: 当数据不足 fft_size 时继续累积
    let mut left_accum = Vec::<f32>::with_capacity(DEFAULT_FFT_SIZE * 2);
    let mut right_accum = Vec::<f32>::with_capacity(DEFAULT_FFT_SIZE * 2);

    // 临时读取缓冲
    let mut read_buf = vec![StereoFrame::default(); DEFAULT_HOP_SIZE];

    info!("分析线程已启动 (FFT size={DEFAULT_FFT_SIZE}, hop={DEFAULT_HOP_SIZE})");

    while !stop_flag.load(Ordering::SeqCst) {
        // 1. 从 ring buffer 读取一批帧
        let n = dequeue_batch(&mut consumer, &mut read_buf);
        if n == 0 {
            // 没数据, 短暂休眠
            thread::sleep(Duration::from_millis(2));
            continue;
        }

        // 2. 进程过滤: 检查白名单进程是否活跃
        if session_filter.is_enabled() && !session_filter.should_process_audio() {
            // 白名单进程不活跃, 丢弃这批数据(并清空累积缓冲, 避免跨段误判)
            left_accum.clear();
            right_accum.clear();
            continue;
        }

        // 3. 解交错到左右声道并累积
        for i in 0..n {
            left_accum.push(read_buf[i].left);
            right_accum.push(read_buf[i].right);
        }

        // 4. 数据足够时进行 FFT 分析
        while left_accum.len() >= DEFAULT_FFT_SIZE {
            // 取 fft_size 个样本分析
            let left_chunk = &left_accum[..DEFAULT_FFT_SIZE];
            let right_chunk = &right_accum[..DEFAULT_FFT_SIZE];

            // FFT
            let (left_spectrum, right_spectrum) = fft_analyzer.analyze(left_chunk, right_chunk);

            // Onset 检测(用左声道频谱, 或合并频谱)
            let combined_spectrum: Vec<f32> = left_spectrum
                .iter()
                .zip(right_spectrum.iter())
                .map(|(l, r)| (l + r) * 0.5)
                .collect();

            if let Some(onset) = onset_detector.detect(&combined_spectrum) {
                // 触发 onset: 估计方位 + 分类
                let angle = localizer.localize(left_chunk, right_chunk);
                let sound_type = classifier.classify(&combined_spectrum, onset.timestamp, 100);

                let event = SoundEvent {
                    angle,
                    intensity: onset.intensity,
                    sound_type: sound_type.as_str().to_string(),
                    timestamp: onset.timestamp,
                };

                // emit 到前端
                if let Err(e) = app.emit("sound_event", &event) {
                    warn!("emit sound_event 失败: {e}");
                }
            }

            // 移除已分析的样本(保留 hop_size 个用于 overlap)
            // 简化: 直接丢弃 fft_size 个, 下次重新累积
            // (更优做法是滑动窗口, 但 v1 简化处理)
            left_accum.drain(0..DEFAULT_FFT_SIZE);
            right_accum.drain(0..DEFAULT_FFT_SIZE);
        }
    }

    info!("分析线程退出");
    Ok(())
}
