// Profile 列表项类型(与 Rust 端 config::profile::ProfileListItem 对应)

export interface ProfileListItem {
  /** 游戏标识 */
  game_id: string;
  /** 显示名称 */
  name: string;
  /** 反作弊风险等级: "high" | "medium" | "low" */
  anticheat_risk: string;
}
