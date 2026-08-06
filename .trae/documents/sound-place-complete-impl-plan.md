# SoundPlace 完整实施计划(阶段 3-6)

## 摘要

在阶段 1(Tauri 骨架 + 双窗口 + overlay 控制)与阶段 2(WASAPI loopback 捕获 + 环形缓冲 + 进程过滤)已推送 GitHub 的基础上,完整实现剩余阶段 3-6,产出可独立运行的 `.exe`。

**用户决策已确认**:
- 方位算法:完整 ILD + GCC-PHAT ITD 融合(目标精度 ±15°)
- 文档:完整帮助页 + 关于页 + 风险告知弹窗(接近发布质量)

**开发模式**:本机 WDAC 限制无法编译验证,只写代码 + 推 GitHub;用户在另一台机器 clone 后 `cargo build --release` 验证。

## 当前状态分析

### 已完成代码

| 模块 | 文件 | 状态 |
|---|---|---|
| Tauri 配置 | `src-tauri/tauri.conf.json`、`capabilities/default.json` | 双窗口 + 权限齐全 |
| 应用入口 | `src-tauri/src/lib.rs`、`main.rs` | 6 命令 + AppState + env_logger |
| 音频捕获 | `src-tauri/src/audio/capture.rs` | WASAPI PollingShared loopback |
| 环形缓冲 | `src-tauri/src/audio/ring_buffer.rs` | SPSC 16k 帧 + 测试 |
| 进程过滤 | `src-tauri/src/audio/session_filter.rs` | COM 调用 + fallback |
| 前端骨架 | `ui/src/views/{Overlay,ControlPanel}.vue` | 占位波纹 + 最小面板 |
| 双入口构建 | `ui/vite.config.ts`、`ui/{index,overlay}.html` | main + overlay |

### 已知问题(必须在阶段 3 开始前修复)

1. **`audio/mod.rs` 编译错误**:`pub use ring_buffer::{AudioFrame, StereoFrame}` 中 `AudioFrame` 在 `ring_buffer.rs` 中未定义。修复:删除 `AudioFrame` 导出,只保留 `StereoFrame`。

2. **SessionFilter 未集成**:虽然 `session_filter.rs` 已实现 `should_process_audio()`,但 `capture.rs` 的 `capture_loop_inner` 中没有任何调用,当前实际是抓全混音。修复方案:在阶段 3 的分析线程入口处调用 `SessionFilter`,而不是在捕获线程中调用(保持捕获线程实时性,过滤决策放在消费端)。

3. **App.vue 路由冗余**:`App.vue` 用 `?window=overlay` 区分窗口,但实际是双 HTML 入口加载不同 main.ts,这套查询参数逻辑是死代码。修复:不动 App.vue(避免破坏已有逻辑),Overlay.vue 独立挂载(`overlay-main.ts` 已正确实现)。

## 待实现模块总览

```
src-tauri/src/
├── audio/                    [已存在,需修复 mod.rs]
├── analysis/                 [待创建 - 阶段 3]
│   ├── mod.rs
│   ├── fft.rs                # realfft + Hann 窗
│   ├── onset.rs              # Spectral Flux + HFC
│   ├── localize.rs           # ILD + GCC-PHAT ITD 融合
│   ├── classify.rs           # 频谱形状规则
│   └── worker.rs             # 分析线程(消费 ring buffer)
├── config/                   [待创建 - 阶段 4]
│   ├── mod.rs
│   ├── profile.rs            # TOML Profile 结构
│   ├── default_profiles/     # include_str! 内嵌
│   │   ├── default.toml
│   │   ├── hunt_showdown.toml
│   │   ├── r6_siege.toml
│   │   └── pubg.toml
│   └── settings.rs           # Appearance + 持久化
├── ui/                       [待创建 - 阶段 5 Rust 端]
│   ├── mod.rs
│   ├── risk_notice.rs        # 首次启动标志
│   └── tray.rs               # 系统托盘
└── lib.rs                    [扩展 - 注册所有新命令]

ui/src/
├── views/
│   ├── Overlay.vue           [扩展 - 接入 useAudioEvents + useWaveRenderer]
│   ├── ControlPanel.vue      [扩展 - 完整控制面板]
│   ├── AppearanceSettings.vue [待创建 - 阶段 5]
│   └── RiskNotice.vue        [待创建 - 阶段 5]
├── composables/              [待创建 - 整个目录]
│   ├── useAudioEvents.ts     # 订阅 sound_event
│   ├── useWaveRenderer.ts    # Canvas 波纹绘制
│   └── useOverlayDrag.ts     # 拖拽位置逻辑(从 Overlay.vue 提取)
└── types/
    ├── audio.ts              # SoundEvent payload 类型
    └── appearance.ts         # Appearance 设置类型
```

