# SoundPlace

> 游戏声音方位分析学习工具 - 通过分析系统音频实时提示声音事件的左右方位

## ⚠️ 免责声明

本软件仅供**学习与个人辅助使用**，不保证不被反作弊系统封禁，用户自担风险；开发者不承担任何直接或间接责任。

- 本软件**不读取游戏内存**、**不挂钩图形 API**、**不注入游戏进程**、**不修改游戏数据**
- 仅分析系统音频输出（WASAPI loopback）
- **不支持**在 Vanguard / EAC 等严格反作弊游戏上使用（如 Valorant、CS2 排位、Apex 排位）

## 物理限制说明

立体声（左右 2 通道）物理上**无法区分前后/上下**。本软件只能提示声音的左右方位，无法告知前后。

| 信息 | 能否得到 |
|---|---|
| 水平左右角度 | ✅ 能（误差典型 ±15°） |
| 前后区分 | ❌ 不能 |
| 上下区分 | ❌ 不能 |
| 多声源分离 | ❌ 不能 |

## 当前状态

开发中 - 阶段 1（工程骨架与 PoC 验证）

详细实施计划见 [.trae/documents/sound-place-overlay-app-plan.md](.trae/documents/sound-place-overlay-app-plan.md)

## 技术栈

- **应用框架**: Tauri 2.x（绿色单 .exe，免安装）
- **后端**: Rust + WASAPI loopback + realfft
- **前端**: Vue3 + Vite + TypeScript
- **配置**: TOML profile，按游戏切换

## 开发环境要求

- Rust（stable，msvc 工具链）
- Node.js 22+
- VS Build Tools 2022（C++ 桌面开发工作负荷）
- Windows 10 1803+ 或 Windows 11

## 构建

```powershell
# 前端依赖
cd ui
npm install

# 开发模式
cd ../src-tauri
cargo tauri dev

# 发布构建（产出单 .exe）
cargo build --release
# 产物：src-tauri/target/release/sound-place.exe
```

## 运行要求（最终用户）

- Windows 10 1803+ 或 Windows 11
- WebView2 Runtime（Win11 自带，Win10 大多自带）
- 游戏需使用**无边框窗口模式**（独占全屏无法显示 overlay）

## License

MIT
