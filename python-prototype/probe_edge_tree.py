"""列出 msedge 进程树, 找出所有 msedge 子进程.
然后对每个子进程尝试 ActivateAudioInterfaceAsync, 找出能成功的那个.

关键: 每次测试在一个独立线程中运行, 在线程里 CoInitializeEx(MTA)."""
import threading
import time
import ctypes
from ctypes import (
    POINTER, byref, cast, c_long, c_uint32, c_float, c_void_p, c_uint16,
    Structure, sizeof, WINFUNCTYPE, c_ubyte, c_wchar_p, c_uint8, c_uint64
)
import comtypes
from comtypes import CoInitialize, CoUninitialize, CoInitializeEx, COMObject, IUnknown, GUID, COMMETHOD, HRESULT
import psutil


# WASAPI 结构
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


# comtypes 接口
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


def try_activate_for_pid(pid, name_hint=""):
    """对指定 PID 尝试激活 Process Loopback, 返回 (hr, success).
    在独立线程里执行, 以确保 MTA 初始化成功."""
    result_holder = {"hr": -1, "ok": False}

    def worker():
        CoInitializeEx(0x0)  # MTA
        try:
            # 构造激活参数
            activation_params = AUDIOCLIENT_ACTIVATION_PARAMS()
            activation_params.ActivationType = AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK
            activation_params.ProcessLoopbackParams.TargetProcessId = pid
            activation_params.ProcessLoopbackParams.ProcessLoopbackMode = PROCESS_LOOPBACK_MODE_INCLUDE

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
                    except Exception as e:
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
    t.join(timeout=10.0)
    return (result_holder["hr"], result_holder["ok"])


def main():
    # 找 msedge 进程树
    msedge_procs = []
    for p in psutil.process_iter(["pid", "name", "ppid"]):
        info = p.info
        if info["name"] and "msedge" in info["name"].lower():
            msedge_procs.append(info)

    print(f"[probe] 找到 {len(msedge_procs)} 个 msedge 进程")

    # 找根进程 (ppid 不在 msedge 列表中)
    msedge_pids = {p["pid"] for p in msedge_procs}
    root_procs = [p for p in msedge_procs if p["ppid"] not in msedge_pids]
    print(f"[probe] 根 msedge 进程: {root_procs}")

    # 优先尝试根进程, 然后所有 msedge.exe (排除 webview2), 最后 webview2
    candidates = (
        root_procs
        + [p for p in msedge_procs if p["name"] == "msedge.exe" and p not in root_procs]
        + [p for p in msedge_procs if p["name"] != "msedge.exe"]
    )

    print(f"\n[probe] 开始对 {len(candidates[:15])} 个候选进程尝试激活...")
    print("=" * 60)

    for info in candidates[:15]:
        pid = info["pid"]
        name = info["name"]
        is_root = info in root_procs
        marker = " (root)" if is_root else ""
        print(f"\n[probe] 尝试 pid={pid} ({name}){marker}...")
        hr, ok = try_activate_for_pid(pid, name)
        if ok:
            print(f"  ✓ 成功! pid={pid} ({name}) 可以激活")
            return
        else:
            hr_val = hr & 0xFFFFFFFF if isinstance(hr, int) else 0
            print(f"  ✗ 失败 hr=0x{hr_val:08X}")

    print("\n[probe] 没有任何 msedge 进程可以激活")


if __name__ == "__main__":
    main()