## 实施步骤

### 阶段 3:方位估计 + 瞬态检测 + 波纹绘制

**目标**:从 ring buffer 读取音频 → FFT → onset 检测 → ILD/GCC-PHAT 方位估计 → 分类 → emit `sound_event` 事件 → 前端 Canvas 绘制波纹。

#### 3.1 修复阶段 2 遗留问题

**文件**:`src-tauri/src/audio/mod.rs`

**改动**:
```rust
// 修改前
pub use ring_buffer::{AudioFrame, StereoFrame};
// 修改后
pub use ring_buffer::StereoFrame;
```

**原因**:`AudioFrame` 未定义,会编译失败。

#### 3.2 创建 analysis 模块

**文件**:`src-tauri/src/analysis/mod.rs`

声明 5 个子模块:`fft`、`onset`、`localize`、`classify`、`worker`。公开导出 `SoundEvent` 结构供 `lib.rs` emit 使用。

```rust
pub mod fft;
pub mod onset;
pub mod localize;
pub mod classify;
pub mod worker;

use serde::Serialize;

/// 声音事件 payload,emit 到前端
#[derive(Clone, Debug, Serialize)]
pub struct SoundEvent {
    /// 水平方位角 [-90.0, +90.0],负=左,正=右,0=正前
    pub angle: f32,
    /// 强度 [0.0, 1.0]
    pub intensity: f32,
    /// 声音类型 "footstep" | "gunshot" | "vehicle" | "generic"
    pub sound_type: String,
    /// 时间戳(毫秒,用于前端动画)
    pub timestamp: u64,
}
```

#### 3.3 实现 FFT 模块

**文件**:`src-tauri/src/analysis/fft.rs`

**职责**:封装 `realfft` crate,预计算 Hann 窗,对左右声道分别做 FFT 输出幅度谱。

**关键 API**:
- `FftAnalyzer::new(size: usize) -> Self`(预计算 Hann 窗 + RealFftPlanner)
- `analyze(&mut self, left: &[f32], right: &[f32]) -> Spectrum`(返回左右幅度谱)

**关键参数**:
- FFT size = 2048(约 42ms @48kHz)
- Hann 窗预计算:`hann[i] = 0.5 - 0.5 * cos(2πi/N)`
- 跳跃长度 hop = 1024(50% overlap)

**依赖**:`realfft = "3"`(Cargo.toml 已声明)。

#### 3.4 实现 Onset 检测

**文件**:`src-tauri/src/analysis/onset.rs`

**职责**:基于 Spectral Flux + HFC 检测瞬态事件(脚步/枪声)。

**算法**:
1. **Spectral Flux**:`flux = Σ max(0, |X_t[k]| - |X_{t-1}[k]|)`(正频谱差之和)
2. **HFC**:`hfc = Σ k * |X_t[k]|`(高频能量加权,对打击声敏感)
3. **自适应阈值**:滑动窗口(约 20 帧)计算中位数 + k×MAD,超过阈值触发 onset
4. **去抖**:同一类型事件最小间隔 100ms(可由 profile 配置)

