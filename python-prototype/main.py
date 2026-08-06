"""SoundPlace Python 原型入口.

用法:
    python main.py
    python main.py --fft-size 4096
    python main.py --no-capture  # 跑离线测试 (synthetic 信号)
    python main.py --device 10   # 指定 sounddevice 设备索引
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from typing import Optional

import numpy as np

from soundplace.capture import CaptureThread
from soundplace.ring_buffer import create_ring_buffer
from soundplace.worker import AnalysisWorker


def run_offline_test(fft_size: int = 2048) -> int:
    """离线测试: 用合成信号验证算法."""
    print("=" * 60)
    print("SoundPlace 离线算法验证 (无需音频设备)")
    print("=" * 60)

    from soundplace.fft import FftAnalyzer
    from soundplace.localize import Localizer
    from soundplace.onset import OnsetDetector
    from soundplace.classify import Classifier, SoundType

    sr = 48000

    # --- 1. FFT 测试: 正弦波 ---
    print("\n[1/4] FFT: 1kHz 正弦波检测")
    analyzer = FftAnalyzer(fft_size)
    t = np.arange(fft_size) / sr
    sine = np.sin(2 * np.pi * 1000.0 * t).astype(np.float32)
    spectrum = analyzer.analyze_single(sine)
    peak_bin = int(np.argmax(spectrum))
    peak_hz = analyzer.bin_to_hz(peak_bin, sr)
    ok = abs(peak_hz - 1000.0) < 50.0
    print(f"    峰值 bin={peak_bin}, 频率={peak_hz:.1f}Hz, "
          f"{'✓ PASS' if ok else '✗ FAIL'} (期望 1000Hz ± 50Hz)")

    # --- 2. Onset 测试 ---
    print("\n[2/4] Onset: 静音→能量爆发")
    detector = OnsetDetector()
    silence_spec = np.zeros(fft_size // 2 + 1, dtype=np.float32)
    for _ in range(20):
        detector.detect(silence_spec)
    loud_t = np.arange(fft_size) / sr
    loud_signal = (np.sin(2 * np.pi * 200.0 * loud_t) * 10.0).astype(np.float32)
    loud_spec = analyzer.analyze_single(loud_signal)
    event = detector.detect(loud_spec)
    ok = event is not None
    print(f"    触发 onset: {'✓ PASS' if ok else '✗ FAIL'} "
          f"(intensity={event.intensity:.2f})" if event else "    未触发")

    # --- 3. 方位估计: 居中 ---
    print("\n[3/4] Localize: 三种场景")
    localizer = Localizer(fft_size)
    # (a) 左右相同 → 0°
    sine_both = np.sin(2 * np.pi * 1000.0 * t).astype(np.float32)
    angle_center = localizer.localize(sine_both, sine_both)
    ok_a = abs(angle_center) < 15.0
    print(f"    (a) 左右相同 → {angle_center:+.1f}° "
          f"{'✓ PASS' if ok_a else '✗ FAIL'} (期望 |angle| < 15°)")

    # (b) 左大右零 → 负角度 (偏左)
    left_only = sine_both.copy()
    right_zero = np.zeros(fft_size, dtype=np.float32)
    angle_left = localizer.localize(left_only, right_zero)
    ok_b = angle_left < -10.0
    print(f"    (b) 左声道 → {angle_left:+.1f}° "
          f"{'✓ PASS' if ok_b else '✗ FAIL'} (期望 < -10°)")

    # (c) 右大左零 → 正角度 (偏右)
    angle_right = localizer.localize(right_zero, left_only)
    ok_c = angle_right > 10.0
    print(f"    (c) 右声道 → {angle_right:+.1f}° "
          f"{'✓ PASS' if ok_c else '✗ FAIL'} (期望 > 10°)")

    # --- 4. 分类测试 ---
    print("\n[4/4] Classify: 脚步/枪声")
    classifier = Classifier(sr, fft_size)
    bin_hz = sr / fft_size

    # 脚步: 200Hz 主导
    spec_footstep = np.zeros(fft_size // 2 + 1, dtype=np.float32)
    bin_200 = int(round(200.0 / bin_hz))
    for i in range(max(0, bin_200 - 2), min(len(spec_footstep), bin_200 + 3)):
        spec_footstep[i] = 10.0
    type_footstep = classifier.classify(spec_footstep, 0, 100)
    ok_d = type_footstep == SoundType.FOOTSTEP
    print(f"    (a) 200Hz 主导 → {type_footstep.value:8s} "
          f"{'✓ PASS' if ok_d else '✗ FAIL'} (期望 footstep)")

    # 枪声: 5kHz 主导
    spec_gunshot = np.zeros(fft_size // 2 + 1, dtype=np.float32)
    bin_5k = int(round(5000.0 / bin_hz))
    for i in range(max(0, bin_5k - 2), min(len(spec_gunshot), bin_5k + 3)):
        spec_gunshot[i] = 10.0
    type_gunshot = classifier.classify(spec_gunshot, 0, 50)
    ok_e = type_gunshot == SoundType.GUNSHOT
    print(f"    (b) 5kHz 主导 → {type_gunshot.value:8s} "
          f"{'✓ PASS' if ok_e else '✗ FAIL'} (期望 gunshot)")

    # 汇总
    all_pass = all([ok, ok_a, ok_b, ok_c, ok_d, ok_e]) and event is not None
    print("\n" + "=" * 60)
    print(f"结果: {'全部 ✓ PASS' if all_pass else '存在 ✗ FAIL'}")
    print("=" * 60)
    return 0 if all_pass else 1


def run_live(fft_size: int = 2048, device: Optional[int] = None) -> int:
    """实时捕获 + 分析."""
    print("=" * 60)
    print("SoundPlace 实时模式 (立体声混音 / loopback)")
    print("=" * 60)
    print("按 Ctrl+C 停止")
    print()

    ring = create_ring_buffer()
    capture = CaptureThread(
        ring, sample_rate=48000, channels=2, device=device
    )

    # 先启动捕获, 等待实际采样率确定后再启动分析
    capture.start()
    # 给捕获线程一点时间初始化设备并设置 self.sample_rate
    time.sleep(2.0)

    actual_sr = capture.sample_rate
    actual_ch = capture.channels
    print(f"[main] 实际采样率: {actual_sr}Hz, 通道: {actual_ch}")

    worker = AnalysisWorker(
        ring, fft_size=fft_size, sample_rate=actual_sr
    )
    worker.start()

    # 等待 Ctrl+C
    try:
        while True:
            time.sleep(1.0)
            avail = ring.available()
            print(f"[stats] ring buffer: {avail} frames", flush=True)
    except KeyboardInterrupt:
        print("\n停止中...")
    finally:
        worker.stop()
        capture.stop()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SoundPlace Python 原型 - 算法验证 + 实时捕获"
    )
    parser.add_argument(
        "--fft-size", type=int, default=2048,
        help="FFT size (默认 2048)"
    )
    parser.add_argument(
        "--no-capture", action="store_true",
        help="不启动 WASAPI 捕获, 只跑离线合成信号测试"
    )
    parser.add_argument(
        "--device", type=int, default=None,
        help="指定 sounddevice 设备索引 (默认自动查找立体声混音)"
    )
    args = parser.parse_args()

    if args.no_capture:
        return run_offline_test(args.fft_size)
    return run_live(args.fft_size, args.device)


if __name__ == "__main__":
    sys.exit(main())
