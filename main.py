#!/usr/bin/env python3
"""QQ 群相册下载桌面应用入口。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# allow `python app/main.py` and `python -m app.main`
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401  ensure webengine init

from app.paths import is_frozen
from app.ui.main_window import MainWindow


def _prepare_webengine_env() -> None:
    """打包后确保 QtWebEngine 能找到进程与资源。"""
    if not is_frozen():
        return
    base = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
    # PyInstaller 6 onedir: 依赖在 _internal；兼容旧布局
    candidates = [
        base / 'PySide6' / 'QtWebEngineProcess.exe',
        base / 'QtWebEngineProcess.exe',
        Path(sys.executable).parent / '_internal' / 'PySide6' / 'QtWebEngineProcess.exe',
        Path(sys.executable).parent / 'PySide6' / 'QtWebEngineProcess.exe',
    ]
    for proc in candidates:
        if proc.is_file():
            os.environ.setdefault('QTWEBENGINEPROCESS_PATH', str(proc))
            os.environ['PATH'] = str(proc.parent) + os.pathsep + os.environ.get('PATH', '')
            break


def main() -> int:
    _prepare_webengine_env()
    # WebEngine needs this on some Windows setups before QApplication
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv)
    app.setApplicationName('QQ群相册下载')
    font = QFont('Microsoft YaHei UI', 10)
    app.setFont(font)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
