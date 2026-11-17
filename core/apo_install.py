# -*- coding: utf-8 -*-
"""Equalizer APO 内置安装器。

官方安装包（EqualizerAPO-x64-1.4.2.exe，NSIS 3 打包、requireAdministrator）
随本程序一起分发，用户不需要再去官网单独下载。本模块负责：

1. 定位随程序打包的官方安装包（onefile 模式下位于 sys._MEIPASS）；
2. 用 ShellExecuteExW("runas") 触发 UAC，以 ``/S`` 静默安装；
3. 判断「已安装」与「已对某个音频设备启用 APO」这两个不同状态：
   Equalizer APO 会把已启用的设备写进
   ``HKLM\\SOFTWARE\\EqualizerAPO\\Child APOs\\{设备GUID}``，
   没有这个子键说明驱动装好了但没有任何设备挂上滤镜（前级增益不会生效）。
"""
from __future__ import annotations

import ctypes
import shutil
import subprocess
import sys
import tempfile
import winreg
from ctypes import wintypes
from pathlib import Path
from typing import Callable, List, Optional, Tuple

BUNDLE_NAME = "EqualizerAPO-x64-1.4.2.exe"
BUNDLE_SIZE = 11_980_366
BUNDLE_SHA256 = "7403be7427bbe1936a40dded082829b6e217fc4f5990fee5cba501f0ae055afa"
UPSTREAM_URL = "https://sourceforge.net/projects/equalizerapo/files/1.4.2/"

INSTALL_DIRS = [
    Path(r"C:\Program Files\EqualizerAPO"),
    Path(r"C:\Program Files (x86)\EqualizerAPO"),
]

CANDIDATE_CONFIGS = [d / "config" / "config.txt" for d in INSTALL_DIRS] + [
    Path(str(Path.home() / "AppData" / "Roaming" / "EqualizerAPO" / "config" / "config.txt")),
]

APO_REG_ROOT = r"SOFTWARE\EqualizerAPO\Child APOs"
MM_RENDER = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render"
PROP_DEVICE_DESC = "{b3f8fa53-0004-438e-9003-51a46e139bfc},6"
PROP_FRIENDLY = "{a45c254e-df1c-4efd-8020-67d146a850e0},2"

# ---------------------------------------------------------------- 基础探测


def install_dir() -> Optional[Path]:
    for d in INSTALL_DIRS:
        if (d / "EqualizerAPO.dll").is_file():
            return d
    return None


def config_file() -> Optional[Path]:
    for p in CANDIDATE_CONFIGS:
        if p.is_file():
            return p
    return None


def is_installed() -> bool:
    return install_dir() is not None or config_file() is not None


def _mm_device_name(guid: str) -> str:
    key = f"{MM_RENDER}\\{guid}\\Properties"
    for prop in (PROP_DEVICE_DESC, PROP_FRIENDLY):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as k:
                value, _ = winreg.QueryValueEx(k, prop)
            if isinstance(value, str) and value.strip():
                return value.strip()
        except OSError:
            continue
    return guid[:8]


def _mm_device_state(guid: str) -> int:
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{MM_RENDER}\\{guid}") as k:
            value, _ = winreg.QueryValueEx(k, "DeviceState")
        return int(value)
    except (OSError, ValueError, TypeError):
        return 0


def enabled_devices() -> List[Tuple[str, int]]:
    """已启用 APO 的设备：[(显示名, DeviceState)]。1=在用 2=禁用 4=未插入 8=拔出。"""
    out: List[Tuple[str, int]] = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, APO_REG_ROOT) as k:
            index = 0
            while True:
                try:
                    guid = winreg.EnumKey(k, index)
                except OSError:
                    break
                index += 1
                if not guid.startswith("{"):
                    continue
                out.append((_mm_device_name(guid), _mm_device_state(guid)))
    except OSError:
        return []
    out.sort(key=lambda item: item[1] != 1)
    return out


def active_device_count() -> int:
    return sum(1 for _, state in enabled_devices() if state == 1)


# ---------------------------------------------------------------- 内置安装包


def bundle_path() -> Optional[Path]:
    """定位随程序分发的官方安装包。"""
    names = [BUNDLE_NAME, "EqualizerAPO-setup.exe"]
    roots: List[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(Path(meipass))
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
    roots.append(Path(__file__).resolve().parent.parent / "assets")
    for root in roots:
        for name in names:
            candidate = root / name
            if candidate.is_file() and candidate.stat().st_size > 1_000_000:
                return candidate
    return None


def bundle_size_mb() -> float:
    path = bundle_path()
    return (path.stat().st_size / 1024 / 1024) if path else 0.0


def extract_bundle() -> Optional[Path]:
    """把安装包解到临时目录（安装器要求可写、可执行的路径）。"""
    src = bundle_path()
    if src is None:
        return None
    tmpdir = Path(tempfile.gettempdir()) / "LuckyVolumeBooster"
    try:
        tmpdir.mkdir(parents=True, exist_ok=True)
        dst = tmpdir / src.name
        if not dst.is_file() or dst.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dst)
        return dst
    except Exception:
        return None


# ---------------------------------------------------------------- 提权执行