**关键 API**:
- `OnsetDetector::new() -> Self`
- `detect(&mut self, spectrum: &Spectrum) -> Option<OnsetEvent>`
- `OnsetEvent { intensity: f32, timestamp: u64 }`

#### 3.5 实现方位估计(完整 ILD + GCC-PHAT ITD)

**文件**:`src-tauri/src/analysis/localize.rs`

**职责**:onset 触发瞬间快照,输出 [-90°, +90°] 水平方位角。

**算法**:

**ILD 部分**:
1. 取 onset 触发瞬间的左右声道 RMS(窗口约 20ms)
2. `ild_db = 20 * log10(left_rms / right_rms)`
3. 经验映射:`angle_from_ild = ild_db * 5.0`(1dB 差约 5°,范围限制 ±90°)
4. ild_db > 0(左大于右)→ 角度为负(偏左)

**GCC-PHAT ITD 部分**:
1. 取 onset 瞬间左右声道 2048 样本
2. 计算 GCC-PHAT 互相关:`R(τ) = IFFT(X_l * conj(X_r) / |X_l * conj(X_r)|)`
3. 在 [-23, +23] 样本范围内找 R(τ) 峰值(23 样本 @48kHz ≈ 0.48ms,对应 ±90°)
4. `itd_samples = argmax(R)`
5. 经验映射:`angle_from_itd = asin(itd_samples / 23) * 180/π`(±90° 范围)
6. itd > 0(右声道先到)→ 角度为正(偏右)

**融合**:
- 加权平均:`angle = 0.6 * angle_from_ild + 0.4 * angle_from_itd`(ILD 更可靠,权重高)
- 钳制:`angle.clamp(-90.0, 90.0)`

**关键 API**:
- `Localizer::new() -> Self`
- `localize(&mut self, left: &[f32], right: &[f32]) -> f32`(返回角度)

**依赖**:`rustfft = "6"`(Cargo.toml 需新增,用于 GCC-PHAT 的 FFT 计算)。

#### 3.6 实现分类器

**文件**:`src-tauri/src/analysis/classify.rs`

**职责**:基于 FFT 频谱形状规则分类。

**规则**(基于频段能量分布):
- **脚步(footstep)**:80-400Hz 能量占比 > 40%,且持续 < 200ms
- **枪声(gunshot)**:宽带瞬态 + 2-12kHz 高频能量 > 30%,且持续 < 100ms
- **载具(vehicle)**:持续低频(< 200Hz)+ 谐波结构,且持续 > 500ms
- **通用(generic)**:不符合上述规则的瞬态事件

**关键 API**:
- `Classifier::new() -> Self`
- `classify(&mut self, spectrum: &Spectrum, duration_ms: u32) -> SoundType`

#### 3.7 实现分析 worker 线程

**文件**:`src-tauri/src/analysis/worker.rs`

**职责**:消费 ring buffer → FFT → onset → 方位 → 分类 → emit `sound_event`。

**线程模型**(沿用 CaptureThread 模式):
```rust
pub struct AnalysisWorker {
    stop_flag: Arc<AtomicBool>,
    handle: Option<JoinHandle<()>>,
}
```

**主循环**:
1. 从 `FrameConsumer` 批量读取 1024 帧(hop size)
2. 调用 `SessionFilter::should_process_audio()` 判断是否处理(集成阶段 2 遗留)
3. 左右声道分别送入 `FftAnalyzer`
4. `OnsetDetector::detect()` 判断是否触发
5. 触发时:`Localizer::localize()` 取角度 + `Classifier::classify()` 取类型
6. 构造 `SoundEvent` + `AppHandle::emit("sound_event", payload)`
7. 未触发时 sleep 1ms 降低 CPU

**集成到 AppState**:`AppState` 新增 `analysis_worker: Mutex<Option<AnalysisWorker>>` 字段。`start_capture` 同时启动捕获线程与分析线程;`stop_capture` 同时停止两者。

