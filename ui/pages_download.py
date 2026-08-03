"""下载进度页。"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class DownloadPage(QWidget):
    pause_clicked = Signal()
    resume_clicked = Signal()
    stop_clicked = Signal()
    home_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = QLabel('正在下载')
        self.title.setObjectName('pageTitle')
        self.status = QLabel('准备中…')
        self.status.setObjectName('statusLine')

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setObjectName('logView')

        self.btn_pause = QPushButton('暂停')
        self.btn_pause.setObjectName('secondaryBtn')
        self.btn_resume = QPushButton('继续')
        self.btn_resume.setObjectName('secondaryBtn')
        self.btn_resume.setEnabled(False)
        self.btn_stop = QPushButton('停止')
        self.btn_stop.setObjectName('secondaryBtn')
        self.btn_home = QPushButton('返回首页')
        self.btn_home.setObjectName('primaryBtn')
        self.btn_home.setEnabled(False)

        self.btn_pause.clicked.connect(self._on_pause)
        self.btn_resume.clicked.connect(self._on_resume)
        self.btn_stop.clicked.connect(self.stop_clicked.emit)
        self.btn_home.clicked.connect(self.home_clicked.emit)

        row = QHBoxLayout()
        row.addWidget(self.btn_pause)
        row.addWidget(self.btn_resume)
        row.addWidget(self.btn_stop)
        row.addStretch(1)
        row.addWidget(self.btn_home)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(10)
        layout.addWidget(self.title)
        layout.addWidget(self.status)
        layout.addWidget(self.progress)
        layout.addWidget(self.log, 1)
        layout.addLayout(row)

    def reset_ui(self) -> None:
        self.progress.setValue(0)
        self.log.clear()
        self.status.setText('准备中…')
        self.btn_pause.setEnabled(True)
        self.btn_resume.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_home.setEnabled(False)

    def append_log(self, line: str) -> None:
        self.log.appendPlainText(line)
        self.status.setText(line)

    def set_progress(self, current: int, total: int) -> None:
        if total <= 0:
            self.progress.setValue(0)
            return
        self.progress.setValue(int(current * 100 / total))

    def set_finished(self) -> None:
        self.btn_pause.setEnabled(False)
        self.btn_resume.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_home.setEnabled(True)

    def _on_pause(self) -> None:
        self.btn_pause.setEnabled(False)
        self.btn_resume.setEnabled(True)
        self.pause_clicked.emit()

    def _on_resume(self) -> None:
        self.btn_pause.setEnabled(True)
        self.btn_resume.setEnabled(False)
        self.resume_clicked.emit()
