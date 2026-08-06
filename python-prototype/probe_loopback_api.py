"""测试 WASAPI Process Loopback API 是否在这台机器上正常工作.
用多种方式验证:
1. EXCLUDE 模式 (排除一个不发声的进程, 等同于捕获所有其他音频)
2. INCLUDE 模式但传入当前 PID (我们自己的 Python 进程)
3. INCLUDE 模式但传入 0 (System Idle)
4. INCLUDE 模式但传入 explorer.exe (肯定会发声)"""
import threading
import time
import ctypes
import os
from ctypes import (
    POINTER, byref, cast, c_long, c_uint32, c_float, c_void_p, c_uint16,
    Structure, sizeof, WINFUNCTYPE, c_wchar_p, c_uint8
)
import comtypes
from comtypes import CoUninitialize, CoInitializeEx, COMObject, IUnknown, GUID, COMMETHOD, HRESULT
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
PROCESS_LOOPBACK_MODE_EXCLUDE = 1
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
    """对指定 (pid, mode) 尝试激活, 返回 (hr, success)."""
    result_holder = {"hr": -1, "ok": False, "label": label}

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


def main():
    print(f"[probe] 当前 Python PID = {os.getpid()}")
    print(f"[probe] Windows Build: ", end="")
    import platform
    print(platform.platform())

    # 找一些候选进程
    targets = []
    for p in psutil.process_iter(["pid", "name"]):
        name = p.info["name"] or ""
        if name.lower() in ("explorer.exe", "svchost.exe", "audiodg.exe", "wininit.exe", "services.exe"):
            targets.append(p.info)
    me = os.getpid()
    my_proc = psutil.Process(me).name()

    tests = [
        # (pid, mode, label)
        (me, PROCESS_LOOPBACK_MODE_EXCLUDE, f"EXCLUDE 自己 ({my_proc}, pid={me}) — 等同于捕获所有其他进程音频"),
        (me, PROCESS_LOOPBACK_MODE_INCLUDE, f"INCLUDE 自己 ({my_proc}, pid={me})"),
        (0, PROCESS_LOOPBACK_MODE_INCLUDE, "INCLUDE pid=0 (System Idle) — 理论上不会发声"),
        (0, PROCESS_LOOPBACK_MODE_EXCLUDE, "EXCLUDE pid=0 — 等同于捕获所有进程音频"),
    ]

    # 加上系统进程
    for info in targets:
        tests.append((info["pid"], PROCESS_LOOPBACK_MODE_INCLUDE,
                      f"INCLUDE {info['name']} (pid={info['pid']})"))
        tests.append((info["pid"], PROCESS_LOOPBACK_MODE_EXCLUDE,
                      f"EXCLUDE {info['name']} (pid={info['pid']})"))

    print()
    print("=" * 80)
    for pid, mode, label in tests:
        print(f"\n[probe] 测试: {label}")
        r = try_activate(pid, mode, label)
        if r["ok"]:
            print(f"  ✓ 成功!")
        else:
            hr = r["hr"]
            hr_val = hr & 0xFFFFFFFF if isinstance(hr, int) else 0
            print(f"  ✗ 失败 hr=0x{hr_val:08X}")


if __name__ == "__main__":
    main()
