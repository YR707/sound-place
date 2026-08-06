"""WASAPI loopback 捕获 (对应 src-tauri/src/audio/capture.rs).

使用 sounddevice 库 (基于 PortAudio, 已签名的 wheel).
sounddevice 0.5.5 + numpy 2.x 已安装.

设计:
- 使用 sounddevice.InputStream 配置 callback 直接捕获
- Windows 上 PortAudio 后端会自动用 WASAPI
- 自动查找 "立体声混音" (Stereo Mix) 设备作为 loopback 源
  如果没有立体声混音, 退而求其次用默认输入 (麦克风)

真正的 WASAPI loopback 在 Rust 版本中实现 (src-tauri/src/audio/capture.rs).
Python 原型主要验证算法逻辑.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import numpy as np
import sounddevice as sd

from .ring_buffer import RingBuffer


class CaptureThread:
    """音频捕获线程 (用 sounddevice).

    使用 InputStream + callback, 在后台线程拉取音频帧.
    支持指定设备索引 (用于选择立体声混音等 loopback 设备).
    """

    def __init__(
        self,
        ring_buffer: RingBuffer,
        sample_rate: int = 48000,
        channels: int = 2,
        blocksize: int = 1024,
        device: Optional[int] = None,
    ) -> None:
        self.ring_buffer = ring_buffer
        self.sample_rate = sample_rate
        self.channels = channels
        self.blocksize = blocksize
        self.device = device  # None = 自动选择; 整数 = 设备索引

        self._stop_flag = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._stream: Optional[sd.InputStream] = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("捕获线程已在运行")
        self._stop_flag.clear()
        self._thread = threading.Thread(
            target=self._capture_loop,
            name="soundplace-audio-capture",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_flag.set()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _capture_loop(self) -> None:
        try:
            self._capture_inner()
        except Exception as e:
            print(f"[capture] 音频捕获线程异常退出: {e}")
            import traceback
            traceback.print_exc()

    def _capture_inner(self) -> None:
        # 自动查找合适的输入设备:
        # 优先级:
        # 1. MME hostapi 下的 "立体声混音" (兼容性最好)
        # 2. Windows DirectSound 下的 "立体声混音"
        # 3. Windows WASAPI 下的 "立体声混音"
        # 4. Windows WDM-KS 下的 "立体声混音" (PortAudio 兼容性差, 最后选)
        # 5. 退而求其次: 默认输入设备 (麦克风)
        chosen_device = self.device

        hostapis = sd.query_hostapis()
        # hostapi 优先级 (名字 → 优先级, 越小越优先)
        hostapi_priority = {
            'MME': 1,
            'Windows DirectSound': 2,
            'Windows WASAPI': 3,
            'Windows WDM-KS': 4,
        }

        if chosen_device is None:
            # 在所有 hostapi 中找立体声混音, 按优先级排序
            candidates = []
            for hidx, h in enumerate(hostapis):
                priority = hostapi_priority.get(h['name'], 99)
                for dev_idx in h['devices']:
                    dev = sd.query_devices(dev_idx)
                    name_lower = dev['name'].lower()
                    if (dev['max_input_channels'] >= 2
                        and ('stereo mix' in name_lower
                             or '立体声混音' in dev['name']
                             or 'loopback' in name_lower)):
                        candidates.append((priority, hidx, dev_idx, dev['name'], h['name']))
                        break  # 每个 hostapi 只取第一个

            if candidates:
                # 按优先级排序, 取第一个
                candidates.sort(key=lambda x: x[0])
                _, hidx, dev_idx, dev_name, hostapi_name = candidates[0]
                chosen_device = dev_idx
                print(f"[capture] 自动找到 loopback 设备: idx={dev_idx} "
                      f"({dev_name}, hostapi={hostapi_name})")

        if chosen_device is None:
            # 退而求其次: 默认输入
            chosen_device = sd.default.device[0]
            if chosen_device is not None and chosen_device >= 0:
                dev_info = sd.query_devices(chosen_device)
                print(f"[capture] 使用默认输入设备: idx={chosen_device} ({dev_info['name']})")
            else:
                print("[capture] 未找到任何输入设备 (包括立体声混音)")
                print("[capture] 提示: 在声音控制面板启用 '立体声混音' 作为录制设备")
                while not self._stop_flag.is_set():
                    time.sleep(0.1)
                return
        else:
            dev_info = sd.query_devices(chosen_device)
            print(f"[capture] 使用设备: idx={chosen_device} ({dev_info['name']})")
            print(f"[capture] 默认采样率: {dev_info['default_samplerate']}Hz")
            print(f"[capture] 最大输入通道: {dev_info['max_input_channels']}")

        # 用设备的默认采样率 (避免不支持的采样率导致失败)
        if 'default_samplerate' in dev_info:
            self.sample_rate = int(dev_info['default_samplerate'])

        # 检查通道数
        channels = min(self.channels, dev_info['max_input_channels'])
        if channels < 2:
            print(f"[capture] 警告: 设备只有 {channels} 个输入通道, 无法做立体声定位")
        self.channels = channels

        # 用 callback 模式启动 InputStream
        # callback 签名: (indata: np.ndarray, frames: int, time_info, status)
        def callback(indata: np.ndarray, frames: int, time_info, status) -> None:
            if status:
                if status.input_overflow:
                    print("[capture] 输入溢出")
                return
            # indata shape: (frames, channels), dtype float32
            if self.channels >= 2:
                left = indata[:, 0].copy()
                right = indata[:, 1].copy()
            else:
                left = indata[:, 0].copy()
                right = left.copy()
            self.ring_buffer.push_batch(left, right)

        try:
            # 在 InputStream 中用 (hostapi, device_within_hostapi) 元组指定设备
            # 因为不同 hostapi 的设备索引空间是独立的
            hostapi_idx = dev_info['hostapi']
            hostapi_dev_list = hostapis[hostapi_idx]['devices']
            # 在该 hostapi 的设备列表里找 chosen_device 的位置
            try:
                dev_within_hostapi = hostapi_dev_list.index(chosen_device)
                device_param: tuple[int, int] | int = (hostapi_idx, dev_within_hostapi)
                print(f"[capture] 设备参数: hostapi={hostapi_idx}, "
                      f"dev_in_hostapi={dev_within_hostapi}")
            except ValueError:
                device_param = chosen_device

            # 多次尝试不同的通道数 (WDM-KS 报告的 max_input_channels 可能不准)
            actual_channels = dev_info['max_input_channels']
            channels_to_try = [actual_channels, 1, 2]
            # 去重
            seen = set()
            channels_to_try = [c for c in channels_to_try if not (c in seen or seen.add(c))]

            self._stream = None
            for try_ch in channels_to_try:
                try:
                    print(f"[capture] 尝试 channels={try_ch}")
                    self._stream = sd.InputStream(
                        samplerate=self.sample_rate,
                        blocksize=self.blocksize,
                        channels=try_ch,
                        dtype='float32',
                        callback=callback,
                        device=device_param,
                    )
                    self._stream.start()
                    self.channels = try_ch
                    print(f"[capture] InputStream 已启动: {self.sample_rate}Hz, {self.channels}ch")
                    break
                except sd.PortAudioError as e:
                    print(f"[capture] channels={try_ch} 失败: {e}")
                    self._stream = None
                    continue

            if self._stream is None:
                raise RuntimeError("所有通道数尝试均失败")

            # 等待停止信号
            while not self._stop_flag.is_set():
                time.sleep(0.1)

        except sd.PortAudioError as e:
            print(f"[capture] PortAudio 错误: {e}")
        except Exception as e:
            print(f"[capture] 流启动失败: {e}")
        finally:
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
            print("[capture] 捕获线程退出")
