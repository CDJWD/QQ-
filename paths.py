"""资源路径：开发目录与 PyInstaller 打包后均可定位。"""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, 'frozen', False))


def bundle_dir() -> Path:
    """打包后数据目录（onedir 下为 _internal）；开发时为项目根。"""
    if is_frozen():
        return Path(getattr(sys, '_MEIPASS'))
    return Path(__file__).resolve().parent.parent


def resource(*parts: str) -> Path:
    return bundle_dir().joinpath(*parts)
