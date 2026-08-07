# SoundPlace Rust 版本测试指南

> 本文档用于在**另一台未启用 Smart App Control (SAC) 的 Windows 电脑**上测试 Rust 版本。
>
> Rust 版本用 `wasapi 0.23` crate 调用**系统级 WASAPI Loopback** API，在默认渲染设备上以 `Direction::Capture` 模式捕获扬声器输出。这与本机 Python 原型调试失败的 `ActivateAudioInterfaceAsync ProcessLoopback` API **完全不同**，不会遇到 `0x80070002 (E_FILE_NOT_FOUND)` 问题。

---

## 0. 前提条件检查

### 0.1 检查 Smart App Control 状态（**必须先关闭或本就未启用**）

SAC 是 Windows 11 的 WDAC 用户态策略，**启用时会拦截未签名的 cargo 编译产物**（`os error 4551`）。SAC 一旦启用**无法关闭**（只能重装系统），所以必须选一台本就未启用 SAC 的电脑。

检查方法：
- 打开 `设置` > `隐私和安全` > `Windows 安全中心` > `应用和浏览器控制` > `智能应用控制`
- 状态应该是 `关闭` 或 `未配置`，**不能是 `启用` 或 `强制`**

如果该机器已启用 SAC，**不要继续**，换一台机器。

### 0.2 检查 Windows 版本

Rust 版本要求 Win10 2004+ 或 Win11（任意版本）。Build 号 ≥ 19041。

在 PowerShell 中检查：
```powershell
winver
# 或
[System.Environment]::OSVersion.Version
# 应输出 ≥ 10.0.19041
```

### 0.3 检查音频设备

确保机器有可用的音频输出设备（扬声器或耳机），且默认设备已设置：
- 右下角任务栏点击音量图标，确认有设备 listed
- 播放一段测试音频确认有声音

---

## 1. 安装开发环境

### 1.1 安装 Git

从 https://git-scm.com/download/win 下载安装，全部默认选项即可。

验证：
```powershell
git --version
# git version 2.4x.x
```

### 1.2 安装 Node.js (LTS)

从 https://nodejs.org/ 下载 LTS 版本（≥ 20.x），安装时勾选 "Add to PATH"。

验证：
```powershell
node --version
# v20.x.x 或更高
npm --version
# 10.x.x 或更高
```

### 1.3 安装 Microsoft Visual C++ Build Tools（Rust 在 Windows 上的链接器依赖）

从 https://visualstudio.microsoft.com/visual-cpp-build-tools/ 下载安装。

安装时勾选：
- **工作负载 → 使用 C++ 的桌面开发**

包含的必要组件：
- MSVC v143 - VS 2022 C++ x64/x86 生成工具
- Windows 11 SDK（或 Windows 10 SDK）

验证（**新开一个 PowerShell** 让 PATH 生效）：
```powershell
cl
# 应输出 "用于 x64 的 Microsoft (R) C/C++ 优化编译器版本..."
# (输入 Ctrl+C 退出)
```

### 1.4 安装 Rust 工具链

从 https://www.rust-lang.org/tools/install 下载 `rustup-init.exe` 并运行。

安装选项：
- 选 `1`（默认安装）
- 默认 host triple：`x86_64-pc-windows-msvc`
- 默认 profile：`default`（包含 rustc, cargo, rustfmt, clippy）

**安装完成后新开一个 PowerShell**，验证：
```powershell
rustc --version
# rustc 1.7x.x
cargo --version
# cargo 1.7x.x
```

### 1.5 安装 Tauri CLI（可选，用于命令行调用）

Tauri CLI 已通过 npm 集成在项目的 `devDependencies` 中，不用单独全局安装。
如果想在终端直接用 `cargo tauri`，可以安装：
```powershell
cargo install tauri-cli --version "^2.0.0"
```

---

## 2. 克隆项目代码

选一个工作目录（路径**不要包含中文或空格**，例如 `C:\dev\`）：

```powershell
cd C:\dev
git clone git@github.com:YR707/sound-place.git
cd sound-place
```

如果用 HTTPS：
```powershell
git clone https://github.com/YR707/sound-place.git
cd sound-place
```

确认当前分支（主分支 `main` 包含 Rust 版本）：
```powershell
git branch
# * main
git log --oneline -3
# 应看到 901fdea / 78864f0 / 3dcbd89 等提交
```

---

## 3. 验证依赖编译（**关键测试**）

### 3.1 先编译 Rust 后端

```powershell
cd src-tauri
cargo build
```

**预期成功输出**（最后几行）：
```
   Compiling sound-place v0.1.0 (C:\dev\sound-place\src-tauri)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in Xs