#### 3.8 前端:类型定义

**文件**:`ui/src/types/audio.ts`

```typescript
export interface SoundEvent {
  angle: number;       // [-90, 90]
  intensity: number;   // [0, 1]
  sound_type: 'footstep' | 'gunshot' | 'vehicle' | 'generic';
  timestamp: number;
}
```

**文件**:`ui/src/types/appearance.ts`(阶段 5 也会用到,先定义)

```typescript
export interface Appearance {
  pos_x_percent: number;     // 0-100
  pos_y_percent: number;     // 0-100
  wave_length: number;       // 80-400 px
  wave_max_height: number;   // 20-120 px
  wave_thickness: number;    // 1-8 px
  opacity: number;           // 0.1-1.0
  color_footstep: string;    // #RRGGBB
  color_gunshot: string;
  color_vehicle: string;
  color_generic: string;
  decay_ms: number;          // 200-2000
  wave_style: 'smooth' | 'sawtooth' | 'step';
  show_divider: boolean;
}
```

#### 3.9 前端:useAudioEvents composable

**文件**:`ui/src/composables/useAudioEvents.ts`

订阅 `sound_event`,维护事件队列(保留最近 500ms 内的事件供渲染)。

```typescript
export function useAudioEvents() {
  const events = ref<SoundEvent[]>([]);
  // listen('sound_event', e => { events.value.push(e.payload); 清理超过 1s 的旧事件 })
  return { events };
}
```

#### 3.10 前端:useWaveRenderer composable

**文件**:`ui/src/composables/useWaveRenderer.ts`

Canvas 2D 绘制波纹条。读取 `events` 与 `appearance`,绘制:
- 左右两条水平波纹条
- 峰值水平位置 = 角度映射(-90° → 左条最左端,0° → 准星处,+90° → 右条最右端)
- 峰值高度 = 强度 × wave_max_height
- 颜色 = 声音类型对应颜色
- 衰减动画:基于 `decay_ms`,从峰值向两端扩散
- 仅在有事件时重绘(空闲时 requestAnimationFrame 跳帧)

**实现细节**:
- 使用 `requestAnimationFrame` 循环
- 维护"活跃事件"列表,每个事件记录触发时间戳
- 每帧计算衰减系数:`alpha = 1 - (now - event.timestamp) / decay_ms`
- `alpha < 0` 时从列表移除
- 列表为空时停止 RAF 循环

#### 3.11 前端:Overlay.vue 接入

**文件**:`ui/src/views/Overlay.vue`(扩展)

替换占位 canvas 逻辑,改为调用 `useAudioEvents` + `useWaveRenderer`。保留编辑模式拖拽逻辑(阶段 5 提取为 `useOverlayDrag`)。

**渲染参数读取**:
- 通过 `invoke('get_appearance')` 获取外观设置(阶段 5 实现,阶段 3 先用默认值硬编码)
- 后续阶段 5 实现后改为响应式读取

### 阶段 4:Profile 配置系统

**目标**:按游戏切换检测参数。

#### 4.1 创建 config 模块

**文件**:`src-tauri/src/config/mod.rs`

声明子模块:`profile`、`settings`、`default_profiles`。

#### 4.2 实现 Profile 结构

**文件**:`src-tauri/src/config/profile.rs`

```rust
#[derive(Deserialize, Serialize, Clone)]
pub struct Profile {
    pub game_id: String,
    pub name: String,
    pub process_names: Vec<String>,
    pub anticheat_risk: String,  // "high" | "medium" | "low"
    pub detection: DetectionConfig,
    pub sound_types: Vec<SoundTypeConfig>,
}

#[derive(Deserialize, Serialize, Clone)]
pub struct DetectionConfig {
    pub fft_size: usize,           // 默认 2048
    pub hop_size: usize,           // 默认 1024
    pub onset_threshold: f32,      // 默认 3.0 (k×MAD)
    pub min_event_interval_ms: u32, // 默认 100
}

#[derive(Deserialize, Serialize, Clone)]
pub struct SoundTypeConfig {
    pub name: String,             // "footstep" 等
    pub freq_range: (u32, u32),    // (80, 400)
    pub min_energy_ratio: f32,     // 0.4
    pub min_duration_ms: u32,
    pub max_duration_ms: u32,
}
```

