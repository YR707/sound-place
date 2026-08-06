// SoundPlace 应用库入口
//
// 模块组织:
// - audio: WASAPI loopback 捕获 + 进程过滤 + 环形缓冲
// - analysis: FFT + onset + 方位估计 (ILD + GCC-PHAT) + 分类 + worker 线程
// - config: TOML profile 配置 + settings.json 外观持久化
// - ui: 风险告知 + 系统托盘

mod analysis;
mod audio;
mod config;
mod ui;

use std::sync::Mutex;

use tauri::{Emitter, Manager, State, WebviewWindow};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

use analysis::worker::AnalysisWorker;
use audio::capture::CaptureThread;
use audio::ring_buffer::create_ring_buffer;
use config::default_profiles::initialize_default_profiles;
use config::profile::{Profile, ProfileListItem};
use config::settings::{Appearance, Settings};
use config::{profiles_dir, settings_path};
use ui::risk_notice;

/// 应用状态:音频捕获线程 + 分析线程
struct AppState {
    /// 捕获线程(启动后存在,停止后为 None)
    capture_thread: Mutex<Option<CaptureThread>>,
    /// 分析线程(启动后存在,停止后为 None)
    analysis_worker: Mutex<Option<AnalysisWorker>>,
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            capture_thread: Mutex::new(None),
            analysis_worker: Mutex::new(None),
        }
    }
}

/// 启动音频捕获与分析
///
/// 创建 ring buffer + 启动 WASAPI loopback 捕获线程 + 启动分析线程
#[tauri::command]
fn start_capture(app: tauri::AppHandle, state: State<'_, AppState>) -> Result<(), String> {
    let mut capture_guard = state.capture_thread.lock().map_err(|e| e.to_string())?;
    if capture_guard.is_some() {
        return Err("音频捕获已在运行".to_string());
    }

    // 创建环形缓冲
    let (producer, consumer) = create_ring_buffer();

    // 启动捕获线程
    let capture_thread = CaptureThread::start(producer)?;

    // 启动分析线程(空进程白名单 = 不过滤, 阶段 4 后从 profile 读取)
    let process_names: Vec<String> = Vec::new();
    let analysis_worker = AnalysisWorker::start(consumer, app, process_names)?;

    // 保存到状态
    *capture_guard = Some(capture_thread);
    let mut analysis_guard = state
        .analysis_worker
        .lock()
        .map_err(|e| e.to_string())?;
    *analysis_guard = Some(analysis_worker);

    log::info!("音频捕获与分析已启动");
    Ok(())
}

/// 停止音频捕获与分析
#[tauri::command]
fn stop_capture(state: State<'_, AppState>) -> Result<(), String> {
    // 先停止分析线程
    let mut analysis_guard = state
        .analysis_worker
        .lock()
        .map_err(|e| e.to_string())?;
    if let Some(worker) = analysis_guard.take() {
        worker.stop()?;
    }
    drop(analysis_guard);

    // 再停止捕获线程
    let mut capture_guard = state.capture_thread.lock().map_err(|e| e.to_string())?;
    if let Some(thread) = capture_guard.take() {
        thread.stop()?;
    }

    log::info!("音频捕获与分析已停止");
    Ok(())
}

/// 列出所有可用的 profile
#[tauri::command]
fn list_profiles() -> Result<Vec<ProfileListItem>, String> {
    let dir = profiles_dir()?;
    let profiles = Profile::load_from_dir(&dir);
    Ok(profiles.iter().map(|p| p.to_list_item()).collect())
}

/// 获取指定 profile 的 TOML 文本
#[tauri::command]
fn get_profile(id: String) -> Result<String, String> {
    let dir = profiles_dir()?;
    let path = dir.join(format!("{id}.toml"));
    std::fs::read_to_string(&path).map_err(|e| format!("读取 {id}.toml 失败: {e}"))
}

/// 保存 profile 的 TOML 文本
#[tauri::command]
fn save_profile(id: String, content: String) -> Result<(), String> {
    let dir = profiles_dir()?;
    Profile::save_to_dir(&dir, &id, &content)
}

/// 设置当前激活的 profile
#[tauri::command]
fn set_active_profile(id: String) -> Result<(), String> {
    let mut settings = Settings::load();
    settings.set_active_profile(&id)
}

