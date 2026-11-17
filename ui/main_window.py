# -*- coding: utf-8 -*-
"""主窗口：五个页面的完整交互逻辑。"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QRectF, QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QBrush, QColor, QDesktopServices, QLinearGradient, QPainter,
    QPainterPath, QRadialGradient, QPixmap, QPen,
)
from PySide6.QtWidgets import (
    QApplication, QBoxLayout, QButtonGroup, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QPlainTextEdit, QProgressBar, QScrollArea, QSlider, QStackedWidget,
    QVBoxLayout, QWidget,
)

from core import apo_install
from core.audio_core import AudioEngine, db_to_factor
from core.eq_apo import DOWNLOAD_URL, EqualizerAPO
from core.video_core import (
    SUPPORTED_EXTS, MediaInfo, build_command, default_output_path,
    find_ffmpeg, parse_progress, probe,
)
from core.window_core import (
    WindowInfo, enum_visible_windows, foreground_window, match_session_keys,
    pid_title_map,
)

from . import theme
from .theme import BRAND_NAME, BRAND_SITE, BRAND_URL
from .widgets import (
    AtmosphereWidget, Button, Card, Divider, DropArea, ElideLabel, FlowLayout,
    InfoBanner, LevelBar, NavButton, ResizeGrip, SessionCard, ToggleSwitch,
    WindowRow, exe_icon, gradient_icon, make_label, set_cls,
)

APP_TITLE = "Lucky Volume Booster"


class LogoMark(QWidget):
    """侧栏樱花标志：五瓣柔光 + 花心，替代通用的方块音量柱。"""
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(40, 40)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(20, 20)
        halo_color = QColor(theme.C["accent_2"])
        halo = QRadialGradient(0, 0, 20)
        halo.setColorAt(0, QColor(halo_color.red(), halo_color.green(),
                                 halo_color.blue(), 130))
        halo.setColorAt(1, QColor(halo_color.red(), halo_color.green(),
                                 halo_color.blue(), 0))
        p.setBrush(halo)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(-20, -20, 40, 40))

        for i in range(5):
            p.save()
            p.rotate(i * 72)
            petal = QLinearGradient(0, -14, 0, 3)
            petal.setColorAt(0, QColor(theme.C["accent"]))
            petal.setColorAt(1, QColor(theme.C["accent_2"]))
            p.setBrush(QBrush(petal))
            p.drawEllipse(QRectF(-5.4, -14, 10.8, 17))
            p.restore()
        p.setBrush(QColor(theme.C["on_accent"]))
        p.drawEllipse(QRectF(-3.4, -3.4, 6.8, 6.8))
        p.end()


class AvatarMark(QWidget):
    """标题栏头像：圆形裁剪 + 主题色细环，跟随主题重绘。"""
    def __init__(self, diameter: int = 36, parent=None) -> None:
        super().__init__(parent)
        self._d = diameter
        self.setFixedSize(diameter, diameter)
        self._pix = self._load_avatar()

    @staticmethod
    def _avatar_path() -> Path | None:
        if getattr(sys, "frozen", False):
            base = Path(getattr(sys, "_MEIPASS", ""))
            for cand in (base / "avatar.jpg", base / "assets" / "avatar.jpg"):
                if cand.is_file():
                    return cand
            return None
        p = Path(__file__).resolve().parent.parent / "assets" / "avatar.jpg"
        return p if p.is_file() else None

    def _load_avatar(self) -> QPixmap | None:
        path = self._avatar_path()
        if not path:
            return None
        pix = QPixmap(str(path))
        if pix.isNull():
            return None
        # 取中心正方形再缩放，避免头像被拉伸
        side = min(pix.width(), pix.height())
        x = (pix.width() - side) // 2
        y = (pix.height() - side) // 2
        return pix.copy(x, y, side, side).scaled(
            self._d * 4, self._d * 4,
            Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation,
        )

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        d = self._d
        rect = QRectF(1.5, 1.5, d - 3, d - 3)
        if self._pix and not self._pix.isNull():
            path_clip = rect
            p.save()
            p.setBrush(QColor(theme.C["bg_card"]))
            p.setPen(Qt.NoPen)
            p.drawEllipse(rect)
            clip = QPainterPath()
            clip.addEllipse(rect)
            p.setClipPath(clip)
            p.drawPixmap(rect.toRect(), self._pix)
            p.restore()
        else:
            # 头像缺失时的兜底：主题渐变圆 + 首字母
            g = QLinearGradient(0, 0, d, d)
            g.setColorAt(0, QColor(theme.C["accent"]))
            g.setColorAt(1, QColor(theme.C["accent_2"]))
            p.setBrush(QBrush(g))
            p.setPen(Qt.NoPen)
            p.drawEllipse(rect)
            p.setPen(QColor(theme.C["on_accent"]))
            f = p.font()
            f.setBold(True)
            p.setFont(f)
            p.drawText(rect, Qt.AlignCenter, "L")
        # 主题色细环
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(theme.C["accent"]), 1.6))
        p.drawEllipse(QRectF(1.5, 1.5, d - 3, d - 3))
        p.end()


class TitleBar(QWidget):
    """可拖动、双击最大化的自定义标题栏。"""
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("titlebar")
        self.setFixedHeight(64)
        self._drag_offset = None
        lay = QHBoxLayout(self)
        lay.setContentsMargins(30, 16, 18, 6)
        lay.setSpacing(6)
        col = QVBoxLayout()
        col.setSpacing(2)
        self.title = make_label("实时音频增强", "title")
        self.subtitle = make_label("自动发现所有正在发声的程序，按会话独立调节音量", "subtitle")
        col.addWidget(self.title)
        col.addWidget(self.subtitle)
        lay.addLayout(col, 1)

        for text, kind, cb in (
            ("—", "min", self._minimize),
            ("□", "max", self._maximize),
            ("×", "close", self._close),
        ):
            b = Button(text, "winbtn")
            b.setProperty("kind", kind)
            b.setFixedSize(34, 30)
            b.clicked.connect(cb)
            set_cls(b, "winbtn")
            lay.addWidget(b)

    def _window(self):
        return self.window()

    def _minimize(self):
        self._window().showMinimized()

    def _maximize(self):
        w = self._window()
        w.showNormal() if w.isMaximized() else w.showMaximized()

    def _close(self):
        self._window().close()

    def set_page(self, title: str, subtitle: str) -> None:
        self.title.setText(title)
        self.subtitle.setText(subtitle)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint()
                - self._window().frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset and (event.buttons() & Qt.LeftButton):
            if self._window().isMaximized():
                self._window().showNormal()
            self._window().move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_offset = None

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self._maximize()


class BoostWorker(QObject):
    """在后台线程跑 ffmpeg，避免阻塞界面；支持中途取消。"""
    progress = Signal(float)
    log = Signal(str)
    done = Signal(bool, str)

    def __init__(self, cmd, duration: float, dst: str) -> None:
        super().__init__()
        self.cmd = cmd
        self.duration = duration
        self.dst = dst
        self._cancelled = False
        self._proc = None

    def cancel(self) -> None:
        self._cancelled = True
        proc = self._proc
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass

    def run(self) -> None:
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            proc = subprocess.Popen(
                self.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, errors="replace", bufsize=1, creationflags=flags,
            )
            self._proc = proc
            for raw in proc.stdout:
                line = raw.strip()
                if not line:
                    continue
                pct = parse_progress(line, self.duration)
                if pct is not None:
                    self.progress.emit(pct)
                elif line.startswith(("frame=", "out_time", "total_size", "bitrate", "speed=")):
                    continue
                elif line.startswith("progress="):
                    continue
                else:
                    self.log.emit(line[:400])
            proc.wait()
            if self._cancelled:
                self.done.emit(False, "已取消处理")
                return
            ok = (
                proc.returncode == 0
                and os.path.isfile(self.dst)
                and os.path.getsize(self.dst) > 0
            )
            self.done.emit(ok, "增强完成，文件已导出" if ok else "处理失败，请查看日志")
        except Exception as exc:
            self.log.emit(f"[异常] {exc}")
            self.done.emit(False, str(exc))


class ProbeWorker(QObject):
    """在后台线程分析媒体音轨，避免选择大文件时界面假死。"""
    done = Signal(object, str)

    def __init__(self, path: str, ffmpeg: str) -> None:
        super().__init__()
        self.path = path
        self.ffmpeg = ffmpeg

    def run(self) -> None:
        try:
            info = probe(self.path, self.ffmpeg, sample_seconds=25)
        except Exception:
            info = None
        self.done.emit(info, self.path)


class APOInstallWorker(QObject):
    """后台静默安装内置 Equalizer APO —— 需要等待 UAC + 安装器结束，不能占用 UI 线程。"""
    status = Signal(str)
    done = Signal(bool, str)

    def __init__(self, action: str = "install") -> None:
        super().__init__()
        self.action = action

    def run(self) -> None:
        try:
            if self.action == "install":
                ok, msg = apo_install.install(self.status.emit)
            elif self.action == "selector":
                self.status.emit("请在「设备选择器」里勾选播放设备，然后点确定…")
                ok, msg = apo_install.open_device_selector()
            else:
                ok, msg = apo_install.open_bundle_folder()
        except Exception as exc:  # noqa: BLE001
            ok, msg = False, f"操作失败：{exc}"
        self.done.emit(ok, msg)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowSystemMenuHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(gradient_icon("L"))
        self.setStyleSheet(theme.stylesheet())
        # 按实际可用工作区自适应，兼容 125% / 150% / 200% DPI 缩放。
        # 最小尺寸降到可容纳单栏布局，用户可自由缩放窗口。
        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else None
        self.setMinimumSize(theme.BP["min_w"], theme.BP["min_h"])
        if avail and avail.width() > 0:
            w = max(theme.BP["min_w"], min(theme.BP["wide"], avail.width() - 80))
            h = max(theme.BP["min_h"], min(810, avail.height() - 60))
            self.resize(w, h)
            self.move(
                avail.x() + max(0, (avail.width() - w) // 2),
                avail.y() + max(0, (avail.height() - h) // 2),
            )
        else:
            self.resize(theme.BP["wide"], 810)

        self.engine = AudioEngine()
        self.eqapo = EqualizerAPO()
        self.sessions = []
        self.windows: list[WindowInfo] = []
        self.window_map = {}
        self.selected_window: WindowInfo | None = None

        self.live_cards: dict[str, SessionCard] = {}
        self.bg_cards: dict[str, SessionCard] = {}
        self.win_cards: dict[str, SessionCard] = {}

        self.master_baseline = self.engine.get_master_volume()
        self.tick_count = 0
        self.media: MediaInfo | None = None
        self.ffmpeg = find_ffmpeg()
        self.boost_thread: QThread | None = None
        self.boost_worker: BoostWorker | None = None
        self._density = ""
        self._page_layouts: list[QVBoxLayout] = []
        self._win_sig = None
        self._probe_thread: QThread | None = None
        self._probe_worker: ProbeWorker | None = None
        self._probe_seq = 0
        self._apo_thread: QThread | None = None
        self._apo_worker: APOInstallWorker | None = None
        self._eq_alt_mode = "bundle"
        self._auto_out = True
        self._boosting = False

        self._build_ui()
        self._build_toast()
        self.grip = ResizeGrip(self.centralWidget())
        self._init_master_ui()
        self.refresh_windows()
        self.refresh_sessions()
        self._apply_responsive(self.width())

        self.timer = QTimer(self)
        self.timer.setInterval(800)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    # ================================================================ 界面搭建
    def _build_ui(self) -> None:
        root = AtmosphereWidget()  # 自绘渐变 + 柔光斑背景
        self.root = root
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._build_sidebar(outer)

        right = QWidget()
        right.setObjectName("content")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        self.titlebar = TitleBar()
        rl.addWidget(self.titlebar)

        self.stack = QStackedWidget()
        rl.addWidget(self.stack, 1)
        outer.addWidget(right, 1)

        self._build_live_page()
        self._build_windows_page()
        self._build_background_page()
        self._build_video_page()
        self._build_about_page()
        self.stack.setCurrentIndex(0)

    def _build_sidebar(self, outer: QHBoxLayout) -> None:
        side = QWidget()
        side.setObjectName("sidebar")
        self.sidebar = side
        side.setFixedWidth(228)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(16, 22, 16, 16)
        lay.setSpacing(7)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        brand.addWidget(AvatarMark(40))
        col = QVBoxLayout()
        col.setSpacing(1)
        t = ElideLabel("LUCKY BOOSTER", "brand-title")
        s = make_label("音量增强控制台", "caption")
        col.addWidget(t)
        col.addWidget(s)
        brand.addLayout(col, 1)
        lay.addLayout(brand)
        lay.addSpacing(12)
        lay.addWidget(Divider())
        lay.addSpacing(8)

        self.nav_group = QButtonGroup(self)
        nav_items = [
            "  实时增强", "  窗口选择", "  后台程序", "  视频增益", "  关于作者",
        ]
        for i, text in enumerate(nav_items):
            b = NavButton(text)
            if i == 0:
                b.setChecked(True)
            self.nav_group.addButton(b, i)
            b.clicked.connect(lambda _, idx=i: self.switch_page(idx))
            lay.addWidget(b)

        lay.addStretch(1)

        # 主音量小控件
        mini = Card(alt=True)
        ml = QVBoxLayout(mini)
        ml.setContentsMargins(13, 12, 13, 12)
        ml.setSpacing(7)
        row = QHBoxLayout()
        row.addWidget(make_label("系统主音量", "caption"))
        self.side_master_label = make_label("--", "accent-value")
        self.side_master_label.setAlignment(Qt.AlignRight)
        row.addWidget(self.side_master_label)
        ml.addLayout(row)
        self.side_master = QSlider(Qt.Horizontal)
        self.side_master.setRange(0, 100)
        self.side_master.setCursor(Qt.PointingHandCursor)
        self.side_master.valueChanged.connect(self._on_side_master_changed)
        ml.addWidget(self.side_master)
        lay.addWidget(mini)

        lay.addSpacing(10)
        lay.addWidget(Divider())
        lay.addSpacing(4)

        # 配色主题切换：即时生效并记住选择
        lay.addWidget(make_label("外观", "hint"))
        trow = QHBoxLayout()
        trow.setSpacing(5)
        self.theme_group = QButtonGroup(self)
        for i, key in enumerate(theme.THEME_ORDER):
            b = Button(theme.label(key), "themebtn")
            b.setCheckable(True)
            b.setFixedHeight(26)
            b.setChecked(key == theme.current())
            b.clicked.connect(lambda _, k=key: self._apply_theme(k))
            self.theme_group.addButton(b, i)
            trow.addWidget(b)
        lay.addLayout(trow)
        lay.addSpacing(8)

        author = make_label(BRAND_NAME, "brand")
        lay.addWidget(author)
        site = Button(BRAND_SITE, "link")
        site.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(BRAND_URL)))
        site.setToolTip("点击访问个人网站")
        lay.addWidget(site)
        ver = make_label(f"v{theme.APP_VERSION}  ·  Windows", "caption")
        lay.addWidget(ver)

        outer.addWidget(side)

    def _page(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(30, 17, 30, 24)
        lay.setSpacing(13)
        self._page_layouts.append(lay)
        return w, lay

    def _scroll_body(self):
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        vbox = QVBoxLayout(body)
        vbox.setContentsMargins(2, 2, 10, 2)
        vbox.setSpacing(10)
        vbox.addStretch(1)
        area.setWidget(body)
        return area, vbox

    # ---------------------------------------------------------- 页 1 实时增强
    def _build_live_page(self) -> None:
        page, lay = self._page()
        lay.addWidget(InfoBanner(
            "Windows 把单个程序音量硬性限制在 100%，因此这里的「增益」是相对提升（例如把 30% 拉到 100%）。"
            "想突破 100% 请用下方 Equalizer APO 前级放大，或用「视频增益」对文件做真正的 dB 放大。"
        ))

        # Hero：左侧衬线大数字 + 右侧控制，非对称排版，不再是同款卡片堆叠
        ctrl = QFrame()
        set_cls(ctrl, "hero")
        cl = QHBoxLayout(ctrl)
        cl.setContentsMargins(24, 18, 24, 20)
        cl.setSpacing(24)
        self.ctrl_row = cl

        left = QVBoxLayout()
        left.setSpacing(2)
        left.addWidget(make_label("MASTER OUTPUT", "caption"))
        self.master_label = make_label("80%", "display-num")
        left.addWidget(self.master_label)
        left.addWidget(make_label("系统主音量", "hint"))
        cl.addLayout(left, 0)

        right = QVBoxLayout()
        right.setSpacing(10)
        right.addWidget(make_label("全局增强", "section"))
        right.addWidget(ElideLabel("一键把所有程序与系统输出调到最佳状态", "hint"))
        self.master_slider = QSlider(Qt.Horizontal)
        self.master_slider.setProperty("cls", "master")
        self.master_slider.setRange(0, 100)
        self.master_slider.setCursor(Qt.PointingHandCursor)
        self.master_slider.valueChanged.connect(self._on_master_slider_changed)
        right.addWidget(self.master_slider)

        b_all = Button("一键增强全部", "primary")
        b_all.clicked.connect(self.boost_all)
        b_restore = Button("恢复原始", "ghost")
        b_restore.clicked.connect(self.restore_all)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(b_all)
        actions.addWidget(b_restore)
        actions.addStretch(1)
        right.addLayout(actions)

        # 流式布局：窄窗口时 chip 自动换行，不会把页面最小宽度撑爆
        grow = FlowLayout(spacing=7)
        grow.addWidget(make_label("快速增益", "caption"))
        gain_chip_group = QButtonGroup(self)
        for db in (3, 6, 12, 18):
            b = Button(f"+{db} dB", "chip")
            b.setCheckable(True)
            b.clicked.connect(lambda _, d=db: self.apply_gain(d))
            gain_chip_group.addButton(b)
            grow.addWidget(b)
        grow.addWidget(make_label("自动刷新", "caption"))
        self.auto_toggle = ToggleSwitch(True)
        self.auto_toggle.toggled.connect(
            lambda on: self.toast("已开启自动监控" if on else "已暂停自动监控")
        )
        grow.addWidget(self.auto_toggle)
        self.gain_row = grow
        right.addLayout(grow)
        cl.addLayout(right, 1)
        lay.addWidget(ctrl)

        head = QHBoxLayout()
        self.session_count = make_label("活动音频会话  ·  0", "section")
        head.addWidget(self.session_count)
        head.addStretch(1)
        rbtn = Button("刷新", "ghost")
        rbtn.setFixedWidth(78)
        rbtn.clicked.connect(self.refresh_all)
        head.addWidget(rbtn)
        lay.addLayout(head)

        self.live_scroll, self.live_layout = self._scroll_body()
        lay.addWidget(self.live_scroll, 1)

        self.eq_card = self._build_eq_card()
        self.live_layout.insertWidget(0, self.eq_card)

        self.stack.addWidget(page)

    def _build_eq_card(self) -> Card:
        card = Card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 15, 18, 15)
        lay.setSpacing(11)
        top = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(ElideLabel("超频增益  ·  Equalizer APO", "section"))
        self.eq_status = ElideLabel(self.eqapo.status_text, "hint")
        col.addWidget(self.eq_status)
        top.addLayout(col, 1)
        self.eq_link_btn = Button("官网", "ghost")
        self.eq_link_btn.setToolTip("Equalizer APO 项目主页（安装包已随程序内置，无需前往）")
        self.eq_link_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(DOWNLOAD_URL)))
        top.addWidget(self.eq_link_btn)
        lay.addLayout(top)

        line = QHBoxLayout()
        line.setSpacing(12)
        self.eq_slider = QSlider(Qt.Horizontal)
        self.eq_slider.setRange(0, 24)
        self.eq_slider.setValue(12)
        self.eq_slider.setCursor(Qt.PointingHandCursor)
        self.eq_slider.valueChanged.connect(
            lambda v: self.eq_value.setText(f"+{v} dB")
        )
        line.addWidget(self.eq_slider, 1)
        self.eq_value = make_label("+12 dB", "section")
        self.eq_value.setFixedWidth(72)
        self.eq_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        line.addWidget(self.eq_value)
        apply_btn = Button("应用", "primary")
        apply_btn.setFixedWidth(86)
        apply_btn.clicked.connect(self.apply_eq_preamp)
        line.addWidget(apply_btn)
        reset_btn = Button("还原", "ghost")
        reset_btn.setFixedWidth(74)
        reset_btn.clicked.connect(self.restore_eq)
        line.addWidget(reset_btn)
        self.eq_line = line
        self.eq_apply_btn = apply_btn
        self.eq_reset_btn = reset_btn
        line.setContentsMargins(0, 0, 0, 0)
        self.eq_line_w = QWidget()
        self.eq_line_w.setLayout(line)
        lay.addWidget(self.eq_line_w)

        # 安装 / 设备选择动作行：只有「不能直接调前级」时才出现
        self.eq_action_row = QWidget()
        arow = QHBoxLayout(self.eq_action_row)
        arow.setContentsMargins(0, 0, 0, 0)
        arow.setSpacing(10)
        self.eq_install_btn = Button("一键安装 Equalizer APO", "primary")
        self.eq_install_btn.setToolTip("安装包已内置在程序里，无需另行下载")
        self.eq_install_btn.clicked.connect(self.install_eq_apo)
        arow.addWidget(self.eq_install_btn, 1)
        self.eq_alt_btn = Button("手动安装", "ghost")
        self.eq_alt_btn.setFixedWidth(96)
        self.eq_alt_btn.setToolTip("把内置安装包解到临时目录并在资源管理器中选中")
        self.eq_alt_btn.clicked.connect(self.open_apo_bundle)
        arow.addWidget(self.eq_alt_btn)
        lay.addWidget(self.eq_action_row)

        self.eq_explain = make_label("", "hint")
        self.eq_explain.setWordWrap(True)
        lay.addWidget(self.eq_explain)
        self._sync_eq_state()
        return card

    # ------------------------------------------------------- EQ 卡片状态机
    def _sync_eq_state(self) -> None:
        """三种状态：未安装 / 已安装但无设备启用 / 已就绪。"""
        if not hasattr(self, "eq_action_row"):
            return
        installed = self.eqapo.installed
        ready = self.eqapo.ready
        self.eq_status.setText(self.eqapo.status_text)
        self.eq_line_w.setVisible(ready)
        self.eq_action_row.setVisible(not ready)
        if ready:
            self.eq_explain.setText(
                "Equalizer APO 工作在音频驱动层，可对最终输出做真正的数字前级放大，不受 100% 上限约束。"
                "本工具只改 config.txt 且自动备份原文件，「还原」即可复位。"
            )
            return
        if not installed:
            size = apo_install.bundle_size_mb()
            tag = f"内置官方安装包 {size:.1f} MB" if size else "内置安装包缺失"
            self.eq_install_btn.setText("一键安装 Equalizer APO")
            self.eq_install_btn.setEnabled(True)
            self.eq_alt_btn.setText("手动安装")
            self.eq_alt_btn.setEnabled(True)
            self._eq_alt_mode = "bundle"
            self.eq_explain.setText(
                f"上方按钮会直接从程序里解出官方安装包（{tag}）并静默安装，"
                "只需在「用户账户控制」窗口点一次“是”，不用再去官网下载。"
                "安装完成后需要重启电脑，音频驱动才会挂上滤波器。"
            )
            return
        # 已安装但没有设备启用
        self.eq_install_btn.setText("打开设备选择器")
        self.eq_install_btn.setEnabled(True)
        self.eq_alt_btn.setText("重新安装")
        self.eq_alt_btn.setEnabled(True)
        self._eq_alt_mode = "install"
        self.eq_explain.setText(
            "驱动已装好，但还没有音频设备挂上 APO 滤镜，所以前级增益不会生效。"
            "点「打开设备选择器」，勾选你的扬声器 / 耳机（可勾「Troubleshooting options」里的全部），"
            "确定后重启电脑即可。"
        )

    # ---------------------------------------------------------- 页 2 窗口选择
    def _build_windows_page(self) -> None:
        page, lay = self._page()
        body = QHBoxLayout()
        body.setSpacing(13)
        self.win_body = body

        left = Card()
        self.win_left = left
        ll = QVBoxLayout(left)
        ll.setContentsMargins(13, 13, 13, 13)
        ll.setSpacing(9)
        srow = QHBoxLayout()
        self.win_search = QLineEdit()
        self.win_search.setPlaceholderText("搜索窗口标题 / 进程名…")
        self.win_search.textChanged.connect(self.filter_windows)
        srow.addWidget(self.win_search, 1)
        pick = Button("拾取", "ghost")
        pick.setFixedWidth(62)
        pick.setToolTip("点击后 5 秒内切换到目标窗口，自动选中")
        pick.clicked.connect(self.start_pick)
        self.pick_btn = pick
        srow.addWidget(pick)
        ref = Button("刷新", "ghost")
        ref.setFixedWidth(58)
        ref.clicked.connect(self.refresh_windows)
        srow.addWidget(ref)
        ll.addLayout(srow)
        self.win_list = QListWidget()
        self.win_list.setMinimumWidth(330)
        self.win_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.win_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.win_list.setUniformItemSizes(True)
        self.win_list.currentItemChanged.connect(self.on_window_selected)
        ll.addWidget(self.win_list, 1)
        body.addWidget(left, 4)

        right = Card()
        self.win_right = right
        rlv = QVBoxLayout(right)
        rlv.setContentsMargins(18, 16, 18, 16)
        rlv.setSpacing(11)
        self.detail_icon = QLabel()
        self.detail_icon.setFixedSize(46, 46)
        self.detail_icon.setScaledContents(True)
        rlv.addWidget(self.detail_icon)
        self.detail_title = make_label("未选择窗口", "section")
        self.detail_title.setWordWrap(True)
        rlv.addWidget(self.detail_title)
        self.detail_sub = make_label("从左侧列表选一个窗口，或点击「拾取」", "hint")
        self.detail_sub.setWordWrap(True)
        rlv.addWidget(self.detail_sub)
        rlv.addWidget(Divider())

        self.match_label = make_label("匹配音频会话：—", "caption")
        rlv.addWidget(self.match_label)
        vrow = QHBoxLayout()
        vrow.addWidget(make_label("目标音量", "caption"))
        self.win_volume_label = make_label("100%", "section")
        vrow.addWidget(self.win_volume_label)
        vrow.addStretch(1)
        rlv.addLayout(vrow)
        self.win_slider = QSlider(Qt.Horizontal)
        self.win_slider.setRange(0, 100)
        self.win_slider.setValue(100)
        self.win_slider.setCursor(Qt.PointingHandCursor)
        self.win_slider.valueChanged.connect(
            lambda v: self.win_volume_label.setText(f"{v}%")
        )
        rlv.addWidget(self.win_slider)
        brow = QHBoxLayout()
        b_apply = Button("应用到此窗口", "primary")
        b_apply.setMinimumHeight(34)
        b_apply.clicked.connect(self.apply_to_window)
        brow.addWidget(b_apply)
        b_max = Button("拉满 100%", "ghost")
        b_max.setMinimumHeight(34)
        b_max.clicked.connect(lambda: (self.win_slider.setValue(100), self.apply_to_window()))
        brow.addWidget(b_max)
        rlv.addLayout(brow)
        rlv.addWidget(make_label("该窗口的音频会话", "caption"))
        self.win_scroll, self.win_layout = self._scroll_body()
        self.win_scroll.setMinimumHeight(160)
        rlv.addWidget(self.win_scroll, 1)
        rlv.addWidget(InfoBanner(
            "浏览器 / 游戏常把音频放在子进程，本工具会自动关联同一进程树及同名进程的全部音频会话。"
        ))
        body.addWidget(right, 5)
        lay.addLayout(body, 1)
        self.stack.addWidget(page)

    # ---------------------------------------------------------- 页 3 后台程序
    def _build_background_page(self) -> None:
        page, lay = self._page()
        bar = QHBoxLayout()
        self.bg_count = make_label("后台音频会话  ·  0", "section")
        bar.addWidget(self.bg_count)
        bar.addStretch(1)
        b = Button("全部拉满 100%", "primary")
        b.clicked.connect(self.boost_background)
        bar.addWidget(b)
        lay.addLayout(bar)
        lay.addWidget(InfoBanner(
            "提示：WASAPI 只会为「当前正在播放声音」的程序创建音频会话。"
            "没在发声的程序既不需要、也无法设置音量；开始播放后会自动出现在这里。"
        ))
        self.bg_scroll, self.bg_layout = self._scroll_body()
        lay.addWidget(self.bg_scroll, 1)
        self.stack.addWidget(page)

    # ---------------------------------------------------------- 页 4 视频增益
    def _build_video_page(self) -> None:
        page, lay = self._page()
        self.drop = DropArea()
        self.drop.fileDropped.connect(self.load_media)
        self.drop.clicked.connect(self.choose_media)
        lay.addWidget(self.drop)

        info = Card(alt=True)
        il = QHBoxLayout(info)
        self.media_info_layout = il
        il.setContentsMargins(16, 12, 16, 12)
        il.setSpacing(18)
        self.media_name = make_label("尚未选择文件", "section")
        il.addWidget(self.media_name, 3)
        self.media_meta = make_label("", "hint")
        il.addWidget(self.media_meta, 2)
        self.media_meta.hide()
        self.media_level = make_label("", "hint")
        il.addWidget(self.media_level, 2)
        self.media_level.hide()
        lay.addWidget(info)

        cfg = Card()
        cv = QVBoxLayout(cfg)
        cv.setContentsMargins(18, 15, 18, 15)
        cv.setSpacing(12)
        mode = FlowLayout(spacing=7)
        mode.addWidget(make_label("增益模式", "caption"))
        self.mode_manual = Button("手动增益", "chip")
        self.mode_manual.setCheckable(True)
        self.mode_manual.setChecked(True)
        self.mode_auto = Button("自动归一化到 -1 dB", "chip")
        self.mode_auto.setCheckable(True)
        mg = QButtonGroup(self)
        mg.addButton(self.mode_manual)
        mg.addButton(self.mode_auto)
        self.mode_manual.clicked.connect(self.on_mode_changed)
        self.mode_auto.clicked.connect(self.on_mode_changed)
        mode.addWidget(self.mode_manual)
        mode.addWidget(self.mode_auto)
        self.gain_value_label = make_label("+6.0 dB  (2.00×)", "section")
        mode.addWidget(self.gain_value_label)
        cv.addLayout(mode)

        grow = QHBoxLayout()
        grow.setSpacing(12)
        self.gain_slider = QSlider(Qt.Horizontal)
        self.gain_slider.setRange(0, 240)   # 0.0 ~ 24.0 dB，精度 0.1
        self.gain_slider.setValue(60)
        self.gain_slider.setCursor(Qt.PointingHandCursor)
        self.gain_slider.valueChanged.connect(self.on_gain_slider)
        grow.addWidget(self.gain_slider, 1)
        limiter_label = make_label("防削波限幅", "caption")
        grow.addWidget(limiter_label)
        self.limiter_toggle = ToggleSwitch(True)
        grow.addWidget(self.limiter_toggle)
        cv.addLayout(grow)

        outrow = QHBoxLayout()
        outrow.addWidget(make_label("输出", "caption"))
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("选择文件后自动生成输出路径")
        self.out_edit.textEdited.connect(self._on_out_edited)
        outrow.addWidget(self.out_edit, 1)
        bo = Button("浏览", "ghost")
        bo.setFixedWidth(72)
        bo.clicked.connect(self.choose_output)
        outrow.addWidget(bo)
        cv.addLayout(outrow)
        lay.addWidget(cfg)

        runrow = QHBoxLayout()
        self.run_row = runrow
        self.run_btn = Button("开始增强", "primary")
        self.run_btn.setFixedWidth(150)
        self.run_btn.setEnabled(False)
        self.run_btn.clicked.connect(self.start_boost)
        runrow.addWidget(self.run_btn)
        self.open_btn = Button("打开输出文件夹", "ghost")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self.open_output)
        runrow.addWidget(self.open_btn)
        runrow.addStretch(1)
        self.progress_label = make_label("就绪", "hint")
        runrow.addWidget(self.progress_label)
        lay.addLayout(runrow)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        lay.addWidget(self.progress)
        self.log = QPlainTextEdit()
        self.log.setProperty("cls", "log")
        set_cls(self.log, "log")
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(118)
        self.log.setPlaceholderText("处理日志会显示在这里…")
        lay.addWidget(self.log)
        self.stack.addWidget(page)

    # ---------------------------------------------------------- 页 5 关于
    def _build_about_page(self) -> None:
        page, lay = self._page()
        hero = Card()
        hl = QVBoxLayout(hero)
        hl.setContentsMargins(28, 28, 28, 26)
        hl.setSpacing(10)
        cap = make_label("DEVELOPED BY", "caption")
        hl.addWidget(cap)
        name = make_label(BRAND_NAME, "hero-name")
        hl.addWidget(name)
        desc = make_label(
            "Lucky Volume Booster  ·  Windows 音频增强控制台", "hint"
        )
        hl.addWidget(desc)
        site = Button("访问个人网站  ·  " + BRAND_SITE, "primary")
        site.setFixedWidth(280)
        site.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(BRAND_URL)))
        hl.addWidget(site)
        lay.addWidget(hero)

        feat = Card()
        fl = QVBoxLayout(feat)
        fl.setContentsMargins(22, 18, 22, 18)
        fl.setSpacing(9)
        fl.addWidget(make_label("功能一览", "section"))
        for line in (
            "实时监控所有活动音频会话，独立调节每个程序音量与静音状态",
            "按 dB 快速提升、一键拉满、原始音量一键还原",
            "枚举桌面窗口并自动关联对应进程（含子进程音频）的音量",
            "单独列出并增强无窗口的后台发声程序",
            "视频 / 音频文件 dB 增益、自动归一化、防削波限幅、画面无损导出",
            "内置 Equalizer APO 官方安装包，一键装好驱动层前级放大，实现真正的 100% 以上全局增益",
        ):
            row = QHBoxLayout()
            dot = make_label("·", "dot")
            dot.setFixedWidth(14)
            row.addWidget(dot, 0, Qt.AlignTop)
            lb = make_label(line, "hint")
            lb.setWordWrap(True)
            row.addWidget(lb, 1)
            fl.addLayout(row)
        lay.addWidget(feat)

        tech = Card(alt=True)
        tl = QVBoxLayout(tech)
        tl.setContentsMargins(22, 18, 22, 18)
        tl.setSpacing(8)
        tl.addWidget(make_label("关于「超过 100%」这件事", "section"))
        txt = make_label(
            "Windows 的 WASAPI 会话接口把每个程序音量限制在 0~100%，这是系统级硬限制，"
            "任何用户态软件都无法单靠 API 把某个窗口推到 200%。本工具因此提供三条真实可行的路径：\n"
            "① 会话级相对增益 + 系统主音量拉满（无需额外安装，听感提升最直接）；\n"
            "② 文件级 DSP 放大（ffmpeg volume + alimiter，可任意 +dB，导出后在任何设备都生效）；\n"
            "③ Equalizer APO 驱动层 Preamp（全局真·超频，安装包已内置在程序里、一键静默安装，"
            "本工具自动写配置并备份；装完需重启一次）。",
            "hint",
        )
        txt.setWordWrap(True)
        tl.addWidget(txt)
        lay.addWidget(tech)
        lay.addStretch(1)
        foot = make_label(
            f"{BRAND_NAME}   ·   {BRAND_SITE}   ·   v{theme.APP_VERSION}", "caption"
        )
        foot.setAlignment(Qt.AlignCenter)
        lay.addWidget(foot)
        self.stack.addWidget(page)

    def _build_toast(self) -> None:
        self.toast_label = QLabel(self.centralWidget())
        self._style_toast(None)
        self.toast_label.hide()

    def _style_toast(self, accent: str | None) -> None:
        c = theme.C
        self.toast_label.setStyleSheet(
            f"background:{c['bg_card']}; color:{c['text']}; "
            f"border:1px solid {accent or c['accent']};"
            "border-radius:10px; padding:9px 18px; font-weight:600;"
        )

    def toast(self, msg: str, ok: bool = True) -> None:
        prefix = "完成  ·  " if ok else "提示  ·  "
        color = theme.C["success"] if ok else theme.C["warning"]
        self._style_toast(color)
        self.toast_label.setText(prefix + msg)
        self.toast_label.adjustSize()
        self.toast_label.move(
            max(20, (self.width() - self.toast_label.width()) // 2),
            self.height() - 78,
        )
        self.toast_label.show()
        self.toast_label.raise_()
        QTimer.singleShot(2600, self.toast_label.hide)

    # ================================================================ 响应式
    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        # 构造早期 resize() 也会触发本事件，此时页面尚未建好
        if hasattr(self, "sidebar") and hasattr(self, "win_body"):
            self._apply_responsive(self.width())

    def _apply_responsive(self, width: int) -> None:
        """按窗口宽度切换密度 / 布局方向，避免窄窗口挤压与横向溢出。"""
        compact = width < theme.BP["compact"]
        density = "compact" if compact else "normal"
        if density != self._density:
            self._density = density
            self.root.setProperty("density", density)
            for widget in self.findChildren(QWidget):
                widget.style().unpolish(widget)
                widget.style().polish(widget)

        self.sidebar.setFixedWidth(176 if compact else 228)
        side_layout = self.sidebar.layout()
        if side_layout:
            m = 10 if compact else 16
            side_layout.setContentsMargins(m, 22, m, 16)

        for lay in self._page_layouts:
            hpad = 16 if compact else theme.SPACE["page"]
            lay.setContentsMargins(hpad, 12 if compact else 17, hpad,
                                   16 if compact else 24)
        self.titlebar.setFixedHeight(52 if compact else 64)
        self.titlebar.subtitle.setVisible(not compact)

        vertical = QBoxLayout.TopToBottom
        horizontal = QBoxLayout.LeftToRight
        # 窄窗口：窗口选择页由左右双栏改为上下堆叠；说明/按钮行、媒体信息行同理
        self.win_body.setDirection(vertical if compact else horizontal)
        self.ctrl_row.setDirection(vertical if compact else horizontal)
        self.media_info_layout.setDirection(vertical if compact else horizontal)
        self.eq_line.setDirection(vertical if compact else horizontal)
        self.win_list.setMinimumWidth(0 if compact else 330)
        self.win_scroll.setMinimumHeight(0 if compact else 160)
        if compact:
            self.win_left.setMinimumHeight(210)
            self.win_left.setMaximumHeight(280)
            self.win_right.setMinimumHeight(0)
        else:
            self.win_left.setMinimumHeight(0)
            self.win_left.setMaximumHeight(0xFFFFFF)
            self.win_right.setMinimumHeight(0)
        self.log.setMaximumHeight(80 if compact else 118)
        self.drop.setMinimumHeight(120 if compact else 168)

        for card in (list(self.live_cards.values()) + list(self.bg_cards.values())
                     + list(self.win_cards.values())):
            lay = card.layout()
            if lay:
                m = 10 if compact else 15
                lay.setContentsMargins(m, 8 if compact else 12, m,
                                       8 if compact else 12)
        if hasattr(self, "grip"):
            self.grip.move(max(0, self.width() - 22), max(0, self.height() - 22))
            self.grip.raise_()

    # ================================================================ 导航
    def _apply_theme(self, name: str, persist: bool = True,
                     notify: bool = True) -> None:
        """切换配色：重刷 QSS、重绘自绘控件与图标，并记住选择。"""
        theme.set_theme(name, persist=persist)
        self.setStyleSheet(theme.stylesheet())
        self.root.update()  # 立刻重绘柔光氛围层
        for widget in self.findChildren(QWidget):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        for cls in (LevelBar, ToggleSwitch, LogoMark, ResizeGrip, AvatarMark):
            for widget in self.findChildren(cls):
                widget.update()
        for card in (list(self.live_cards.values())
                     + list(self.bg_cards.values())
                     + list(self.win_cards.values())):
            card.refresh_icon()
        self.drop.setStyleSheet("")
        self._style_toast(None)
        self.setWindowIcon(gradient_icon("L"))
        for i, key in enumerate(theme.THEME_ORDER):
            btn = self.theme_group.button(i)
            if btn:
                btn.blockSignals(True)
                btn.setChecked(key == name)
                btn.blockSignals(False)
        if notify:
            self.toast(f"已切换到「{theme.label(name)}」配色")

    def switch_page(self, idx: int) -> None:
        titles = [
            ("实时音频增强", "自动发现所有正在发声的程序，按会话独立调节音量"),
            ("选择桌面窗口", "选中窗口即可单独提高它对应程序的音量，自动关联子进程音频"),
            ("后台程序增强", "无可见窗口但正在发声的后台进程，如播放器 / 通讯软件 / 游戏服务"),
            ("视频音量增益", "真正的 dB 放大（可超 100%），视频画面直接拷贝、画质无损"),
            ("关于作者", "开发者信息与技术实现说明"),
        ]
        self.stack.setCurrentIndex(idx)
        self.titlebar.set_page(*titles[idx])
        btn = self.nav_group.button(idx)
        if btn:
            btn.setChecked(True)
            # 让键盘焦点跟随选中项，避免焦点环与选中态落在两个按钮上
            btn.setFocus()

    # ================================================================ 数据刷新
    def refresh_windows(self, force: bool = False) -> None:
        """增量刷新：窗口集合没变就不重建列表，避免定时刷新清掉搜索/选中/滚动。"""
        wins = enum_visible_windows(include_self=False)
        signature = [(w.hwnd, w.title, w.pid) for w in wins]
        if not force and signature == self._win_sig:
            return
        self._win_sig = signature
        prev = self.selected_window.hwnd if self.selected_window else None
        scroll = self.win_list.verticalScrollBar().value()
        self.windows = wins
        self.window_map = pid_title_map(wins)
        self.win_list.blockSignals(True)
        self.win_list.clear()
        for w in wins:
            item = QListWidgetItem(self.win_list)
            row = WindowRow(w)
            item.setSizeHint(QSize(300, 54))
            item.setData(Qt.UserRole, w.hwnd)
            item.setData(Qt.UserRole + 1,
                         f"{w.title} {w.process_name} {w.pid}".lower())
            self.win_list.addItem(item)
            self.win_list.setItemWidget(item, row)
        self.win_list.blockSignals(False)

        target = prev
        if target is None and self.win_list.count():
            target = self.win_list.item(0).data(Qt.UserRole)
        if target is not None:
            for i in range(self.win_list.count()):
                if self.win_list.item(i).data(Qt.UserRole) == target:
                    self.win_list.setCurrentRow(i)
                    break
        self.filter_windows(self.win_search.text())
        self.win_list.verticalScrollBar().setValue(scroll)
        self._sync_window_cards()

    def refresh_sessions(self) -> None:
        self.sessions = self.engine.refresh(self.window_map)
        live = self.sessions
        background = [s for s in self.sessions if s.is_background]
        self._sync_cards(self.live_layout, self.live_cards, live, anchor=self.eq_card)
        self._sync_cards(self.bg_layout, self.bg_cards, background)
        self.session_count.setText(f"活动音频会话  ·  {len(live)}")
        self.bg_count.setText(f"后台音频会话  ·  {len(background)}")
        self._sync_window_cards()

    def _sync_cards(self, layout: QVBoxLayout, store: dict, infos,
                    anchor: QWidget | None = None) -> None:
        keys = {i.key for i in infos}
        for key in list(store):
            if key not in keys:
                widget = store.pop(key)
                layout.removeWidget(widget)
                widget.setParent(None)
                widget.deleteLater()
        for info in infos:
            card = store.get(info.key)
            if card is None:
                card = SessionCard(info)
                card.volumeChanged.connect(self.on_card_volume)
                card.muteToggled.connect(self.on_card_mute)
                store[info.key] = card
                if anchor is not None:
                    pos = layout.indexOf(anchor)
                    idx = pos if pos >= 0 else max(0, layout.count() - 1)
                else:
                    idx = max(0, layout.count() - 1)
                layout.insertWidget(idx, card)
            else:
                card.apply_data(info)

    def _sync_window_cards(self) -> None:
        if self.selected_window is None:
            keys = []
            self.match_label.setText("匹配音频会话：—")
        else:
            keys = match_session_keys(self.selected_window, self.sessions)
            self.match_label.setText(
                f"匹配音频会话：{len(keys)} 条" if keys else "该窗口暂无活动音频会话（播放声音后自动出现）"
            )
        infos = [s for s in self.sessions if s.key in keys]
        self._sync_cards(self.win_layout, self.win_cards, infos)

    def refresh_all(self) -> None:
        self.refresh_windows(force=True)
        self.refresh_sessions()
        self.toast("已刷新窗口与音频会话")

    def _tick(self) -> None:
        # 「拾取窗口」期间暂停自动刷新，避免打断用户刚切过去的窗口
        if not self.auto_toggle.isChecked() or getattr(self, "_picking", False):
            return
        self.tick_count += 1
        self.refresh_sessions()
        if self.tick_count % 5 == 0:
            self.refresh_windows()
            cur = self.engine.get_master_volume()
            v = int(round(cur * 100))
            if not self.master_slider.isSliderDown():
                self.master_slider.blockSignals(True)
                self.master_slider.setValue(v)
                self.master_slider.blockSignals(False)
                self.master_label.setText(f"{v}%")
            if not self.side_master.isSliderDown():
                self.side_master.blockSignals(True)
                self.side_master.setValue(v)
                self.side_master.blockSignals(False)
                self.side_master_label.setText(f"{v}%")

    def _set_master(self, v: int, source) -> None:
        """两个主音量滑块即时双向同步，不再依赖 4 秒一次的定时刷新。"""
        self.engine.set_master_volume(v / 100.0)
        self.master_label.setText(f"{v}%")
        self.side_master_label.setText(f"{v}%")
        for slider in (self.master_slider, self.side_master):
            if slider is not source and slider.value() != v:
                slider.blockSignals(True)
                slider.setValue(v)
                slider.blockSignals(False)

    def _on_master_slider_changed(self, v: int) -> None:
        self._set_master(v, self.master_slider)

    def _on_side_master_changed(self, v: int) -> None:
        self._set_master(v, self.side_master)

    def _init_master_ui(self) -> None:
        """启动时把真实系统主音量同步到两个滑块，避免出现 0% / -- 的假初值。"""
        v = int(round(self.master_baseline * 100))
        for slider, label in (
            (self.master_slider, self.master_label),
            (self.side_master, self.side_master_label),
        ):
            slider.blockSignals(True)
            slider.setValue(v)
            slider.blockSignals(False)
            label.setText(f"{v}%")

    # ================================================================ 音量操作
    def on_card_volume(self, key: str, value: float) -> None:
        self.engine.set_volume(key, value)

    def on_card_mute(self, key: str, muted: bool) -> None:
        self.engine.set_mute(key, muted)

    def apply_gain(self, db: float) -> None:
        capped = sum(1 for s in self.sessions if s.volume >= 0.995)
        n = self.engine.apply_gain(self.sessions, db)
        extra = f"，{capped} 个已在 100% 上限" if capped else ""
        self.toast(f"已按 +{db} dB 提升 {n} 个会话（{db_to_factor(db):.2f}×{extra}）")
        self.refresh_sessions()

    def boost_all(self) -> None:
        n = self.engine.max_all(self.sessions)
        self.engine.set_master_volume(1.0)
        self.engine.set_master_mute(False)
        self.master_slider.setValue(100)
        self.toast(f"已拉满 {n} 个会话与系统主音量")
        self.refresh_sessions()

    def restore_all(self) -> None:
        n = self.engine.restore_all(self.sessions)
        self.engine.set_master_volume(self.master_baseline)
        v = int(round(self.master_baseline * 100))
        self.master_slider.setValue(v)
        self.toast(f"已恢复 {n} 个会话与原始主音量 {v}%")
        self.refresh_sessions()

    def boost_background(self) -> None:
        targets = [s for s in self.sessions if s.is_background]
        n = self.engine.max_all(targets)
        self.toast(f"已拉满 {n} 个后台程序")
        self.refresh_sessions()

    # ================================================================ 窗口页
    def filter_windows(self, text: str) -> None:
        q = (text or "").lower().strip()
        for i in range(self.win_list.count()):
            item = self.win_list.item(i)
            item.setHidden(bool(q) and q not in (item.data(Qt.UserRole + 1) or ""))

    def on_window_selected(self, current, previous=None) -> None:
        if current is None:
            self.selected_window = None
            return
        hwnd = current.data(Qt.UserRole)
        self.selected_window = next((w for w in self.windows if w.hwnd == hwnd), None)
        if self.selected_window is None:
            return
        w = self.selected_window
        self.detail_icon.setPixmap(exe_icon(w.exe, w.process_name).pixmap(46, 46))
        self.detail_title.setText(w.title[:90])
        self.detail_sub.setText(
            f"{w.process_name}   ·   PID {w.pid}   ·   {w.size_text}   ·   {w.class_name}"
        )
        self._sync_window_cards()

    def start_pick(self) -> None:
        if getattr(self, "_picking", False):
            return
        self._picking = True
        self._pick_left = 34  # 34 * 150ms ≈ 5s
        self.pick_btn.setText("切换…")
        self.toast("5 秒内请切换到目标窗口", ok=False)

        def check():
            if not getattr(self, "_picking", False):
                return
            self._pick_left -= 1
            fw = foreground_window()
            if fw and fw.pid != os.getpid() and fw.title:
                for w in self.windows:
                    if w.hwnd == fw.hwnd or (w.pid == fw.pid and w.title == fw.title):
                        for i in range(self.win_list.count()):
                            if self.win_list.item(i).data(Qt.UserRole) == w.hwnd:
                                self.win_list.setCurrentRow(i)
                                break
                        self._finish_pick(True)
                        return
                # 窗口可能刚出现，强制刷新后再找
                self.refresh_windows(force=True)
                for i in range(self.win_list.count()):
                    if self.win_list.item(i).data(Qt.UserRole) == fw.hwnd:
                        self.win_list.setCurrentRow(i)
                        self._finish_pick(True)
                        return
            if self._pick_left <= 0:
                self._finish_pick(False)
            else:
                QTimer.singleShot(150, check)

        QTimer.singleShot(150, check)

    def _finish_pick(self, ok: bool) -> None:
        self._picking = False
        self.pick_btn.setText("拾取")
        if ok:
            self.toast("已选中前台窗口")
        else:
            self.toast("未捕捉到窗口，请从列表手动选择", ok=False)

    def apply_to_window(self) -> None:
        if self.selected_window is None:
            self.toast("请先选择一个窗口", ok=False)
            return
        keys = match_session_keys(self.selected_window, self.sessions)
        if not keys:
            # 会话可能刚出现，先刷新再匹配一次，避免误报「不支持」
            self.refresh_sessions()
            keys = match_session_keys(self.selected_window, self.sessions)
        if not keys:
            self.toast("该窗口暂无活动音频会话：请让它播放声音后重试", ok=False)
            return
        value = self.win_slider.value() / 100.0
        for key in keys:
            self.engine.set_volume(key, value)
            self.engine.set_mute(key, False)
        self.toast(f"已将 {self.win_slider.value()}% 应用到 {len(keys)} 条音频会话")
        self.refresh_sessions()

    # ================================================================ EQ APO
    def install_eq_apo(self) -> None:
        """主按钮：未安装→静默安装；已安装但无设备→打开设备选择器。"""
        if self.eqapo.installed and not self.eqapo.ready:
            self._start_apo_action("selector", "打开设备选择器")
        else:
            self._start_apo_action("install", "一键安装")

    def open_apo_bundle(self) -> None:
        """次按钮：手动安装（解出内置安装包）/ 重新安装。"""
        if self._eq_alt_mode == "install":
            self._start_apo_action("install", "重新安装")
        else:
            self._start_apo_action("bundle", "手动安装")

    def _start_apo_action(self, action: str, label: str) -> None:
        if self._apo_thread is not None:
            self.toast("上一个操作还在进行中，请稍候", ok=False)
            return
        self.eq_install_btn.setEnabled(False)
        self.eq_alt_btn.setEnabled(False)
        self.eq_install_btn.setText(f"{label}中…")
        self.eq_status.setText(f"{label}中，请稍候…")
        self._apo_thread = QThread(self)
        self._apo_worker = APOInstallWorker(action)
        self._apo_worker.moveToThread(self._apo_thread)
        self._apo_thread.started.connect(self._apo_worker.run)
        self._apo_worker.status.connect(self.eq_status.setText)
        self._apo_worker.done.connect(self.on_apo_done)
        self._apo_worker.done.connect(self._apo_thread.quit)
        self._apo_thread.finished.connect(self._apo_thread.deleteLater)
        self._apo_thread.start()

    def on_apo_done(self, ok: bool, msg: str) -> None:
        self._apo_thread = None
        self._apo_worker = None
        # 重新探测：安装后 config.txt 与注册表都可能刚出现
        self.eqapo = EqualizerAPO()
        self._sync_eq_state()
        self.eq_install_btn.setEnabled(True)
        self.eq_alt_btn.setEnabled(True)
        self.toast(msg, ok)

    def apply_eq_preamp(self) -> None:
        if not self.eqapo.ready:
            self.toast("请先装好 Equalizer APO 并启用音频设备", ok=False)
            self._sync_eq_state()
            return
        db = self.eq_slider.value()
        ok, msg = self.eqapo.set_preamp(db)
        self._sync_eq_state()
        self.toast(msg, ok)

    def restore_eq(self) -> None:
        if not self.eqapo.installed:
            self.toast("未检测到 Equalizer APO，无需还原", ok=False)
            return
        ok, msg = self.eqapo.restore()
        self._sync_eq_state()
        self.toast(msg, ok)

    # ================================================================ 视频页
    def choose_media(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择视频或音频文件", "",
            "媒体文件 (*.mp4 *.mkv *.avi *.mov *.m4v *.webm *.flv *.wmv *.ts *.mp3 *.wav *.flac *.m4a *.aac *.ogg);;所有文件 (*.*)",
        )
        if path:
            self.load_media(path)

    def load_media(self, path: str) -> None:
        p = Path(path)
        if not p.is_file():
            self.toast("文件不存在", ok=False)
            return
        if p.suffix.lower() not in SUPPORTED_EXTS:
            self.toast("暂不支持该文件格式", ok=False)
            return
        if not self.ffmpeg:
            self.toast("未找到 ffmpeg，请把 ffmpeg.exe 放到程序目录", ok=False)
            return

        self.media = None
        self.run_btn.setEnabled(False)
        self.open_btn.setEnabled(False)
        self.media_name.setText(p.name[:60])
        self.media_meta.setText("正在后台分析音轨…")
        self.media_meta.show()
        self.media_level.setText("")
        self.media_level.hide()
        self.progress_label.setText("分析音轨中…")
        self.log.appendPlainText(f"[载入] {p}")

        self._auto_out = True
        self._probe_seq += 1
        seq = self._probe_seq
        if self._probe_thread and self._probe_thread.isRunning():
            self._probe_thread.quit()
            self._probe_thread.wait(500)
        thread = QThread(self)
        worker = ProbeWorker(str(p), self.ffmpeg)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.done.connect(
            lambda info, src, s=seq: self._on_probe_done(info, src, s)
        )
        worker.done.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        self._probe_thread = thread
        self._probe_worker = worker
        thread.start()

    def _on_probe_done(self, info, path: str, seq: int) -> None:
        if seq != self._probe_seq:
            return  # 分析期间用户又选了别的文件，丢弃过期结果
        if info is None or not info.has_audio:
            self.media_meta.setText("分析失败或未检测到可用音轨")
            self.media_meta.show()
            self.media_level.hide()
            self.run_btn.setEnabled(False)
            self.progress_label.setText("就绪")
            self.toast("未检测到可用音轨或分析失败", ok=False)
            return
        self.media = info
        self.media_meta.setText(
            f"{info.size_text}  ·  {info.duration_text}  ·  "
            f"音轨 {info.audio_codec.upper() or '未知'}"
        )
        self.media_level.setText(
            f"平均 {info.mean_volume:.1f} dB  /  峰值 {info.max_volume:.1f} dB  "
            f"·  建议 +{info.suggested_gain:g} dB"
            if info.mean_volume is not None and info.max_volume is not None
            else "电平分析完成"
        )
        self.media_meta.show()
        self.media_level.show()
        self.run_btn.setEnabled(True)
        self.progress_label.setText("就绪")
        self.log.appendPlainText(
            f"[分析] 峰值 {info.max_volume} dB，建议增益 +{info.suggested_gain:g} dB"
        )
        self.toast("文件分析完成")
        self.on_mode_changed()

    def _on_out_edited(self, _text: str) -> None:
        """用户手动改过输出路径后，不再自动覆盖。"""
        self._auto_out = False

    def _update_auto_output(self) -> None:
        if self.media and self._auto_out:
            self.out_edit.setText(
                default_output_path(self.media.path, self.current_gain_db())
            )

    def current_gain_db(self) -> float:
        return self.gain_slider.value() / 10.0

    def on_gain_slider(self, value: int) -> None:
        db = value / 10.0
        self.gain_value_label.setText(f"+{db:.1f} dB  ({db_to_factor(db):.2f}×)")
        self._update_auto_output()

    def on_mode_changed(self) -> None:
        auto = self.mode_auto.isChecked()
        self.gain_slider.setEnabled(not auto)
        if auto and self.media and self.media.max_volume is not None:
            db = self.media.suggested_gain
            self.gain_slider.blockSignals(True)
            self.gain_slider.setValue(int(round(db * 10)))
            self.gain_slider.blockSignals(False)
            self.gain_value_label.setText(
                f"+{db:.1f} dB  (自动归一化至 -1 dB)"
            )
            self.log.appendPlainText(f"[模式] 自动归一化，计算增益 +{db:g} dB")
        else:
            self.on_gain_slider(self.gain_slider.value())
        self._update_auto_output()

    def choose_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "选择输出路径", self.out_edit.text(), "所有文件 (*.*)"
        )
        if path:
            self.out_edit.setText(path)

    def start_boost(self) -> None:
        if self._boosting:
            if self.boost_worker:
                self.boost_worker.cancel()
            self.progress_label.setText("正在取消…")
            return
        if not self.media or not self.ffmpeg:
            self.toast("请先选择媒体文件", ok=False)
            return
        src = self.media.path
        dst = self.out_edit.text().strip() or default_output_path(src, self.current_gain_db())
        db = self.current_gain_db()
        cmd = build_command(
            self.ffmpeg, src, dst, db,
            limiter=self.limiter_toggle.isChecked(), bitrate="192k",
        )
        self.out_edit.setText(dst)
        self.log.clear()
        self.log.appendPlainText("[命令] " + " ".join(cmd))
        self.progress.setValue(0)
        self.progress_label.setText("处理中…")
        self._boosting = True
        self.run_btn.setText("取消处理")
        self.run_btn.setEnabled(True)
        self.open_btn.setEnabled(False)

        self.boost_thread = QThread(self)
        self.boost_worker = BoostWorker(cmd, self.media.duration, dst)
        self.boost_worker.moveToThread(self.boost_thread)
        self.boost_thread.started.connect(self.boost_worker.run)
        self.boost_worker.progress.connect(self.on_boost_progress)
        self.boost_worker.log.connect(self.log.appendPlainText)
        self.boost_worker.done.connect(self.on_boost_done)
        self.boost_worker.done.connect(self.boost_thread.quit)
        self.boost_thread.finished.connect(self.boost_thread.deleteLater)
        self.boost_thread.start()

    def on_boost_progress(self, pct: float) -> None:
        self.progress.setValue(int(pct))
        self.progress_label.setText(f"处理中  {int(pct)}%")

    def on_boost_done(self, ok: bool, msg: str) -> None:
        self._boosting = False
        self.run_btn.setText("开始增强")
        self.run_btn.setEnabled(True)
        self.open_btn.setEnabled(ok)
        if ok:
            self.progress.setValue(100)
            self.progress_label.setText("完成")
            self.log.appendPlainText(f"[完成] {self.out_edit.text()}")
        else:
            self.progress_label.setText("失败")
            self.log.appendPlainText(f"[失败] {msg}")
        self.toast(msg, ok)

    def open_output(self) -> None:
        dst = self.out_edit.text().strip()
        if dst and os.path.isfile(dst):
            try:
                subprocess.Popen(["explorer", "/select,", os.path.normpath(dst)])
            except Exception:
                os.startfile(os.path.dirname(dst))
        elif dst and os.path.isdir(os.path.dirname(dst)):
            os.startfile(os.path.dirname(dst))

    # ================================================================ 生命周期
    def closeEvent(self, event) -> None:  # noqa: N802
        # APO 安装线程阻塞在等待安装器退出，强行销毁 QThread 会崩，直接拦住关闭
        if self._apo_thread and self._apo_thread.isRunning():
            self.toast("Equalizer APO 安装还在进行，请等它完成后再关闭", ok=False)
            event.ignore()
            return
        self.timer.stop()
        self._probe_seq += 1
        if self._probe_thread and self._probe_thread.isRunning():
            self._probe_thread.quit()
            self._probe_thread.wait(1000)
        if self.boost_thread and self.boost_thread.isRunning():
            if self.boost_worker:
                self.boost_worker.cancel()
            self.boost_thread.quit()
            self.boost_thread.wait(1500)
        event.accept()
