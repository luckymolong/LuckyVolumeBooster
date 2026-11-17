# -*- coding: utf-8 -*-
"""Windows 音频会话控制核心层。

基于 WASAPI (pycaw / comtypes)：
  - 枚举当前所有「正在发声」的音频会话（每个程序一条或多条）
  - 读取 / 设置每个会话的音量、静音状态、实时峰值电平
  - 读取 / 设置系统主音量

重要事实：Windows 的 ISimpleAudioVolume 接口把单个会话的音量硬性限制在
0.0 ~ 1.0 (0% ~ 100%)，任何用户态程序都无法把某个窗口推到 200%。
因此本模块提供的是：
  1) 会话级「相对增益」：按 dB 提升，结果受 100% 上限约束
  2) 一键拉满 / 取消静音 / 主音量拉满（听感提升最明显的部分）
  3) 真正的 >100% 增益由 Equalizer APO 前级放大或视频 DSP 实现，见 eq_apo.py / video_core.py
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional

import psutil

try:
    from pycaw.pycaw import (
        AudioUtilities,
        IAudioEndpointVolume,
        IAudioMeterInformation,
        ISimpleAudioVolume,
    )
    from comtypes import CLSCTX_ALL

    _PYCAW_OK = True
    _PYCAW_ERR = ""
except Exception as exc:  # pragma: no cover - 仅在缺失依赖时
    _PYCAW_OK = False
    _PYCAW_ERR = str(exc)


def db_to_factor(db: float) -> float:
    """分贝转线性幅度倍数。+6dB ≈ 1.995x，+12dB ≈ 3.98x。"""
    return 10.0 ** (db / 20.0)


@dataclass
class SessionInfo:
    """一条音频会话的快照。"""

    key: str
    pid: int
    name: str
    exe: str
    display_name: str
    volume: float          # 0.0 ~ 1.0
    muted: bool
    peak: float            # 0.0 ~ 1.0 实时电平
    window_title: str = ""
    is_background: bool = False
    is_system: bool = False
    is_self: bool = False

    @property
    def percent(self) -> int:
        return int(round(self.volume * 100))

    @property
    def label(self) -> str:
        if self.display_name and not self.display_name.startswith("@"):
            return self.display_name
        if self.name:
            return self.name
        return "系统声音"


def _safe_process_info(pid: int):
    try:
        p = psutil.Process(pid)
        return p.name(), p.exe()
    except Exception:
        return "", ""


class AudioEngine:
    """封装全部 WASAPI 操作。所有方法都做了异常保护，音频设备异常时不会让 UI 崩溃。"""

    def __init__(self) -> None:
        self._sessions: Dict[str, object] = {}
        self._baseline: Dict[str, float] = {}
        self._endpoint = None
        self._last_error: str = ""
        self.available = _PYCAW_OK
        if not _PYCAW_OK:
            self._last_error = _PYCAW_ERR

    # ------------------------------------------------------------------ 主音量
    def _get_endpoint(self):
        if self._endpoint is None and self.available:
            try:
                device = AudioUtilities.GetSpeakers()
                # pycaw 2026+ 返回 AudioDevice，直接暴露 EndpointVolume；
                # 旧版本返回 IMMDevice，需要手动 Activate。
                endpoint = getattr(device, "EndpointVolume", None)
                if endpoint is None:
                    endpoint = device.Activate(
                        IAudioEndpointVolume._iid_, CLSCTX_ALL, None
                    )
                self._endpoint = endpoint
            except Exception as exc:
                self._last_error = str(exc)
        return self._endpoint

    def get_master_volume(self) -> float:
        ep = self._get_endpoint()
        if ep is None:
            return 0.0
        try:
            return float(ep.GetMasterVolumeLevelScalar())
        except Exception:
            return 0.0

    def set_master_volume(self, value: float) -> bool:
        ep = self._get_endpoint()
        if ep is None:
            return False
        try:
            ep.SetMasterVolumeLevelScalar(max(0.0, min(1.0, value)), None)
            return True
        except Exception as exc:
            self._last_error = str(exc)
            return False

    def set_master_mute(self, muted: bool) -> bool:
        ep = self._get_endpoint()
        if ep is None:
            return False
        try:
            ep.SetMute(1 if muted else 0, None)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------ 会话枚举
    def refresh(self, window_map: Optional[Dict[int, str]] = None) -> List[SessionInfo]:
        """重新枚举所有活动音频会话。window_map: pid -> 首个可见窗口标题。"""
        window_map = window_map or {}
        infos: List[SessionInfo] = []
        if not self.available:
            return infos

        try:
            raw_sessions = AudioUtilities.GetAllSessions()
        except Exception as exc:
            self._last_error = str(exc)
            return infos

        live: Dict[str, object] = {}
        for idx, sess in enumerate(raw_sessions):
            try:
                pid = int(sess.ProcessId)
            except Exception:
                try:
                    pid = int(sess.Process.pid) if sess.Process else 0
                except Exception:
                    pid = 0

            try:
                instance = str(sess.InstanceIdentifier or "")
            except Exception:
                instance = ""
            key = f"{pid}|{instance}" if instance else f"{pid}|#{idx}"

            try:
                vol_iface = sess.SimpleAudioVolume
                volume = float(vol_iface.GetMasterVolume())
                muted = bool(vol_iface.GetMute())
            except Exception:
                vol_iface = None
                volume, muted = 0.0, False

            try:
                meter = sess._ctl.QueryInterface(IAudioMeterInformation)
                peak = float(meter.GetPeakValue())
            except Exception:
                peak = 0.0

            try:
                display = str(sess.DisplayName or "")
            except Exception:
                display = ""

            name, exe = _safe_process_info(pid)
            title = window_map.get(pid, "")
            is_system = pid in (0, 4) or not name or "@" in display[:2] or "System Sounds" in display
            if is_system and not name:
                name = "系统声音"

            infos.append(
                SessionInfo(
                    key=key,
                    pid=pid,
                    name=name or "未知程序",
                    exe=exe,
                    display_name=display,
                    volume=max(0.0, min(1.0, volume)),
                    muted=muted,
                    peak=max(0.0, min(1.0, peak)),
                    window_title=title,
                    is_background=not bool(title),
                    is_system=is_system,
                )
            )
            if vol_iface is not None:
                live[key] = vol_iface
                self._baseline.setdefault(key, volume)

        self._sessions = live
        # 清理已经消失的会话基线
        for old in list(self._baseline):
            if old not in live:
                self._baseline.pop(old, None)
        return infos

    # ------------------------------------------------------------------ 会话控制
    def set_volume(self, key: str, value: float) -> bool:
        iface = self._sessions.get(key)
        if iface is None:
            return False
        try:
            iface.SetMasterVolume(max(0.0, min(1.0, float(value))), None)
            return True
        except Exception as exc:
            self._last_error = str(exc)
            return False

    def set_mute(self, key: str, muted: bool) -> bool:
        iface = self._sessions.get(key)
        if iface is None:
            return False
        try:
            iface.SetMute(1 if muted else 0, None)
            return True
        except Exception:
            return False

    def set_volume_by_pid(self, pid: int, value: float) -> int:
        """把一个进程的所有音频会话一起设置，返回成功条数。"""
        count = 0
        for key in list(self._sessions):
            if key.split("|", 1)[0] == str(pid):
                count += int(self.set_volume(key, value))
        return count

    def apply_gain(self, sessions: List[SessionInfo], db: float) -> int:
        """按 dB 对每个会话做相对增益（受 100% 上限约束），并自动取消静音。"""
        factor = db_to_factor(db)
        changed = 0
        for s in sessions:
            if s.key not in self._sessions:
                continue
            if self.set_volume(s.key, min(1.0, s.volume * factor)):
                self.set_mute(s.key, False)
                changed += 1
        return changed

    def max_all(self, sessions: List[SessionInfo]) -> int:
        changed = 0
        for s in sessions:
            if self.set_volume(s.key, 1.0):
                self.set_mute(s.key, False)
                changed += 1
        return changed

    def snapshot_baseline(self, sessions: List[SessionInfo]) -> None:
        for s in sessions:
            self._baseline[s.key] = s.volume

    def restore_all(self, sessions: List[SessionInfo]) -> int:
        changed = 0
        for s in sessions:
            target = self._baseline.get(s.key, s.volume)
            changed += int(self.set_volume(s.key, target))
        return changed

    @property
    def last_error(self) -> str:
        return self._last_error
