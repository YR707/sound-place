# SoundPlace 声音方位辅助软件 — 实施计划

## 摘要

构建一个 Windows 桌面应用 **SoundPlace**，定位为**声音分析学习工具 + 谨慎辅助**。通过分析系统音频（WASAPI loopback + 进程白名单过滤），在游戏画面上叠加一个透明置顶的覆盖窗，以**准星左右两侧的动态波纹条**实时提示脚步声/枪声/车辆声等事件的左右方位与强度。软件为绿色单 `.exe`，免安装，零游戏内存交互。支持按游戏切换配置 profile。

## 用户需求与约束

| 项    | 内容                                                         |
| ---- | ---------------------------------------------------------- |
| 形态   | Tauri 2.x 桌面应用，单 `.exe` 绿色免安装，不动注册表/不写系统目录                 |
| 音频源  | WASAPI 系统音频回环 + **进程白名单过滤**（只抓指定游戏进程，排除 Discord/浏览器/QQ 干扰） |
| 核心功能 | 声音事件检测（脚步/枪声/车辆/通用）+ 左右方位提示                                |
| 显示方式 | 透明置顶悬浮窗 + **准星左右两侧动态波纹条**（不暗示前后）                           |
| 配置   | 每游戏可独立 profile，可自定义检测声音类型与参数                               |
| 产品定位 | **学习为主 + 谨慎辅助**；首次启动显示风险告知书；明确不支持 Vanguard/EAC 等严格反作弊游戏    |
| 合规红线 | **绝对不与游戏进程交互、不读内存、不挂钩图形 API、不注入**，纯音频侧分析                   |

## 物理限制（必须明确告知用户）

### 立体声定位的硬限制

立体声只有左右 2 个通道，物理上能提取的方位信息是**1D**：声源相对正前方的水平偏角 θ ∈ \[-90°, +90°]。

| 信息              | 能否得到 | 说明                                 |
| --------------- | ---- | ---------------------------------- |
| 水平左右角度（ILD/ITD） | ✅ 能  | 偏左 30° 还是偏左 60° 可以估算，误差典型 ±15°     |
| 前后区分            | ❌ 不能 | 前方 30° 和后方 30° 的左右差**完全相同**，算法无法区分 |
| 上下区分            | ❌ 不能 | 垂直方向左右耳几乎无差异                       |
| 多声源分离           | ❌ 不能 | 同时发声会叠加成单一方位                       |

### 显示策略：可自由配置的波纹条组

为规避前后误判硬伤，采用**左右两侧动态波纹条**而非雷达圆。默认样式：

```
                    ┌──准星──┐
                    │   +    │
        ◢━━━━━━━━━━━│        │━━━━━━━━━━━◣
        ▁▂▃▅▇▅▃▂▁   └────────┘   ▁▂▃▅▇▅▃▂▁
        ← 左侧波纹条              右侧波纹条 →
```

**信息编码：**
- **条的位置**：默认紧贴准星左右水平延伸，但**可自由拖动到屏幕任意位置**（按住拖拽手柄移动整个波纹组）
- **波纹峰值水平位置**（连续方位映射）：
  - 声音在最左 (-90°) → 左条峰值在最左端，右条无峰值
  - 声音在正前方 (0°) → 左条峰值在最右端（靠近中心），右条峰值在最左端（靠近中心）
  - 声音在最右 (+90°) → 左条无峰值，右条峰值在最右端
  - 即两条波纹条合起来形成一个连续的方位指示带，声源角度直接映射到峰值在带上的位置
- **波纹峰值高度**：声音越大 → 峰值越高
- **波纹颜色**：按声音类型，**颜色完全可自定义**（默认：脚步黄/枪红/车蓝/通用白）
- **衰减动画**：事件后波纹从峰值向两端衰减消失（约 600-800ms，可调）
- **多声源**：按时间错开显示，同一瞬态时刻只画能量最大者

### Overlay 外观完全可自定义

用户可在控制面板「外观设置」中调整以下参数，所有设置实时生效并持久化：

