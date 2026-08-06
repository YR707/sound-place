// Profile 结构与读写
//
// 一个 Profile 描述一个游戏的检测参数:
// - 进程名(用于过滤)
// - 反作弊风险等级
// - 检测参数(FFT size / hop / onset 阈值 / 去抖间隔)
// - 声音类型规则(频段范围 / 能量占比 / 持续时间)

use std::fs;
use std::path::Path;

use serde::{Deserialize, Serialize};

/// 一个游戏的完整检测配置
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Profile {
    pub game_id: String,
    pub name: String,
    pub process_names: Vec<String>,
    /// 反作弊风险等级: "high" | "medium" | "low"
    pub anticheat_risk: String,
    pub detection: DetectionConfig,
    pub sound_types: Vec<SoundTypeConfig>,
}

/// 检测参数
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct DetectionConfig {
    /// FFT size (必须是 2 的幂)
    pub fft_size: usize,
    /// 跳跃长度 (FFT 分析的 hop size)
    pub hop_size: usize,
    /// Onset 阈值倍数 k (阈值 = median + k * MAD)
    pub onset_threshold: f32,
    /// 最小事件间隔(毫秒), 用于去抖
    pub min_event_interval_ms: u32,
}

/// 声音类型规则
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct SoundTypeConfig {
    pub name: String,
    /// (最低频率, 最高频率) Hz
    pub freq_range: (u32, u32),
    /// 该频段最低能量占比 (0.0-1.0)
    pub min_energy_ratio: f32,
    /// 最短持续时间(毫秒)
    pub min_duration_ms: u32,
    /// 最长持续时间(毫秒)
    pub max_duration_ms: u32,
}

/// Profile 列表项(轻量, 用于 UI 列表展示)
#[derive(Clone, Debug, Serialize)]
pub struct ProfileListItem {
    pub game_id: String,
    pub name: String,
    pub anticheat_risk: String,
}

impl Profile {
    /// 从目录扫描所有 .toml 文件
    ///
    /// 返回所有解析成功的 Profile, 解析失败的文件会被跳过(并记日志)
    pub fn load_from_dir(dir: &Path) -> Vec<Profile> {
        let mut profiles = Vec::new();

        let entries = match fs::read_dir(dir) {
            Ok(e) => e,
            Err(e) => {
                log::warn!("读取 profile 目录失败 {}: {e}", dir.display());
                return profiles;
            }
        };

        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|s| s.to_str()) != Some("toml") {
                continue;
            }

            let content = match fs::read_to_string(&path) {
                Ok(c) => c,
                Err(e) => {
                    log::warn!("读取 profile 失败 {}: {e}", path.display());
                    continue;
                }
            };

            match toml::from_str::<Profile>(&content) {
                Ok(p) => profiles.push(p),
                Err(e) => {
                    log::warn!("解析 profile 失败 {}: {e}", path.display());
                }
            }
        }

        profiles
    }

    /// 保存单个 profile 到目录, 文件名为 {game_id}.toml
    pub fn save_to_dir(dir: &Path, id: &str, content: &str) -> Result<(), String> {
        fs::create_dir_all(dir).map_err(|e| format!("创建目录失败: {e}"))?;
        let path = dir.join(format!("{id}.toml"));
        fs::write(&path, content).map_err(|e| format!("写入文件失败: {e}"))
    }

    /// 从列表中按 game_id 查找
    pub fn get_by_id<'a>(profiles: &'a [Profile], id: &str) -> Option<&'a Profile> {
        profiles.iter().find(|p| p.game_id == id)
    }

    /// 转为 ProfileListItem
    pub fn to_list_item(&self) -> ProfileListItem {
        ProfileListItem {
            game_id: self.game_id.clone(),
            name: self.name.clone(),
            anticheat_risk: self.anticheat_risk.clone(),
        }
    }
}
