"""验证 PROPVARIANT_BLOB 和相关结构的内存布局."""
import ctypes
from ctypes import (
    POINTER, Structure, byref, cast, c_long, c_uint16, c_uint32,
    c_uint8, c_void_p, sizeof, WINFUNCTYPE,
)


class GUID(Structure):
    _fields_ = [
        ("Data1", c_uint32),
        ("Data2", c_uint16),
        ("Data3", c_uint16),
        ("Data4", c_uint8 * 8),
    ]


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


# 旧版 (带显式 padding)
class _BLOB_padded(Structure):
    _fields_ = [
        ("cbSize", c_uint32),
        ("_padding", c_uint32),
        ("pBlobData", c_void_p),
    ]


class PROPVARIANT_BLOB_padded(Structure):
    _fields_ = [
        ("vt", c_uint16),
        ("wReserved1", c_uint16),
        ("wReserved2", c_uint16),
        ("wReserved3", c_uint16),
        ("blob", _BLOB_padded),
    ]


# 新版 (无显式 padding, 让 ctypes 自动对齐)
class _BLOB_auto(Structure):
    _fields_ = [
        ("cbSize", c_uint32),
        ("pBlobData", c_void_p),
    ]


class PROPVARIANT_BLOB_auto(Structure):
    _fields_ = [
        ("vt", c_uint16),
        ("wReserved1", c_uint16),
        ("wReserved2", c_uint16),
        ("wReserved3", c_uint16),
        ("blob", _BLOB_auto),
    ]


# Windows SDK 真实 PROPVARIANT 的 union 应该是 16 字节 (容纳 BLOB 或 IUnknown* 等)
# 完整模拟 (用 c_byte[16] 作为 union 占位符)
class PROPVARIANT_full(Structure):
    _fields_ = [
        ("vt", c_uint16),
        ("wReserved1", c_uint16),
        ("wReserved2", c_uint16),
        ("wReserved3", c_uint16),
        ("_union", c_uint8 * 16),  # 16 字节 union
    ]


def show_layout(name, struct_class):
    print(f"=== {name} ===")
    print(f"  sizeof = {sizeof(struct_class)}")
    for fname, _ in struct_class._fields_:
        field = getattr(struct_class, fname)
        print(f"  {fname}: offset={field.offset}, size={field.size}")
    print()


print("==== 基础结构 ====")
print(f"sizeof(GUID) = {sizeof(GUID)}")
print(f"sizeof(AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS) = {sizeof(AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS)}")
print(f"sizeof(AUDIOCLIENT_ACTIVATION_PARAMS) = {sizeof(AUDIOCLIENT_ACTIVATION_PARAMS)}")
print(f"sizeof(c_void_p) = {sizeof(c_void_p)}")
print()

show_layout("_BLOB_padded", _BLOB_padded)
show_layout("PROPVARIANT_BLOB_padded", PROPVARIANT_BLOB_padded)
show_layout("_BLOB_auto", _BLOB_auto)
show_layout("PROPVARIANT_BLOB_auto", PROPVARIANT_BLOB_auto)
show_layout("PROPVARIANT_full", PROPVARIANT_full)

# 测试 PROPVARIANT_BLOB_padded 是否与 PROPVARIANT_full 大小一致
assert sizeof(PROPVARIANT_BLOB_padded) == sizeof(PROPVARIANT_full), \
    f"PROPVARIANT size mismatch: {sizeof(PROPVARIANT_BLOB_padded)} != {sizeof(PROPVARIANT_full)}"
print(f"✓ PROPVARIANT_BLOB_padded 与 PROPVARIANT_full 大小一致 ({sizeof(PROPVARIANT_BLOB_padded)})")

# 测试 _BLOB 的 pBlobData 偏移
padded_offset = _BLOB_padded.pBlobData.offset
auto_offset = _BLOB_auto.pBlobData.offset
print(f"_BLOB_padded.pBlobData offset = {padded_offset}")
print(f"_BLOB_auto.pBlobData offset = {auto_offset}")
if padded_offset == 8:
    print("✓ _BLOB_padded 的 pBlobData 偏移正确 (8, 对齐 8)")
else:
    print(f"✗ _BLOB_padded 的 pBlobData 偏移错误 (期望 8, 实际 {padded_offset})")
if auto_offset == 8:
    print("✓ _BLOB_auto 的 pBlobData 偏移正确 (8, ctypes 自动 padding)")
else:
    print(f"✗ _BLOB_auto 的 pBlobData 偏移错误 (期望 8, 实际 {auto_offset})")