| 参数       | 说明                 | 范围         | 默认值           |
| -------- | ------------------ | ---------- | ------------- |
| 波纹组位置 X  | 波纹组中心在屏幕的水平位置      | 0-100%     | 屏幕宽度 50%      |
| 波纹组位置 Y  | 波纹组中心在屏幕的垂直位置      | 0-100%     | 屏幕高度 50%（准星处） |
| 波纹条总长度   | 单侧波纹条水平延伸长度        | 80-400px   | 200px         |
| 波纹条最大高度  | 峰值最大垂直高度           | 20-120px   | 50px          |
| 波纹条厚度    | 波纹线条粗细             | 1-8px      | 3px           |
| 整体透明度    | Overlay 整体不透明度     | 0.1-1.0    | 0.85          |
| 脚步声颜色    | 十六进制颜色             | #RRGGBB    | #FFD700（黄）    |
| 枪声颜色     | 十六进制颜色             | #RRGGBB    | #FF4444（红）    |
| 车辆声颜色    | 十六进制颜色             | #RRGGBB    | #44A4FF（蓝）    |
| 通用事件颜色   | 十六进制颜色             | #RRGGBB    | #FFFFFF（白）    |
| 衰减时长     | 事件后波纹消失时间          | 200-2000ms | 700ms         |
| 波纹样式     | 平滑曲线 / 锯齿 / 阶梯     | 枚举         | 平滑曲线          |
| 显示左右分界标记 | 是否在中心显示一个小竖线作为左右分界 | bool       | true          |

**拖拽交互：**

* Overlay 处于"编辑模式"时（控制面板中点击「调整位置」按钮启用），波纹组显示拖拽手柄

* 用户按住手柄拖动整个波纹组到任意位置

* 拖动时实时显示坐标，松开后位置自动保存到 `settings.json`

* 编辑模式下波纹组边框高亮，方便看清；退出编辑模式后边框消失，恢复正常透明状态

**优势：**

* ✅ 只表示左右，绝不暗示前后，避免误导

* ✅ 默认紧贴准星，但用户可自由调整位置（不限于准星两侧）

* ✅ 峰值位置+高度双重编码，信息密度高

* ✅ 外观完全可自定义，适应不同游戏 UI 布局

* ✅ 自然适合"按时间错开"的多声源显示

### 反作弊风险告知（首次启动弹窗）

**无法保证不被封号，也无法事后申诉成功。** 反作弊（Vanguard/BattlEye/EAC）判定黑盒，无公开白名单认证机制，开发者无法"证明"软件无害获得豁免。

**风险分级（仅供参考，不代表保证）：**

| 风险等级 | 游戏                                           | 建议          |
| ---- | -------------------------------------------- | ----------- |
| 高    | Valorant (Vanguard 内核级)、CS2 排位 (VAC)、Apex 排位 | **禁止使用本软件** |
| 中    | PUBG、彩六围攻 (BattlEye 用户态)                     | 用小号先测，避开排位  |
| 低    | 单机游戏、无反作弊多人游戏                                | 自由使用        |

**首次启动强制弹窗**，用户必须勾选"我已知晓风险"才能继续。

## 性能影响评估

### 对游戏性能的直接影响：几乎为零

* WASAPI loopback 是**复制系统已有的混音输出**，不插入游戏音频链路，游戏感知不到

* 进程白名单过滤只是**读取 WASAPI session 列表**（每秒几次），不改游戏音频流

* 软件本身 CPU 占用预估 < 2%（FFT 2048 + onset 检测轻量）

### 间接影响与缓解

| 风险点                 | 机制                  | 缓解                      |
| ------------------- | ------------------- | ----------------------- |
| Tauri overlay 透明窗合成 | DWM 合成多一层，独占全屏时可能掉帧 | 强制要求**无边框窗口模式**而非独占全屏   |
| Canvas 60fps 重绘     | GPU 占用              | 仅在有事件时重绘，空闲时跳帧          |
| 高采样率音频              | FFT 计算量上升           | profile 固定 48kHz，必要时重采样 |

**结论**：无边框窗口模式下性能影响可忽略；独占全屏下 overlay 不显示，软件也不介入。

