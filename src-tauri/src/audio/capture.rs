// WASAPI loopback 捕获线程
//
// 职责:
// 1. 初始化 COM + 获取默认渲染设备(扬声器)
// 2. 以 Direction::Capture 在渲染设备上初始化 AudioClient => loopback 模式
// 3. 轮询读取缓冲区,deinterleave 左右声道
// 4. 写入 SPSC 环形缓冲供分析线程消费
//
// 设计选择:
// - PollingShared 而非 EventsShared: 跨版本兼容性更好(老版本 Win10 不支持事件驱动 loopback)
// - 32-bit float 格式: 与 FFT 库兼容,无需额外转换
// - 自动重采样(autoconvert=true): 让音频引擎替我们处理格式转换

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread::{self, JoinHandle};
use std::time::Duration;

use log::{error, info, warn};
use wasapi::{
    initialize_mta, AudioCaptureClient, AudioClient, DeviceEnumerator, Direction, SampleType,
    StreamMode, WaveFormat,
};

use super::ring_buffer::{enqueue_batch, FrameProducer, StereoFrame};

/// 捕获线程的样本格式参数
const SAMPLE_RATE: u32 = 48000;
const CHANNELS: u16 = 2;
const BITS_PER_SAMPLE: u16 = 32;
const BUFFER_DURATION_HNS: i64 = 200_000; // 20ms

/// 捕获线程控制块
pub struct CaptureThread {
    /// 停止标志(捕获线程轮询)
    stop_flag: Arc<AtomicBool>,
    /// 线程句柄
    handle: Option<JoinHandle<()>>,
}

impl CaptureThread {
    /// 启动捕获线程
    ///
    /// producer: 环形缓冲的生产者端,捕获线程将数据写入这里
    pub fn start(mut producer: FrameProducer) -> Result<Self, String> {
        let stop_flag = Arc::new(AtomicBool::new(false));
        let stop_for_thread = stop_flag.clone();

        let handle = thread::Builder::new()
            .name("soundplace-audio-capture".to_string())
            .spawn(move || {
                if let Err(e) = capture_loop(&stop_for_thread, &mut producer) {
                    error!("音频捕获线程异常退出: {e}");
                }
            })
            .map_err(|e| format!("启动捕获线程失败: {e}"))?;

        Ok(Self {
            stop_flag,
            handle: Some(handle),
        })
    }

    /// 停止捕获线程并等待退出
    pub fn stop(mut self) -> Result<(), String> {
        self.stop_flag.store(true, Ordering::SeqCst);
        if let Some(handle) = self.handle.take() {
            handle
                .join()
                .map_err(|_| "捕获线程 join 失败".to_string())?;
        }
        Ok(())
    }
}

/// 捕获线程主循环
fn capture_loop(
    stop_flag: &Arc<AtomicBool>,
    producer: &mut FrameProducer,
) -> Result<(), String> {
    // 1. 初始化 COM (MTA,因为这是工作线程不是 UI 线程)
    initialize_mta().map_err(|e| format!("COM 初始化失败: hr=0x{:08X}", e))?;

    // 2. 获取默认渲染设备(扬声器)
    let enumerator =
        DeviceEnumerator::new().map_err(|e| format!("创建设备枚举器失败: {e:?}"))?;
    let render_device = enumerator
        .get_default_device(&Direction::Render)
        .map_err(|e| format!("获取默认渲染设备失败: {e:?}"))?;

    let device_name = render_device
        .get_friendly_name()
        .unwrap_or_else(|_| "<unknown>".to_string());
    info!("使用音频设备: {device_name}");

    // 3. 激活 AudioClient
    let mut audio_client = render_device
        .get_iaudioclient()
        .map_err(|e| format!("激活 AudioClient 失败: {e:?}"))?;

    // 4. 尝试获取 mix format;失败则构造一个标准格式
    let format = match audio_client.get_mixformat() {
        Ok(fmt) => {
            info!(
                "使用 mix format: {}Hz, {}ch, {}bit",
                fmt.get_samples_per_sec(),
                fmt.get_nchannels(),
                fmt.get_bits_per_sample()
            );
            // 如果 mix format 不是 2 声道或不是 float,降级到我们构造的格式
            if fmt.get_nchannels() >= 2 && fmt.get_bits_per_sample() == 32 {
                fmt
            } else {
                construct_default_format()
            }
        }
        Err(e) => {
            warn!("获取 mix format 失败,使用默认格式: {e:?}");
            construct_default_format()
        }
    };

    // 5. 初始化 client (Capture 方向 + Shared Polling = loopback)
    let mode = StreamMode::PollingShared {
        autoconvert: true,
        buffer_duration_hns: BUFFER_DURATION_HNS,
    };
    audio_client
        .initialize_client(&format, &Direction::Capture, &mode)
        .map_err(|e| format!("初始化 AudioClient 失败: {e:?}"))?;

    // 6. 获取捕获客户端
    let capture_client = audio_client
        .get_audiocaptureclient()
        .map_err(|e| format!("获取 AudioCaptureClient 失败: {e:?}"))?;

    // 7. 启动流
    audio_client
        .start_stream()
        .map_err(|e| format!("启动音频流失败: {e:?}"))?;
    info!("音频捕获已启动 ({}Hz, {}ch)", SAMPLE_RATE, CHANNELS);

    // 8. 轮询读取循环
    let block_align = format.get_blockalign() as usize;
    let channels = format.get_nchannels() as usize;
    let result = capture_loop_inner(
        stop_flag,
        &capture_client,
        producer,
        block_align,
        channels,
    );

    // 9. 停止并清理
    if let Err(e) = audio_client.stop_stream() {
        warn!("停止音频流失败: {e:?}");
    }
    wasapi::deinitialize();

    result
}

