# -*- coding: utf-8 -*-
"""二次元柔光设计系统（Lucky Volume Booster）。

方向锁定（frontend-design / Impeccable / UI设计系统）：
  Purpose        桌面音频增强工具，面向 ACG / 二次元爱好者
  Tone           柔光通透、圆润但不幼稚，像高质感 ACG 音乐播放器
  Differentiation 柔光氛围背景 + 衬线大字非对称排版 + 半透明玻璃层次
  反 AI slop     不再「万物皆卡片」、不再居中一切、不再平均分配配色

三套主题同属一个方向，只是光色不同：
  sakura   樱昼 —— 奶油白 + 樱粉 / 雾蓝（默认）
  mist     雾蓝 —— 冷白 + 雾蓝 / 薄荷
  yozakura 夜樱 —— 带紫调的墨色 + 淡樱粉 / 淡紫

C 是可变字典，set_theme() 原地更新；所有自绘控件通过 theme.C[...] 动态取色。
"""
from __future__ import annotations

from pathlib import Path

BRAND_NAME = "Lucky万山之龙"
BRAND_SITE = "www.Luckywszl.top"
BRAND_URL = "https://www.Luckywszl.top"

# ---------------------------------------------------------------- 设计令牌
FONT_DISPLAY = '"Noto Serif SC", "SimSun", Georgia, serif'
FONT_BODY = '"Microsoft YaHei UI", "Segoe UI", "PingFang SC", sans-serif'
FONT_NUM = 'Georgia, "Cascadia Mono", monospace'

TYPE = {"sm": 12, "base": 14, "lg": 16, "title": 28, "hero": 38, "num": 46}
SPACE = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "page": 30}
RADIUS = {"sm": 10, "md": 14, "lg": 20, "xl": 24}
BP = {"min_w": 760, "min_h": 520, "compact": 1060, "wide": 1240}
MIN_CONTRAST = 4.5

THEMES: dict[str, dict] = {
    "sakura": {
        "label": "樱昼",
        "bg_main": "#FDF8F8", "bg_end": "#F8F0F4", "bg_deep": "#F0E3EA",
        "root_border": "#EFDDE5", "bg_sidebar": "#FBF2F5",
        "bg_card": "#FFFEFE", "bg_card_alt": "#FDF4F7",
        "bg_input": "#FFFFFF", "bg_log": "#FBF4F7",
        "border": "#EEDFE6", "border_soft": "#F3E8ED",
        "accent": "#C63F6B", "accent_2": "#7EA6D8", "accent_soft": "#E88AA8", "on_accent": "#FFFFFF",
        "link": "#B23A64", "banner_border": "#F0D6E0", "drop_border": "#E5C8D6",
        "text": "#33262E", "text_dim": "#6B5560", "text_faint": "#78606C",
        "success": "#3E8E6E", "warning": "#A6712C", "danger": "#C4505F",
        "hover": "#FBE9EF", "pressed": "#F6DCE6", "disabled_bg": "#F5ECEF",
        "groove": "#EBD9E1", "handle": "#FFFFFF",
        "scroll": "#E3CBD7", "scroll_hover": "#C9A8BA",
        "level_low": "#8FB6C9", "level_mid": "#E0A05C", "level_high": "#D9567F",
        "level_off": "#EFE0E7",
        "toggle_off": "#EAD9E1", "toggle_border": "#DCC2CF", "toggle_knob": "#FFFFFF",
        "check_border": "#DCC2CF",
        "glow_1": "#F9C9DC", "glow_2": "#CBE0F7", "glow_alpha": 0.55,
        "hero_1": "#FFF2F6", "hero_2": "#EEF4FC",
    },
    "mist": {
        "label": "雾蓝",
        "bg_main": "#F7FAFD", "bg_end": "#EDF4FB", "bg_deep": "#E1EDF8",
        "root_border": "#D8E7F4", "bg_sidebar": "#F1F7FC",
        "bg_card": "#FFFFFF", "bg_card_alt": "#F3F8FD",
        "bg_input": "#FFFFFF", "bg_log": "#F2F8FD",
        "border": "#DCE8F2", "border_soft": "#E9F1F8",
        "accent": "#3470AB", "accent_2": "#4FB0A8", "accent_soft": "#82B2DC", "on_accent": "#FFFFFF",
        "link": "#2F6CA6", "banner_border": "#CBE0F1", "drop_border": "#BFD8EC",
        "text": "#213241", "text_dim": "#4F6474", "text_faint": "#5A7182",
        "success": "#2F8B73", "warning": "#A2762C", "danger": "#C05060",
        "hover": "#E9F3FC", "pressed": "#DCEBF8", "disabled_bg": "#EDF3F9",
        "groove": "#DCE9F4", "handle": "#FFFFFF",
        "scroll": "#C9DCEC", "scroll_hover": "#AAC6DE",
        "level_low": "#7FB8C8", "level_mid": "#E0B26B", "level_high": "#E07F9B",
        "level_off": "#E4EFF7",
        "toggle_off": "#DCE9F4", "toggle_border": "#C6D9EA", "toggle_knob": "#FFFFFF",
        "check_border": "#C6D9EA",
        "glow_1": "#C7E6F7", "glow_2": "#D2F0E4", "glow_alpha": 0.50,
        "hero_1": "#F0F8FF", "hero_2": "#EAF7F3",
    },
    "yozakura": {
        "label": "夜樱",
        "bg_main": "#1E1A26", "bg_end": "#242030", "bg_deep": "#15121C",
        "root_border": "#3A3044", "bg_sidebar": "#1C1825",
        "bg_card": "#282231", "bg_card_alt": "#2E2738",
        "bg_input": "#211C2A", "bg_log": "#1A1622",
        "border": "#3D3447", "border_soft": "#332C3D",
        "accent": "#F08FB0", "accent_2": "#C6A6E8", "accent_soft": "#F7B6CE", "on_accent": "#241C2C",
        "link": "#F5A8C4", "banner_border": "#4A3A52", "drop_border": "#4E3D57",
        "text": "#F5EDF3", "text_dim": "#C3B2C6", "text_faint": "#A291A8",
        "success": "#86C9A8", "warning": "#E6C07B", "danger": "#EE8C9B",
        "hover": "#332A3D", "pressed": "#3B3147", "disabled_bg": "#292331",
        "groove": "#3A3145", "handle": "#FBF3F8",
        "scroll": "#4A3E56", "scroll_hover": "#62526F",
        "level_low": "#8FA9C9", "level_mid": "#E6C07B", "level_high": "#F08FB0",
        "level_off": "#3A3145",
        "toggle_off": "#3A3145", "toggle_border": "#50425C", "toggle_knob": "#FBF3F8",
        "check_border": "#50425C",
        "glow_1": "#5A2F50", "glow_2": "#2E3560", "glow_alpha": 0.48,
        "hero_1": "#2C2233", "hero_2": "#242A42",
    },
}

