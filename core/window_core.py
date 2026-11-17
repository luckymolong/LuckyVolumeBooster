# -*- coding: utf-8 -*-
"""桌面窗口枚举与「窗口 -> 音频会话」关联。"""
from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass
from typing import Dict, List, Set

import psutil

try:
    import win32con
    import win32gui
    import win32process

    _WIN32_OK = True
except Exception:  # pragma: no cover
    _WIN32_OK = False

DWMWA_CLOAKED = 14
_SKIP_CLASSES = {
    "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
    "NotifyIconOverflowWindow", "Windows.UI.Core.CoreWindow",
    "ForegroundStaging", "ApplicationFrameWindow",
}


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    pid: int
    process_name: str
    exe: str
    class_name: str
    rect: tuple

    @property
    def size_text(self) -> str:
        l, t, r, b = self.rect
        return f"{max(0, r - l)} × {max(0, b - t)}"


def _is_cloaked(hwnd: int) -> bool:
    try:
        val = ctypes.c_int(0)
        ctypes.windll.dwmapi.DwmGetWindowAttribute(
            hwnd, DWMWA_CLOAKED, ctypes.byref(val), ctypes.sizeof(val)
        )
        return bool(val.value)
    except Exception:
        return False


def enum_visible_windows(include_self: bool = False) -> List[WindowInfo]:
    """列出所有可见、有标题、非工具窗口的顶层桌面窗口。"""
    if not _WIN32_OK:
        return []
    self_pid = os.getpid()
    result: List[WindowInfo] = []

    def _callback(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            if win32gui.GetParent(hwnd) != 0:
                return
            title = win32gui.GetWindowText(hwnd).strip()
            if not title or len(title) < 2:
                return
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if ex_style & win32con.WS_EX_TOOLWINDOW:
                return
            if _is_cloaked(hwnd):
                return
            cls = win32gui.GetClassName(hwnd)
            if cls in _SKIP_CLASSES:
                return
            if win32gui.IsIconic(hwnd):
                # 最小化窗口依然算，用户可能想调它的音量
                pass
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if not include_self and pid == self_pid:
                return
            try:
                rect = win32gui.GetWindowRect(hwnd)
            except Exception:
                rect = (0, 0, 0, 0)
            pname, exe = "", ""
            try:
                p = psutil.Process(pid)
                pname, exe = p.name(), p.exe()
            except Exception:
                pass
            result.append(WindowInfo(hwnd, title, pid, pname, exe, cls, rect))
        except Exception:
            return

    try:
        win32gui.EnumWindows(_callback, None)
    except Exception:
        pass
    result.sort(key=lambda w: w.title.lower())
    return result


def pid_title_map(windows: List[WindowInfo]) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for w in windows:
        out.setdefault(w.pid, w.title)
    return out


def foreground_window() -> WindowInfo | None:
    """返回当前前台窗口，供「拾取窗口」功能使用。"""
    if not _WIN32_OK:
        return None
    try:
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd).strip()
        if not title:
            return None
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        pname, exe = "", ""
        try:
            p = psutil.Process(pid)
            pname, exe = p.name(), p.exe()
        except Exception:
            pass
        return WindowInfo(hwnd, title, pid, pname, exe,
                          win32gui.GetClassName(hwnd), win32gui.GetWindowRect(hwnd))
    except Exception:
        return None


def related_pids(pid: int) -> Set[int]:
    """返回与窗口进程相关的 PID 集合。

    很多程序（Chrome / Edge / 游戏 / 播放器）把音频放在子进程里，
    仅用窗口 PID 精确匹配会漏掉音频会话，因此同时纳入子进程与同名进程。
    """
    pids: Set[int] = {pid}
    name = ""
    try:
        p = psutil.Process(pid)
        name = p.name().lower()
        try:
            for child in p.children(recursive=True):
                pids.add(child.pid)
        except Exception:
            pass
    except Exception:
        return pids
    if name:
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if (proc.info.get("name") or "").lower() == name:
                    pids.add(proc.info["pid"])
            except Exception:
                continue
    return pids


def match_session_keys(window: WindowInfo, sessions) -> List[str]:
    """为一个窗口找出所有对应的音频会话 key，按匹配优先级排序。"""
    pids = related_pids(window.pid)
    exact, same_name, parent = [], [], []
    wname = (window.process_name or "").lower()
    for s in sessions:
        if s.pid in pids:
            exact.append(s.key)
        elif wname and s.name and s.name.lower() == wname:
            same_name.append(s.key)
    # 去重并保持顺序
    seen, out = set(), []
    for key in exact + same_name + parent:
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out
