"""首页：输入群号。"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class HomePage(QWidget):
    continue_clicked = Signal(str)  # group_id
    resume_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        title = QLabel('QQ 群相册下载')
        title.setObjectName('heroTitle')
        subtitle = QLabel('输入群号，在内置浏览器登录后选择相册下载。支持 ZIP / 原图，并可断点续传。')
        subtitle.setObjectName('heroSub')
        subtitle.setWordWrap(True)

        self.group_input = QLineEdit()
        self.group_input.setPlaceholderText('请输入 QQ 群号，例如 464121892')
        self.group_input.setClearButtonEnabled(True)

        self.btn_start = QPushButton('打开相册并登录')
        self.btn_start.setObjectName('primaryBtn')
        self.btn_start.clicked.connect(self._on_start)

        self.btn_resume = QPushButton('打开上次未完成任务')
        self.btn_resume.setObjectName('secondaryBtn')
        self.btn_resume.clicked.connect(self.resume_clicked.emit)

        tip = QLabel('提示：需使用有该群相册权限的 QQ 账号登录。')
        tip.setObjectName('muted')

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 40, 48, 40)
        layout.setSpacing(16)
        layout.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(12)
        layout.addWidget(QLabel('群号'))
        layout.addWidget(self.group_input)
        row = QHBoxLayout()
        row.addWidget(self.btn_start)
        row.addWidget(self.btn_resume)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addWidget(tip)
        layout.addStretch(2)

    def _on_start(self) -> None:
        gid = self.group_input.text().strip()
        if not gid.isdigit():
            self.group_input.setFocus()
            self.group_input.selectAll()
            return
        self.continue_clicked.emit(gid)