THEME_ORDER = ["sakura", "mist", "yozakura"]
DEFAULT_THEME = "sakura"
_CONFIG = Path.home() / ".lucky_volume_booster" / "theme.txt"

_current = DEFAULT_THEME
C: dict = dict(THEMES[DEFAULT_THEME])


def load() -> None:
    global _current
    try:
        name = _CONFIG.read_text(encoding="utf-8").strip()
        legacy = {"paper": "sakura", "forest": "yozakura", "slate": "mist"}
        name = legacy.get(name, name)
        if name in THEMES:
            _current = name
    except Exception:
        pass
    C.clear()
    C.update(THEMES[_current])


def current() -> str:
    return _current


def label(name: str | None = None) -> str:
    return THEMES[name or _current]["label"]


def set_theme(name: str, persist: bool = True) -> None:
    global _current
    if name not in THEMES:
        return
    _current = name
    C.clear()
    C.update(THEMES[name])
    if persist:
        try:
            _CONFIG.parent.mkdir(parents=True, exist_ok=True)
            _CONFIG.write_text(name, encoding="utf-8")
        except Exception:
            pass


def rgba(color: str, alpha: float) -> str:
    h = color.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alpha})"


def accent_gradient() -> str:
    """同色系柔和渐变（避免粉→蓝撞色条带），用于滑块 / 进度 / 开关。"""
    return (f"qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 {C['accent']}, stop:1 {C['accent_soft']})")


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG 相对亮度对比度，供设计系统自检使用。"""
    def luminance(color: str) -> float:
        h = color.lstrip("#")
        channels = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
        linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
                  for c in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    l1, l2 = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def stylesheet() -> str:
    g = accent_gradient()
    tint = rgba(C["accent"], 0.11)
    tint_soft = rgba(C["accent"], 0.055)
    surface = rgba(C["bg_card"], 0.86)
    surface_alt = rgba(C["bg_card_alt"], 0.80)
    sidebar = rgba(C["bg_sidebar"], 0.74)
    input_bg = rgba(C["bg_input"], 0.90)
    return f"""