SEE_MASK_NOCLOSEPROCESS = 0x00000040
SEE_MASK_NOASYNC = 0x00000100
SW_SHOWNORMAL = 1
ERROR_CANCELLED = 1223
WAIT_TIMEOUT = 0x00000102
STILL_ACTIVE = 259


class _SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", ctypes.c_ulong),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIcon", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


def run_elevated(
    exe: Path, params: str = "", cwd: Optional[Path] = None, timeout: int = 900
) -> Tuple[bool, int, str]:
    """以管理员身份运行并等待结束。返回 (是否成功启动并结束, 退出码, 错误说明)。

    用户点「否」拒绝 UAC 时返回 (False, -1, "cancelled")。
    """
    if not hasattr(ctypes, "windll"):
        return False, -1, "当前系统不支持提权"
    info = _SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC
    info.lpVerb = "runas"
    info.lpFile = str(exe)
    info.lpParameters = params or None
    info.lpDirectory = str(cwd) if cwd else None
    info.nShow = SW_SHOWNORMAL

    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(_SHELLEXECUTEINFOW)]
    shell32.ShellExecuteExW.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    if not shell32.ShellExecuteExW(ctypes.byref(info)):
        code = ctypes.get_last_error()
        if code == ERROR_CANCELLED:
            return False, -1, "cancelled"
        return False, -1, f"ShellExecuteEx 失败（错误码 {code}）"
    handle = info.hProcess
    if not handle:
        return False, -1, "未能获取安装进程句柄"
    try:
        wait_ms = timeout * 1000
        result = kernel32.WaitForSingleObject(handle, wait_ms)
        if result == WAIT_TIMEOUT:
            return False, -1, f"等待超时（超过 {timeout // 60} 分钟）"
        exit_code = wintypes.DWORD(STILL_ACTIVE)
        kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        return True, int(exit_code.value), ""
    finally:
        kernel32.CloseHandle(handle)


# ---------------------------------------------------------------- 对外动作


def install(progress: Optional[Callable[[str], None]] = None, timeout: int = 900) -> Tuple[bool, str]:
    """静默安装内置 Equalizer APO。返回 (成功, 说明)。"""

    def tell(msg: str) -> None:
        if progress is not None:
            try:
                progress(msg)
            except Exception:
                pass

    tell("正在解出内置安装包…")
    setup = extract_bundle()
    if setup is None:
        return False, f"内置安装包缺失（{BUNDLE_NAME}），请重新下载完整版本"

    tell("请在「用户账户控制」窗口点击「是」…")
    ok, code, err = run_elevated(setup, "/S", setup.parent, timeout=timeout)
    if not ok:
        if err == "cancelled":
            return False, "已取消安装（安装 Equalizer APO 需要管理员权限）"
        return False, f"安装未能完成：{err}"

    tell("安装进程已结束，正在检查结果…")
    if not is_installed():
        return False, f"安装未成功（退出码 {code}），可能被安全软件拦截；已在临时目录保留安装包"
    if code not in (0, 1):  # 1 = 已安装后取消，视作可用
        return False, f"安装程序返回异常退出码 {code}"

    devices = enabled_devices()
    if not devices:
        return True, "Equalizer APO 已装好，但还没有设备启用——请打开「设备选择器」勾选音频设备"
    return True, f"Equalizer APO 安装完成，已对 {len(devices)} 个设备启用，重启电脑后生效"


def open_device_selector() -> Tuple[bool, str]:
    """打开官方设备选择器（需要管理员权限，用于给音频设备挂上 APO 滤镜）。"""
    root = install_dir()
    exe = None
    if root:
        for name in ("DeviceSelector.exe", "Configurator.exe"):
            if (root / name).is_file():
                exe = root / name
                break
    if exe is None:
        return False, "未找到设备选择器，请确认 Equalizer APO 已正确安装"
    ok, _code, err = run_elevated(exe, "", root, timeout=1800)
    if not ok:
        return False, "已取消" if err == "cancelled" else f"启动失败：{err}"
    return True, "设备选择器已关闭，勾选设备后请重启电脑"


def open_bundle_folder() -> Tuple[bool, str]:
    """备用通道：把内置安装包解到临时目录并在资源管理器里选中。"""
    setup = extract_bundle()
    if setup is None:
        return False, "内置安装包缺失"
    try:
        subprocess.Popen(["explorer", "/select,", str(setup)])
        return True, "已打开内置安装包所在目录"
    except Exception as exc:
        return False, f"打开目录失败：{exc}"


def status_summary() -> str:
    """给界面用的一行状态描述。"""
    if not is_installed():
        size = bundle_size_mb()
        tail = f"内置官方安装包 {size:.1f} MB，一键装好即可突破 100% 上限" if size else "未检测到安装"
        return f"未安装 · {tail}"
    devices = enabled_devices()
    if not devices:
        return "已安装 · 尚无设备启用 APO 滤镜（前级增益不会生效）"
    live = [name for name, state in devices if state == 1]
    if live:
        return f"已就绪 · {len(live)} 个在用设备已启用（如 {live[0][:22]}）"
    return f"已启用 {len(devices)} 个设备，但当前都不在用（插上耳机/音箱后生效）"