```

**如果出现 `os error 4551`**：说明该机器也启用了 SAC，回到第 0.1 步检查。
**如果出现 `error: linking failed`**：MSVC Build Tools 未正确安装，回到 1.3 重装。
**如果出现 `error: failed to run custom build`**：可能缺少 Windows SDK，回到 1.3 检查组件。

### 3.2 编译 Release 版本（生成可执行文件）

```powershell
cargo build --release
```

生成的 `.exe` 在：
```
src-tauri\target\release\sound-place.exe
```

⚠️ 注意：直接运行这个 exe 可能报错，因为它需要前端资源。完整可运行的 .exe 需要通过 `cargo tauri build` 生成（见第 6 步）。

---

## 4. 安装前端依赖并启动开发模式

### 4.1 安装 npm 包

```powershell
cd ..\ui
npm install
```

**预期**：输出一堆包安装信息，无 error。

### 4.2 启动 Tauri 开发模式（同时启动前端 dev server 和 Rust 后端）

新开一个 PowerShell，回到项目根：
```powershell
cd C:\dev\sound-place
```

**方式 A：用 npx（推荐，无需全局安装）**
```powershell
# 进入 src-tauri 目录运行, 因为 tauri.conf.json 在那里
cd src-tauri
npx tauri dev
```

**方式 B：用 cargo tauri（如果安装了全局 tauri-cli）**
```powershell
cd src-tauri
cargo tauri dev
```

**预期行为**：
1. 终端输出编译日志（首次编译会很慢，约 3-10 分钟）
2. 编译完成后自动弹出一个桌面窗口（SoundPlace 主界面）
3. 窗口应显示风险提示页 / 控制面板

**如果窗口没有弹出**：
- 检查终端是否有 error 输出
- 常见原因：前端 dev server 启动失败（检查 5173 端口是否被占用）

---

## 5. 测试音频捕获功能

### 5.1 启动应用后

1. 看到风险提示页 → 点击 `我已了解并同意`
2. 进入控制面板

### 5.2 开始捕获音频

1. 在控制面板找到 `捕获控制` 区域
2. 点击 `开始捕获` 按钮
3. **播放一段音频**（例如在浏览器播放 YouTube 视频，或打开 Spotify）
4. 观察应用界面：
   - 应该看到波形显示区域有动画
   - FFT 频谱应该有响应
   - 声音方位指示器应该有变化

### 5.3 验证日志

应用启动时终端会输出日志，确认看到：
```
[INFO  sound_place_lib::audio::capture] 使用音频设备: <你的扬声器名>
[INFO  sound_place_lib::audio::capture] 使用 mix format: 48000Hz, 2ch, 32bit
[INFO  sound_place_lib::audio::capture] 音频捕获已启动 (48000Hz, 2ch)
```

如果没有 `音频捕获已启动`，检查错误信息。

### 5.4 测试快捷键

默认全局快捷键（可在设置中修改）：
- `Ctrl+Shift+S`：开始/停止捕获
- `Ctrl+Shift+O`：显示/隐藏叠加层

### 5.5 退出

按 `Ctrl+C` 终止终端中的 `tauri dev` 进程。

---

## 6. 生成独立的 Release 可执行文件

如果开发模式测试通过，可以生成完整的 release 版本：

```powershell
cd src-tauri
cargo tauri build
```

生成的产物：
```
src-tauri\target\release\bundle\msi\sound-place_0.1.0_x64_en-US.msi    # 安装包
src-tauri\target\release\bundle\nsis\sound-place_0.1.0_x64-setup.exe    # NSIS 安装程序
```

双击 `.msi` 或 `.exe` 即可安装到任何 Windows 机器（不需要 Rust 环境）。

---

## 7. 常见问题排查

### 7.1 `error: failed to get default render device`

**原因**：机器没有可用的音频输出设备。
**解决**：插入耳机或确保扬声器已启用，在系统设置中设为默认设备。

### 7.2 应用启动但捕获无数据

**可能原因**：
- 系统静音 → 取消静音
- 默认设备不是当前播放设备 → 在系统设置中确认
- 没有进程在播放音频 → 用浏览器放视频

### 7.3 FFT 频谱全为 0

检查日志中 `mix format` 是否为 `2ch, 32bit`。如果不是，可能格式降级失败。

### 7.4 `error: linker 'link.exe' not found`

MSVC Build Tools 未安装或 PATH 未生效。重新安装（1.3 步）并**新开 PowerShell**。

### 7.5 `error: could not compile 'windows-sys'`

Windows SDK 缺失。在 Visual Studio Installer 中确认勾选了 "Windows 11 SDK" 或 "Windows 10 SDK"。

### 7.6 Tauri dev 启动后窗口白屏

可能是 Vue 前端编译错误。打开浏览器开发者工具（F12）查看控制台错误。
也检查 `ui/` 目录下是否有 TypeScript 编译错误：
```powershell
cd ui
npx vue-tsc --noEmit
```

### 7.7 编译过程中电脑突然卡顿

首次编译会占用大量 CPU 和内存（Rust + Tauri 依赖很多），建议关闭其他大型程序。如果内存不足（< 8GB），可能编译失败。

---

## 8. 回退到 Python 原型（备选方案）

如果 Rust 版本在某些机器上编译失败但想快速验证算法逻辑，可以回退到 Python 原型：

```powershell
cd C:\dev\sound-place
git checkout python-prototype
cd python-prototype
pip install -r requirements.txt
python main.py
```

Python 原型包含**两种**捕获实现：
- `soundplace/capture.py`：系统级 Loopback + pycaw session 过滤（备选方案，在所有 Win10/11 上工作）
- 调试脚本 `probe_*.py`：诊断 WASAPI API 是否可用

---

## 9. 测试完成后反馈

请记录以下信息反馈：

- [ ] 测试机 Windows 版本（`winver` 输出）
- [ ] 测试机 SAC 状态（启用/未启用）
- [ ] `cargo build` 是否成功
- [ ] `cargo tauri dev` 是否成功启动窗口
- [ ] 音频捕获是否工作（日志中 `音频捕获已启动`）
- [ ] 波形/FFT 是否有响应
- [ ] 遇到的任何错误信息

---

## 附录 A：项目结构

```
sound-place/
├── src-tauri/              # Rust 后端 + Tauri 配置
│   ├── src/
│   │   ├── audio/          # WASAPI 捕获 + 环形缓冲
│   │   ├── analysis/        # FFT/Onset/Classify/Localize 算法
│   │   ├── config/          # TOML 配置 + 游戏配置档案
│   │   └── ui/              # Tauri 命令 + 托盘
│   ├── Cargo.toml           # 依赖: wasapi 0.23, tauri 2, realfft 3
│   └── tauri.conf.json      # Tauri 应用配置
├── ui/                     # Vue3 前端
│   └── src/
│       ├── views/          # Overlay/ControlPanel 等
│       └── composables/    # useWaveRenderer/useCaptureControl 等
├── python-prototype/       # Python 原型 (备选/算法验证)
└── README.md
```

## 附录 B：关键依赖版本

| 依赖 | 版本 | 说明 |
|------|------|------|
| Rust | ≥ 1.77 | `rust-version` 字段要求 |
| Tauri | 2.x | 跨平台 GUI 框架 |
| wasapi | 0.23 | Windows Audio Session API 绑定 |
| windows-sys | 0.59 | Windows API 绑定 |
| realfft | 3.x | 实数 FFT |
| Vue | 3.5+ | 前端框架 |
| Vite | 5.4+ | 前端构建工具 |
| Node.js | ≥ 20 | npm 运行时 |

## 附录 C：Rust 与 Python 版本的差异

| 维度 | Rust 版本 | Python 版本 |
|------|-----------|-------------|
| WASAPI API | `DeviceEnumerator` + `AudioClient.initialize_client` + `Direction::Capture`（标准 loopback） | `ActivateAudioInterfaceAsync ProcessLoopback`（进程级 loopback） |
| 编译 | 需要 `cargo build`，会被 SAC 拦截 | 无需编译，JIT 运行 |
| 性能 | 高（原生代码 + SPSC 无锁队列） | 中（GIL + Lock） |
| 跨平台 | 仅 Windows | 仅 Windows |
| GUI | Tauri + Vue3 | 无（CLI） |
| 用途 | 最终发布版本 | 算法原型验证 / 调试 |

**关键**：Rust 版本用的是**系统级** WASAPI Loopback（捕获所有音频流），**不依赖** Process Loopback API。所以在 Rust 版本中不会出现 Python 调试时遇到的 `0x80070002` 问题。