* {{
    font-family: {FONT_BODY};
    font-size: {TYPE['base']}px;
    color: {C['text']};
}}
QWidget {{ background: transparent; }}

/* 背景由 AtmosphereWidget 自绘（渐变 + 柔光斑），QSS 只负责圆角与边框 */
#root {{
    background: transparent;
    border: 1px solid {C['root_border']};
    border-radius: {RADIUS['lg']}px;
}}
#sidebar {{
    background: {sidebar};
    border-right: 1px solid {C['border_soft']};
    border-top-left-radius: {RADIUS['lg']}px;
    border-bottom-left-radius: {RADIUS['lg']}px;
}}
#titlebar, #content {{ background: transparent; }}

QLabel {{ background: transparent; }}
QLabel[cls="title"] {{
    font-family: {FONT_DISPLAY}; font-size: {TYPE['title']}px;
    font-weight: 700; letter-spacing: -0.4px;
}}
QLabel[cls="subtitle"] {{ font-size: {TYPE['sm']}px; color: {C['text_dim']}; }}
QLabel[cls="section"] {{ font-size: {TYPE['lg']}px; font-weight: 700; }}
QLabel[cls="caption"] {{ font-size: {TYPE['sm']}px; color: {C['text_faint']}; }}
QLabel[cls="value"] {{ font-size: 22px; font-weight: 700; }}
QLabel[cls="display-num"] {{
    font-family: {FONT_NUM}; font-size: {TYPE['num']}px;
    font-weight: 700; color: {C['accent']}; letter-spacing: -1px;
}}
QLabel[cls="row-num"] {{
    font-family: {FONT_NUM}; font-size: 24px;
    font-weight: 700; color: {C['accent']};
}}
QLabel[cls="brand"] {{ font-size: {TYPE['base']}px; font-weight: 800; color: {C['accent']}; }}
QLabel[cls="brand-title"] {{
    font-family: {FONT_DISPLAY}; font-size: 15px;
    font-weight: 800; letter-spacing: 1px;
}}
QLabel[cls="hero-name"] {{
    font-family: {FONT_DISPLAY}; font-size: {TYPE['hero']}px;
    font-weight: 800; color: {C['accent']}; letter-spacing: 1px;
}}
QLabel[cls="accent-value"] {{ color: {C['accent']}; font-size: {TYPE['sm']}px; font-weight: 800; }}
QLabel[cls="dot"] {{ color: {C['accent_2']}; font-size: 18px; font-weight: 900; }}
QLabel[cls="drop-plus"] {{ font-size: 42px; font-weight: 300; color: {C['accent']}; }}
QLabel[cls="banner-dot"] {{
    background: {C['accent']}; color: {C['on_accent']};
    border-radius: 9px; font-weight: 800;
}}
QLabel[cls="hint"] {{ font-size: {TYPE['sm']}px; color: {C['text_dim']}; }}

/* 表面：半透明玻璃，让底层柔光透出；不再是厚重圆角卡片 */
QFrame[cls="card"] {{
    background: {surface};
    border: 1px solid {C['border']};
    border-radius: {RADIUS['lg']}px;
}}
QFrame[cls="card-alt"] {{
    background: {surface_alt};
    border: 1px solid {C['border_soft']};
    border-radius: {RADIUS['md']}px;
}}
QFrame[cls="hero"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {C['hero_1']}, stop:1 {C['hero_2']});
    border: 1px solid {C['border']};
    border-radius: {RADIUS['xl']}px;
}}
QFrame[cls="banner"] {{
    background: {tint_soft};
    border: none;
    border-left: 3px solid {C['accent']};
    border-radius: 4px;
}}
QFrame[cls="divider"] {{ background: {C['border_soft']}; max-height: 1px; border: none; }}
QFrame[cls="dropzone"] {{
    background: {input_bg};
    border: 2px dashed {C['drop_border']};
    border-radius: {RADIUS['lg']}px;
}}
/* 会话行：分隔线式列表，替代「每张都套一张卡片」 */
QFrame[cls="row"] {{
    background: transparent;
    border: none;
    border-bottom: 1px solid {C['border_soft']};
    border-radius: 0px;
}}
QFrame[cls="row"]:hover {{ background: {rgba(C['hover'], 0.55)}; }}

/* ---------------------------------------------------------- 按钮 */
QPushButton {{
    background: {surface_alt};
    border: 1px solid {C['border']};
    border-radius: 12px;
    padding: 9px 16px;
    color: {C['text']};
    font-weight: 600;
}}
QPushButton:hover {{ background: {C['hover']}; border-color: {C['accent']}; }}
QPushButton:pressed {{ background: {C['pressed']}; }}
QPushButton:disabled {{
    color: {C['text_faint']}; background: {C['disabled_bg']};
    border-color: {C['border_soft']};
}}

