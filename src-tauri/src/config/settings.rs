// 全局设置: 风险告知标志 + 激活 profile + 外观设置
//
// 持久化到 %APPDATA%\sound-place\settings.json

use std::fs;

use serde::{Deserialize, Serialize};

use super::app_data_dir;

/// 全局设置(持久化)
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Settings {
    /// 是否已接受风险告知
    pub risk_accepted: bool,
    /// 当前激活的 profile game_id
    pub active_profile: String,
    /// 外观设置
    pub appearance: Appearance,
}

/// 外观设置
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Appearance {
    pub pos_x_percent: f32,
    pub pos_y_percent: f32,
    pub wave_length: u32,
    pub wave_max_height: u32,
    pub wave_thickness: u32,
    pub opacity: f32,
    pub color_footstep: String,
    pub color_gunshot: String,
    pub color_vehicle: String,
    pub color_generic: String,
    pub decay_ms: u32,
    pub wave_style: String,
    pub show_divider: bool,
}

impl Default for Appearance {
    fn default() -> Self {
        Self {
            pos_x_percent: 50.0,
            pos_y_percent: 50.0,
            wave_length: 200,
            wave_max_height: 60,
            wave_thickness: 3,
            opacity: 0.85,
            color_footstep: "#FFD166".to_string(), // 黄
            color_gunshot: "#EF476F".to_string(),  // 红
            color_vehicle: "#118AB2".to_string(),  // 蓝
            color_generic: "#06D6A0".to_string(),  // 绿
            decay_ms: 800,
            wave_style: "smooth".to_string(),
            show_divider: true,
        }
    }
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            risk_accepted: false,
            active_profile: "default".to_string(),
            appearance: Appearance::default(),
        }
    }
}

impl Settings {
    /// 从 settings.json 加载, 不存在则返回默认
    pub fn load() -> Self {
        let path = match app_data_dir() {
            Ok(dir) => dir.join("settings.json"),
            Err(e) => {
                log::warn!("无法获取数据目录: {e}, 使用默认设置");
                return Self::default();
            }
        };

        match fs::read_to_string(&path) {
            Ok(content) => match serde_json::from_str::<Settings>(&content) {
                Ok(s) => s,
                Err(e) => {
                    log::warn!("解析 settings.json 失败: {e}, 使用默认");
                    Self::default()
                }
            },
            Err(_) => Self::default(),
        }
    }

    /// 保存到 settings.json
    pub fn save(&self) -> Result<(), String> {
        let dir = app_data_dir()?;
        fs::create_dir_all(&dir).map_err(|e| format!("创建目录失败: {e}"))?;
        let path = dir.join("settings.json");
        let content = serde_json::to_string_pretty(self)
            .map_err(|e| format!("序列化失败: {e}"))?;
        fs::write(&path, content).map_err(|e| format!("写入失败: {e}"))
    }

    /// 标记风险已接受并保存
    pub fn accept_risk(&mut self) -> Result<(), String> {
        self.risk_accepted = true;
        self.save()
    }

    /// 设置激活 profile 并保存
    pub fn set_active_profile(&mut self, id: &str) -> Result<(), String> {
        self.active_profile = id.to_string();
        self.save()
    }

    /// 更新外观并保存
    pub fn update_appearance(&mut self, appearance: Appearance) -> Result<(), String> {
        self.appearance = appearance;
        self.save()
    }
}
