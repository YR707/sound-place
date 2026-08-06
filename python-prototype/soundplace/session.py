"""音频会话枚举 (对应 src-tauri/src/audio/session_filter.rs).

用 pycaw 的 AudioUtilities.GetAllSessions() 列出当前所有有音频会话的进程.
- 自动模式: 启动时列出, 用户选择一个进程作为捕获目标
- 手动模式: 通过 --pid 或 --process 指定
"""

from __future__ import annotations

import psutil
from dataclasses import dataclass
from pycaw.pycaw import AudioUtilities
from typing import Optional


@dataclass(slots=True)
class AudioProcess:
    """一个有音频会话的进程."""
    pid: int
    name: str  # 例如 "msedge.exe"
    display_name: str  # 可读名称, 例如 "Microsoft Edge"
    exe_path: Optional[str]  # 完整路径, 可能因权限不足为 None

    def __str__(self) -> str:
        return f"[{self.pid:>6}] {self.display_name} ({self.name})"


def list_audio_processes() -> list[AudioProcess]:
    """列出当前所有有音频会话的进程 (去重, 排除系统空闲会话).

    Returns:
        AudioProcess 列表, 按 pid 升序.
    """
    seen_pids: set[int] = set()
    result: list[AudioProcess] = []

    sessions = AudioUtilities.GetAllSessions()
    for session in sessions:
        process = session.Process
        if process is None:
            # 系统空闲会话 (pid=0 或 None), 跳过
            continue
        pid = process.pid
        if pid in seen_pids:
            continue
        seen_pids.add(pid)

        name = process.name()  # e.g. "msedge.exe"
        exe_path: Optional[str] = None
        try:
            exe_path = process.exe()
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
            exe_path = None

        display_name = _build_display_name(name, exe_path)

        result.append(AudioProcess(
            pid=pid,
            name=name,
            display_name=display_name,
            exe_path=exe_path,
        ))

    result.sort(key=lambda p: p.pid)
    return result


def _build_display_name(name: str, exe_path: Optional[str]) -> str:
    """从文件名和路径构建可读名称."""
    # 简单映射表, 后续可扩展
    known = {
        "msedge.exe": "Microsoft Edge",
        "chrome.exe": "Google Chrome",
        "firefox.exe": "Mozilla Firefox",
        "Weixin.exe": "微信",
        "QQ.exe": "QQ",
        "Discord.exe": "Discord",
        "Spotify.exe": "Spotify",
        "steam.exe": "Steam",
        "cs2.exe": "Counter-Strike 2",
        "Valorant.exe": "Valorant",
        "PUBG.exe": "PUBG",
        "Trae CN.exe": "Trae CN",
        "explorer.exe": "Windows Explorer",
    }
    if name in known:
        return known[name]
    # 去掉 .exe 后缀
    return name[:-4] if name.lower().endswith(".exe") else name


def select_process_interactive() -> Optional[AudioProcess]:
    """交互式选择进程: 打印列表, 让用户输入序号.

    Returns:
        选中的 AudioProcess, 或 None (用户取消).
    """
    procs = list_audio_processes()
    if not procs:
        print("[session] 未检测到任何有音频会话的进程")
        return None

    print("=" * 60)
    print("检测到以下有音频输出的进程:")
    print("-" * 60)
    for i, p in enumerate(procs, 1):
        print(f"  {i:2d}. {p}")
    print("-" * 60)
    print("  0. 退出")
    print("=" * 60)

    while True:
        try:
            choice = input("请选择要捕获的进程序号: ").strip()
            idx = int(choice)
            if idx == 0:
                return None
            if 1 <= idx <= len(procs):
                return procs[idx - 1]
            print(f"  序号超出范围 (1-{len(procs)})", flush=True)
        except ValueError:
            print("  请输入数字", flush=True)
        except (EOFError, KeyboardInterrupt):
            return None


def find_process_by_pid(pid: int) -> Optional[AudioProcess]:
    """按 PID 查找有音频会话的进程."""
    sessions = AudioUtilities.GetAllSessions()
    for session in sessions:
        process = session.Process
        if process is not None and process.pid == pid:
            name = process.name()
            exe_path: Optional[str] = None
            try:
                exe_path = process.exe()
            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                pass
            return AudioProcess(
                pid=pid,
                name=name,
                display_name=_build_display_name(name, exe_path),
                exe_path=exe_path,
            )
    return None


def find_process_by_name(name_pattern: str) -> Optional[AudioProcess]:
    """按进程名查找 (大小写不敏感, 可带或不带 .exe).

    Returns:
        第一个匹配的 AudioProcess, 或 None.
    """
    pattern = name_pattern.lower()
    if not pattern.endswith(".exe"):
        pattern = pattern + ".exe"

    sessions = AudioUtilities.GetAllSessions()
    for session in sessions:
        process = session.Process
        if process is None:
            continue
        proc_name = process.name().lower()
        if proc_name == pattern:
            exe_path: Optional[str] = None
            try:
                exe_path = process.exe()
            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                pass
            return AudioProcess(
                pid=process.pid,
                name=process.name(),
                display_name=_build_display_name(process.name(), exe_path),
                exe_path=exe_path,
            )
    return None
