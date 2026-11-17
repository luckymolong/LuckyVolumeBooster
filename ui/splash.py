# -*- coding: utf-8 -*-
"""启动动画：弹出圆形头像 + 作者名 + 网址，淡入停留淡出后进入主窗口。"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import (
    QPropertyAnimation, QRectF, Qt, QTimer, Signal,
)
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontDatabase, QLinearGradient, QPainter,
    QPainterPath, QPixmap, QPen, QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from . import theme
from .theme import BRAND_NAME, BRAND_SITE, BRAND_URL


def avatar_pixmap(diameter: int) -> QPixmap | None:
    """读取作者头像（frozen 时从 _MEIPASS 取），中心方裁剪后平滑缩放。"""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", ""))
        candidates = (base / "avatar.jpg", base / "assets" / "avatar.jpg")
    else:
        p = Path(__file__).resolve().parent.parent / "assets" / "avatar.jpg"
        candidates = (p,)
    for cand in candidates:
        if cand.is_file():
            pix = QPixmap(str(cand))
            if pix.isNull():
                break
            side = min(pix.width(), pix.height())
            x = (pix.width() - side) // 2
            y = (pix.height() - side) // 2
            return pix.copy(x, y, side, side).scaled(
                diameter * 4, diameter * 4,
                Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation,
            )
    return None


def _resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", ""))
    return Path(__file__).resolve().parent.parent


class Splash(QWidget):
    """无边框启动卡片：柔光氛围 + 头像 + 名字，淡入 → 停留 → 淡出。"""

    finished = Signal()

    FADE_IN_MS = 320
    HOLD_MS = 950
    FADE_OUT_MS = 420

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.SplashScreen | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._opacity = 0.0
        self._pix = avatar_pixmap(96)
        self._serif = self._pick_font()

        card_w, card_h = 360, 210
        self.setFixedSize(card_w + 80, card_h + 80)  # 外圈留给光晕
        screen = self.screen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(
                geo.x() + (geo.width() - self.width()) // 2,
                geo.y() + (geo.height() - self.height()) // 2,
            )

        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(self.FADE_IN_MS)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.finished.connect(self._hold)

    @staticmethod
    def _pick_font() -> str | None:
        db = QFontDatabase()
        for fam in ("Noto Serif SC", "Source Han Serif SC", "SimSun"):
            if fam in db.families():
                return fam
        return None

    # -------------------------------------------------- 流程控制
    def start(self) -> None:
        self.show()
        self._fade.start()

    def _hold(self) -> None:
        if self.windowOpacity() < 1.0:
            return  # 是淡出动画结束的信号，直接收尾
        QTimer.singleShot(self.HOLD_MS, self._fade_out)

    def _fade_out(self) -> None:
        self._fade.setDuration(self.FADE_OUT_MS)
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        try:
            self._fade.finished.disconnect(self._hold)
        except Exception:
            pass
        self._fade.finished.connect(self._done)
        self._fade.start()

    def _done(self) -> None:
        self.close()
        self.finished.emit()

    # -------------------------------------------------- 绘制
    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        C = theme.C

        cw, ch = 360, 210
        ox, oy = (self.width() - cw) // 2, (self.height() - ch) // 2

        # 主题色柔光光晕
        halo = QRadialGradient(self.width() / 2, self.height() / 2, cw / 1.4)
        halo_c = QColor(C["accent"])
        halo.setColorAt(0, QColor(halo_c.red(), halo_c.green(), halo_c.blue(), 90))
        halo.setColorAt(1, QColor(halo_c.red(), halo_c.green(), halo_c.blue(), 0))
        p.setBrush(halo)
        p.setPen(Qt.NoPen)
        p.drawEllipse(self.rect())

        # 卡片
        card = QRectF(ox, oy, cw, ch)
        p.setBrush(QColor(C["bg_card"]))
        p.setPen(QPen(QColor(C["border"]), 1))
        p.drawRoundedRect(card, 22, 22)

        # 顶部主题色条
        g = QLinearGradient(ox, oy, ox + cw, oy)
        g.setColorAt(0, QColor(C["accent"]))
        g.setColorAt(1, QColor(C["accent_soft"]))
        p.setBrush(QBrush(g))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(ox, oy, cw, 5), 2.5, 2.5)

        # 头像（圆形裁剪 + 细环）
        d = 96
        ax = ox + (cw - d) // 2
        ay = oy + 26
        ring = QRectF(ax - 2, ay - 2, d + 4, d + 4)
        if self._pix:
            clip = QPainterPath()
            clip.addEllipse(QRectF(ax, ay, d, d))
            p.save()
            p.setClipPath(clip)
            p.drawPixmap(QRectF(ax, ay, d, d).toRect(), self._pix)
            p.restore()
        else:
            grad = QLinearGradient(ax, ay, ax + d, ay + d)
            grad.setColorAt(0, QColor(C["accent"]))
            grad.setColorAt(1, QColor(C["accent_soft"]))
            p.setBrush(QBrush(grad))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(ax, ay, d, d))
            p.setPen(QColor(C["on_accent"]))
            f = QFont()
            f.setPixelSize(40)
            f.setBold(True)
            p.setFont(f)
            p.drawText(QRectF(ax, ay, d, d), Qt.AlignCenter, "L")
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(C["accent"]), 2))
        p.drawEllipse(ring)

        # 名字与副标题
        ty = ay + d + 14
        p.setPen(QColor(C["text"]))
        f = QFont(self._serif or QFont().family())
        f.setPixelSize(26)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(ox, ty, cw, 34), Qt.AlignHCenter | Qt.AlignVCenter, BRAND_NAME)

        p.setPen(QColor(C["text_dim"]))
        f2 = QFont()
        f2.setPixelSize(13)
        p.setFont(f2)
        p.drawText(
            QRectF(ox, ty + 36, cw, 20), Qt.AlignHCenter | Qt.AlignVCenter,
            "LUCKY VOLUME BOOSTER",
        )

        p.setPen(QColor(C["link"]))
        p.drawText(
            QRectF(ox, ty + 58, cw, 18), Qt.AlignHCenter | Qt.AlignVCenter, BRAND_URL,
        )
        p.end()


def splash_then_show(window) -> None:
    """播放启动动画，动画结束后 show 主窗口。window 需已创建但未显示。"""
    def _finish() -> None:
        window.show()

    if "--nosplash" in sys.argv:
        _finish()
        return
    try:
        splash = Splash()
        splash.finished.connect(_finish)
        splash.start()
    except Exception:
        _finish()
