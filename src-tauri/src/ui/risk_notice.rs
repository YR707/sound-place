// 风险告知接受标志读写
//
// 复用 config::settings::Settings 的 risk_accepted 字段

use crate::config::settings::Settings;

/// 查询是否已接受风险告知
pub fn is_risk_accepted() -> bool {
    Settings::load().risk_accepted
}

/// 标记用户已接受风险告知
pub fn accept_risk() -> Result<(), String> {
    let mut settings = Settings::load();
    settings.accept_risk()
}
