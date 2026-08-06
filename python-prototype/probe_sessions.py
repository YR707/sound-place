"""检查 Edge 是否有活跃的音频会话."""
from soundplace.session import list_audio_processes, find_process_by_pid
import ctypes
from ctypes import wintypes


def get_process_pids_by_name(name: str):
    """通过 CreateToolhelp32Snapshot 获取所有匹配进程的 PID."""
    TH32CS_SNAPPROCESS = 0x00000002

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    kernel32 = ctypes.windll.kernel32
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    pe = PROCESSENTRY32W()
    pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)

    pids = []
    if kernel32.Process32FirstW(snap, ctypes.byref(pe)):
        while True:
            if name.lower() in pe.szExeFile.lower():
                pids.append((pe.th32ProcessID, pe.szExeFile))
            if not kernel32.Process32NextW(snap, ctypes.byref(pe)):
                break
    kernel32.CloseHandle(snap)
    return pids


print("=== 所有 msedge.exe 进程 ===")
all_pids = get_process_pids_by_name("msedge")
for pid, name in all_pids:
    print(f"  PID={pid}, name={name}")

print(f"\n总计 {len(all_pids)} 个 msedge 进程")

print("\n=== pycaw 看到的音频会话进程 ===")
sessions = list_audio_processes()
for s in sessions:
    marker = " <-- msedge" if "msedge" in (s.name or "").lower() else ""
    print(f"  PID={s.pid}, name={s.name}, display={s.display_name}{marker}")
