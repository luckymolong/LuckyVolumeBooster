# -*- coding: utf-8 -*-
"""生成界面预览图：python capture_preview.py

输出五个页面截图，外加三套配色的对比图（均为第 1 页）。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QColor, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui import theme  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402

OUT = ROOT / "assets" / "preview"
OUT.mkdir(parents=True, exist_ok=True)


def grab(win, app, path: Path, page: int = 0) -> None:
    win.switch_page(page)
    for _ in range(8):
        app.processEvents()
    time.sleep(0.25)
    pm = win.grab()
    canvas = QPixmap(pm.size())
    # 高 DPI 屏幕下 grab() 返回物理像素，必须同步像素比
    canvas.setDevicePixelRatio(pm.devicePixelRatio())
    canvas.fill(QColor(theme.C["bg_deep"]))
    p = QPainter(canvas)
    p.drawPixmap(0, 0, pm)
    p.end()
    canvas.save(str(path), "PNG")
    print("saved:", path)


def main() -> int:
    app = QApplication([])
    win = MainWindow()
    win.show()
    for _ in range(8):
        app.processEvents()
    time.sleep(0.4)

    original = theme.current()
    names = ["live", "windows", "background", "video", "about"]
    for i, name in enumerate(names):
        grab(win, app, OUT / f"{i + 1}_{name}.png", i)

    # 三套配色对比图，不写入用户偏好
    for key in theme.THEME_ORDER:
        win._apply_theme(key, persist=False, notify=False)
        grab(win, app, OUT / f"theme_{key}.png", 0)

    # 响应式尺寸对比：紧凑 / 宽屏，各出实时页与窗口选择页
    win._apply_theme("sakura", persist=False, notify=False)
    for tag, size in (("compact", (820, 620)), ("wide", (1240, 810))):
        win.resize(*size)
        for _ in range(8):
            app.processEvents()
        time.sleep(0.25)
        grab(win, app, OUT / f"responsive_{tag}_live.png", 0)
        grab(win, app, OUT / f"responsive_{tag}_windows.png", 1)

    win._apply_theme(original, persist=False, notify=False)
    win.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