## 当前状态分析

- 工作目录 `sound-place` 为空，全新项目

* 用户技术栈：Vue3/Vite（前端熟练）、Spring Boot/MyBatis（后端熟悉），Rust 为新栈，计划需明确指引

* Tauri 2.x 已稳定（2024 年 7 月 GA），生态成熟

* 关键依赖 crate：`wasapi`（loopback）、`windows-sys`（进程 session 枚举）、`realfft`（FFT）、`toml`/`serde`（配置）、`heapless`（无锁队列）

## 项目结构

```
sound-place/
├── Cargo.toml
├── tauri.conf.json
├── build.rs
├── src/                          # Rust 后端
│   ├── main.rs                   # Tauri 入口 + 命令注册
│   ├── audio/
│   │   ├── mod.rs
│   │   ├── capture.rs             # WASAPI loopback 捕获线程
│   │   ├── session_filter.rs      # 进程白名单过滤（windows-sys COM 调用）
│   │   └── ring_buffer.rs         # 无锁 SPSC 环形缓冲
│   ├── analysis/
│   │   ├── mod.rs
│   │   ├── fft.rs                 # realfft 封装 + Hann 窗
│   │   ├── onset.rs               # Spectral Flux + HFC 瞬态检测
│   │   ├── localize.rs            # ILD/ITD 左右方位估计（输出 -90°~+90°）
│   │   └── classify.rs            # 频谱形状规则分类（脚步/枪声/载具）
│   ├── config/
│   │   ├── mod.rs
│   │   ├── profile.rs             # TOML profile 结构 + 加载
│   │   └── default_profiles/      # 内嵌默认 profile（include_str!）
│   │       ├── default.toml
│   │       ├── hunt_showdown.toml
│   │       ├── r6_siege.toml
│   │       └── pubg.toml
│   ├── ui/
│   │   ├── mod.rs
│   │   ├── risk_notice.rs         # 首次启动风险告知逻辑
│   │   └── settings.rs             # 外观设置持久化（位置/大小/颜色/透明度）
│   └── overlay/
│       ├── mod.rs
│       └── window.rs              # 透明置顶窗 + 点击穿透切换 + 编辑模式切换
├── ui/                           # Vue3 前端
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── src/
│   │   ├── main.ts
│   │   ├── App.vue                # 入口，根据 route 切换 overlay/control
│   │   ├── views/
│   │   │   ├── Overlay.vue        # 波纹条覆盖窗（含编辑模式拖拽）
│   │   │   ├── ControlPanel.vue    # 配置/游戏切换面板
│   │   │   ├── AppearanceSettings.vue # 外观设置页（位置/大小/颜色/透明度）
│   │   │   └── RiskNotice.vue     # 首次启动风险告知弹窗
│   │   ├── composables/
│   │   │   ├── useAudioEvents.ts  # 订阅 Rust 音频事件
│   │   │   ├── useWaveRenderer.ts # Canvas 波纹条绘制（读取外观设置）
│   │   │   └── useOverlayDrag.ts  # 编辑模式下拖拽位置逻辑
│   │   └── types/
│   │       ├── audio.ts
│   │       └── appearance.ts       # 外观设置类型定义
│   └── tsconfig.json
└── .trae/documents/
    └── sound-place-overlay-app-plan.md
```

## 实施步骤

### 阶段 1：工程骨架与 PoC 验证（关键风险点先行）

**目标**：先验证最高风险点 — Tauri 2.x 透明置顶窗 + 点击穿透在 Windows 上的稳定性。

1. 初始化 Tauri 2.x + Vue3 项目（`npm create tauri-app@latest` 选 Vue + TypeScript）
2. 配置 `tauri.conf.json`：主窗口为控制面板（普通窗口），第二窗口为 overlay（`transparent: true, decorations: false, alwaysOnTop: true, skipTaskbar: true, shadow: false, visible: false`）
3. 实现 Rust 命令 `enable_overlay` / `disable_overlay`，调用 `window.set_ignore_cursor_events(true)` 实现全窗穿透
4. Overlay.vue：透明背景 + 准星位置画两个水平条占位（Canvas 2D），验证可见且鼠标穿透
5. 配置绿色打包：`tauri.conf.json` 中 `"bundle": { "active": false }`，确认 `cargo build --release` 产出单 `.exe`

