// 外观设置类型(与 Rust 端 config::settings::Appearance 对应)

export type WaveStyle = 'smooth' | 'sawtooth' | 'step';

export interface Appearance {
  /** 波纹组中心 X 位置 (0-100 百分比) */
  pos_x_percent: number;
  /** 波纹组中心 Y 位置 (0-100 百分比) */
  pos_y_percent: number;
  /** 波纹条总长度 (80-400 px) */
  wave_length: number;
  /** 波纹条最大高度 (20-120 px) */
  wave_max_height: number;
  /** 波纹条厚度 (1-8 px) */
  wave_thickness: number;
  /** 整体透明度 (0.1-1.0) */
  opacity: number;
  /** 脚步声颜色 (#RRGGBB) */
  color_footstep: string;
  /** 枪声颜色 */
  color_gunshot: string;
  /** 载具声颜色 */
  color_vehicle: string;
  /** 通用声颜色 */
  color_generic: string;
  /** 衰减时长 (200-2000 ms) */
  decay_ms: number;
  /** 波纹样式 */
  wave_style: WaveStyle;
  /** 是否显示左右分界标记 */
  show_divider: boolean;
}

/** 默认外观设置 */
export const DEFAULT_APPEARANCE: Appearance = {
  pos_x_percent: 50,
  pos_y_percent: 50,
  wave_length: 200,
  wave_max_height: 60,
  wave_thickness: 3,
  opacity: 0.85,
  color_footstep: '#FFD166', // 黄色
  color_gunshot: '#EF476F', // 红色
  color_vehicle: '#118AB2', // 蓝色
  color_generic: '#06D6A0', // 绿色
  decay_ms: 800,
  wave_style: 'smooth',
  show_divider: true,
};
