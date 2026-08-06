// 配置模块
//
// 子模块:
// - profile: TOML profile 结构与读写
// - settings: 全局设置(风险标志/激活 profile/外观) + 持久化
// - default_profiles: 内嵌的默认 profile TOML 文件

pub mod default_profiles;
pub mod profile;
pub mod settings;

use std::path::PathBuf;

/// 获取应用数据目录: %APPDATA%\sound-place\
///
/// Windows: C:\Users\<user>\AppData\Roaming\sound-place\
/// 用 directories crate 获取, 绝不硬编码用户路径
pub fn app_data_dir() -> Result<PathBuf, String> {
    let proj_dirs = directories::ProjectDirs::from("", "", "sound-place")
        .ok_or_else(|| "无法获取应用数据目录".to_string())?;
    Ok(proj_dirs.data_dir().to_path_buf())
}

/// 获取 profiles 目录: %APPDATA%\sound-place\profiles\
pub fn profiles_dir() -> Result<PathBuf, String> {
    Ok(app_data_dir()?.join("profiles"))
}

/// 获取 settings.json 路径: %APPDATA%\sound-place\settings.json
pub fn settings_path() -> Result<PathBuf, String> {
    Ok(app_data_dir()?.join("settings.json"))
}
