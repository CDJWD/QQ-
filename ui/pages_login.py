"""登录页：内置 WebEngine。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.bridge import LoginWatcher, QQBridge


class LoginPage(QWidget):
    back_clicked = Signal()
    start_processing = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.group_id = ''
        self.bridge: QQBridge | None = None
        self.watcher: LoginWatcher | None = None

        self.status_label = QLabel('请在下方页面登录 QQ')
        self.status_label.setObjectName('statusLine')

        self.btn_back = QPushButton('返回')
        self.btn_back.setObjectName('secondaryBtn')
        self.btn_back.clicked.connect(self.back_clicked.emit)

        self.btn_refresh = QPushButton('刷新页面')
        self.btn_refresh.setObjectName('secondaryBtn')
        self.btn_refresh.clicked.connect(self._refresh)

        self.btn_start = QPushButton('开始处理')
        self.btn_start.setObjectName('primaryBtn')
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self._on_start)

        top = QHBoxLayout()
        top.addWidget(self.status_label, 1)
        top.addWidget(self.btn_back)
        top.addWidget(self.btn_refresh)
        top.addWidget(self.btn_start)

        profile_dir = Path.home() / '.qq_album_downloader' / 'webengine'
        profile_dir.mkdir(parents=True, exist_ok=True)
        self.profile = QWebEngineProfile('QQAlbumProfile', self)
        self.profile.setPersistentStoragePath(str(profile_dir))
        self.profile.setCachePath(str(profile_dir / 'cache'))
        self.profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )
        self.page_engine = QWebEnginePage(self.profile, self)
        self.web = QWebEngineView()
        self.web.setPage(self.page_engine)
        settings = self.web.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        layout.addLayout(top)
        layout.addWidget(self.web, 1)

    def open_group(self, group_id: str) -> None:
        self.group_id = group_id
        self.btn_start.setEnabled(False)
        self.status_label.setText('正在打开群相册，请登录…')
        url = f'https://h5.qzone.qq.com/groupphoto/index?inqq=1&groupId={group_id}'
        if self.watcher:
            self.watcher.stop()
        self.bridge = QQBridge(self.web.page(), self)
        self.watcher = LoginWatcher(self.bridge, self)
        self.watcher.reset_session()
        self.watcher.ready_changed.connect(self._on_ready)
        self.watcher.status.connect(self.status_label.setText)
        self.watcher.need_refresh.connect(self._auto_refresh)
        try:
            self.web.loadFinished.disconnect(self._on_load_finished)
        except Exception:
            pass
        self.web.loadFinished.connect(self._on_load_finished)
        try:
            self.web.urlChanged.disconnect(self._on_url_changed)
        except Exception:
            pass
        self.web.urlChanged.connect(self._on_url_changed)
        self.web.setUrl(QUrl(url))

    def _on_url_changed(self, url: QUrl) -> None:
        # 登录跳转后重新给页面初始化时间，避免立刻误刷
        if self.watcher:
            self.watcher.notify_reload_started()

    def _on_load_finished(self, ok: bool) -> None:
        if self.watcher:
            self.watcher.start()

    def _on_ready(self, ready: bool) -> None:
        self.btn_start.setEnabled(ready)
        if ready and self.watcher:
            self.watcher._auto_refresh_count = 0  # noqa: SLF001

    def _auto_refresh(self) -> None:
        self.status_label.setText('页面状态未就绪，正在自动刷新…')
        if self.watcher:
            self.watcher.notify_reload_started()
        self.web.reload()

    def _refresh(self) -> None:
        if self.watcher:
            self.watcher.notify_reload_started()
            # 手动刷新时允许再自动刷几次
            self.watcher._auto_refresh_count = 0  # noqa: SLF001
        self.web.reload()

    def _on_start(self) -> None:
        if self.watcher:
            self.watcher.stop()
        self.start_processing.emit()

    def get_bridge(self) -> QQBridge | None:
        return self.bridge
