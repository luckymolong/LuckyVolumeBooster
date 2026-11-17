# -*- coding: utf-8 -*-
"""可复用的自定义界面控件。"""
from __future__ import annotations

import math
import os

from PySide6.QtCore import QFileInfo, QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath,
    QPen, QPixmap, QRadialGradient,
)
from PySide6.QtWidgets import (
    QFileIconProvider, QFrame, QHBoxLayout, QLabel, QLayout, QPushButton,
    QSizeGrip, QSizePolicy, QSlider, QVBoxLayout, QWidget,
)

from . import theme


def set_cls(widget: QWidget, cls: str) -> None:
    """设置 QSS 属性选择器并立即刷新样式。"""
    widget.setProperty("cls", cls)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def make_label(text: str, cls: str = "") -> QLabel:
    lb = QLabel(text)
    if cls:
        set_cls(lb, cls)
    return lb


class ElideLabel(QLabel):
    """宽度不足时自动省略长文本，而不是硬截断或撑破布局。

    对应 UI UX Pro Max 的「resilient text / no clipping」规则：
    完整内容始终可通过 tooltip 访问。
    """
    def __init__(self, text: str = "", cls: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self._full = text or ""
        if cls:
            set_cls(self, cls)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(0)
        self._refresh()

    def setText(self, text: str) -> None:  # noqa: N802
        self._full = text or ""
        self._refresh()

    def full_text(self) -> str:
        return self._full

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        width = max(8, self.contentsRect().width())
        elided = self.fontMetrics().elidedText(self._full, Qt.ElideRight, width)
        super().setText(elided)
        self.setToolTip(self._full if elided != self._full else "")


class FlowLayout(QLayout):
    """自动换行的流式布局，用于按钮组 / 信息条，避免窄窗口下溢出。"""

    def __init__(self, parent=None, spacing: int = 8, margin: int = 0) -> None:
        super().__init__(parent)
        self._items: list = []
        self._spacing = spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:  # noqa: N802
        return len(self._items)

    def itemAt(self, index):  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        m = self.contentsMargins()
        return self._layout(QRect(0, 0, width, 0), True, m)

    def setGeometry(self, rect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._layout(rect, False, self.contentsMargins())

    def sizeHint(self):  # noqa: N802
        return self.minimumSize()

    def minimumSize(self):  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _layout(self, rect, test_only: bool, m) -> int:
        x = rect.x() + m.left()
        y = rect.y() + m.top()
        right = rect.right() - m.right()
        line_height = 0
        for item in self._items:
            hint = item.sizeHint()
            w, h = hint.width(), hint.height()
            if line_height > 0 and x + w > right:
                x = rect.x() + m.left()
                y += line_height + self._spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += w + self._spacing
            line_height = max(line_height, h)
        return y + line_height - rect.y() + m.bottom()


class ResizeGrip(QSizeGrip):
    """无边框窗口右下角的自定义尺寸把手。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self.setCursor(Qt.SizeFDiagCursor)
        self.setToolTip("拖动调整窗口大小")

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        color = QColor(theme.C["scroll_hover"])
        color.setAlpha(190)
        p.setPen(QPen(color, 1.5))
        for i in range(3):
            offset = 3 + i * 4
            p.drawLine(offset, 15, 15, offset)
        p.end()


class AtmosphereWidget(QWidget):
    """窗口根背景：底色渐变 + 多个柔光斑（frontend-design 的 atmosphere 层）。

    QSS 只负责圆角边框，实际背景在这里用 QPainter 绘制，
    这样三套主题切换时只需 update() 就能换掉整片光色。
    """
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("root")

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        radius = theme.RADIUS["lg"]
        path = QPainterPath()
        path.addRoundedRect(
            QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5), radius, radius
        )
        p.setClipPath(path)

        base = QLinearGradient(0, 0, rect.width(), rect.height())
        base.setColorAt(0, QColor(theme.C["bg_main"]))
        base.setColorAt(1, QColor(theme.C["bg_end"]))
        p.fillRect(rect, base)

        alpha = theme.C["glow_alpha"]
        spots = (
            (0.14, 0.10, 0.78, "glow_1"),
            (0.88, 0.90, 0.72, "glow_2"),
            (0.66, 0.16, 0.44, "glow_1"),
        )
        span = max(rect.width(), rect.height())
        for fx, fy, scale, key in spots:
            color = QColor(theme.C[key])
            gradient = QRadialGradient(
                rect.width() * fx, rect.height() * fy, span * scale
            )
            gradient.setColorAt(
                0, QColor(color.red(), color.green(), color.blue(),
                          int(255 * alpha))
            )
            gradient.setColorAt(
                1, QColor(color.red(), color.green(), color.blue(), 0)
            )
            p.fillRect(rect, gradient)

        # 极淡的斜向细线，给柔光一点材质感，不抢内容
        p.setClipping(False)
        line = QColor(theme.C["root_border"])
        line.setAlpha(70)
        p.setPen(QPen(line, 1))
        for x in range(-rect.height(), rect.width(), 46):
            p.drawLine(x, 0, x + rect.height(), rect.height())
        p.setPen(QPen(QColor(theme.C["root_border"]), 1))
        p.drawPath(path)
        p.end()


def gradient_icon(seed: str = "?") -> QIcon:
    """没有可执行文件时的渐变字母图标。"""
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    grad = QLinearGradient(0, 0, 64, 64)
    grad.setColorAt(0, QColor(theme.C["accent"]))
    grad.setColorAt(1, QColor(theme.C["accent_2"]))
    p.setBrush(QBrush(grad))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(0, 0, 64, 64), 17, 17)
    p.setPen(QColor(theme.C["on_accent"]))
    f = QFont("Segoe UI")
    f.setBold(True)
    f.setPointSize(27)
    p.setFont(f)
    p.drawText(QRectF(0, 0, 64, 64), Qt.AlignCenter, (seed or "?")[:1].upper())
    p.end()
    return QIcon(pm)


def exe_icon(exe: str, name: str = "") -> QIcon:
    if exe and os.path.isfile(exe):
        try:
            icon = QFileIconProvider().icon(QFileInfo(exe))
            if not icon.isNull():
                return icon
        except Exception:
            pass
    return gradient_icon(name or exe or "?")


class Card(QFrame):
    def __init__(self, alt: bool = False, parent=None) -> None:
        super().__init__(parent)
        set_cls(self, "card-alt" if alt else "card")


class Button(QPushButton):
    def __init__(self, text: str, cls: str = "", parent=None) -> None:
        super().__init__(text, parent)
        if cls:
            set_cls(self, cls)
        self.setCursor(Qt.PointingHandCursor)


class NavButton(QPushButton):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        set_cls(self, "nav")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(44)


class Divider(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        set_cls(self, "divider")
        self.setFixedHeight(1)


class SectionHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        lay.addWidget(make_label(title, "section"))
        if subtitle:
            sub = make_label(subtitle, "hint")
            sub.setWordWrap(True)
            lay.addWidget(sub)


class ToggleSwitch(QWidget):
    """滑动开关。"""
    toggled = Signal(bool)

    def __init__(self, state: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._on = bool(state)
        self.setFixedSize(42, 23)
        self.setCursor(Qt.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._on

    def setChecked(self, value: bool) -> None:
        value = bool(value)
        if value == self._on:
            return
        self._on = value
        self.update()
        self.toggled.emit(self._on)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.setChecked(not self._on)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if self._on:
            g = QLinearGradient(0, 0, w, 0)
            g.setColorAt(0, QColor(theme.C["accent"]))
            g.setColorAt(1, QColor(theme.C["accent_soft"]))
            p.setBrush(QBrush(g))
            p.setPen(Qt.NoPen)
        else:
            p.setBrush(QColor(theme.C["toggle_off"]))
            p.setPen(QPen(QColor(theme.C["toggle_border"]), 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), h / 2, h / 2)
        p.setBrush(QColor(theme.C["toggle_knob"]))
        p.setPen(Qt.NoPen)
        x = w - h + 1.5 if self._on else 2.5
        p.drawEllipse(QRectF(x, 3, h - 6, h - 6))
        p.end()


def peak_to_level(peak: float) -> float:
    """把线性峰值按 -60dB ~ 0dB 映射到 0~1，观感更接近真实电平表。"""
    if peak <= 1e-7:
        return 0.0
    db = 20 * math.log10(min(1.0, peak))
    return max(0.0, min(1.0, (db + 60.0) / 60.0))


class LevelBar(QWidget):
    """分段式实时电平表。"""
    def __init__(self, segments: int = 36, parent=None) -> None:
        super().__init__(parent)
        self._value = 0.0
        self._segments = segments
        self.setFixedHeight(5)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def setValue(self, peak: float) -> None:  # noqa: N802
        v = peak_to_level(peak)
        if abs(v - self._value) < 0.008:
            return
        self._value = v
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        n = self._segments
        gap = 2.0
        seg_w = (w - gap * (n - 1)) / n
        active = int(round(self._value * n))
        for i in range(n):
            x = i * (seg_w + gap)
            if i < active:
                t = i / max(1, n - 1)
                if t > 0.85:
                    color = QColor(theme.C["level_high"])
                elif t > 0.65:
                    color = QColor(theme.C["level_mid"])
                else:
                    low = QColor(theme.C["level_low"])
                    mid = QColor(theme.C["level_mid"])
                    f = t / 0.65
                    color = QColor(
                        int(low.red() + (mid.red() - low.red()) * f),
                        int(low.green() + (mid.green() - low.green()) * f),
                        int(low.blue() + (mid.blue() - low.blue()) * f),
                    )
                p.setBrush(color)
            else:
                p.setBrush(QColor(theme.C["level_off"]))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(x, 1, max(1.5, seg_w), h - 2), 2, 2)
        p.end()


class SessionCard(QFrame):
    """音频会话行：分隔线式列表项，替代原来「每条都套一张圆角卡片」。"""
    volumeChanged = Signal(str, float)
    muteToggled = Signal(str, bool)

    def __init__(self, info, icon: QIcon | None = None, parent=None) -> None:
        super().__init__(parent)
        set_cls(self, "row")
        self.setAttribute(Qt.WA_Hover, True)
        self.key = info.key
        self._icon_source = (info.exe, info.name)
        self._initial_icon = icon
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 9)
        root.setSpacing(5)

        top = QHBoxLayout()
        top.setSpacing(11)
        self.iconLabel = QLabel()
        self.iconLabel.setFixedSize(38, 38)
        self.iconLabel.setScaledContents(True)
        self.refresh_icon()
        top.addWidget(self.iconLabel)

        col = QVBoxLayout()
        col.setSpacing(3)
        self.nameLabel = ElideLabel(info.name)
        self.nameLabel.setStyleSheet("font-weight:700;")
        self.subLabel = ElideLabel("", "caption")
        col.addWidget(self.nameLabel)
        col.addWidget(self.subLabel)
        top.addLayout(col, 1)

        self.muteBtn = Button("静音", "iconbtn")
        self.muteBtn.setCheckable(True)
        self.muteBtn.setFixedWidth(62)
        top.addWidget(self.muteBtn, 0, Qt.AlignVCenter)

        self.pctLabel = make_label("100%", "row-num")
        self.pctLabel.setFixedWidth(76)
        self.pctLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        top.addWidget(self.pctLabel)
        root.addLayout(top)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setCursor(Qt.PointingHandCursor)
        root.addWidget(self.slider)

        self.level = LevelBar()
        root.addWidget(self.level)

        self.slider.valueChanged.connect(
            lambda v: self.volumeChanged.emit(self.key, v / 100.0)
        )
        self.muteBtn.toggled.connect(
            lambda on: (self.muteBtn.setText("已静音" if on else "静音"),
                        self.muteToggled.emit(self.key, on))
        )
        self.apply_data(info)

    def refresh_icon(self) -> None:
        """主题切换后重绘程序图标（无 exe 图标时用的是主题渐变字母图标）。"""
        exe, name = self._icon_source
        icon = self._initial_icon or exe_icon(exe, name)
        self.iconLabel.setPixmap(icon.pixmap(38, 38))

    def apply_data(self, info) -> None:
        self.key = info.key
        self.nameLabel.setText(info.name)
        sub = f"PID {info.pid}"
        if info.window_title:
            sub += f"   ·   {info.window_title}"
        elif info.is_background:
            sub += "   ·   后台进程 / 无窗口"
        dn = info.display_name or ""
        # 系统会话的 DisplayName 常是 @%SystemRoot%\... 之类的资源字符串，不展示
        if dn and not dn.startswith("@") and dn != info.name and len(dn) <= 36:
            sub += f"   ·   {dn}"
        self.subLabel.setText(sub)
        self.level.setValue(info.peak)
        if not self.slider.isSliderDown():
            self.slider.blockSignals(True)
            self.slider.setValue(info.percent)
            self.slider.blockSignals(False)
        self.pctLabel.setText(f"{info.percent}%")
        self.muteBtn.blockSignals(True)
        self.muteBtn.setChecked(info.muted)
        self.muteBtn.setText("已静音" if info.muted else "静音")
        self.muteBtn.blockSignals(False)


class WindowRow(QWidget):
    """窗口列表中的一行。"""
    def __init__(self, window, icon: QIcon | None = None, parent=None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(9, 5, 9, 5)
        lay.setSpacing(10)
        self.setMinimumHeight(52)
        ic = QLabel()
        ic.setFixedSize(30, 30)
        ic.setScaledContents(True)
        ic.setPixmap((icon or exe_icon(window.exe, window.process_name)).pixmap(30, 30))
        lay.addWidget(ic)
        col = QVBoxLayout()
        col.setSpacing(2)
        t = ElideLabel(window.title)
        t.setMinimumHeight(18)
        t.setStyleSheet("font-weight:650; font-size:12px;")
        s = ElideLabel(
            f"{window.process_name}   ·   PID {window.pid}   ·   {window.size_text}",
            "caption",
        )
        s.setMinimumHeight(15)
        col.addWidget(t)
        col.addWidget(s)
        lay.addLayout(col, 1)


class DropArea(QFrame):
    """支持拖放的视频文件选择区。"""
    fileDropped = Signal(str)
    clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        set_cls(self, "dropzone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(168)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(9)
        big = make_label("＋", "drop-plus")
        big.setAlignment(Qt.AlignCenter)
        lay.addWidget(big)
        t = QLabel("把视频拖到这里，或点击选择文件")
        t.setWordWrap(True)
        set_cls(t, "section")
        t.setAlignment(Qt.AlignCenter)
        lay.addWidget(t)
        s = QLabel("支持 MP4 / MKV / MOV / AVI / WebM / MP3 等，视频画面无损直拷")
        s.setWordWrap(True)
        set_cls(s, "hint")
        s.setAlignment(Qt.AlignCenter)
        lay.addWidget(s)

    def _highlight(self, on: bool) -> None:
        if on:
            self.setStyleSheet(
                f"background:{theme.C['bg_input']}; "
                f"border:2px dashed {theme.C['accent_2']}; border-radius:16px;"
            )
        else:
            # 清空内联样式，交还给 QSS（切换主题时会自动跟随）
            self.setStyleSheet("")

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._highlight(True)

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._highlight(False)

    def dropEvent(self, event) -> None:  # noqa: N802
        self._highlight(False)
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path:
                self.fileDropped.emit(path)
                event.acceptProposedAction()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.clicked.emit()


class InfoBanner(QFrame):
    """顶部提示条。"""
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        set_cls(self, "banner")
        self.setMinimumHeight(42)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        dot = QLabel("i")
        dot.setFixedSize(19, 19)
        dot.setAlignment(Qt.AlignCenter)
        set_cls(dot, "banner-dot")
        lay.addWidget(dot, 0, Qt.AlignTop)
        lb = make_label(text, "hint")
        lb.setWordWrap(True)
        lay.addWidget(lb, 1)