/// 获取当前激活的 profile id
#[tauri::command]
fn get_active_profile() -> Result<String, String> {
    Ok(Settings::load().active_profile)
}

/// 获取外观设置
#[tauri::command]
fn get_appearance() -> Result<Appearance, String> {
    Ok(Settings::load().appearance)
}

/// 保存外观设置
#[tauri::command]
fn save_appearance(app: tauri::AppHandle, appearance: Appearance) -> Result<(), String> {
    let mut settings = Settings::load();
    settings.update_appearance(appearance.clone())?;

    // 通知 overlay 实时更新
    let overlay: Option<WebviewWindow> = app.get_webview_window("overlay");
    if let Some(window) = overlay {
        let _ = window.emit("appearance-changed", &appearance);
    }
    Ok(())
}

/// 重置外观设置为默认值
#[tauri::command]
fn reset_appearance() -> Result<Appearance, String> {
    let mut settings = Settings::load();
    let default = Appearance::default();
    settings.update_appearance(default.clone())?;
    Ok(default)
}

/// 查询用户是否已接受风险告知
#[tauri::command]
fn is_risk_accepted() -> bool {
    risk_notice::is_risk_accepted()
}

/// 标记用户已接受风险告知
#[tauri::command]
fn accept_risk() -> Result<(), String> {
    risk_notice::accept_risk()
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
        .on_window_event(|window, event| {
            // 拦截主窗口关闭: 隐藏到托盘而非退出
            if window.label() == "main" {
                if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            enable_overlay,
            disable_overlay,
            enter_edit_mode,
            exit_edit_mode,
            start_capture,
            stop_capture,
            list_profiles,
            get_profile,
            save_profile,
            set_active_profile,
            get_active_profile,
            get_appearance,
            save_appearance,
            reset_appearance,
            is_risk_accepted,
            accept_risk,
        ])
        .setup(|_app| {
            // 首次启动初始化: 写出默认 profile + settings.json
            if let Ok(pdir) = profiles_dir() {
                if let Err(e) = initialize_default_profiles(&pdir) {
                    log::warn!("初始化默认 profile 失败: {e}");
                }
            }
            // 写出默认 settings.json(仅在不存在时)
            if let Ok(spath) = settings_path() {
                if !spath.exists() {
                    let _ = Settings::default().save();
                }
            }

            // 初始化系统托盘
            if let Err(e) = ui::tray::init_tray(&_app.handle()) {
                log::warn!("托盘初始化失败: {e}");
            }

            // 全局快捷键: Ctrl+Alt+S 切换覆盖显隐
            let app_for_shortcut = _app.handle().clone();
            let overlay_shortcut = Shortcut::new(Some(Modifiers::CONTROL | Modifiers::ALT), "KeyS");
            if let Err(e) = _app.global_shortcut().on_shortcut(overlay_shortcut, move |_app, _shortcut, event| {
                if event.state() == ShortcutState::Pressed {
                    if let Some(window) = app_for_shortcut.get_webview_window("overlay") {
                        if window.is_visible().unwrap_or(false) {
                            let _ = window.set_ignore_cursor_events(false);
                            let _ = window.hide();
                        } else {
                            let _ = window.set_ignore_cursor_events(true);
                            let _ = window.show();
                        }
                    }
                }
            }) {
                log::warn!("绑定 Ctrl+Alt+S 失败: {e}");
            }

            // 全局快捷键: Ctrl+Alt+E 切换编辑模式
            let app_for_edit = _app.handle().clone();
            let edit_shortcut = Shortcut::new(Some(Modifiers::CONTROL | Modifiers::ALT), "KeyE");
            if let Err(e) = _app.global_shortcut().on_shortcut(edit_shortcut, move |_app, _shortcut, event| {
                if event.state() == ShortcutState::Pressed {
                    if let Some(window) = app_for_edit.get_webview_window("overlay") {
                        // 简化: 每次触发进入编辑模式, 前端用按钮退出
                        let _ = window.set_ignore_cursor_events(false);
                        let _ = window.emit("edit-mode", true);
                    }
                }
            }) {
                log::warn!("绑定 Ctrl+Alt+E 失败: {e}");
            }

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
