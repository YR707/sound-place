// 声音事件 payload 类型(与 Rust 端 analysis::SoundEvent 对应)

export type SoundType = 'footstep' | 'gunshot' | 'vehicle' | 'generic';

export interface SoundEvent {
  /** 水平方位角 [-90, 90], 负=左, 正=右, 0=正前 */
  angle: number;
  /** 强度 [0, 1] */
  intensity: number;
  /** 声音类型 */
  sound_type: SoundType;
  /** 时间戳(毫秒) */
  timestamp: number;
}
