"""检查哪些进程当前真的在播放音频 (用 IAudioMeterInformation 看峰值)."""
from comtypes import CoInitialize, CoUninitialize
from pycaw.pycaw import AudioUtilities, IAudioMeterInformation


def main():
    CoInitialize()
    try:
        # 用 pycaw 的高层 API: GetAllSessions 返回 AudioSession 列表
        sessions = AudioUtilities.GetAllSessions()
        print(f"[probe] 共 {len(sessions)} 个会话")

        # 状态常量
        state_names = {0: "Inactive", 1: "Active", 2: "Expired"}

        active_pids = []
        for i, sess in enumerate(sessions):
            try:
                pid = sess.ProcessId
                proc_name = ""
                try:
                    import psutil
                    proc = psutil.Process(pid)
                    proc_name = proc.name()
                except Exception:
                    pass

                state = sess.State
                state_name = state_names.get(state, f"Unknown({state})")

                # 获取音量峰值
                peak = -1.0
                try:
                    meter = sess.QueryInterface(IAudioMeterInformation)
                    peak = meter.GetPeakValue()
                except Exception:
                    pass

                marker = ""
                if state == 1 and peak > 0.001:
                    marker = " <<<< ACTIVE PLAYING"
                    active_pids.append((pid, proc_name, peak))
                print(f"  [{i}] pid={pid} ({proc_name}), state={state_name}, peak={peak:.4f}{marker}")
            except Exception as e:
                print(f"  [{i}] error: {e}")

        print()
        if active_pids:
            print(f"[probe] 当前正在播放音频的进程: {len(active_pids)} 个")
            for pid, name, peak in active_pids:
                print(f"  pid={pid} ({name}), peak={peak:.4f}")
        else:
            print("[probe] ✗ 没有进程正在播放音频")

    finally:
        CoUninitialize()


if __name__ == "__main__":
    main()
