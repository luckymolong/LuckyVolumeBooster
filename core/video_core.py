# -*- coding: utf-8 -*-
"""视频音量增益模块：真正的 +dB 放大，可突破 100%。

流程：ffmpeg 探测音轨峰值 -> 计算/指定增益 -> volume + alimiter 限幅防削波
      -> 视频流直接拷贝（不重编码、不掉画质）-> 音轨重新编码为 AAC 导出。
"""
from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".m4v", ".flv", ".wmv", ".webm", ".ts", ".mpg", ".mpeg"}
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma"}
SUPPORTED_EXTS = VIDEO_EXTS | AUDIO_EXTS

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_MEAN_RE = re.compile(r"mean_volume:\s*([-+]?\d+(?:\.\d+)?)\s*dB")
_MAX_RE = re.compile(r"max_volume:\s*([-+]?\d+(?:\.\d+)?)\s*dB")
_AUDIO_STREAM_RE = re.compile(r"Stream #\d+:\d+.*?:\s*Audio:\s*([a-zA-Z0-9_]+)")
_OUT_TIME_RE = re.compile(r"^out_time=(\d+):(\d+):(\d+(?:\.\d+)?)$")


@dataclass
class MediaInfo:
    path: str
    size_bytes: int
    duration: float
    has_audio: bool
    audio_codec: str
    mean_volume: Optional[float]
    max_volume: Optional[float]

    @property
    def filename(self) -> str:
        return Path(self.path).name

    @property
    def size_text(self) -> str:
        return format_size(self.size_bytes)

    @property
    def duration_text(self) -> str:
        return format_duration(self.duration)

    @property
    def suggested_gain(self) -> float:
        if self.max_volume is None:
            return 6.0
        return max(0.0, min(24.0, round((-1.0 - self.max_volume) * 10) / 10))


def format_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} GB"


def format_duration(sec: float) -> str:
    if sec <= 0:
        return "--:--"
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def find_ffmpeg() -> Optional[str]:
    """优先程序自带 -> PATH -> imageio-ffmpeg 内置二进制。"""
    bases: List[str] = []
    if getattr(sys, "_MEIPASS", None):
        bases.append(sys._MEIPASS)
    bases.append(os.path.dirname(os.path.abspath(sys.executable)))
    bases.append(str(Path(__file__).resolve().parent.parent / "assets"))
    for base in bases:
        for name in ("ffmpeg.exe", "ffmpeg"):
            candidate = os.path.join(base, name)
            if os.path.isfile(candidate):
                return candidate
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _run(cmd: List[str], timeout: int = 180) -> subprocess.CompletedProcess:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(
        cmd, capture_output=True, text=True, errors="replace",
        timeout=timeout, creationflags=creationflags,
    )


def probe(path: str, ffmpeg: Optional[str] = None, sample_seconds: int = 60) -> MediaInfo:
    """用 volumedetect 采样音轨，拿到平均/峰值电平和时长。"""
    exe = ffmpeg or find_ffmpeg()
    size = os.path.getsize(path) if os.path.isfile(path) else 0
    empty = MediaInfo(path, size, 0.0, False, "", None, None)
    if not exe:
        return empty
    cmd = [
        exe, "-hide_banner", "-nostats", "-i", path,
        "-t", str(sample_seconds), "-map", "0:a:0",
        "-af", "volumedetect", "-f", "null", "-",
    ]
    try:
        r = _run(cmd, timeout=180)
    except Exception:
        return empty
    text = (r.stderr or "") + "\n" + (r.stdout or "")
    duration = 0.0
    m = _DURATION_RE.search(text)
    if m:
        duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    mean = float(_MEAN_RE.search(text).group(1)) if _MEAN_RE.search(text) else None
    peak = float(_MAX_RE.search(text).group(1)) if _MAX_RE.search(text) else None
    codec_m = _AUDIO_STREAM_RE.search(text)
    codec = codec_m.group(1) if codec_m else ""
    # 只有 volumedetect 真正输出峰值才算有可用音轨；
    # 仅凭输入流信息里的 "Audio:" 会误判被禁用 / 映射失败的音轨。
    has_audio = peak is not None
    return MediaInfo(path, size, duration, has_audio, codec, mean, peak)


def default_output_path(src: str, gain_db: float) -> str:
    p = Path(src)
    tag = f"{gain_db:g}dB".replace("+", "")
    out = p.with_name(f"{p.stem}_boost_{tag}{p.suffix}")
    idx = 1
    while out.exists():
        out = p.with_name(f"{p.stem}_boost_{tag}_{idx}{p.suffix}")
        idx += 1
    return str(out)


def build_command(
    ffmpeg: str,
    src: str,
    dst: str,
    gain_db: float,
    limiter: bool = True,
    bitrate: str = "192k",
) -> List[str]:
    filters = [f"volume={gain_db:+.2f}dB"]
    if limiter:
        filters.append("alimiter=limit=0.95")
    af = ",".join(filters)
    p = Path(src)
    is_audio_only = p.suffix.lower() in AUDIO_EXTS
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", src]
    if is_audio_only:
        cmd += ["-map", "0:a:0", "-c:a", "aac" if p.suffix.lower() != ".mp3" else "libmp3lame",
                "-b:a", bitrate, "-af", af]
    else:
        # 视频/字幕直接拷贝，只重编码第一条音轨，画质无损。
        # ffmpeg 对 "-c copy" + "-c:a:0 aac" 会给出 "Multiple -codec options"
        # 警告（结果正确但会污染日志），故日志级别设为 error。
        cmd += [
            "-map", "0", "-c", "copy",
            "-c:a:0", "aac", "-b:a:0", bitrate,
            "-filter:a:0", af,
        ]
    cmd += ["-progress", "pipe:1", "-nostats", dst]
    return cmd


def parse_progress(line: str, duration: float) -> Optional[float]:
    """解析 ffmpeg -progress 输出，返回 0~100 的百分比。

    注意：实测 ffmpeg 9.x 的 ``out_time_ms`` 与 ``out_time_us`` **都是微秒**
    （3 秒视频输出 3000000），旧实现把 out_time_ms 当毫秒会让进度瞬间跳到
    100%。因此优先解析无歧义的 ``out_time=HH:MM:SS.xxxxxx``。
    """
    line = line.strip()
    if line.startswith("progress=end"):
        return 100.0

    def percent(seconds: float) -> Optional[float]:
        if duration <= 0:
            return None
        return max(0.0, min(100.0, seconds / duration * 100.0))

    m = _OUT_TIME_RE.match(line)
    if m:
        seconds = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        return percent(seconds)
    if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
        try:
            microseconds = float(line.split("=", 1)[1])
        except (ValueError, IndexError):
            return None
        return percent(microseconds / 1_000_000.0)
    return None
