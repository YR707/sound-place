"""直接通过 IAudioSessionEnumerator 列出所有音频会话, 找到正在发声的进程."""
import time
from ctypes import POINTER, byref
from comtypes import CoInitialize, CoUninitialize, CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioSessionManager2, IAudioMeterInformation


def main():
    CoInitialize()
    try:
        devices = AudioUtilities.GetSpeakers()
        immdevice = devices._dev
        sess_mgr_ptr = immdevice.Activate(
            IAudioSessionManager2._iid_, CLSCTX_ALL, None
        )
        sessions_mgr = sess_mgr_ptr.QueryInterface(IAudioSessionManager2)
        sess_enum = sessions_mgr.GetSessionEnumerator()
        count = sess_enum.GetCount()
        print(f"[probe] 共 {count} 个会话\n")

        state_names = {0: "Inactive", 1: "Active", 2: "Expired"}

        # 第一次采样
        samples1 = []
        for i in range(count):
            sess = sess_enum.GetSession(i)
            try:
                # sess 是 IAudioSessionControl (comtypes POINTER)
                # 用 QueryInterface 拿到 IAudioSessionControl2
                from comtypes import IID
                # IAudioSessionControl2 IID: {bfb7ff88-7238-49c2-be59-1b5d8f7a5b8d}
                IID_AudioSessionControl2 = IID("{BFB7FF88-7238-49C2-BE59-1B5D8F7A5B8D}")
                sess2 = sess.QueryInterface(IID_AudioSessionControl2)

                # 直接用 ctypes 调 GetProcessId (vtable 索引 3)
                import ctypes
                from ctypes import c_void_p, c_uint32, WINFUNCTYPE, cast, c_long
                sess2_ptr = cast(sess2, c_void_p).value
                vtable_ptr = ctypes.cast(sess2_ptr, POINTER(c_void_p))[0]
                # vtable[3] = GetProcessId (IAudioSessionControl2)
                GET_PID = WINFUNCTYPE(c_long, c_void_p, POINTER(c_uint32))
                get_pid = GET_PID(vtable_ptr + 3 * ctypes.sizeof(c_void_p))
                pid_val = c_uint32(0)
                hr = get_pid(sess2_ptr, byref(pid_val))
                if hr != 0:
                    print(f"  [{i}] GetProcessId 失败 hr=0x{hr & 0xFFFFFFFF:08X}")
                    continue
                pid = pid_val.value

                # vtable[4] = IsSystemSoundsSession (返回 BOOL)
                # vtable[5] = SetDuckingPreferences (返回 HRESULT)
                # 直接用 IAudioMeterInformation
                peak = -1.0
                try:
                    meter = sess2.QueryInterface(IAudioMeterInformation)
                    peak = meter.GetPeakValue()
                except Exception as e:
                    peak = -2.0  # QueryInterface 失败

                proc_name = ""
                try:
                    import psutil
                    proc = psutil.Process(pid)
                    proc_name = proc.name()
                except Exception:
                    pass

                # 状态 - IAudioSessionControl::GetState (vtable 索引 4)
                GET_STATE = WINFUNCTYPE(c_long, c_void_p, POINTER(c_uint32))
                get_state = GET_STATE(vtable_ptr + 4 * ctypes.sizeof(c_void_p))
                state_val = c_uint32(0)
                hr = get_state(sess2_ptr, byref(state_val))
                state = state_val.value if hr == 0 else -1

                samples1.append((pid, proc_name, state, peak))
                state_str = state_names.get(state, '?')
                print(f"  [{i}] pid={pid} ({proc_name}), state={state_str}({state}), peak={peak:.4f}")
            except Exception as e:
                print(f"  [{i}] error: {e}")

        print("\n[probe] 等待 1.5 秒再采样...")
        time.sleep(1.5)

        # 第二次采样
        print("\n[probe] 第二次采样:")
        playing_pids = []
        for i in range(count):
            sess = sess_enum.GetSession(i)
            try:
                from comtypes import IID
                IID_AudioSessionControl2 = IID("{BFB7FF88-7238-49C2-BE59-1B5D8F7A5B8D}")
                sess2 = sess.QueryInterface(IID_AudioSessionControl2)

                import ctypes
                from ctypes import c_void_p, c_uint32, WINFUNCTYPE, cast, c_long
                sess2_ptr = cast(sess2, c_void_p).value
                vtable_ptr = ctypes.cast(sess2_ptr, POINTER(c_void_p))[0]
                GET_PID = WINFUNCTYPE(c_long, c_void_p, POINTER(c_uint32))
                get_pid = GET_PID(vtable_ptr + 3 * ctypes.sizeof(c_void_p))
                pid_val = c_uint32(0)
                get_pid(sess2_ptr, byref(pid_val))
                pid = pid_val.value

                peak = -1.0
                try:
                    meter = sess2.QueryInterface(IAudioMeterInformation)
                    peak = meter.GetPeakValue()
                except Exception:
                    peak = -2.0

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
                    playing_pids.append((pid, proc_name, peak))
                print(f"  [{i}] pid={pid} ({proc_name}), peak={peak:.4f}{marker}")
            except Exception as e:
                pass

        print()
        if playing_pids:
            print(f"[probe] 正在播放音频的进程: {len(playing_pids)} 个")
            for pid, name, peak in playing_pids:
                print(f"  pid={pid} ({name}), peak={peak:.4f}")
        else:
            print("[probe] ✗ 没有进程正在播放音频")

    finally:
        CoUninitialize()


if __name__ == "__main__":
    main()
