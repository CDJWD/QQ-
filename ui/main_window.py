"""主窗口：页面切换与下载编排。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, Qt, Slot
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.downloader import BridgeSyncCaller, DownloadWorker
from app.core import state as state_mod
from app.ui.pages_albums import AlbumsPage
from app.ui.pages_download import DownloadPage
from app.ui.pages_home import HomePage
from app.ui.pages_login import LoginPage


STYLE = """
QWidget {
  background: #f6f4f1;
  color: #1c1917;
  font-size: 14px;
}
QLabel#heroTitle {
  font-size: 32px;
  font-weight: 700;
  color: #0c0a09;
}
QLabel#heroSub, QLabel#muted {
  color: #57534e;
}
QLabel#pageTitle {
  font-size: 22px;
  font-weight: 650;
}
QLabel#statusLine {
  color: #292524;
}
QLineEdit {
  background: #ffffff;
  border: 1px solid #d6d3d1;
  border-radius: 8px;
  padding: 10px 12px;
  selection-background-color: #292524;
}
QPushButton#primaryBtn {
  background: #1c1917;
  color: #fafaf9;
  border: none;
  border-radius: 8px;
  padding: 10px 18px;
  font-weight: 600;
}
QPushButton#primaryBtn:disabled {
  background: #a8a29e;
}
QPushButton#primaryBtn:hover:!disabled {
  background: #44403c;
}
QPushButton#secondaryBtn {
  background: #ffffff;
  color: #1c1917;
  border: 1px solid #d6d3d1;
  border-radius: 8px;
  padding: 9px 14px;
}
QPushButton#secondaryBtn:hover {
  background: #f5f5f4;
}
QTableWidget {
  background: #ffffff;
  border: 1px solid #e7e5e4;
  border-radius: 8px;
  gridline-color: #f5f5f4;
}
QHeaderView::section {
  background: #fafaf9;
  padding: 8px;
  border: none;
  border-bottom: 1px solid #e7e5e4;
}
QPlainTextEdit#logView {
  background: #1c1917;
  color: #e7e5e4;
  border-radius: 8px;
  padding: 10px;
  font-family: Consolas, "Courier New", monospace;
  font-size: 12px;
}
QProgressBar {
  border: 1px solid #d6d3d1;
  border-radius: 6px;
  background: #ffffff;
  text-align: center;
  height: 18px;
}
QProgressBar::chunk {
  background: #292524;
  border-radius: 5px;
}
QRadioButton, QCheckBox {
  spacing: 10px;
  padding: 8px 4px;
  background: transparent;
}
QWidget#modeBox {
  background: #ffffff;
  border: 1px solid #e7e5e4;
  border-radius: 8px;
}
QRadioButton::indicator {
  width: 18px;
  height: 18px;
  border-radius: 10px;
  border: 2px solid #a8a29e;
  background: #ffffff;
}
QRadioButton::indicator:hover {
  border-color: #57534e;
}
QRadioButton::indicator:checked {
  border: 5px solid #1c1917;
  background: #fafaf9;
  width: 8px;
  height: 8px;
}
QCheckBox::indicator {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  border: 2px solid #a8a29e;
  background: #ffffff;
}
QCheckBox::indicator:hover {
  border-color: #57534e;
}
QCheckBox::indicator:checked {
  border: 2px solid #1c1917;
  background: #1c1917;
  image: url("__CHECK_ICON__");
}
QRadioButton:checked, QCheckBox:checked {
  color: #0c0a09;
  font-weight: 600;
}
QRadioButton:!checked, QCheckBox:!checked {
  color: #57534e;
  font-weight: 400;
}
"""


def _ensure_check_icon() -> Path:
    """生成勾选图标：自定义 indicator 后系统勾号会消失。"""
    # 放在用户目录，避免样式表 url 含中文路径失效
    path = Path.home() / '.qq_album_downloader' / 'check.png'
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return path
    img = QImage(16, 16, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor('#ffffff'))
    pen.setWidth(2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.drawPolyline([QPoint(3, 8), QPoint(6, 11), QPoint(13, 4)])
    painter.end()
    img.save(str(path))
    return path


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle('QQ 群相册下载')
        self.resize(1100, 760)
        self.group_id = ''
        self.albums: list[dict] = []
        self.task_state: dict[str, Any] | None = None
        self.worker: DownloadWorker | None = None
        self.sync_caller: BridgeSyncCaller | None = None

        self.stack = QStackedWidget()
        self.home = HomePage()
        self.login = LoginPage()
        self.albums_page = AlbumsPage()
        self.download_page = DownloadPage()
        self.stack.addWidget(self.home)
        self.stack.addWidget(self.login)
        self.stack.addWidget(self.albums_page)
        self.stack.addWidget(self.download_page)

        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.stack)
        self.setCentralWidget(root)
        check_icon = _ensure_check_icon().as_posix()
        self.setStyleSheet(STYLE.replace('__CHECK_ICON__', check_icon))

        self.home.continue_clicked.connect(self._open_login)
        self.home.resume_clicked.connect(self._resume_last)
        self.login.back_clicked.connect(lambda: self.stack.setCurrentWidget(self.home))
        self.login.start_processing.connect(self._fetch_albums)
        self.albums_page.back_clicked.connect(lambda: self.stack.setCurrentWidget(self.login))
        self.albums_page.download_clicked.connect(self._start_download)
        self.download_page.pause_clicked.connect(self._pause)
        self.download_page.resume_clicked.connect(self._resume)
        self.download_page.stop_clicked.connect(self._stop)
        self.download_page.home_clicked.connect(self._to_home)

    def _open_login(self, group_id: str) -> None:
        self.group_id = group_id
        self.stack.setCurrentWidget(self.login)
        self.login.open_group(group_id)

    def _resume_last(self) -> None:
        st = state_mod.find_latest_state(Path.home() / 'Downloads')
        if not st:
            QMessageBox.information(self, '提示', '没有找到未完成的任务状态文件。')
            return
        self.group_id = str(st.get('groupId') or '')
        self.task_state = st
        # need login page open first for bridge
        self.stack.setCurrentWidget(self.login)
        self.login.open_group(self.group_id)
        QMessageBox.information(
            self,
            '续传',
            '请先在内置浏览器完成登录，然后点击「开始处理」拉取列表；\n'
            '若仍选择相同保存目录与相册，下载页会按 state.json 跳过已完成项。\n'
            f"群号: {self.group_id}\n目录: {st.get('saveDir')}",
        )

    def _fetch_albums(self) -> None:
        bridge = self.login.get_bridge()
        if not bridge:
            QMessageBox.warning(self, '错误', '浏览器未就绪')
            return
        # 先留在登录页拉取，避免用户误以为页面丢了；成功后再跳转
        self.login.status_label.setText('正在拉取相册列表，请稍候（勿关闭/刷新页面）…')
        self.login.btn_start.setEnabled(False)

        def on_result(result: dict) -> None:
            if not result.get('ok'):
                err = str(result.get('error') or '未知错误')

                def after_diag(info: dict) -> None:
                    detail = (
                        f"{err}\n\n"
                        f"页面: {info.get('href', '')}\n"
                        f"GroupZone: {info.get('hasGroupZone')}  "
                        f"GPHOTO: {info.get('hasGPHOTO')}  "
                        f"getAlbumList: {info.get('hasGetAlbumList')}\n"
                        f"seajs: {info.get('hasSeajs')}  API: {info.get('hasAPI')}  "
                        f"ready: {info.get('apiReady')}"
                    )
                    self.login.status_label.setText(f'拉取失败: {err}')
                    self.login.btn_start.setEnabled(True)
                    QMessageBox.warning(self, '拉取失败', detail)

                bridge.diagnose(after_diag)
                return

            albums = result.get('data') or []
            if not albums:
                self.login.status_label.setText('拉取到 0 个相册')
                self.login.btn_start.setEnabled(True)
                QMessageBox.information(self, '提示', '接口返回 0 个相册，请确认该群确有相册且账号有权限。')
                return

            self.albums = albums
            self.stack.setCurrentWidget(self.albums_page)
            self.albums_page.set_albums(albums)
            self.albums_page.set_loading(False)
            if self.task_state:
                save_dir = self.task_state.get('saveDir') or ''
                mode = self.task_state.get('mode') or 'zip'
                selected = set(self.task_state.get('selectedAlbumIds') or [])
                if save_dir:
                    self.albums_page.save_edit.setText(save_dir)
                if mode == 'photos':
                    self.albums_page.mode_photos.setChecked(True)
                else:
                    self.albums_page.mode_zip.setChecked(True)
                if selected:
                    for row, a in enumerate(albums):
                        wrap = self.albums_page.table.cellWidget(row, 0)
                        chk = wrap.findChild(QCheckBox) if wrap else None
                        if chk:
                            chk.setChecked(a.get('id') in selected)
                    self.albums_page.hint.setText(
                        f'已载入续传任务（群 {self.group_id}），共 {len(albums)} 个相册'
                    )

        bridge.list_albums(on_result)

    def _start_download(self, opts: dict) -> None:
        bridge = self.login.get_bridge()
        if not bridge:
            QMessageBox.warning(self, '错误', '请先保持登录页浏览器会话')
            return
        selected = opts['selected']
        mode = opts['mode']
        save_dir = opts['saveDir']
        Path(save_dir).mkdir(parents=True, exist_ok=True)

        # merge with existing state if same group+dir
        existing = state_mod.load_state(save_dir, self.group_id)
        selected_ids = [a['id'] for a in selected]
        if (
            existing
            and existing.get('mode') == mode
            and existing.get('saveDir') == save_dir
        ):
            # keep done progress for selected albums
            st = existing
            st['selectedAlbumIds'] = selected_ids
            for a in selected:
                if a['id'] not in st['albums']:
                    st['albums'][a['id']] = {
                        'title': a.get('title') or '',
                        'photoCount': a.get('photoCount') or 0,
                        'status': 'pending',
                        'doneParts': [],
                        'donePhotoIds': [],
                        'error': None,
                    }
                else:
                    st['albums'][a['id']]['title'] = a.get('title') or st['albums'][a['id']].get('title')
                    st['albums'][a['id']]['photoCount'] = a.get('photoCount') or 0
                    if st['albums'][a['id']].get('status') == 'failed':
                        st['albums'][a['id']]['status'] = 'pending'
            state_mod.save_state(st)
            self.task_state = st
        else:
            self.task_state = state_mod.new_state(
                self.group_id, mode, save_dir, self.albums or opts.get('allAlbums') or selected, selected_ids
            )
            state_mod.save_state(self.task_state)

        self.download_page.reset_ui()
        self.stack.setCurrentWidget(self.download_page)
        self.download_page.append_log(f"任务已创建，状态文件: {state_mod.state_path(save_dir, self.group_id)}")

        self.sync_caller = BridgeSyncCaller(self)
        self.sync_caller.request.connect(
            self._on_bridge_request, Qt.ConnectionType.QueuedConnection
        )

        self.worker = DownloadWorker(self.task_state, self.sync_caller, self)
        self.worker.progress.connect(self.download_page.append_log)
        self.worker.album_progress.connect(self._on_album_progress)
        self.worker.finished_ok.connect(self._on_worker_done)
        self.worker.finished_err.connect(self._on_worker_err)
        self.worker.start()

    @Slot(str, object)
    def _on_bridge_request(self, method: str, payload: object) -> None:
        bridge = self.login.get_bridge()
        caller = self.sync_caller
        if not bridge or not caller:
            return
        data = payload if isinstance(payload, dict) else {}

        def reply(result: dict) -> None:
            caller.set_result(result)

        if method == 'get_album_zip':
            bridge.get_album_zip_url(data['albumId'], data['title'], reply)
        elif method == 'get_batch_zip':
            bridge.get_batch_zip_url(data['albumId'], data['title'], data['photoIds'], reply)
        elif method == 'list_photos':
            bridge.list_photos(data['albumId'], reply)
        else:
            reply({'ok': False, 'error': f'unknown method {method}'})

    def _on_album_progress(self, album_id: str, status: str, done: int, total: int) -> None:
        self.download_page.set_progress(done, total)

    def _on_worker_done(self) -> None:
        self.download_page.set_finished()
        self.download_page.append_log('可返回首页或关闭程序。')

    def _on_worker_err(self, err: str) -> None:
        self.download_page.set_finished()
        self.download_page.append_log(f'异常结束: {err}')

    def _pause(self) -> None:
        if self.worker:
            self.worker.request_pause()
            self.download_page.append_log('已暂停')

    def _resume(self) -> None:
        if self.worker:
            self.worker.request_resume()
            self.download_page.append_log('继续下载')

    def _stop(self) -> None:
        if self.worker:
            self.worker.request_stop()
            self.download_page.append_log('正在停止…')

    def _to_home(self) -> None:
        self.stack.setCurrentWidget(self.home)
