# SoundPlace Python 原型

在 SAC 拦截 Rust 编译产物的本机环境下,使用 Python 验证后端算法逻辑。
Python 解释器是签名 PE,SAC 放行;numpy/scipy wheel 由发行商签名,SAC 放行;
pycaw 是纯 Python(ctypes 调用系统 DLL),不引入新的未签名 PE。

## 目录结构

```
python-prototype/
├── README.md               # 本文件
├── requirements.txt        # 依赖清单
├── soundplace/             # 主包
│   ├── __init__.py
│   ├── capture.py          # WASAPI loopback 捕获 (pycaw)
│   ├── ring_buffer.py      # 环形缓冲 (numpy 数组 + 锁)
│   ├── fft.py              # FFT + Hann 窗 (numpy.fft)
│   ├── onset.py            # Onset 检测 (Spectral Flux + HFC)
│   ├── localize.py         # 方位估计 (ILD + GCC-PHAT ITD)
│   ├── classify.py         # 声音分类 (频谱形状规则)
│   └── worker.py           # 主分析循环 (整合上述模块)
├── tests/                  # 单元测试 (synthetic 信号)
│   ├── test_fft.py
│   ├── test_onset.py
│   ├── test_localize.py
│   └── test_classify.py
└── main.py                 # CLI 入口
```

## 算法对应关系 (与 Rust 版本一致)

| Rust 模块                          | Python 模块            | 说明                                  |
| ---------------------------------- | ---------------------- | ------------------------------------- |
| `src/audio/capture.rs`             | `soundplace/capture.py` | WASAPI loopback + PollingShared        |
| `src/audio/ring_buffer.rs`         | `soundplace/ring_buffer.py` | SPSC 环形缓冲 (threading.Lock 替代)   |
| `src/analysis/fft.rs`               | `soundplace/fft.py`     | 2048 FFT + Hann, 复数用 rustfft        |
| `src/analysis/onset.rs`             | `soundplace/onset.py`   | Spectral Flux + HFC, 自适应阈值        |
| `src/analysis/localize.rs`          | `soundplace/localize.py` | ILD + GCC-PHAT ITD 融合                |
| `src/analysis/classify.rs`          | `soundplace/classify.py` | 频谱形状规则                           |
| `src/analysis/worker.rs`            | `soundplace/worker.py`   | 消费 ring buffer → 触发 onset → 定位   |

## 使用

```powershell
pip install --user -r requirements.txt
python main.py
```

## 限制

- 无 GUI (Tauri 是 Rust 专属,Python 版本仅 CLI 输出)
- 无系统托盘
- 无快捷键
- 仅用于**算法验证**:确认 FFT/onset/方位/分类逻辑正确,等 SAC 解除后即可在 Rust 版本上跑通
