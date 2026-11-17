# -*- coding: utf-8 -*-
"""Equalizer APO 前级增益集成。

Windows 用户态 API 无法把音频推过 100%，唯一干净的做法是让音频驱动层
（Equalizer APO 的 APO 滤镜）做数字前级放大。本模块只读写它的 config.txt，
不改动注册表、不需要管理员权限、不重启音频服务，Equalizer APO 会自动热重载。
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Optional, Tuple

from core.apo_install import CANDIDATE_CONFIGS, enabled_devices

BACKUP_SUFFIX = ".luckybooster.bak"
PREAMP_RE = re.compile(r"^\s*Preamp\s*:\s*([-+]?\d+(?:\.\d+)?)\s*dB", re.I)
DEVICE_RE = re.compile(r"^\s*Device\s*:", re.I)

DOWNLOAD_URL = "https://sourceforge.net/projects/equalizerapo/"


class EqualizerAPO:
    def __init__(self) -> None:
        self.config_path: Optional[Path] = None
        for candidate in CANDIDATE_CONFIGS:
            if candidate.is_file():
                self.config_path = candidate
                break

    @property
    def installed(self) -> bool:
        return self.config_path is not None

    def read_config(self) -> str:
        if not self.installed:
            return ""
        try:
            return self.config_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            try:
                return self.config_path.read_text(encoding="utf-16", errors="replace")
            except Exception:
                return ""

    def read_preamp(self) -> Optional[float]:
        for line in self.read_config().splitlines():
            m = PREAMP_RE.match(line)
            if m:
                return float(m.group(1))
        return None

    def set_preamp(self, db: float) -> Tuple[bool, str]:
        """写入前级增益。会自动备份一次原始配置。返回 (成功, 说明)。"""
        if not self.installed:
            return False, "未检测到 Equalizer APO"
        path = self.config_path
        backup = path.with_suffix(path.suffix + BACKUP_SUFFIX)
        try:
            original = self.read_config()
            if not backup.exists():
                # 写入备份（保留原始编码内容）
                try:
                    backup.write_text(original, encoding="utf-8")
                except Exception:
                    pass
            lines = original.splitlines() or []
            new_line = f"Preamp: {db:g} dB"
            replaced = False
            for i, line in enumerate(lines):
                if PREAMP_RE.match(line):
                    lines[i] = new_line
                    replaced = True
                    break
            if not replaced:
                insert_at = 0
                for i, line in enumerate(lines):
                    if DEVICE_RE.match(line):
                        insert_at = i + 1
                        break
                lines.insert(insert_at, new_line)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return True, f"已写入 {new_line}，Equalizer APO 会自动生效"
        except Exception as exc:
            return False, f"写入失败：{exc}（可尝试以管理员身份运行）"

    def restore(self) -> Tuple[bool, str]:
        if not self.installed:
            return False, "未检测到 Equalizer APO"
        path = self.config_path
        backup = path.with_suffix(path.suffix + BACKUP_SUFFIX)
        try:
            if backup.exists():
                shutil.copy2(backup, path)
                return True, "已恢复原始配置"
            # 没有备份则只移除 Preamp 行
            lines = [l for l in self.read_config().splitlines() if not PREAMP_RE.match(l)]
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return True, "已移除前级增益行"
        except Exception as exc:
            return False, f"恢复失败：{exc}"

    @property
    def ready(self) -> bool:
        """已安装且至少对一个音频设备启用了 APO 滤镜。"""
        return self.installed and bool(enabled_devices())

    @property
    def status_text(self) -> str:
        if not self.installed:
            return "未安装 · 内置官方安装包，一键装好即可突破 100% 上限"
        if not enabled_devices():
            return "已安装 · 尚无设备启用 APO 滤镜，前级增益不会生效"
        cur = self.read_preamp()
        return f"已就绪 · 当前前级增益 {cur:g} dB" if cur is not None else "已就绪 · 未设置前级增益"
