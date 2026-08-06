"""以管理员权限重启自身并测试 WASAPI Process Loopback."""
import ctypes
import sys
import os


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def run_as_admin():
    # 获取当前脚本路径和参数
    script = os.path.abspath(__file__)
    params = " ".join(sys.argv[1:])
    # ShellExecuteW runas 以管理员权限运行
    rc = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, f'"{script}" {params}', None, 1
    )
    return rc > 32


def main_test():
    """以管理员权限运行的实际测试."""
    print(f"[admin] 当前是否管理员: {is_admin()}")
    if not is_admin():
        print("[admin] 请在 UAC 弹窗中同意以管理员权限运行")
        return

    # 在管理员权限下运行 Process Loopback 激活测试
    print("[admin] 开始测试 WASAPI Process Loopback (管理员权限)...")
    import threading
    import ctypes
    from ctypes import (
        POINTER, byref, cast, c_long, c_uint32, c_void_p, c_uint16,
        Structure, sizeof, c_wchar_p, c_uint8
    )
    from comtypes import CoInitializeEx, CoUninitialize, COMObject, IUnknown, GUID, COMMETHOD, HRESULT
    import psutil

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

    VIRTUAL_AUDIO_DEVICE_PROCESS_LOOPBACK = "Virtual Audio Device Process Loopback"
    AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK = 1
    PROCESS_LOOPBACK_MODE_INCLUDE = 0
    VT_BLOB = 0x0041

    class AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS(Structure):
        _fields_ = [
            ("TargetProcessId", c_uint32),
            ("ProcessLoopbackMode", c_uint32),
        ]

    class AUDIOCLIENT_ACTIVATION_PARAMS(Structure):
        _fields_ = [
            ("ActivationType", c_uint32),
            ("ProcessLoopbackParams", AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS),
        ]

    class _BLOB(Structure):
        _fields_ = [
            ("cbSize", c_uint32),
            ("_padding", c_uint32),
            ("pBlobData", c_void_p),
        ]

    class PROPVARIANT_BLOB(Structure):
        _fields_ = [
            ("vt", c_uint16),
            ("wReserved1", c_uint16),
            ("wReserved2", c_uint16),
            ("wReserved3", c_uint16),
            ("blob", _BLOB),
        ]

    class IActivateAudioInterfaceAsyncOperation(IUnknown):
        _iid_ = GUID("{72A6C5A0-4B2A-4C6E-A5A0-2D23B8C96009}")
        _methods_ = (
            COMMETHOD([], HRESULT, "GetActivateResult",
                (["out"], POINTER(HRESULT), "activateResult"),
                (["out"], POINTER(POINTER(IUnknown)), "activatedInterface"),
            ),
        )

    class IActivateAudioInterfaceCompletionHandler(IUnknown):
        _iid_ = GUID("{41D949AB-9862-444A-80F6-86F28A9D3A8B}")
        _methods_ = (
            COMMETHOD([], HRESULT, "ActivateCompleted",
                (["in"], POINTER(IActivateAudioInterfaceAsyncOperation), "activateOperation"),
            ),
        )

    class IAgileObject(IUnknown):
        _iid_ = GUID("{94EA2B94-E9CC-49E0-C0FF-EE64CA8F5B90}")
        _methods_ = ()

    def try_activate(pid, mode, label=""):
        result_holder = {"hr": -1, "ok": False}

        def worker():
            CoInitializeEx(0x0)  # MTA
            try:
                activation_params = AUDIOCLIENT_ACTIVATION_PARAMS()
                activation_params.ActivationType = AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK
                activation_params.ProcessLoopbackParams.TargetProcessId = pid
                activation_params.ProcessLoopbackParams.ProcessLoopbackMode = mode

                propvar = PROPVARIANT_BLOB()
                propvar.vt = VT_BLOB
                propvar.blob.cbSize = sizeof(AUDIOCLIENT_ACTIVATION_PARAMS)
                propvar.blob.pBlobData = cast(byref(activation_params), c_void_p).value

                activation_done = threading.Event()
                cb_result = {"hr": -1, "iface": None}

                class _Handler(COMObject):
                    _com_interfaces_ = [IActivateAudioInterfaceCompletionHandler, IAgileObject]
                    def ActivateCompleted(self, this, op):
                        try:
                            r = op.GetActivateResult()
                            if isinstance(r, tuple) and len(r) == 2:
                                hr_val, iface = r
                                cb_result["hr"] = hr_val if isinstance(hr_val, int) else 0
                                cb_result["iface"] = iface
                        except Exception:
                            cb_result["hr"] = -2
                        finally:
                            activation_done.set()
                        return 0

                handler = _Handler()
                handler_ptr = handler.QueryInterface(IActivateAudioInterfaceCompletionHandler)
                handler_ptr_val = cast(handler_ptr, c_void_p).value or 0

                ActivateAudioInterfaceAsync = ctypes.windll.mmdevapi.ActivateAudioInterfaceAsync
                ActivateAudioInterfaceAsync.restype = c_long
                ActivateAudioInterfaceAsync.argtypes = [
                    c_wchar_p, POINTER(WGUID), c_void_p, c_void_p, POINTER(c_void_p)
                ]

                op_ptr = c_void_p()
                hr = ActivateAudioInterfaceAsync(
                    VIRTUAL_AUDIO_DEVICE_PROCESS_LOOPBACK,
                    byref(IID_IAudioClient),
                    byref(propvar),
                    handler_ptr_val,
                    byref(op_ptr),
                )
                if hr != 0:
                    result_holder["hr"] = hr
                    return

                if not activation_done.wait(timeout=5.0):
                    result_holder["hr"] = -3
                    return

                hr_val = cb_result["hr"]
                result_holder["hr"] = hr_val
                result_holder["ok"] = (hr_val == 0 and cb_result["iface"] is not None)
            finally:
                CoUninitialize()

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        t.join(timeout=8.0)
        return result_holder

    # 找一个 msedge 进程
    target_pid = None
    for p in psutil.process_iter(["pid", "name"]):
        if p.info["name"] == "msedge.exe":
            target_pid = p.info["pid"]
            break

    if target_pid is None:
        print("[admin] 未找到 msedge.exe, 用 pid=0 测试")
        target_pid = 0

    print(f"[admin] 测试 INCLUDE pid={target_pid}...")
    r = try_activate(target_pid, PROCESS_LOOPBACK_MODE_INCLUDE, f"INCLUDE {target_pid}")
    if r["ok"]:
        print(f"  ✓ 成功! (管理员权限解决了问题)")
    else:
        hr = r["hr"]
        hr_val = hr & 0xFFFFFFFF if isinstance(hr, int) else 0
        print(f"  ✗ 失败 hr=0x{hr_val:08X}")
        if hr_val == 0x80070002:
            print(f"  -> 仍然返回 E_FILE_NOT_FOUND, 说明不是权限问题, 而是 WASAPI 本身的问题")
        elif hr_val == 0x80070005:
            print(f"  -> E_ACCESSDENIED, 是权限问题")

    input("\n[admin] 按回车退出...")


if __name__ == "__main__":
    if is_admin():
        main_test()
    else:
        print("[admin] 当前非管理员, 尝试以管理员权限重启...")
        rc = run_as_admin()
        if rc:
            print("[admin] UAC 弹窗已触发, 请在新窗口查看结果")
        else:
            print("[admin] 用户拒绝了 UAC, 退出")
