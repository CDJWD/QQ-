#!/usr/bin/env python3
"""QQ 群相册下载桌面应用入口。"""

from __future__ import annotations

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

from app.ui.main_window import MainWindow


def main() -> int:
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