**API**:
- `Profile::load_from_dir(dir: &Path) -> Vec<Profile>`(扫描目录所有 .toml)
- `Profile::save_to_dir(dir: &Path, id: &str, content: &str) -> Result<()>`
- `Profile::get_by_id(profiles: &[Profile], id: &str) -> Option<&Profile>`

#### 4.3 内嵌默认 profile

**文件**:`src-tauri/src/config/default_profiles/{default,hunt_showdown,r6_siege,pubg}.toml`

用 `include_str!` 编译进二进制。每个文件包含完整 TOML 结构。

**default.toml**(通用基线):
- process_names: []
- anticheat_risk: "low"
- fft_size: 2048, hop_size: 1024
- onset_threshold: 3.0
- 4 种 sound_type 默认配置

**hunt_showdown.toml**:
- process_names: ["Hunt_Showdown"]
- anticheat_risk: "medium"
- 脚步声灵敏度提高

**r6_siege.toml**:
- process_names: ["RainbowSix"]
- anticheat_risk: "medium"

**pubg.toml**:
- process_names: ["TslGame"]
- anticheat_risk: "medium"

#### 4.4 Tauri 命令

新增 4 个命令注册到 `lib.rs`:
- `list_profiles() -> Vec<ProfileListItem>`(返回 game_id/name/anticheat_risk 列表)
- `get_profile(id: String) -> String`(返回 TOML 文本)
- `save_profile(id: String, content: String) -> ()`(写入 %APPDATA%\sound-place\profiles\{id}.toml)
- `set_active_profile(id: String) -> ()`(写入 settings.json 的 active_profile 字段)

#### 4.5 首次启动初始化

在 `lib.rs` 的 `setup` 回调中:
1. 用 `directories::ProjectDirs` 获取 `%APPDATA%\sound-place\` 路径
2. 检测 `profiles/` 不存在 → 写出 4 个默认 profile
3. 检测 `settings.json` 不存在 → 写出默认设置 + `risk_accepted: false` + `active_profile: "default"`

### 阶段 5:风险告知 + 外观自定义 + 托盘 + 快捷键

**目标**:完整交互体验与合规边界。

#### 5.1 Rust:风险告知标志管理

**文件**:`src-tauri/src/ui/risk_notice.rs`

新增命令:
- `is_risk_accepted() -> bool`(读 settings.json)
- `accept_risk() -> ()`(写入 true)

#### 5.2 Rust:外观设置持久化

**文件**:`src-tauri/src/config/settings.rs`

```rust
#[derive(Deserialize, Serialize)]
pub struct Settings {
    pub risk_accepted: bool,
    pub active_profile: String,
    pub appearance: Appearance,
}

