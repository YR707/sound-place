"""检查可能阻止 WASAPI Process Loopback 的系统设置."""
import ctypes
import os
import subprocess
import winreg


def check_windows_build():
    """检查 Windows 版本."""
    import platform
    print(f"[check] Windows: {platform.platform()}")
    print(f"[check] 版本: {platform.version()}")


def check_audio_services():
    """检查音频服务状态."""
    print("\n[check] 音频服务状态:")
    services = [
        "Audiosrv",       # Windows Audio
        "AudioEndpointBuilder",  # Windows Audio Endpoint Builder
        "MMCSS",          # Multimedia Class Scheduler
    ]
    for svc in services:
        try:
            result = subprocess.run(
                ["sc", "query", svc], capture_output=True, text=True, timeout=5
            )
            state_line = [l for l in result.stdout.split("\n") if "STATE" in l]
            state = state_line[0].split(":", 1)[1].strip() if state_line else "?"
            print(f"  {svc}: {state}")
        except Exception as e:
            print(f"  {svc}: 查询失败 ({e})")


def check_audio_device():
    """检查默认音频设备."""
    print("\n[check] 默认音频设备:")
    try:
        from comtypes import CoInitialize, CoUninitialize
        from pycaw.pycaw import AudioUtilities
        CoInitialize()
        try:
            speakers = AudioUtilities.GetSpeakers()
            print(f"  {speakers}")
            # 不直接调 vtable, 用 pycaw 已有的方法
            # AudioDevice 没有 GetState, 但可以查 friendly name
            print(f"  Friendly name: {speakers.FriendlyName}")
        finally:
            CoUninitialize()
    except Exception as e:
        print(f"  检查失败: {e}")


def check_sac():
    """检查 Smart App Control 状态."""
    print("\n[check] Smart App Control 状态:")
    try:
        # SAC 的策略文件
        import os.path
        policy_path = r"C:\Windows\System32\CodeIntegrity\CIpolicies\Active"
        if os.path.exists(policy_path):
            files = os.listdir(policy_path)
            print(f"  Active 策略目录: {len(files)} 个文件")
            for f in files:
                print(f"    {f}")
        else:
            print("  无 Active 策略目录")
    except Exception as e:
        print(f"  检查失败: {e}")


def check_app_capability():
    """检查是否有 AppContainer / UWP 限制."""
    print("\n[check] 进程信息:")
    import psutil
    me = psutil.Process(os.getpid())
    print(f"  PID: {me.pid}")
    print(f"  Name: {me.name()}")

    # 检查权限
    try:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        print(f"  管理员权限: {'是' if is_admin else '否'}")
    except Exception:
        pass


def check_loopback_device():
    """直接检查 VIRTUAL_AUDIO_DEVICE_PROCESS_LOOPBACK 是否能被识别."""
    print("\n[check] 测试 ActivateAudioInterfaceAsync 调用本身:")
    import ctypes
    from ctypes import (
        POINTER, byref, cast, c_long, c_uint32, c_void_p, c_uint16,
        Structure, sizeof, c_wchar_p, c_uint8
    )

    class WGUID(Structure):
        _fields_ = [
            ("Data1", c_uint32),
            ("Data2", c_uint16),
            ("Data3", c_uint16),
            ("Data4", c_uint8 * 8),
        ]

    IID_IAudioClient = WGUID(
        Data1=0x1CB9AD4C, Data2=0xDBFA, Data3=0x4c32,
        Data4=(0xB1, 0x78, 0xC2, 0xF5, 0x68, 0xA7, 0x03, 0xB2),
    )

    ActivateAudioInterfaceAsync = ctypes.windll.mmdevapi.ActivateAudioInterfaceAsync
    ActivateAudioInterfaceAsync.restype = c_long
    ActivateAudioInterfaceAsync.argtypes = [
        c_wchar_p, POINTER(WGUID), c_void_p, c_void_p, POINTER(c_void_p)
    ]

    op_ptr = c_void_p()
    # 传 nullptr 作为 propvariant 和 callback
    hr = ActivateAudioInterfaceAsync(
        "Virtual Audio Device Process Loopback",
        byref(IID_IAudioClient),
        None,
        None,
        byref(op_ptr),
    )
    hr_val = hr & 0xFFFFFFFF
    print(f"  测试1 (ProcessLoopback + nullptr propvar/handler): hr=0x{hr_val:08X}")

    op_ptr2 = c_void_p()
    hr2 = ActivateAudioInterfaceAsync(
        "NonExistent Audio Device XXX",
        byref(IID_IAudioClient),
        None,
        None,
        byref(op_ptr2),
    )
    hr2_val = hr2 & 0xFFFFFFFF
    print(f"  测试2 (无效设备路径): hr=0x{hr2_val:08X}")

    # 测试 3: 用 pycaw 获取默认 render 设备 ID
    try:
        from comtypes import CoInitialize, CoUninitialize
        from pycaw.pycaw import AudioUtilities
        CoInitialize()
        try:
            speakers = AudioUtilities.GetSpeakers()
            # pycaw 的 AudioDevice 有 id 属性 (字符串)
            dev_id = speakers.id
            print(f"  默认扬声器设备 ID: {dev_id}")

            op_ptr3 = c_void_p()
            hr3 = ActivateAudioInterfaceAsync(
                dev_id,
                byref(IID_IAudioClient),
                None,
                None,
                byref(op_ptr3),
            )
            hr3_val = hr3 & 0xFFFFFFFF
            print(f"  测试3 (真实设备 ID + nullptr propvar): hr=0x{hr3_val:08X}")
        finally:
            CoUninitialize()
    except Exception as e:
        print(f"  测试3 失败: {e}")


if __name__ == "__main__":
    check_windows_build()
    check_audio_services()
    check_audio_device()
    check_sac()
    check_app_capability()
    check_loopback_device()
