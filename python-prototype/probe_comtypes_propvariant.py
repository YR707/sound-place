"""使用 comtypes.automation 的 PROPVARIANT 测试."""
import ctypes
from ctypes import byref, c_uint32, sizeof, addressof, cast, c_void_p
from comtypes.automation import PROPVARIANT, VT_BLOB


# 检查 PROPVARIANT 大小
print(f"sizeof(PROPVARIANT) = {sizeof(PROPVARIANT)}")

# 看字段
for name, _ in PROPVARIANT._fields_:
    field = getattr(PROPVARIANT, name)
    print(f"  {name}: offset={field.offset}, size={field.size}")

# 测试创建一个 VT_BLOB PROPVARIANT
class AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS(ctypes.Structure):
    _fields_ = [
        ("TargetProcessId", c_uint32),
        ("ProcessLoopbackMode", c_uint32),
    ]


class AUDIOCLIENT_ACTIVATION_PARAMS(ctypes.Structure):
    _fields_ = [
        ("ActivationType", c_uint32),
        ("ProcessLoopbackParams", AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS),
    ]


# CoTaskMemAlloc
CoTaskMemAlloc = ctypes.windll.ole32.CoTaskMemAlloc
CoTaskMemAlloc.restype = c_void_p
CoTaskMemAlloc.argtypes = [ctypes.c_size_t]

params_size = sizeof(AUDIOCLIENT_ACTIVATION_PARAMS)
blob_data_ptr = CoTaskMemAlloc(params_size)
params = AUDIOCLIENT_ACTIVATION_PARAMS.from_address(blob_data_ptr)
params.ActivationType = 1
params.ProcessLoopbackParams.TargetProcessId = 23608
params.ProcessLoopbackParams.ProcessLoopbackMode = 0

print(f"\nblob_data_ptr = 0x{blob_data_ptr or 0:016X}")
print(f"params_size = {params_size}")

# 尝试创建 comtypes PROPVARIANT
pv = PROPVARIANT()
print(f"\nPROPVARIANT 创建: type={type(pv)}")
print(f"pv.vt = 0x{pv.vt:04X}")  # 初始 VT_EMPTY = 0

# 手动设置 VT_BLOB
pv.vt = VT_BLOB

# 看 PROPVARIANT 的 blob 字段
print(f"\nPROPVARIANT fields: {[f[0] for f in PROPVARIANT._fields_]}")

# 直接访问 blob 字段
# comtypes.automation.PROPVARIANT 的内部布局可能因版本而异
# 检查是否有 blob 字段
for attr in dir(pv):
    if "blob" in attr.lower() or "blob" in attr.lower():
        print(f"  发现 blob 属性: {attr}")

# 检查 .value
try:
    print(f"\npv.value = {pv.value}")
except Exception as e:
    print(f"\n.value 失败: {e}")
