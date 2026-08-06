// SoundPlace 应用库入口
// 阶段 1：仅初始化 Tauri + 双窗口 + overlay 控制命令

// 后续阶段将逐步启用：
// mod audio;
// mod analysis;
// mod config;
// mod ui;
// mod overlay;

use tauri::{Emitter, Manager, WebviewWindow};

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

/// 禁用 overlay 窗口（隐藏并关闭点击穿透）
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

/// 进入编辑模式：关闭点击穿透以便拖动
#[tauri::command]
fn enter_edit_mode(app: tauri::AppHandle) -> Result<(), String> {
    let overlay: Option<WebviewWindow> = app.get_webview_window("overlay");
    if let Some(window) = overlay {
        window
            .set_ignore_cursor_events(false)
            .map_err(|e| format!("关闭点击穿透失败: {e}"))?;
        // 通知前端进入编辑模式
        window
            .emit("edit-mode", true)
            .map_err(|e| format!("通知前端失败: {e}"))?;
        Ok(())
    } else {
        Err("overlay 窗口未找到".to_string())
    }
}

/// 退出编辑模式：恢复点击穿透
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
    tauri::Builder::default()
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            enable_overlay,
            disable_overlay,
            enter_edit_mode,
            exit_edit_mode,
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
