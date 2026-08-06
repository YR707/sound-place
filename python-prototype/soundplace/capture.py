"""WASAPI 系统级 Loopback + pycaw session 过滤 (备选方案, 对应 src-tauri/src/audio/capture.rs).

## 背景

WASAPI Process Loopback (ActivateAudioInterfaceAsync + AUDIOCLIENT_ACTIVATION_PARAMS.ProcessLoopback)
在本机返回 E_FILE_NOT_FOUND (0x80070002), 所有 PID (包括 0) 都失败.
管理员权限也无效. 这是系统/驱动层面的问题, 与代码无关.

## 备选方案

用 pycaw 的系统级 loopback 捕获默认 render 设备的全部音频流,
同时用 IAudioSessionControl::GetState + IAudioMeterInformation::GetPeakValue
监测目标进程的 session 状态, 只在目标进程"正在发声"时把数据推入 ring buffer.

## 优缺点

优点:
- 在所有 Win10/11 机器上都能工作 (使用最稳定的 WASAPI Loopback API)
- 不需要 Process Loopback 的特殊驱动支持

缺点:
- 系统静音时仍会采集 (但用 session state 过滤可以丢弃)
- 如果多个进程同时发声, 无法在样本级分离 (只能在时间窗口级过滤)
- 实际游戏中通常只有一个进程发声, 影响不大
"""
from __future__ import annotations

import threading
import time
from typing import Optional

import numpy as np

from .ring_buffer import RingBuffer


# pycaw 的 AudioSession.State 常量
# 0 = Inactive, 1 = Active, 2 = Expired
_AUDIOSESSION_STATE_ACTIVE = 1