**验证标准**：双击 `.exe` 启动；点击"启用覆盖"后准星左右出现透明波纹条占位；鼠标点击波纹区域可穿透到下层游戏窗口；任务栏不显示 overlay；无边框窗口模式下游戏内 overlay 可见。

### 阶段 2：音频捕获链路 + 进程过滤

**目标**：WASAPI loopback + 进程白名单 → ring buffer → FFT → 控制台打印频谱条。

1. 添加依赖：`wasapi = "2"`, `windows-sys = { version = "0.52", features = ["Win32_Media_Audio", "Win32_System_Com", "Win32_System_ProcessStatus"] }`, `realfft = "3"`, `rustfft = "6"`, `heapless = "0.8"`, `serde = { version = "1", features = ["derive"] }`, `toml = "0.8"`, `directories = "5"`
2. `audio/capture.rs`：WASAPI 共享模式 loopback 拉取线程，事件驱动（`SetEventHandle`），deinterleave 左右声道，写入 `heapless::spsc::Queue`
3. `audio/session_filter.rs`：用 `IAudioSessionEnumerator` 枚举系统混音中各进程的音频流，按 profile 中 `process_names` 白名单过滤，只抓游戏进程的音频。约 150 行 windows-sys COM 代码
4. `analysis/fft.rs`：`RealFftPlanner` 初始化（size=2048），Hann 窗预计算，每 hop=1024 样本做一次 FFT，输出左右声道幅度谱
5. 分析 worker 线程：从 ring buffer 读 → FFT → 打印频谱条到控制台
6. Tauri 命令 `start_capture` / `stop_capture`

**验证标准**：`start_capture` 后控制台持续打印左右声道频谱条；播放游戏时可见能量分布；同时播放 Discord/浏览器时游戏进程音频仍被正确抓取（其他进程被过滤）；左右声道在播放立体声测试音频时有差异。

### 阶段 3：方位估计 + 瞬态检测

**目标**：在覆盖窗画出准星左右波纹条。

1. `analysis/onset.rs`：Spectral Flux（正频谱差之和）+ HFC（高频能量加权），滑动窗口峰值拾取（中位数 + k×MAD 自适应阈值）
2. `analysis/localize.rs`：onset 触发瞬间快照 ILD（左右 RMS 比 → 方位角）与 ITD（GCC-PHAT 互相关 → 时延差 → 角度），加权融合输出 \[-90°, +90°] 相对正前方的水平偏角
3. `analysis/classify.rs`：基于 FFT 频谱形状规则分类（脚步：80-400Hz 集中；枪声：宽带瞬态+2-12kHz 高频；载具：持续低频+谐波），输出事件类型枚举
4. 分析线程通过 `AppHandle::emit("sound_event", payload)` 发布事件到前端，payload 包含 `{ angle: -45.0, intensity: 0.8, sound_type: "footstep" }`
5. `useAudioEvents.ts` 订阅 `sound_event`
6. `useWaveRenderer.ts` 用 Canvas 2D 绘制：

   * 左右两条水平波纹条，紧贴准星

   * 峰值水平位置 = 角度映射（-90° → 左条最左端，0° → 准星处，+90° → 右条最右端）

   * 峰值高度 = 强度映射

   * 颜色 = 声音类型

   * 衰减动画 600-800ms，从峰值向两端扩散消失

   * 仅在有事件时重绘，空闲跳帧

**验证标准**：播放左右测试音频，波纹峰值出现在对应条对应位置；播放脚步/枪声音频样本，波纹颜色按类型区分；事件后波纹衰减消失；同时播放 Discord 对话不被误报。

### 阶段 4：Profile 配置系统

**目标**：按游戏切换检测参数。