/// 内层读取循环(分离出来便于错误传播)
fn capture_loop_inner(
    stop_flag: &Arc<AtomicBool>,
    capture_client: &AudioCaptureClient,
    producer: &mut FrameProducer,
    block_align: usize,
    channels: usize,
) -> Result<(), String> {
    // 复用缓冲区,避免每次分配
    // 假设单次读取最多 4096 帧 (约 85ms @48kHz,远大于 20ms 的标称包)
    let mut byte_buf = vec![0u8; 4096 * block_align];
    let mut frame_buf: Vec<StereoFrame> = Vec::with_capacity(4096);

    while !stop_flag.load(Ordering::SeqCst) {
        // 循环读取当前所有可用包
        loop {
            let packet_size = capture_client
                .get_next_packet_size()
                .map_err(|e| format!("查询包大小失败: {e:?}"))?;
            if packet_size == 0 {
                break; // 没有数据,退出内层循环去 sleep
            }

            // 读取一个包到字节缓冲区
            let (frames_read, buffer_info) = capture_client
                .read_from_device_to_slice(&mut byte_buf)
                .map_err(|e| format!("读取音频数据失败: {e:?}"))?;

            if frames_read == 0 {
                break;
            }

            // 如果是静音包,跳过处理(但仍写入零帧以保持时间对齐?这里选择跳过)
            if buffer_info.flags.silent {
                continue;
            }

            // Deinterleave: 字节流 -> StereoFrame
            deinterleave_to_stereo(
                &byte_buf[..(frames_read as usize * block_align)],
                channels,
                &mut frame_buf,
            );

            // 写入环形缓冲
            if !frame_buf.is_empty() {
                enqueue_batch(producer, &frame_buf);
                frame_buf.clear();
            }
        }

        // 没有数据时短暂休眠,降低 CPU 占用
        // 20ms 缓冲 => sleep 5ms 足够及时
        thread::sleep(Duration::from_millis(5));
    }

    info!("音频捕获线程退出");
    Ok(())
}

/// 构造默认的 48kHz 立体声 32-bit float 格式
fn construct_default_format() -> WaveFormat {
    WaveFormat::new(
        BITS_PER_SAMPLE,
        BITS_PER_SAMPLE,
        &SampleType::Float,
        SAMPLE_RATE,
        CHANNELS,
        None,
    )
}

/// 将交错字节流转换为 StereoFrame 序列
///
/// 输入: 原始字节(每帧 block_align 字节,包含 channels 个样本)
/// 输出: frame_buf 追加 StereoFrame (只取前两个声道)
///
/// 假设: 32-bit float 样本(与 construct_default_format 一致)
fn deinterleave_to_stereo(
    bytes: &[u8],
    channels: usize,
    frame_buf: &mut Vec<StereoFrame>,
) {
    // 每个样本 4 字节 (32-bit float)
    let bytes_per_sample = 4;
    let frame_stride = channels * bytes_per_sample;
    let num_frames = bytes.len() / frame_stride;

    frame_buf.reserve(num_frames);

    for i in 0..num_frames {
        let frame_start = i * frame_stride;
        let left = read_f32_le(&bytes[frame_start..frame_start + bytes_per_sample]);
        let right = if channels >= 2 {
            read_f32_le(&bytes[frame_start + bytes_per_sample..frame_start + 2 * bytes_per_sample])
        } else {
            // 单声道 => 左右相同
            left
        };
        frame_buf.push(StereoFrame { left, right });
    }
}

/// 从 4 字节小端序读取 f32
#[inline]
fn read_f32_le(bytes: &[u8]) -> f32 {
    let arr: [u8; 4] = [bytes[0], bytes[1], bytes[2], bytes[3]];
    f32::from_le_bytes(arr)
}