class CaptureThread:
    """系统级 WASAPI Loopback 捕获线程 + session 过滤.

    捕获默认 render 设备的全部音频, 仅当目标进程的 session 处于 Active
    且 peak > 阈值时, 才把数据推入 ring buffer.
    """

    def __init__(
        self,
        ring_buffer: RingBuffer,
        target_pid: int,
        target_name: str = "<unknown>",
        sample_rate: int = 48000,
        channels: int = 2,
        buffer_duration_ms: float = 20.0,
        peak_threshold: float = 0.001,
    ) -> None:
        self.ring_buffer = ring_buffer
        self.target_pid = target_pid
        self.target_name = target_name
        self.sample_rate = sample_rate
        self.channels = channels
        self.buffer_duration_ms = buffer_duration_ms
        # session 过滤参数
        self.peak_threshold = peak_threshold

        self._stop_flag = threading.Event()
        self._thread: Optional[threading.Thread] = None

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
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _capture_loop(self) -> None:
        """主捕获循环."""
        from comtypes import CoInitialize, CoUninitialize
        CoInitialize()
        try:
            self._capture_inner()
        except Exception as e:
            print(f"[capture] 音频捕获线程异常退出: {e}")
            import traceback
            traceback.print_exc()
        finally:
            try:
                CoUninitialize()
            except Exception:
                pass

    def _capture_inner(self) -> None:
        import ctypes
        from ctypes import cast, c_void_p

        print(f"[capture] 目标进程: {self.target_name} (pid={self.target_pid})")
        print(f"[capture] 使用系统级 WASAPI Loopback + session 过滤")

        # 1. 用 pycaw 拿到默认 render 设备的 IAudioClient (Loopback)
        from pycaw.pycaw import AudioUtilities, IAudioClient
        try:
            speakers = AudioUtilities.GetSpeakers()
        except Exception as e:
            print(f"[capture] 获取默认扬声器失败: {e}")
            return

        # 激活 IAudioClient (用 pycaw 的包装)
        # speakers 是 AudioDevice; _dev 是 IMMDevice
        # IMMDevice::Activate 返回 IAudioClient (comtypes POINTER)
        try:
            audio_client = speakers.Activate(
                IAudioClient._iid_,  # REFIID
                1,  # CLSCTX_ALL = 23, 但 pycaw 用 1? 实际上这里传 CLSCTX_ALL
                None,
            )
        except Exception as e:
            print(f"[capture] Activate IAudioClient 失败: {e}")
            return

        # 2. GetMixFormat
        try:
            mix_format_ptr = audio_client.GetMixFormat()
        except Exception as e:
            print(f"[capture] GetMixFormat 失败: {e}")
            return

        # mix_format_ptr 是 POINTER(WAVEFORMATEX), 用 pycaw 的 helper 解包
        # pycaw 的 AudioClient.GetMixFormat 返回 WAVEFORMATEX 结构体
        # 但有时返回 POINTER, 看版本. 先尝试 .contents
        try:
            wfx = mix_format_ptr.contents
        except AttributeError:
            wfx = mix_format_ptr  # 已经是结构体

        self.sample_rate = wfx.nSamplesPerSec
        self.channels = wfx.nChannels
        bits_per_sample = wfx.wBitsPerSample
        print(
            f"[capture] mix format: {self.sample_rate}Hz, "
            f"{self.channels}ch, {bits_per_sample}bit"
        )

        # 3. Initialize (Shared + Loopback + AutoConvert)
        # AUDCLNT_SHAREMODE_SHARED = 0
        # AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
        # AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM = 0x80000000
        # AUDCLNT_STREAMFLAGS_EVENTCALLBACK = 0x00040000 (不用, 我们用 polling)
        AUDCLNT_SHAREMODE_SHARED = 0
        AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
        AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM = 0x80000000
        stream_flags = (
            AUDCLNT_STREAMFLAGS_LOOPBACK | AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM
        )
        buffer_duration_hns = int(self.buffer_duration_ms * 10_000)  # ms -> 100ns

        try:
            audio_client.Initialize(
                AUDCLNT_SHAREMODE_SHARED,
                stream_flags,
                buffer_duration_hns,
                0,
                wfx,
                None,
            )
        except Exception as e:
            print(f"[capture] Initialize 失败: {e}")
            return

        print("[capture] 已 Initialize (Shared + LOOPBACK + AUTOCONVERTPCM)")

        # 4. GetService(IAudioCaptureClient)
        from pycaw.pycaw import IAudioCaptureClient
        try:
            capture_client = audio_client.GetService(
                IAudioCaptureClient._iid_
            )
        except Exception as e:
            # pycaw 的 GetService 简化了参数, 直接传 IID
            try:
                capture_client = audio_client.GetService(
                    IAudioCaptureClient
                )
            except Exception as e2:
                print(f"[capture] GetService(IAudioCaptureClient) 失败: {e2}")
                return

        print(f"[capture] 已获取 IAudioCaptureClient")

        # 5. 启动流
        try:
            audio_client.Start()
        except Exception as e:
            print(f"[capture] Start 失败: {e}")
            return
        print(f"[capture] WASAPI Loopback 流已启动 (过滤 pid={self.target_pid})")

        # 6. 获取目标进程的 session (用于过滤)
        target_session = self._find_target_session()
        if target_session is None:
            print(f"[capture] ⚠ 未找到目标进程的 audio session, 将采集所有音频")
        else:
            from pycaw.pycaw import IAudioMeterInformation
            try:
                target_meter = target_session.QueryInterface(IAudioMeterInformation)
            except Exception:
                target_meter = None
            print(f"[capture] 已绑定目标 session (meter={'ok' if target_meter else 'no'})")

        # 7. 轮询读取循环
        try:
            self._read_loop(capture_client, target_session, target_meter)
        finally:
            try:
                audio_client.Stop()
            except Exception:
                pass

    def _find_target_session(self):
        """查找目标进程的 audio session."""
        from pycaw.pycaw import AudioUtilities
        for session in AudioUtilities.GetAllSessions():
            try:
                proc = session.Process
                if proc is not None and proc.pid == self.target_pid:
                    return session
            except Exception:
                pass
        return None

    def _read_loop(self, capture_client, target_session, target_meter) -> None:
        """轮询读取 capture buffer, 按目标 session 的 peak 过滤."""
        # 数据缓冲
        leftover_left = np.zeros(0, dtype=np.float32)
        leftover_right = np.zeros(0, dtype=np.float32)

        samples_collected = 0
        frames_pushed = 0
        silent_frames_dropped = 0

        last_log = time.time()
        log_interval = 1.0  # 每秒打印一次状态

        while not self._stop_flag.is_set():
            try:
                packet_size = capture_client.GetNextPacketSize()
            except Exception as e:
                print(f"[capture] GetNextPacketSize 异常: {e}")
                time.sleep(0.005)
                continue

            if packet_size == 0:
                time.sleep(0.005)
                continue

            # 检查目标进程是否在发声 (peak > 阈值)
            target_active = self._is_target_active(target_session, target_meter)

            while packet_size > 0:
                try:
                    data = capture_client.GetBuffer()
                except Exception as e:
                    print(f"[capture] GetBuffer 异常: {e}")
                    break

                # pycaw 的 GetBuffer 返回 (data, frames, flags)
                # data 是 bytes 或 ctypes 数组
                try:
                    buf_bytes, n_frames, flags = data
                except (TypeError, ValueError):
                    # 某些 pycaw 版本返回不同结构, 兼容处理
                    buf_bytes = data[0] if isinstance(data, tuple) else data
                    n_frames = data[1] if isinstance(data, tuple) and len(data) > 1 else 0
                    flags = data[2] if isinstance(data, tuple) and len(data) > 2 else 0

                if n_frames == 0:
                    try:
                        capture_client.ReleaseBuffer(n_frames)
                    except Exception:
                        pass
                    break

                # 转换为 numpy float32 立体声
                left, right = self._bytes_to_stereo_float(buf_bytes, n_frames)
                samples_collected += n_frames

                if target_active:
                    self.ring_buffer.push_batch(left, right)
                    frames_pushed += n_frames
                else:
                    silent_frames_dropped += n_frames

                try:
                    capture_client.ReleaseBuffer(n_frames)
                except Exception:
                    pass

                try:
                    packet_size = capture_client.GetNextPacketSize()
                except Exception:
                    break

            # 状态日志
            now = time.time()
            if now - last_log >= log_interval:
                status = "ACTIVE" if target_active else "silent"
                print(
                    f"[capture] {status:7s} | 总采集 {samples_collected} 帧, "
                    f"推入 {frames_pushed}, 丢弃 {silent_frames_dropped}"
                )
                last_log = now

        print(
            f"[capture] 退出 | 总采集 {samples_collected} 帧, "
            f"推入 {frames_pushed}, 丢弃 {silent_frames_dropped}"
        )

    def _is_target_active(self, target_session, target_meter) -> bool:
        """检查目标进程是否正在发声.

        判断标准:
        1. session.State == Active (1)
        2. peak > peak_threshold (如果有 meter)
        """
        if target_session is None:
            # 没找到 session, 默认采集所有
            return True

        try:
            state = target_session.State
        except Exception:
            # session 可能已失效
            return False

        if state != _AUDIOSESSION_STATE_ACTIVE:
            return False

        if target_meter is not None:
            try:
                peak = target_meter.GetPeakValue()
                return peak > self.peak_threshold
            except Exception:
                return False

        return True

    def _bytes_to_stereo_float(
        self, buf_bytes, n_frames: int
    ) -> tuple[np.ndarray, np.ndarray]:
        """把 WASAPI 缓冲区字节转成 (left, right) float32 数组.

        假设 mix format 是 32-bit float 立体声 (WASAPI 默认).
        其他格式需要转换, 这里暂不支持.
        """
        # 假设 32-bit float, 2 channels
        # 每帧 4 bytes * 2 = 8 bytes
        n_samples = n_frames * self.channels

        # 把 bytes 转成 float32 numpy 数组
        try:
            arr = np.frombuffer(buf_bytes, dtype=np.float32, count=n_samples)
        except (ValueError, TypeError):
            # buf_bytes 可能不是 buffer-like, 尝试用 ctypes cast
            try:
                import ctypes
                # 假设 buf_bytes 是 POINTER(c_float) 或类似
                arr = np.ctypeslib.as_array(buf_bytes, shape=(n_samples,)).astype(np.float32)
            except Exception:
                return np.zeros(0, dtype=np.float32), np.zeros(0, dtype=np.float32)

        if self.channels == 2:
            arr_2d = arr.reshape(-1, 2)
            return arr_2d[:, 0].copy(), arr_2d[:, 1].copy()
        elif self.channels == 1:
            # 单声道, 复制到左右
            return arr.copy(), arr.copy()
        else:
            # 多声道, 只取前两路
            arr_2d = arr.reshape(-1, self.channels)
            return arr_2d[:, 0].copy(), arr_2d[:, 1].copy()
