# -*- coding: utf-8 -*-
"""离屏界面 + 功能回归自检：python ui_smoke.py"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtWidgets import QApplication, QBoxLayout  # noqa: E402

from core.video_core import parse_progress  # noqa: E402
from ui import theme  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402


def visible_items(lst) -> int:
    return sum(1 for i in range(lst.count()) if not lst.item(i).isHidden())


def main() -> int:
    app = QApplication([])
    win = MainWindow()
    win.show()
    app.processEvents()

    print(f"会话数={len(win.sessions)}  窗口数={len(win.windows)}  卡片数={len(win.live_cards)}")
    assert len(win.live_cards) == len(win.sessions), "实时页卡片数量不匹配"
    assert len(win.bg_cards) == len([s for s in win.sessions if s.is_background]), "后台页卡片数量不匹配"
    assert win.grip is not None, "缺少窗口尺寸把手"

    for i in range(5):
        win.switch_page(i)
        app.processEvents()
    for _ in range(3):
        win._tick()
        app.processEvents()
    print("  五个页面 / 自动刷新 OK")

    # 设计系统：三套主题的所有文字色都必须达到 4.5:1
    for name, palette in theme.THEMES.items():
        worst = min(
            theme.contrast_ratio(palette[fg], palette[bg])
            for fg in ("text", "text_dim", "text_faint")
            for bg in ("bg_main", "bg_card", "bg_sidebar", "bg_input")
        )
        assert worst >= theme.MIN_CONTRAST, f"{name} 对比度不足: {worst:.2f}"
        print(f"  配色 {theme.label(name)} 最低文字对比度 {worst:.2f}:1 OK")

    # ffmpeg 进度解析（out_time_ms 实际是微秒）
    assert abs(parse_progress("out_time=00:00:01.500000", 3.0) - 50.0) < 0.01
    assert abs(parse_progress("out_time_us=1500000", 3.0) - 50.0) < 0.01
    assert abs(parse_progress("out_time_ms=3000000", 3.0) - 100.0) < 0.01
    assert parse_progress("progress=end", 3.0) == 100.0
    print("  视频进度解析 (HH:MM:SS / 微秒 / 结束) OK")

    # 定时刷新后搜索过滤必须保留
    win.win_search.setText("zzz_no_such_window")
    app.processEvents()
    before = visible_items(win.win_list)
    win.refresh_windows(force=True)
    app.processEvents()
    after = visible_items(win.win_list)
    assert before == 0 and after == 0, f"搜索过滤被刷新清掉: {before} -> {after}"
    win.win_search.setText("")
    win.filter_windows("")
    print("  窗口搜索过滤在重建后保持 OK")

    # 主音量双滑块必须即时双向同步（不改动真实系统音量）
    original_setter = win.engine.set_master_volume
    win.engine.set_master_volume = lambda v: True
    try:
        win.side_master.setValue(37)
        app.processEvents()
        assert win.master_slider.value() == 37, "侧栏 -> 主页面未即时同步"
        assert win.master_label.text() == "37%"
        win.master_slider.setValue(63)
        app.processEvents()
        assert win.side_master.value() == 63, "主页面 -> 侧栏未即时同步"
        assert win.side_master_label.text() == "63%"
    finally:
        win.engine.set_master_volume = original_setter
    print("  主音量双滑块即时双向同步 OK")

    # 响应式断点：密度、侧栏宽度、双栏方向、无横向溢出
    for w, h in ((760, 520), (960, 740), (1240, 810)):
        win.resize(w, h)
        app.processEvents()
        expected = "compact" if w < theme.BP["compact"] else "normal"
        assert win._density == expected, f"{w}px 密度错误: {win._density}"
        assert win.root.property("density") == expected
        content_w = w - win.sidebar.width()
        for i in range(win.stack.count()):
            page = win.stack.widget(i)
            min_w = page.layout().minimumSize().width()
            assert min_w <= content_w + 24, (
                f"页面 {i} 在 {w}px 下横向溢出 {min_w} > {content_w}"
            )
        expected_dir = (QBoxLayout.TopToBottom if expected == "compact"
                        else QBoxLayout.LeftToRight)
        assert win.win_body.direction() == expected_dir, "窗口页布局方向未随宽度切换"
        print(f"  {w}x{h}: density={expected}, 侧栏={win.sidebar.width()}px, 无横向溢出 OK")

    if win.win_list.count():
        win.win_list.setCurrentRow(0)
        app.processEvents()
        print(f"  窗口选中 OK: {win.selected_window.title[:26] if win.selected_window else '-'}")

    win.on_mode_changed()
    win.toast("自检提示")
    win.refresh_all()
    app.processEvents()

    original = theme.current()
    for key in theme.THEME_ORDER:
        win._apply_theme(key, persist=False, notify=False)
        app.processEvents()
        print(f"  配色 {theme.label(key)} 切换 OK")
    win._apply_theme(original, persist=False, notify=False)
    app.processEvents()

    win.close()
    print("\nUI SMOKE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
