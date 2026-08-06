"""验证 PROPVARIANT 布局和 pBlobData 地址的传递."""
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


# 模拟 capture.py 的构造过程
activation_params = AUDIOCLIENT_ACTIVATION_PARAMS()
activation_params.ActivationType = 1  # PROCESS_LOOPBACK
activation_params.ProcessLoopbackParams.TargetProcessId = 23608  # msedge
activation_params.ProcessLoopbackParams.ProcessLoopbackMode = 0  # INCLUDE

propvar = PROPVARIANT_BLOB()
propvar.vt = 0x0041  # VT_BLOB
propvar.blob.cbSize = sizeof(AUDIOCLIENT_ACTIVATION_PARAMS)
# 注意: cast(byref(...), c_void_p).value 返回 activation_params 的地址
propvar.blob.pBlobData = cast(byref(activation_params), c_void_p).value

print("=== 模拟 capture.py 的构造 ===")
print(f"sizeof(AUDIOCLIENT_ACTIVATION_PARAMS) = {sizeof(AUDIOCLIENT_ACTIVATION_PARAMS)}")
print(f"addressof(activation_params) = 0x{addressof(activation_params):016X}")
print(f"cast(byref(activation_params), c_void_p).value = 0x{propvar.blob.pBlobData or 0:016X}")
print(f"propvar.blob.cbSize = {propvar.blob.cbSize}")

print("\n=== 读取 activation_params 内容 (从 pBlobData 地址) ===")
blob_addr = propvar.blob.pBlobData
# 从 blob_addr 读取 AUDIOCLIENT_ACTIVATION_PARAMS
read_back = AUDIOCLIENT_ACTIVATION_PARAMS.from_address(blob_addr)
print(f"read_back.ActivationType = {read_back.ActivationType} (期望 1)")
print(f"read_back.ProcessLoopbackParams.TargetProcessId = {read_back.ProcessLoopbackParams.TargetProcessId} (期望 23608)")
print(f"read_back.ProcessLoopbackParams.ProcessLoopbackMode = {read_back.ProcessLoopbackParams.ProcessLoopbackMode} (期望 0)")

print("\n=== 检查对齐问题 ===")
print(f"alignment(AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS) = {alignment(AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS)}")
print(f"alignment(AUDIOCLIENT_ACTIVATION_PARAMS) = {alignment(AUDIOCLIENT_ACTIVATION_PARAMS)}")

# 字段偏移
for name, _ in AUDIOCLIENT_ACTIVATION_PARAMS._fields_:
    field = getattr(AUDIOCLIENT_ACTIVATION_PARAMS, name)
    print(f"  AUDIOCLIENT_ACTIVATION_PARAMS.{name}: offset={field.offset}")

for name, _ in AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS._fields_:
    field = getattr(AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS, name)
    print(f"  AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS.{name}: offset={field.offset}")

# Microsoft 官方 C 结构布局参考:
# typedef struct AUDIOCLIENT_ACTIVATION_PARAMS {
#   AUDIOCLIENT_ACTIVATION_TYPE ActivationType;   // DWORD (4 bytes)
#   union {
#     AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS ProcessLoopbackParams;
#   } DUMMYUNIONNAME;
# } AUDIOCLIENT_ACTIVATION_PARAMS;
#
# typedef struct AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS {
#   DWORD TargetProcessId;        // 4 bytes
#   PROCESS_LOOPBACK_MODE ProcessLoopbackMode;  // DWORD, 4 bytes
# } AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS;
#
# 总大小: 4 (ActivationType) + 8 (ProcessLoopbackParams) = 12 字节
print(f"\n期望 sizeof = 12, 实际 sizeof = {sizeof(AUDIOCLIENT_ACTIVATION_PARAMS)}")
