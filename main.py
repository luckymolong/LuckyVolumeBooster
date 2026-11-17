# -*- coding: utf-8 -*-
"""Lucky Volume Booster - Windows 音频增强控制台，程序入口。"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication


def run_selfcheck() -> int:
    """供打包后验证：LuckyVolumeBooster.exe --selfcheck

    结果写到 exe 同目录的 selfcheck_result.txt（无控制台模式下也能查看）。
    """
    import traceback
    from pathlib import Path

    lines: list[str] = []
    try:
        from core.audio_core import AudioEngine
        from core.eq_apo import EqualizerAPO
        from core.video_core import find_ffmpeg
        from core.window_core import enum_visible_windows
        from ui.main_window import MainWindow

        app = QApplication(sys.argv[:1])
        engine = AudioEngine()
        sessions = engine.refresh()
        windows = enum_visible_windows()
        lines.append(f"python      = {sys.version.split()[0]}")
        lines.append(f"frozen      = {getattr(sys, 'frozen', False)}")
        lines.append(f"audio       = available={engine.available}, sessions={len(sessions)}")
        lines.append(f"windows     = {len(windows)}")
        lines.append(f"master      = {engine.get_master_volume() * 100:.1f}%")
        lines.append(f"ffmpeg      = {find_ffmpeg()}")
        lines.append(f"eq_apo      = {EqualizerAPO().status_text}")
        win = MainWindow()
        win.show()
        app.processEvents()
        lines.append(f"ui          = pages={win.stack.count()}, cards={len(win.live_cards)}")
        from ui.splash import avatar_pixmap
        splash_pix = avatar_pixmap(96)
        lines.append(
            "splash      = "
            + ("OK" if splash_pix is not None and not splash_pix.isNull() else "MISSING avatar")
        )
        win.close()
        lines.append("SELFCHECK: PASS")
    except Exception:
        lines.append("SELFCHECK: FAIL")
        lines.append(traceback.format_exc())

    try:
        (Path(sys.executable).resolve().parent / "selfcheck_result.txt").write_text(
            "\n".join(lines), encoding="utf-8"
        )
    except Exception:
        pass
    try:
        print("\n".join(lines))
    except Exception:
        pass
    return 0 if "SELFCHECK: PASS" in lines else 1


def main() -> int:
    if "--selfcheck" in sys.argv:
        return run_selfcheck()
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("Lucky Volume Booster")
    app.setOrganizationName("Lucky万山之龙")
    app.setStyle("Fusion")

    from ui.main_window import MainWindow
    from ui.splash import splash_then_show

    window = MainWindow()
    splash_then_show(window)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