1. `config/profile.rs`：定义 `Profile` 结构（game\_id, name, process\_names, detection 参数, sound\_types 配置, overlay 配置），`serde` 反序列化 TOML
2. `config/default_profiles/`：内嵌 4 个默认 profile（default / hunt\_showdown / r6\_siege / pubg），用 `include_str!` 编译进二进制
3. Tauri 命令 `list_profiles` / `get_profile(id)` / `save_profile(id, content)` / `set_active_profile(id)`
4. 首次启动：检测 `%APPDATA%\sound-place\profiles\` 不存在则写出默认 profile；同时写出 `risk_accepted: false` 标志
5. `ControlPanel.vue`：左侧 profile 列表（含反作弊风险等级标签），右侧 TOML 编辑器（简单 `<textarea>` 或 Monaco），保存按钮调用 `save_profile`；切换激活 profile 调用 `set_active_profile`
6. 分析线程运行时读取当前激活 profile 的参数（FFT size、onset 阈值、各 sound\_type 的 freq\_range、min\_interval），动态生效

**验证标准**：默认 profile 写入 `%APPDATA%`；UI 列出 4 个游戏并标注风险等级；切换激活 profile 后检测行为符合配置（如关闭脚步声检测后不再触发脚步事件）。

### 阶段 5：风险告知 + 控制面板 + 托盘 + 外观自定义

**目标**：完整交互体验与合规边界。

1. `RiskNotice.vue`：首次启动强制弹窗，内容包含：

   * 立体声定位的物理限制（无法区分前后）

   * 反作弊风险分级表

   * "本软件不读取游戏内存、不挂钩图形 API、不注入游戏进程、不修改游戏数据，仅分析系统音频输出"

   * "用户自担风险，开发者不承担封号责任"

   * 必须勾选"我已知晓风险"才能继续
2. 控制面板 UI：启动/停止捕获、启用/禁用覆盖、当前激活 profile 显示、灵敏度滑块
3. `AppearanceSettings.vue` 外观设置页：

   * 波纹组位置 X/Y（百分比滑块 + 「重置到屏幕中心」按钮）

   * 波纹条总长度、最大高度、厚度（滑块）

   * 整体透明度（滑块，实时预览）

   * 4 种声音类型颜色（颜色选择器 `<input type="color">`）

   * 衰减时长（滑块）

   * 波纹样式（下拉：平滑曲线/锯齿/阶梯）

   * 显示左右分界标记（开关）

   * 所有改动实时同步到 overlay，并写入 `settings.json`
4. `ui/settings.rs`：`Appearance` 结构 + serde 序列化到 `%APPDATA%\sound-place\settings.json`；Tauri 命令 `get_appearance` / `save_appearance` / `reset_appearance`
5. `useOverlayDrag.ts`：编辑模式下：

   * 控制面板点击「调整位置」→ overlay 进入编辑模式

   * Overlay.vue 在波纹组上方显示半透明拖拽手柄（圆点 + 边框高亮）

   * 鼠标按住手柄拖动 → 实时更新位置 → 通过 Tauri 命令保存

   * 退出编辑模式时手柄与边框消失，恢复完全透明

   * 编辑模式下点击穿透关闭，方便拖动；退出后恢复点击穿透
6. 系统托盘（`tauri-plugin-tray`）：图标 + 右键菜单（显示/隐藏面板、启用/禁用覆盖、调整位置、退出）；关闭主窗口时最小化到托盘而非退出
7. 全局快捷键（`tauri-plugin-global-shortcut`）：`Ctrl+Alt+S` 切换覆盖显隐、`Ctrl+Alt+E` 切换编辑模式
8. 设置持久化：面板状态 + 外观设置全部写入 `%APPDATA%\sound-place\settings.json`

**验证标准**：首次启动弹出风险告知；勾选后不再弹；外观设置改动实时生效；编辑模式下可拖动 overlay 到任意位置并保存；托盘菜单可用；快捷键切换覆盖与编辑模式；重启后恢复上次状态与位置。

### 阶段 6：合规性、文档与打包

**目标**：可发布的绿色版。

1. 合规声明：在控制面板"关于"页与面板内帮助页明确合规边界
2. 全屏独占限制提示：若检测到游戏全屏独占，UI 提示"请使用无边框窗口模式"
3. `cargo build --release` 产出单 `.exe`（预期 6-10 MB），本地测试在 Win10/Win11 上运行
4. 面板内帮助页：使用前提、游戏模式要求、profile 配置说明、常见问题、风险告知复述

**验证标准**：单 `.exe` 在干净 Win11 上双击可运行；不写注册表；配置全部在 `%APPDATA%\sound-place\`；卸载只需删 exe + 删配置目录。

## 关键技术决策汇总

| 决策点  | 选择                                              | 理由                                                           |
| ---- | ----------------------------------------------- | ------------------------------------------------------------ |
| 应用框架 | Tauri 2.x                                       | 单 exe 体积小、性能好、Rust 后端适合音频实时处理                                |
| 音频捕获 | `wasapi` crate                                  | 直接暴露 loopback 模式，Windows 原生                                  |
| 进程过滤 | `windows-sys` 直接调 COM                           | `wasapi` crate 未暴露 session 枚举，需直接调 `IAudioSessionEnumerator` |
| FFT  | `realfft`                                       | 实数信号优化，API 干净                                                |
| 配置格式 | TOML                                            | 比 JSON 易手写，比 YAML 安全                                         |
| 前端   | Vue3 + Vite + TS                                | 用户熟悉栈                                                        |
| 波纹绘制 | Canvas 2D                                       | 60fps 足够，仅事件时重绘                                              |
| 打包   | `bundle.active=false` + `cargo build --release` | 纯绿色单 exe                                                     |
| 方位算法 | ILD + GCC-PHAT ITD 融合                           | 立体声源最佳可行方案，输出限制在 \[-90°, +90°]                               |
| 显示方式 | 可拖动+可自定义的左右波纹条                                  | 规避前后误判硬伤，适应不同游戏 UI 布局                                        |
| 外观配置 | `settings.json` + 实时预览 + 编辑模式拖拽                 | 用户可自由调整位置/大小/颜色/透明度                                          |
| 瞬态检测 | Spectral Flux + HFC                             | 对打击/枪声响应好                                                    |
| 分类   | 频谱形状规则（v1）→ ONNX（v2 可选）                         | 先简后繁                                                         |
| 产品定位 | 学习为主 + 谨慎辅助                                     | 用户明确不希望冒险                                                    |

## 假设与开放项

1. **假设**：用户机器为 Windows 10 1803+ 或 Windows 11，已预装 WebView2 Runtime
2. **假设**：用户愿意在游戏中使用"无边框窗口模式"而非全屏独占
3. **假设**：用户理解立体声无法区分前后的物理限制，接受波纹条只提示左右
4. **开放项**：v1 不做声音事件录制回放、不做历史统计、不做声音训练；如后续需要可扩展
5. **开放项**：反作弊兼容性需用户在实际游戏中验证；建议先用低风险游戏测试，严格反作弊游戏（Valorant/CS2排位/Apex排位）禁止使用
6. **开放项**：进程过滤依赖 WASAPI session 暴露进程名，少数游戏可能不暴露，需 fallback 到全混音

## 开源与隐私合规（GitHub 公共仓库）

本项目将推送到 GitHub 公共仓库，必须从工程第一天就做好隐私与合规隔离。

### 隐私保护设计

| 项          | 措施                                                                              |
| ---------- | ------------------------------------------------------------------------------- |
| 配置存储       | 所有用户数据仅存于本地 `%APPDATA%\sound-place\`，绝不上传、绝不联网                                  |
| 无遥测        | 不集成任何分析 SDK（无 Sentry / Google Analytics / Crashpad 上报）                          |
| 无网络请求      | v1 不做联网功能；Cargo.toml 禁用任何 `reqwest`/`ureq`/`tokio` 网络依赖；可在 CI 用 `cargo deny` 检查 |
| 进程信息       | 仅读取进程名做白名单匹配，不记录、不保存、不上报                                                        |
| 音频数据       | 仅内存中实时分析，绝不写入磁盘；如后续加录制功能需显式用户操作并保存到用户指定路径                                       |
| 默认 profile | 内嵌于二进制，不含任何用户机器信息                                                               |

### 仓库结构与敏感信息隔离

1. **`.gitignore`** **必须包含**：

   * `/target/`（Rust 构建产物）

   * `/ui/node_modules/`、`/ui/dist/`

   * `.env*`、`*.env`

   * `*.log`、`/logs/`

   * `.vscode/`、`.idea/`

   * 任何本地测试音频文件（`*.wav`、`*.mp3`、`*.flac` 放在 `tests/samples/` 但该目录加入 `.gitignore`，改用 README 说明下载地址）

   * `%APPDATA%` 下的本地配置不应进入仓库
2. **代码中绝不硬编码**：

   * 个人路径（如 `C:\Users\28567\...`），改用 `directories` crate 获取

   * 个人邮箱、Key、Token

   * 测试用的具体游戏账号信息
3. **提交前检查**：

   * 首次提交前用 `git log -p | grep -i "C:\\\\Users"` 等检查是否泄漏本地路径

   * 用 `git-secrets` 或 `trufflehog` 做密钥扫描

### 开源合规

1. **License**：选择 `MIT` 或 `Apache-2.0`（推荐 MIT，简洁宽松），在仓库根放 `LICENSE` 文件，`Cargo.toml` 与 `package.json` 都声明 `license`
2. **README.md 必含**：

   * 项目简介与截图占位

   * **免责声明**：本软件仅供学习与个人辅助使用，不保证不被反作弊系统封禁，用户自担风险；开发者不承担任何直接或间接责任

   * 物理限制说明（立体声无法区分前后）

   * 安装与使用前提（WebView2、无边框窗口模式）

   * 构建说明（`pnpm install` + `cargo build --release`）

   * 配置 profile 说明

   * 贡献指南（Contributing.md 可选）
3. **第三方依赖合规**：

   * 所有 Rust crate 必须是 MIT/Apache-2.0/MPL-2.0/BSD 等宽松许可证，禁用 GPL/AGPL（避免传染性）

   * 所有 npm 包检查 License

   * 用 `cargo deny` + `license` 检查（CI 集成）
4. **DCO / CLA**：个人项目可选不签 CLA；若担心未来贡献者纠纷，加 DCO（Developer Certificate of Origin）`Signed-off-by` 要求
5. **仓库 Settings 建议**：

   * 启用 Issues、Wiki（可选）

   * 禁用 Sponsor 按钮（除非希望接受赞助）

   * 启用 Security Policy（`SECURITY.md`），说明漏洞报告方式

   * 启用 Discussions 作为问答区，与 Issues 分离

### 文件清单补充

仓库根新增：

* `LICENSE`（MIT 全文）

* `README.md`（中文为主，可选英文翻译）

* `SECURITY.md`（漏洞报告方式）

* `CODE_OF_CONDUCT.md`（可选，Contributor Covenant v2.1）

* `.gitignore`（含上述规则）

* `deny.toml`（cargo-deny 配置：禁网络依赖、禁 GPL、禁已知漏洞 crate）

* `CONTRIBUTING.md`（可选，说明 PR 流程）

## 验证步骤（整体）

1. 双击单 `.exe` 启动，首次弹出风险告知，勾选后进入控制面板，托盘图标出现
2. 选择"猎杀对决" profile（标注中风险），点击"启用覆盖"+"开始捕获"
3. 启动游戏（无边框窗口模式），进入对局
4. 验证：开枪时准星右侧（或左侧）波纹条出现红色峰值，峰值位置对应方位；脚步声出现黄色峰值；车辆出现蓝色峰值
5. 验证：鼠标点击穿透到游戏，不影响操作
6. 验证：同时开 Discord 通话，游戏声音仍被正确抓取，Discord 声音被过滤
7. 验证：切换到"彩六" profile，脚步声灵敏度提升、枪声灵敏度下降
8. 验证：关闭软件后 `%APPDATA%\sound-place\` 配置保留，重启恢复状态
9. 验证：卸载仅需删 exe + 配置目录，无残留

