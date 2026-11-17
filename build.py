# -*- coding: utf-8 -*-
"""一键打包为单文件 Windows GUI 程序：python build.py

产物：dist/LuckyVolumeBooster.exe
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
DIST = ROOT / "dist"


def make_icon() -> Path | None:
    """用标准库生成与界面 Logo 一致的 ICO 图标（渐变圆角 + 音量柱）。"""
    import math
    import struct
    import zlib

    size = 256
    heights = [62, 104, 150, 104, 62]

    def sd_round_box(px, py, hw, hh, r):
        qx, qy = abs(px) - hw + r, abs(py) - hh + r
        return min(max(qx, qy), 0.0) + math.hypot(max(qx, 0), max(qy, 0)) - r

    raw = bytearray()
    for y in range(size):
        raw.append(0)  # PNG filter: None
        py = y - size / 2 + 0.5
        for x in range(size):
            px = x - size / 2 + 0.5
            d = sd_round_box(px, py, size / 2 - 8, size / 2 - 8, 54)
            alpha = max(0.0, min(1.0, 0.5 - d))
            t = (x + y) / (2 * size)
            # 与默认「樱昼」主题一致：樱粉 -> 雾蓝，音量柱用纯白
            r = 198 + (126 - 198) * t
            g = 63 + (166 - 63) * t
            b = 107 + (216 - 107) * t
            bar_a = 0.0
            for i, bh in enumerate(heights):
                bd = sd_round_box(px - (i - 2) * 40, py, 13, bh / 2, 12)
                bar_a = max(bar_a, max(0.0, min(1.0, 0.5 - bd)))
            if bar_a > 0:
                r, g, b = (r * (1 - bar_a) + 255 * bar_a,
                           g * (1 - bar_a) + 255 * bar_a,
                           b * (1 - bar_a) + 255 * bar_a)
            raw += bytes((int(r), int(g), int(b), int(alpha * 255)))

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    ico = (struct.pack("<HHH", 0, 1, 1)
           + struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 22)
           + png)
    ASSETS.mkdir(exist_ok=True)
    path = ASSETS / "icon.ico"
    path.write_bytes(ico)
    return path


def locate_ffmpeg() -> Path | None:
    local = ASSETS / "ffmpeg.exe"
    if local.is_file() and local.stat().st_size > 1_000_000:
        return local
    try:
        import imageio_ffmpeg

        src = Path(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        found = shutil.which("ffmpeg")
        src = Path(found) if found else None
    if src and src.is_file():
        ASSETS.mkdir(exist_ok=True)
        shutil.copy2(src, local)
        return local
    return None


def main() -> int:
    icon = make_icon()
    print(f"[ok] 程序图标: {icon}")
    ffmpeg = locate_ffmpeg()
    if not ffmpeg:
        print("[!] 未找到 ffmpeg，视频增益功能将不可用（其余功能正常）")
    else:
        print(f"[ok] 内置 ffmpeg: {ffmpeg}  ({ffmpeg.stat().st_size / 1024 / 1024:.1f} MB)")

    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--onefile", "--windowed",
        "--name", "LuckyVolumeBooster",
        "--distpath", str(DIST),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT),
        "--hidden-import", "comtypes",
        "--hidden-import", "comtypes.client",
        "--hidden-import", "comtypes.automation",
        "--hidden-import", "comtypes.gen",
        "--hidden-import", "pycaw.pycaw",
        "--hidden-import", "win32gui",
        "--hidden-import", "win32process",
        "--hidden-import", "win32con",
        "--hidden-import", "psutil",
        "--hidden-import", "imageio_ffmpeg",
        "--collect-submodules", "pycaw",
        "--collect-submodules", "comtypes",
    ]
    if ffmpeg:
        args += ["--add-binary", f"{ffmpeg}{os.pathsep}."]
    avatar = ASSETS / "avatar.jpg"
    if avatar.is_file():
        args += ["--add-data", f"{avatar}{os.pathsep}."]
    else:
        print("[!] 未找到 assets/avatar.jpg，标题栏将显示兜底图标")
    if icon:
        args += ["--icon", str(icon)]
    args.append(str(ROOT / "main.py"))

    print("[..] 正在打包，首次打包约需 1-3 分钟…", flush=True)
    result = subprocess.run(args, cwd=str(ROOT))
    if result.returncode != 0:
        print("[!] 打包失败")
        return result.returncode
    exe = DIST / "LuckyVolumeBooster.exe"
    if exe.is_file():
        print(f"\n[完成] {exe}  ({exe.stat().st_size / 1024 / 1024:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
