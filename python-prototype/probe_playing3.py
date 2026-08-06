"""检查 msedge 进程当前是否真的在播放音频 - 用最简单的方式.
直接用 IMMDeviceEnumerator + IAudioSessionManager2 + IAudioSessionEnumerator + IAudioMeterInformation."""
import time
import ctypes
from ctypes import (
    POINTER, byref, cast, c_long, c_uint32, c_float, c_void_p, c_uint16,
    Structure, sizeof, WINFUNCTYPE, c_ubyte
)
import comtypes
from comtypes import CoInitialize, CoUninitialize, CLSCTX_ALL, GUID
from comtypes.automation import IDispatch


# IAudioMeterInformation IID: {C9227D61-8EDD-4F20-94F8-9D0B6E0C4AA8}
IID_IAudioMeterInformation = GUID("{C9227D61-8EDD-4F20-94F8-9D0B6E0C4AA8}")
# IMMDeviceEnumerator IID: {A95664D2-9614-4F35-A746-DE8DB63617E5}
IID_IMMDeviceEnumerator = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E5}")
# IAudioSessionManager2 IID: {77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F}
IID_AudioSessionManager2 = GUID("{77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F}")
# IAudioSessionControl2 IID: {BFB7FF88-7238-49C2-BE59-1B5D8F7A5B8D}
IID_AudioSessionControl2 = GUID("{BFB7FF88-7238-49C2-BE59-1B5D8F7A5B8D}")


def main():
    CoInitialize()
    try:
        # 用 pycaw 的 AudioUtilities 获取默认扬声器设备 (高层 API)
        from pycaw.pycaw import AudioUtilities
        devices = AudioUtilities.GetSpeakers()
        immdevice = devices._dev

        # 激活 IAudioSessionManager2
        sess_mgr_ptr = immdevice.Activate(IID_AudioSessionManager2, CLSCTX_ALL, None)

        # QueryInterface 到 IAudioSessionManager2 - 用 comtypes 直接调
        # 注意: pycaw 已经定义了这个接口, comtypes 知道 vtable 布局
        from pycaw.pycaw import IAudioSessionManager2
        sessions_mgr = sess_mgr_ptr.QueryInterface(IAudioSessionManager2)

        # GetSessionEnumerator
        sess_enum = sessions_mgr.GetSessionEnumerator()
        count = sess_enum.GetCount()
        print(f"[probe] 共 {count} 个会话\n")

        # 对每个会话尝试不同方式拿 peak
        # IAudioSessionControl 是 IAudioSessionControl2 的父接口
        # comtypes 的 GetSession 返回 POINTER(IAudioSessionControl) 或 POINTER(IAudioSessionControl2)
        from pycaw.pycaw import IAudioSessionControl2

        state_names = {0: "Inactive", 1: "Active", 2: "Expired"}

        # 多次采样找稳定播放的进程
        playing_pids = set()
        for round_idx in range(3):
            print(f"--- 采样 #{round_idx + 1} ---")
            for i in range(count):
                try:
                    sess = sess_enum.GetSession(i)
                    # 强制 QueryInterface 到 IAudioSessionControl2
                    sess2 = sess.QueryInterface(IAudioSessionControl2)
                    pid = sess2.GetProcessId()
                    state = sess2.GetState()

                    # IAudioMeterInformation 从 sess2 拿 (不是从 sess)
                    try:
                        meter = sess2.QueryInterface(IID_IAudioMeterInformation)
                        # meter 是 POINTER(IUnknown), 调 vtable[3] = GetPeakValue
                        meter_ptr = ctypes.cast(meter, c_void_p).value
                        # 通过 comtypes 接口调用
                        peak = meter.GetPeakValue()
                    except Exception as e:
                        peak = -1.0

                    proc_name = ""
                    try:
                        import psutil
                        proc = psutil.Process(pid)
                        proc_name = proc.name()
                    except Exception:
                        pass

                    marker = ""
                    if peak > 0.001:
                        marker = " <<<< PLAYING"
                        playing_pids.add(pid)
                    print(f"  [{i}] pid={pid} ({proc_name}), state={state_names.get(state, '?')}, peak={peak:.4f}{marker}")
                except Exception as e:
                    print(f"  [{i}] error: {e}")
            time.sleep(0.5)
            print()

        print("=" * 60)
        if playing_pids:
            print(f"[probe] 正在播放音频的进程: {playing_pids}")
            for pid in playing_pids:
                try:
                    import psutil
                    proc = psutil.Process(pid)
                    print(f"  pid={pid} ({proc.name()})")
                except Exception:
                    print(f"  pid={pid}")
        else:
            print("[probe] ✗ 没有进程正在播放音频")
    finally:
        CoUninitialize()


if __name__ == "__main__":
    main()
