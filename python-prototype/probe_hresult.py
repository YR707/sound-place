"""查询 HRESULT 0x8000000E 的错误消息描述."""
import ctypes


def format_hresult(hr: int) -> str:
    """使用 FormatMessageW 转换 HRESULT 为错误描述."""
    buf = ctypes.create_unicode_buffer(512)
    # FORMAT_MESSAGE_FROM_SYSTEM = 0x00001000
    # 有时候需要同时使用 IGNORE_INSERTS
    flags = 0x00001000 | 0x00000200  # FROM_SYSTEM | IGNORE_INSERTS
    n = ctypes.windll.kernel32.FormatMessageW(
        flags,
        None,
        hr,
        0,  # 默认语言
        buf,
        len(buf),
        None,
    )
    if n == 0:
        return f"<无法获取错误消息, FormatMessageW 返回 0>"
    return buf.value.strip()


# 测试多个可能的 HRESULT
hr_values = [
    0x8000000E,
    0x80004003,  # E_POINTER (标准)
    0x8007000E,  # E_OUTOFMEMORY
    0x80070057,  # E_INVALIDARG
    0x80004001,  # E_NOTIMPL
    0x88890008,  # AUDCLNT_E_NOT_STOPPED
    0x80040154,  # REGDB_E_CLASSNOTREG
    0x80004005,  # E_FAIL
    0x80070005,  # E_ACCESSDENIED
    0x80004002,  # E_NOINTERFACE
]

for hr in hr_values:
    msg = format_hresult(hr)
    print(f"0x{hr & 0xFFFFFFFF:08X}: {msg}")
