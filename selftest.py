# -*- coding: utf-8 -*-
"""环境与功能自检：python selftest.py"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.audio_core import AudioEngine, db_to_factor  # noqa: E402
from core.eq_apo import EqualizerAPO  # noqa: E402
from core.video_core import build_command, find_ffmpeg, probe  # noqa: E402
from core.window_core import enum_visible_windows, pid_title_map  # noqa: E402


def line(title):
    print("\n" + "=" * 60)
    print(" " + title)
    print("=" * 60)


def test_audio():
    line("1. WASAPI 音频会话")
    wins = enum_visible_windows()
    print(f"可见桌面窗口: {len(wins)}")
    for w in wins[:8]:
        print(f"   pid={w.pid:<8} {w.process_name[:24]:<26} {w.title[:40]}")
    eng = AudioEngine()
    print(f"引擎可用: {eng.available}  {eng.last_error}")
    sessions = eng.refresh(pid_title_map(wins))
    print(f"活动音频会话: {len(sessions)}")
    for s in sessions[:10]:
        tag = "后台" if s.is_background else "窗口"
        print(f"   pid={s.pid:<8} vol={s.percent:>3}% peak={s.peak:.3f} [{tag}] {s.name[:26]} {s.window_title[:26]}")
    print(f"系统主音量: {eng.get_master_volume() * 100:.1f}%")
    print(f"+6dB 倍数: {db_to_factor(6):.3f}x  /  +12dB: {db_to_factor(12):.3f}x")
    print(f"Equalizer APO: {EqualizerAPO().status_text}")
    return len(sessions) > 0


def test_video():
    line("2. 视频音轨增益（端到端）")
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("!! 未找到 ffmpeg")
        return False
    print("ffmpeg:", ffmpeg)
    with tempfile.TemporaryDirectory(prefix="luckyboost_") as td:
        src = os.path.join(td, "src.mp4")
        gen = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=320x180:rate=10",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-af", "volume=-24dB", "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", "-shortest", src,
        ]
        r = subprocess.run(gen, capture_output=True, text=True, errors="replace")
        if not os.path.isfile(src):
            print("!! 测试素材生成失败:", r.stderr[-600:])
            return False
        before = probe(src, ffmpeg)
        print(f"源文件: {before.size_text} 时长 {before.duration_text} 音轨 {before.audio_codec}")
        print(f"  平均电平 {before.mean_volume} dB / 峰值 {before.max_volume} dB")
        dst = os.path.join(td, "out.mp4")
        cmd = build_command(ffmpeg, src, dst, 12.0, limiter=True)
        print("命令:", " ".join(f'"{c}"' if " " in c else c for c in cmd))
        r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=120)
        if not os.path.isfile(dst):
            print("!! 增益编码失败:", (r.stderr or "")[-1200:])
            return False
        after = probe(dst, ffmpeg)
        print(f"输出文件: {Path(dst).stat().st_size / 1024:.1f} KB 音轨 {after.audio_codec}")
        print(f"  平均电平 {after.mean_volume} dB / 峰值 {after.max_volume} dB")
        if before.max_volume is not None and after.max_volume is not None:
            delta = after.max_volume - before.max_volume
            print(f"  实测增益: {delta:+.1f} dB (期望 +12 dB)")
            return delta > 5
        return False


if __name__ == "__main__":
    ok_audio = test_audio()
    ok_video = test_video()
    print("\n" + "=" * 60)
    print(f"RESULT  audio={'PASS' if ok_audio else 'FAIL'}  video={'PASS' if ok_video else 'FAIL'}")
    print("=" * 60)
    sys.exit(0 if (ok_audio and ok_video) else 1)