QPushButton[cls="primary"] {{
    background: {C['accent']};
    border: none;
    color: {C['on_accent']};
    font-weight: 800;
    padding: 10px 22px;
    border-radius: 12px;
}}
QPushButton[cls="primary"]:hover {{ background: {C['accent_2']}; }}
QPushButton[cls="primary"]:pressed {{ background: {C['accent']}; }}
QPushButton[cls="primary"]:disabled {{
    background: {C['disabled_bg']}; color: {C['text_faint']};
}}

QPushButton[cls="ghost"] {{
    background: transparent; border: 1px solid {C['border']}; color: {C['text_dim']};
}}
QPushButton[cls="ghost"]:hover {{ color: {C['text']}; background: {C['hover']}; }}

QPushButton[cls="chip"] {{
    background: {input_bg};
    border: 1px solid {C['border']};
    border-radius: 18px;
    padding: 6px 15px;
    color: {C['text_dim']};
    font-weight: 600;
}}
QPushButton[cls="chip"]:hover {{ border-color: {C['accent']}; color: {C['text']}; }}
QPushButton[cls="chip"]:checked {{
    background: {tint}; border-color: {C['accent']}; color: {C['text']};
}}

QPushButton[cls="themebtn"] {{
    background: transparent;
    border: 1px solid {C['border']};
    border-radius: 9px;
    padding: 3px 5px;
    font-size: {TYPE['sm']}px;
    color: {C['text_dim']};
    font-weight: 600;
}}
QPushButton[cls="themebtn"]:hover {{ border-color: {C['accent']}; color: {C['text']}; }}
QPushButton[cls="themebtn"]:checked {{
    background: {C['accent']}; border-color: {C['accent']}; color: {C['on_accent']};
}}

/* 导航：细竖条指示，不再整块填充 */
QPushButton[cls="nav"] {{
    background: transparent;
    border: none;
    border-radius: {RADIUS['sm']}px;
    padding: 11px 14px;
    text-align: left;
    color: {C['text_dim']};
    font-size: {TYPE['base']}px;
    font-weight: 600;
}}
QPushButton[cls="nav"]:hover {{ background: {rgba(C['hover'], 0.55)}; color: {C['text']}; }}
QPushButton[cls="nav"]:checked {{
    background: {tint_soft};
    color: {C['text']};
    border-left: 3px solid {C['accent']};
    font-weight: 800;
}}

QPushButton[cls="winbtn"] {{
    background: transparent; border: none; border-radius: {RADIUS['sm']}px;
    font-size: 15px; font-weight: 700; color: {C['text_dim']}; padding: 0px;
}}
QPushButton[cls="winbtn"]:hover {{ background: {C['hover']}; color: {C['text']}; }}
QPushButton[cls="winbtn"][kind="close"]:hover {{
    background: {C['danger']}; color: {C['on_accent']};
}}

QPushButton[cls="link"] {{
    background: transparent; border: none; color: {C['link']};
    text-align: left; padding: 0px; font-weight: 700; text-decoration: underline;
}}
QPushButton[cls="link"]:hover {{ color: {C['accent_2']}; }}

QPushButton[cls="iconbtn"] {{
    background: {input_bg}; border: 1px solid {C['border']}; border-radius: {RADIUS['sm']}px;
    padding: 5px 9px; font-size: {TYPE['sm']}px; color: {C['text_dim']};
}}
QPushButton[cls="iconbtn"]:hover {{ color: {C['text']}; border-color: {C['accent']}; }}
QPushButton[cls="iconbtn"]:checked {{ color: {C['warning']}; border-color: {C['warning']}; }}