#[derive(Deserialize, Serialize, Clone)]
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
```

**API**:
- `Settings::load() -> Settings`(读 %APPDATA%\sound-place\settings.json,不存在返回默认)
- `Settings::save(&self) -> Result<()>`
- `Appearance::default() -> Appearance`(返回计划文档表格中的默认值)

新增命令:
- `get_appearance() -> Appearance`
- `save_appearance(a: Appearance) -> ()`
- `reset_appearance() -> Appearance`

#### 5.3 Rust:系统托盘

**文件**:`src-tauri/src/ui/tray.rs`

用 `tauri::tray::TrayIconBuilder` 创建托盘:
- 图标(用内置 Tauri 图标或简单 base64)
- 右键菜单:显示面板 / 启用覆盖 / 调整位置 / 退出
- 关闭主窗口时拦截 → 最小化到托盘(不退出)

在 `lib.rs` 的 `setup` 中初始化托盘。

#### 5.4 Rust:全局快捷键

**文件**:`src-tauri/src/lib.rs`(扩展 setup)

绑定:
- `Ctrl+Alt+S` → 切换 overlay 显隐(emit 事件给主窗口切换状态)
- `Ctrl+Alt+E` → 切换编辑模式(emit `edit-mode` 事件)

#### 5.5 前端:RiskNotice.vue

**文件**:`ui/src/views/RiskNotice.vue`

强制弹窗组件,内容:
- 立体声定位的物理限制(无法区分前后)
- 反作弊风险分级表(高/中/低 + 对应游戏)
- 合规声明文本
- "我已知晓风险"勾选框 + 确认按钮
- 未勾选时确认按钮禁用

**集成**:ControlPanel.vue 在 `onMounted` 调用 `is_risk_accepted()`,未接受则全屏遮罩显示 RiskNotice。

#### 5.6 前端:AppearanceSettings.vue

**文件**:`ui/src/views/AppearanceSettings.vue`

外观设置页,所有改动通过 `save_appearance` 实时持久化 + emit `appearance-changed` 事件让 Overlay 实时更新。

控件:
- 位置 X/Y:range 滑块(0-100)+ 重置按钮
- 波纹长度/高度/厚度:range 滑块
- 透明度:range 滑块(0.1-1.0)
- 4 个颜色选择器(`<input type="color">`)
- 衰减时长:range 滑块(200-2000)
- 波纹样式:select(平滑/锯齿/阶梯)
- 显示分界标记:checkbox

#### 5.7 前端:ControlPanel.vue 完整版

**文件**:`ui/src/views/ControlPanel.vue`(扩展)

布局:
- 顶部:启动/停止捕获 + 启用/禁用覆盖按钮 + 当前 profile 显示
- Tab 切换:Profile 管理 / 外观设置 / 帮助 / 关于
- Profile 管理 Tab:左侧列表(含风险标签)+ 右侧 TOML 编辑器(textarea)+ 保存/激活按钮
- 外观设置 Tab:嵌入 AppearanceSettings.vue
- 帮助 Tab:嵌入帮助文档
- 关于 Tab:版本 + 开源地址 + 免责声明

#### 5.8 前端:useOverlayDrag composable

**文件**:`ui/src/composables/useOverlayDrag.ts`

从 Overlay.vue 提取拖拽逻辑,增加位置持久化:拖动结束时调用 `save_appearance` 保存新位置。

### 阶段 6:合规性、文档与打包

**目标**:可发布的绿色版。

#### 6.1 Rust:合规声明与全屏检测

在 ControlPanel 的帮助 Tab 内显示合规文本。

全屏独占检测(可选,简化版):尝试调用 `GetForegroundWindow` + 检查窗口样式,若为全屏独占则 emit `fullscreen-exclusive` 事件,前端显示提示。**v1 简化**:不实现自动检测,仅在帮助页文档中提示用户使用无边框窗口模式。

#### 6.2 前端:帮助页与关于页

**文件**:`ui/src/views/HelpPage.vue`(新建,作为 ControlPanel 的 Tab 内容)

内容:
- 使用前提(Windows 10 1803+,WebView2 Runtime)
- 游戏模式要求(必须无边框窗口模式,不支持独占全屏)
- Profile 配置说明(每个字段的含义)
- 常见问题(为什么没反应?为什么方位不准?会被封号吗?)
- 风险告知复述

**文件**:`ui/src/views/AboutPage.vue`(新建)

内容:
- 应用版本(从 Cargo.toml 读取或硬编码 0.1.0)
- 开源地址(github.com/YR707/sound-place)
- MIT License
- 免责声明全文

#### 6.3 打包验证

`cargo build --release` 产出单 `.exe`。验证:
- 双击运行不写注册表
- 配置全部在 `%APPDATA%\sound-place\`
- 卸载只需删 exe + 删配置目录

## 假设与决策

1. **假设**:用户在另一台机器装好 Rust stable + Node 20 + VS Build Tools(C++ 桌面开发),clone 后 `cargo build` 通过。
2. **假设**:用户理解本机无法编译验证,接受"代码写完即推送,实机验证延后"的开发模式。
3. **决策**:方位算法用完整 ILD + GCC-PHAT ITD 融合(用户确认),精度目标 ±15°,代码量约 300 行。
4. **决策**:文档写完整内容(用户确认),包括帮助页与关于页。
5. **决策**:SessionFilter 集成在分析线程入口处调用,不在捕获线程中调用(保持捕获实时性)。
6. **决策**:全屏独占自动检测 v1 不实现,仅文档提示(降低复杂度)。
7. **决策**:托盘图标用 Tauri 默认图标(避免引入额外资源)。
8. **决策**:`rustfft = "6"` 需在 Cargo.toml 新增(GCC-PHAT 需要,realfft 内部用 rustfft 但未暴露通用 FFT)。

## 验证步骤

由于本机无法编译,验证分两阶段:

### 阶段 A:代码完整性自检(本机可做)

- 每个新文件创建后,用 Grep 检查导出的类型/函数是否在 `lib.rs` 或 `mod.rs` 中正确注册
- 检查所有 `invoke('xxx')` 的命令名在 Rust 端 `generate_handler!` 中存在
- 检查所有 `listen('xxx')` 的事件名在 Rust 端 `emit` 中存在
- 检查 Cargo.toml 的新依赖是否都加了

### 阶段 B:用户在另一台机器验证

1. `git pull`
2. `cd ui && npm install`
3. `cd src-tauri && cargo build`(debug 编译通过)
4. `cargo tauri dev`(dev 模式运行,验证 GUI 启动 + 双窗口 + overlay 控制)
5. 播放测试音频,验证波纹条响应
6. `cargo build --release`(产出 .exe)
7. 双击 .exe 验证绿色版运行

## 文件改动清单

### 新建文件(17 个)

**Rust**:
- `src-tauri/src/analysis/mod.rs`
- `src-tauri/src/analysis/fft.rs`
- `src-tauri/src/analysis/onset.rs`
- `src-tauri/src/analysis/localize.rs`
- `src-tauri/src/analysis/classify.rs`
- `src-tauri/src/analysis/worker.rs`
- `src-tauri/src/config/mod.rs`
- `src-tauri/src/config/profile.rs`
- `src-tauri/src/config/settings.rs`
- `src-tauri/src/config/default_profiles/default.toml`
- `src-tauri/src/config/default_profiles/hunt_showdown.toml`
- `src-tauri/src/config/default_profiles/r6_siege.toml`
- `src-tauri/src/config/default_profiles/pubg.toml`
- `src-tauri/src/ui/mod.rs`
- `src-tauri/src/ui/risk_notice.rs`
- `src-tauri/src/ui/tray.rs`

**前端**:
- `ui/src/types/audio.ts`
- `ui/src/types/appearance.ts`
- `ui/src/composables/useAudioEvents.ts`
- `ui/src/composables/useWaveRenderer.ts`
- `ui/src/composables/useOverlayDrag.ts`
- `ui/src/views/AppearanceSettings.vue`
- `ui/src/views/RiskNotice.vue`
- `ui/src/views/HelpPage.vue`
- `ui/src/views/AboutPage.vue`

### 修改文件(5 个)

- `src-tauri/Cargo.toml`(新增 rustfft)
- `src-tauri/src/audio/mod.rs`(修复 AudioFrame 导出 bug)
- `src-tauri/src/lib.rs`(注册所有新命令 + 托盘 + 快捷键 + setup 初始化)
- `ui/src/views/Overlay.vue`(接入 composables)
- `ui/src/views/ControlPanel.vue`(完整版控制面板)
