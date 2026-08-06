"""快速测试 WASAPI Process Loopback 捕获是否工作 (5 秒后自动停止)."""
import sys
import time
import threading
import faulthandler

faulthandler.enable()

sys.path.insert(0, ".")

from soundplace.capture import CaptureThread
from soundplace.ring_buffer import create_ring_buffer
from soundplace.session import find_process_by_name


def main() -> int:
    target = find_process_by_name("msedge")
    if target is None:
        print("[test] 未找到 msedge 进程, 请先在 Edge 中播放音频")
        return 1

    print(f"[test] 目标进程: {target}", flush=True)

    ring = create_ring_buffer()
    capture = CaptureThread(
        ring,
        target_pid=target.pid,
        target_name=target.display_name,
    )

    print("[test] 启动捕获线程...", flush=True)
    capture.start()

    # 运行 8 秒 (给异步激活留足时间)
    time.sleep(8.0)

    avail = ring.available()
    print(f"[test] 8 秒后 ring buffer 可用帧数: {avail}", flush=True)

    if avail == 0:
        print("[test] ✗ 未捕获到音频数据")
        print("[test]   可能原因: Edge 没有正在播放音频, 或权限不足")
    else:
        print(f"[test] ✓ 成功捕获 {avail} 帧音频数据")
        left, right = ring.pop_batch(min(avail, 1024))
        print(f"[test]   左声道: min={left.min():.4f}, max={left.max():.4f}, rms={float((left**2).mean()**0.5):.4f}")
        print(f"[test]   右声道: min={right.min():.4f}, max={right.max():.4f}, rms={float((right**2).mean()**0.5):.4f}")

    capture.stop()
    print("[test] 完成", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