/* ---------------------------------------------------------- 输入 */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {input_bg};
    border: 1px solid {C['border']};
    border-radius: 11px;
    padding: 8px 11px;
    color: {C['text']};
    selection-background-color: {C['accent']};
}}
QLineEdit:focus, QComboBox:focus {{ border-color: {C['accent']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {C['bg_card']}; border: 1px solid {C['border']};
    selection-background-color: {C['accent']}; color: {C['text']};
    outline: none;
}}

QCheckBox {{ color: {C['text_dim']}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 5px;
    border: 1px solid {C['check_border']}; background: {C['bg_input']};
}}
QCheckBox::indicator:checked {{ background: {g}; border-color: {C['accent']}; }}

/* ---------------------------------------------------------- 滑块 */
QSlider::groove:horizontal {{
    height: 6px; background: {C['groove']}; border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    height: 6px; background: {g}; border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {C['handle']}; width: 16px; height: 16px;
    margin: -5px 0; border-radius: 8px; border: 2px solid {C['accent']};
}}
QSlider::handle:horizontal:hover {{
    background: {C['handle']}; border-color: {C['accent']};
    width: 18px; height: 18px; margin: -6px 0;
}}
QSlider[cls="master"]::groove:horizontal {{ height: 10px; border-radius: 5px; }}
QSlider[cls="master"]::sub-page:horizontal {{ height: 10px; border-radius: 5px; }}
QSlider[cls="master"]::handle:horizontal {{
    width: 22px; height: 22px; margin: -6px 0; border-radius: 11px;
}}

/* ---------------------------------------------------------- 进度 / 日志 */
QProgressBar {{
    background: {C['groove']}; border: none; border-radius: 7px;
    height: 14px; text-align: center; color: {C['text']};
    font-size: {TYPE['sm']}px; font-weight: 700;
}}
QProgressBar::chunk {{ background: {g}; border-radius: 7px; }}

QPlainTextEdit[cls="log"] {{
    background: {C['bg_log']}; border: 1px solid {C['border_soft']};
    border-radius: {RADIUS['md']}px; color: {C['text_dim']};
    font-family: "Cascadia Mono", Consolas, monospace; font-size: {TYPE['sm']}px;
    padding: 9px;
}}

/* ---------------------------------------------------------- 列表 / 滚动 */
QListWidget {{
    background: {input_bg}; border: 1px solid {C['border_soft']};
    border-radius: {RADIUS['md']}px; padding: 6px; outline: none;
}}
QListWidget::item {{
    padding: 0px; border-radius: {RADIUS['sm']}px; margin: 1px 2px;
    color: {C['text_dim']};
}}
QListWidget::item:hover {{ background: {C['hover']}; color: {C['text']}; }}
QListWidget::item:selected {{
    background: {tint}; color: {C['text']}; border-left: 3px solid {C['accent']};
}}

QScrollBar:vertical {{ background: transparent; width: 9px; margin: 0px; }}
QScrollBar::handle:vertical {{
    background: {C['scroll']}; border-radius: 5px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {C['scroll_hover']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 9px; }}
QScrollBar::handle:horizontal {{
    background: {C['scroll']}; border-radius: 5px; min-width: 30px;
}}

QScrollArea {{ border: none; background: transparent; }}
QToolTip {{
    background: {C['bg_card']}; color: {C['text']}; border: 1px solid {C['accent']};
    border-radius: 6px; padding: 5px;
}}

/* ---------------------------------------------------------- 键盘焦点（WCAG 2.4.7） */
QLineEdit:focus, QComboBox:focus,
QPlainTextEdit:focus, QListWidget:focus, QCheckBox:focus {{
    border: 2px solid {C['accent']};
}}
QPushButton:focus {{ border: 1px dashed {C['accent']}; }}
QPushButton:checked:focus {{ border: 1px solid {C['accent']}; }}
QPushButton[cls="nav"]:checked:focus {{
    border: none; border-left: 3px solid {C['accent']};
}}
QCheckBox:focus {{ color: {C['text']}; }}

/* ---------------------------------------------------------- 紧凑密度 */
#root[density="compact"] QLabel[cls="title"] {{ font-size: 21px; }}
#root[density="compact"] QLabel[cls="display-num"] {{ font-size: 34px; }}
#root[density="compact"] QLabel[cls="hero-name"] {{ font-size: 29px; }}
#root[density="compact"] QLabel[cls="brand-title"] {{ font-size: 10px; letter-spacing: 0; }}
#root[density="compact"] QPushButton[cls="link"] {{ font-size: 11px; }}
#root[density="compact"] QLabel[cls="drop-plus"] {{ font-size: 32px; }}
#root[density="compact"] QPushButton {{ padding: 6px 11px; }}
#root[density="compact"] QPushButton[cls="primary"] {{ padding: 8px 15px; }}
#root[density="compact"] QPushButton[cls="nav"] {{ padding: 8px 10px; font-size: {TYPE['sm']}px; }}
#root[density="compact"] QPushButton[cls="chip"] {{ padding: 5px 11px; }}
#root[density="compact"] QFrame[cls="card"] {{ border-radius: {RADIUS['md']}px; }}
#root[density="compact"] QFrame[cls="dropzone"] {{ border-radius: {RADIUS['md']}px; }}

QSizeGrip {{ background: transparent; }}
"""


load()
