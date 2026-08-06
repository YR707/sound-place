"""探测: 列出所有进程及其音频会话状态, 找出真正正在播放音频的进程.
用 pycaw 的 IAudioMeterInformation (峰值 > 0 表示当前有声音)."""
import time
from comtypes import CoInitialize, CoUninitialize
from pycaw.pycaw import AudioUtilities, IAudioMeterInformation


def main():
    CoInitialize()
    try:
        # 多次采样峰值, 确认进程真的在播放音频 (而不是瞬时静音)
        print("[probe] 第一次采样...")
        sessions1 = AudioUtilities.GetAllSessions()
        peaks1 = {}
        info1 = []
        for i, sess in enumerate(sessions1):
            try:
                pid = sess.ProcessId
                proc_name = ""
                try:
                    import psutil
                    proc = psutil.Process(pid)
                    proc_name = proc.name()
                except Exception:
                    pass

                state = sess.State  # 0=Inactive, 1=Active, 2=Expired
                peak = -1.0
                try:
                    meter = sess.QueryInterface(IAudioMeterInformation)
                    peak = meter.GetPeakValue()
                except Exception:
                    pass
                peaks1[pid] = peak
                info1.append((pid, proc_name, state, peak))
            except Exception as e:
                pass

        print("[probe] 等待 1 秒, 再次采样...")
        time.sleep(1.0)

        print("[probe] 第二次采样...")
        sessions2 = AudioUtilities.GetAllSessions()
        peaks2 = {}
        for sess in sessions2:
            try:
                pid = sess.ProcessId
                peak = -1.0
                try:
                    meter = sess.QueryInterface(IAudioMeterInformation)
                    peak = meter.GetPeakValue()
                except Exception:
                    pass
                peaks2[pid] = peak
            except Exception:
                pass

        state_names = {0: "Inactive", 1: "Active", 2: "Expired"}
        print(f"\n[probe] {'pid':<8} {'name':<30} {'state':<10} {'peak1':<10} {'peak2':<10} {'playing?'}")
        print("-" * 90)
        for pid, name, state, peak1 in info1:
            peak2 = peaks2.get(pid, -1.0)
            playing = "YES <<<<" if (peak1 > 0.001 or peak2 > 0.001) else "no"
            print(f"  {pid:<8} {name[:30]:<30} {state_names.get(state, '?'):<10} {peak1:<10.4f} {peak2:<10.4f} {playing}")

        # 找出真正在播放的进程
        playing_pids = [pid for pid, p1 in peaks1.items()
                        if (p1 > 0.001 or peaks2.get(pid, 0) > 0.001)]
        print()
        if playing_pids:
            print(f"[probe] 正在播放音频的进程: {playing_pids}")
        else:
            print("[probe] ✗ 没有进程正在播放音频")
            print()
            print("请在 Edge 中播放一段视频/音乐, 然后重新运行此脚本")
    finally:
        CoUninitialize()


if __name__ == "__main__":
    main()
