// SoundPlace 应用库入口
//
// 模块组织:
// - audio: WASAPI loopback 捕获 + 进程过滤 + 环形缓冲
// - (阶段 3 启用) analysis: FFT + onset + 方位估计 + 分类
// - (阶段 4 启用) config: TOML profile 配置

mod audio;

use std::sync::Mutex;

use tauri::{Emitter, Manager, State, WebviewWindow};

use audio::capture::CaptureThread;
use audio::ring_buffer::{create_ring_buffer, FrameConsumer};

/// 应用状态:音频捕获线程 + 环形缓冲消费者
struct AppState {
    /// 捕获线程(启动后存在,停止后为 None)
    capture_thread: Mutex<Option<CaptureThread>>,
    /// 环形缓冲消费者(启动后存在,停止后为 None)
    consumer: Mutex<Option<FrameConsumer>>,
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            capture_thread: Mutex::new(None),
            consumer: Mutex::new(None),
        }
    }
}

/// 启动音频捕获
///
/// 创建 ring buffer + 启动 WASAPI loopback 捕获线程
#[tauri::command]
fn start_capture(state: State<'_, AppState>) -> Result<(), String> {
    let mut capture_guard = state.capture_thread.lock().map_err(|e| e.to_string())?;
    if capture_guard.is_some() {
        return Err("音频捕获已在运行".to_string());
    }

    // 创建环形缓冲
    let (producer, consumer) = create_ring_buffer();

    // 启动捕获线程
    let thread = CaptureThread::start(producer)?;

    // 保存到状态
    *capture_guard = Some(thread);
    let mut consumer_guard = state.consumer.lock().map_err(|e| e.to_string())?;
    *consumer_guard = Some(consumer);

    log::info!("音频捕获已启动");
    Ok(())
}

/// 停止音频捕获
#[tauri::command]
fn stop_capture(state: State<'_, AppState>) -> Result<(), String> {
    let mut capture_guard = state.capture_thread.lock().map_err(|e| e.to_string())?;
    let thread = capture_guard.take();
    if let Some(t) = thread {
        t.stop()?;
    }

    let mut consumer_guard = state.consumer.lock().map_err(|e| e.to_string())?;
    *consumer_guard = None;

    log::info!("音频捕获已停止");
    Ok(())
}

/// 启用 overlay 窗口并设置为鼠标点击穿透
#[tauri::command]
fn enable_overlay(app: tauri::AppHandle) -> Result<(), String> {
    let overlay: Option<WebviewWindow> = app.get_webview_window("overlay");
    if let Some(window) = overlay {
        window
            .set_ignore_cursor_events(true)
            .map_err(|e| format!("设置点击穿透失败: {e}"))?;
        window
            .show()
            .map_err(|e| format!("显示 overlay 失败: {e}"))?;
        Ok(())
    } else {
        Err("overlay 窗口未找到".to_string())
    }
}

/// 禁用 overlay 窗口(隐藏并关闭点击穿透)
#[tauri::command]
fn disable_overlay(app: tauri::AppHandle) -> Result<(), String> {
    let overlay: Option<WebviewWindow> = app.get_webview_window("overlay");
    if let Some(window) = overlay {
        window
            .set_ignore_cursor_events(false)
            .map_err(|e| format!("关闭点击穿透失败: {e}"))?;
        window
            .hide()
            .map_err(|e| format!("隐藏 overlay 失败: {e}"))?;
        Ok(())
    } else {
        Err("overlay 窗口未找到".to_string())
    }
}

/// 进入编辑模式:关闭点击穿透以便拖动
#[tauri::command]
fn enter_edit_mode(app: tauri::AppHandle) -> Result<(), String> {
    let overlay: Option<WebviewWindow> = app.get_webview_window("overlay");
    if let Some(window) = overlay {
        window
            .set_ignore_cursor_events(false)
            .map_err(|e| format!("关闭点击穿透失败: {e}"))?;
        window
            .emit("edit-mode", true)
            .map_err(|e| format!("通知前端失败: {e}"))?;
        Ok(())
    } else {
        Err("overlay 窗口未找到".to_string())
    }
}

/// 退出编辑模式:恢复点击穿透
#[tauri::command]
fn exit_edit_mode(app: tauri::AppHandle) -> Result<(), String> {
    let overlay: Option<WebviewWindow> = app.get_webview_window("overlay");
    if let Some(window) = overlay {
        window
            .emit("edit-mode", false)
            .map_err(|e| format!("通知前端失败: {e}"))?;
        window
            .set_ignore_cursor_events(true)
            .map_err(|e| format!("恢复点击穿透失败: {e}"))?;
        Ok(())
    } else {
        Err("overlay 窗口未找到".to_string())
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // 初始化日志
    let _ = env_logger::Builder::from_env(
        env_logger::Env::default().default_filter_or("info"),
    )
    .try_init();

    tauri::Builder::default()
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .manage(AppState::default())
        .invoke_handler(tauri::generate_handler![
            enable_overlay,
            disable_overlay,
            enter_edit_mode,
            exit_edit_mode,
            start_capture,
            stop_capture,
        ])
        .setup(|_app| {
            #[cfg(debug_assertions)]
            {
                use tauri::Manager;
                if let Some(window) = _app.get_webview_window("main") {
                    window.open_devtools();
                }
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("启动 Tauri 应用失败");
}
