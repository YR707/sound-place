"""探测 PROPVARIANT 结构布局 + cast(byref()) 行为."""
from ctypes import (
    Structure, c_uint16, c_uint32, c_void_p, sizeof, alignment,
    byref, cast, pointer, addressof,
)


class _BLOB(Structure):
    _fields_ = [
        ("cbSize", c_uint32),
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


print("=== 结构布局 ===")
print(f"sizeof(_BLOB) = {sizeof(_BLOB)} (期望 16)")
print(f"alignment(_BLOB) = {alignment(_BLOB)} (期望 8)")
print(f"sizeof(PROPVARIANT_BLOB) = {sizeof(PROPVARIANT_BLOB)} (期望 24)")
print(f"alignment(PROPVARIANT_BLOB) = {alignment(PROPVARIANT_BLOB)} (期望 8)")

print("\n=== 字段偏移 ===")
for name, _ in PROPVARIANT_BLOB._fields_:
    field = getattr(PROPVARIANT_BLOB, name)
    print(f"  {name}: offset={field.offset}, size={field.size}")

print("\n=== BLOB 字段偏移 ===")
for name, _ in _BLOB._fields_:
    field = getattr(_BLOB, name)
    print(f"  {name}: offset={field.offset}, size={field.size}")

print("\n=== cast(byref) vs addressof ===")


class AUDIOCLIENT_ACTIVATION_PARAMS(Structure):
    _fields_ = [
        ("ActivationType", c_uint32),
        ("TargetProcessId", c_uint32),
        ("ProcessLoopbackMode", c_uint32),
    ]


p = AUDIOCLIENT_ACTIVATION_PARAMS()
p.ActivationType = 1
p.TargetProcessId = 12345
p.ProcessLoopbackMode = 0

addr_direct = addressof(p)
print(f"addressof(p) = 0x{addr_direct:016X}")

v_byref = cast(byref(p), c_void_p).value
print(f"cast(byref(p), c_void_p).value = 0x{v_byref:016X}")

v_pointer = cast(pointer(p), c_void_p).value
print(f"cast(pointer(p), c_void_p).value = 0x{v_pointer:016X}")

print(f"byref == addressof? {v_byref == addr_direct}")
print(f"pointer == addressof? {v_pointer == addr_direct}")

print("\n=== PROPVARIANT 实际写入测试 ===")
propvar = PROPVARIANT_BLOB()
propvar.vt = 0x0041  # VT_BLOB
propvar.blob.cbSize = sizeof(AUDIOCLIENT_ACTIVATION_PARAMS)
propvar.blob.pBlobData = addressof(p)

print(f"propvar.vt = 0x{propvar.vt:04X}")
print(f"propvar.blob.cbSize = {propvar.blob.cbSize}")
print(f"propvar.blob.pBlobData = 0x{propvar.blob.pBlobData or 0:016X}")

# 读出原始字节验证布局
import ctypes
raw = (ctypes.c_ubyte * sizeof(PROPVARIANT_BLOB)).from_address(addressof(propvar))
print(f"\nraw bytes = {bytes(raw).hex(' ')}")
print("期望布局: 41 00 00 00 00 00 00 00 | 0C 00 00 00 00 00 00 00 | <ptr 8 bytes>")
