// 系统托盘
//
// 创建托盘图标 + 右键菜单:
// - 显示面板: 显示主窗口
// - 启用覆盖: 调用 enable_overlay
// - 调整位置: 调用 enter_edit_mode
// - 退出: 关闭应用
//
// 关闭主窗口时拦截, 最小化到托盘而不退出

use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    AppHandle, Manager, WindowEvent,
};

/// 初始化系统托盘
pub fn init_tray(app: &AppHandle) -> Result<(), String> {
    // 创建菜单项
    let show_panel = MenuItem::with_id(app, "show_panel", "显示面板", true, None::<&str>)
        .map_err(|e| format!("创建菜单项失败: {e}"))?;
    let enable_overlay = MenuItem::with_id(app, "enable_overlay", "启用覆盖", true, None::<&str>)
        .map_err(|e| format!("创建菜单项失败: {e}"))?;
    let edit_position = MenuItem::with_id(app, "edit_position", "调整位置", true, None::<&str>)
        .map_err(|e| format!("创建菜单项失败: {e}"))?;
    let quit = MenuItem::with_id(app, "quit", "退出", true, None::<&str>)
        .map_err(|e| format!("创建菜单项失败: {e}"))?;

    let menu = Menu::with_items(
        app,
        [&show_panel, &enable_overlay, &edit_position, &quit],
    )
    .map_err(|e| format!("创建菜单失败: {e}"))?;

    // 创建托盘图标
    TrayIconBuilder::new()
        .menu(&menu)
        .tooltip("SoundPlace - 声音方位分析")
        .on_menu_event(|app, event| {
            match event.id.as_ref() {
                "show_panel" => {
                    if let Some(window) = app.get_webview_window("main") {
                        let _ = window.show();
                        let _ = window.set_focus();
                    }
                }
                "enable_overlay" => {
                    if let Some(window) = app.get_webview_window("overlay") {
                        let _ = window.set_ignore_cursor_events(true);
                        let _ = window.show();
                    }
                }
                "edit_position" => {
                    if let Some(window) = app.get_webview_window("overlay") {
                        let _ = window.set_ignore_cursor_events(false);
                        let _ = window.emit("edit-mode", true);
                    }
                }
                "quit" => {
                    app.exit(0);
                }
                _ => {}
            }
        })
        .build(app)
        .map_err(|e| format!("创建托盘图标失败: {e}"))?;

    Ok(())
}

/// 拦截主窗口关闭事件: 隐藏而非退出
pub fn on_window_event(window: &WindowEvent) {
    if let WindowEvent::CloseRequested { api, .. } = window {
        // 阻止默认关闭行为
        api.prevent_close();
        // 隐藏窗口(最小化到托盘)
        // 注意: 这里是简化实现, 实际 on_window_event 回调在 lib.rs 的 setup 中绑定
    }
}
