// 默认 profile TOML 文件(用 include_str! 编译进二进制)
//
// 首次启动时写出这些文件到 %APPDATA%\sound-place\profiles\

/// 默认通用 profile
pub const DEFAULT_TOML: &str = include_str!("default_profiles/default.toml");

/// 猎杀对决 profile
pub const HUNT_SHOWDOWN_TOML: &str = include_str!("default_profiles/hunt_showdown.toml");

/// 彩虹六号围攻 profile
pub const R6_SIEGE_TOML: &str = include_str!("default_profiles/r6_siege.toml");

/// PUBG profile
pub const PUBG_TOML: &str = include_str!("default_profiles/pubg.toml");

/// 所有默认 profile 的 (game_id, toml_content) 列表
pub fn all_default_profiles() -> Vec<(&'static str, &'static str)> {
    vec![
        ("default", DEFAULT_TOML),
        ("hunt_showdown", HUNT_SHOWDOWN_TOML),
        ("r6_siege", R6_SIEGE_TOML),
        ("pubg", PUBG_TOML),
    ]
}

/// 首次启动初始化: 写出所有默认 profile 到目录
pub fn initialize_default_profiles(dir: &std::path::Path) -> Result<(), String> {
    std::fs::create_dir_all(dir).map_err(|e| format!("创建目录失败: {e}"))?;

    for (id, content) in all_default_profiles() {
        let path = dir.join(format!("{id}.toml"));
        if !path.exists() {
            std::fs::write(&path, content).map_err(|e| format!("写入 {id}.toml 失败: {e}"))?;
            log::info!("已写出默认 profile: {id}.toml");
        }
    }
    Ok(())
}
