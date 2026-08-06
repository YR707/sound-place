"""探测 comtypes COMObject 的指针获取方式."""
from comtypes import COMObject, IUnknown, GUID, COMMETHOD, HRESULT
import ctypes


class Foo(COMObject):
    _com_interfaces_ = [IUnknown]


obj = Foo()
ptr = obj.QueryInterface(IUnknown)
print(f"type: {type(ptr)}")
print(f"dir (non-private): {[x for x in dir(ptr) if not x.startswith('__')][:30]}")
print(f"_as_parameter_: {getattr(ptr, '_as_parameter_', 'N/A')}")
print(f"_b_base_: {getattr(ptr, '_b_base_', 'N/A')}")

# 尝试几种取地址方式
print()
print("尝试取地址:")
try:
    v = ctypes.addressof(ptr.contents)
    print(f"  addressof(ptr.contents) = 0x{v:X}")
except Exception as e:
    print(f"  addressof(ptr.contents) 失败: {e}")

try:
    v = ctypes.cast(ptr, ctypes.c_void_p).value
    print(f"  cast(ptr, c_void_p).value = 0x{v:X}")
except Exception as e:
    print(f"  cast(ptr, c_void_p).value 失败: {e}")

try:
    v = ptr._as_parameter_
    print(f"  ptr._as_parameter_ = {v}")
except Exception as e:
    print(f"  ptr._as_parameter_ 失败: {e}")

# comtypes 的 POINTER 对象本身就是 ctypes 指针
# 用 ctypes.addressof(ptr) 取指针本身的地址 (不是对象的地址)
try:
    v = ctypes.addressof(ptr)
    print(f"  addressof(ptr) = 0x{v:X}")
except Exception as e:
    print(f"  addressof(ptr) 失败: {e}")

# 用 ctypes.POINTER(IUnknown) 的 from_param?
try:
    v = ctypes.cast(ptr, ctypes.c_void_p)
    print(f"  cast type: {type(v)}, value: {v.value}")
except Exception as e:
    print(f"  cast failed: {e}")
