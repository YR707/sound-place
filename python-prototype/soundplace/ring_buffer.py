"""环形缓冲 (对应 src-tauri/src/audio/ring_buffer.rs).

Rust 版本用 SPSC 无锁队列; Python 用 threading.Lock 保护一个 numpy 数组.
性能要求不高 (分析线程 ~50fps), Lock 足够.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class StereoFrame:
    """单帧立体声样本 (与 Rust 版本对齐)."""
    left: float
    right: float


class RingBuffer:
    """SPSC 环形缓冲 (Python 版本用 Lock 替代无锁)."""

    def __init__(self, capacity: int = 16384) -> None:
        if capacity <= 0:
            raise ValueError(f"capacity 必须 > 0, 得到 {capacity}")
        self.capacity = capacity
        # 用两个独立数组存储左右声道, 比 list[StereoFrame] 更高效
        self._left = np.zeros(capacity, dtype=np.float32)
        self._right = np.zeros(capacity, dtype=np.float32)
        self._head = 0  # 写入位置
        self._tail = 0  # 读取位置
        self._count = 0  # 当前帧数
        self._lock = threading.Lock()

    def push_batch(self, left: np.ndarray, right: np.ndarray) -> int:
        """批量写入帧. 返回实际写入数 (满时丢弃最旧数据)."""
        n = min(len(left), len(right))
        if n == 0:
            return 0
        with self._lock:
            for i in range(n):
                self._left[self._head] = left[i]
                self._right[self._head] = right[i]
                self._head = (self._head + 1) % self.capacity
                if self._count < self.capacity:
                    self._count += 1
                else:
                    # 满了, 丢弃最旧的一帧
                    self._tail = (self._tail + 1) % self.capacity
            return n

    def pop_batch(self, max_frames: int) -> tuple[np.ndarray, np.ndarray]:
        """批量读取帧. 返回 (left, right) 数组."""
        with self._lock:
            n = min(max_frames, self._count)
            if n == 0:
                return np.zeros(0, dtype=np.float32), np.zeros(0, dtype=np.float32)

            out_left = np.empty(n, dtype=np.float32)
            out_right = np.empty(n, dtype=np.float32)
            for i in range(n):
                out_left[i] = self._left[self._tail]
                out_right[i] = self._right[self._tail]
                self._tail = (self._tail + 1) % self.capacity
            self._count -= n
            return out_left, out_right

    def available(self) -> int:
        """返回可读帧数."""
        with self._lock:
            return self._count


def create_ring_buffer(capacity: int = 16384) -> RingBuffer:
    """工厂函数, 对齐 Rust 的 create_ring_buffer."""
    return RingBuffer(capacity)
