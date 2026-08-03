"""相册勾选与下载选项。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class AlbumsPage(QWidget):
    back_clicked = Signal()
    download_clicked = Signal(dict)  # {selected, mode, saveDir}

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._albums: list[dict] = []

        self.title = QLabel('选择要下载的相册')
        self.title.setObjectName('pageTitle')
        self.hint = QLabel('拉取中…')
        self.hint.setObjectName('muted')

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['选择', '相册名称', '数量'])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)

        self.btn_all = QPushButton('全选')
        self.btn_none = QPushButton('全不选')
        self.btn_all.setObjectName('secondaryBtn')
        self.btn_none.setObjectName('secondaryBtn')
        self.btn_all.clicked.connect(lambda: self._set_all(True))
        self.btn_none.clicked.connect(lambda: self._set_all(False))

        self.mode_zip = QRadioButton('保存为 ZIP（按相册打包，超大相册自动分卷）')
        self.mode_photos = QRadioButton('直接保存照片/视频（每个相册一个文件夹）')
        self.mode_zip.setChecked(True)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.mode_zip)
        self.mode_group.addButton(self.mode_photos)
        self.mode_zip.setObjectName('modeRadio')
        self.mode_photos.setObjectName('modeRadio')

        mode_box = QWidget()
        mode_box.setObjectName('modeBox')
        mode_lay = QVBoxLayout(mode_box)
        mode_lay.setContentsMargins(12, 10, 12, 10)
        mode_lay.setSpacing(4)
        mode_lay.addWidget(self.mode_zip)
        mode_lay.addWidget(self.mode_photos)

        self.save_edit = QLineEdit()
        self.save_edit.setPlaceholderText('选择保存目录')
        default = str(Path.home() / 'Downloads' / 'QQ群相册')
        self.save_edit.setText(default)
        self.btn_browse = QPushButton('浏览…')
        self.btn_browse.setObjectName('secondaryBtn')
        self.btn_browse.clicked.connect(self._browse)

        self.btn_back = QPushButton('返回')
        self.btn_back.setObjectName('secondaryBtn')
        self.btn_back.clicked.connect(self.back_clicked.emit)

        self.btn_download = QPushButton('开始下载')
        self.btn_download.setObjectName('primaryBtn')
        self.btn_download.clicked.connect(self._on_download)

        sel_row = QHBoxLayout()
        sel_row.addWidget(self.btn_all)
        sel_row.addWidget(self.btn_none)
        sel_row.addStretch(1)

        path_row = QHBoxLayout()
        path_row.addWidget(self.save_edit, 1)
        path_row.addWidget(self.btn_browse)

        bottom = QHBoxLayout()
        bottom.addWidget(self.btn_back)
        bottom.addStretch(1)
        bottom.addWidget(self.btn_download)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(10)
        layout.addWidget(self.title)
        layout.addWidget(self.hint)
        layout.addLayout(sel_row)
        layout.addWidget(self.table, 1)
        layout.addWidget(QLabel('保存方式'))
        layout.addWidget(mode_box)
        layout.addWidget(QLabel('保存目录'))
        layout.addLayout(path_row)
        layout.addLayout(bottom)

    def set_loading(self, loading: bool, text: str = '') -> None:
        self.btn_download.setEnabled(not loading)
        self.hint.setText(text or ('拉取相册列表中…' if loading else ''))

    def set_albums(self, albums: list[dict]) -> None:
        self._albums = albums
        self.table.setRowCount(0)
        for a in albums:
            row = self.table.rowCount()
            self.table.insertRow(row)
            chk = QCheckBox()
            chk.setChecked(True)
            wrap = QWidget()
            lay = QHBoxLayout(wrap)
            lay.setContentsMargins(8, 0, 8, 0)
            lay.addWidget(chk, 0, Qt.AlignmentFlag.AlignCenter)
            self.table.setCellWidget(row, 0, wrap)
            self.table.setItem(row, 1, QTableWidgetItem(a.get('title') or ''))
            self.table.setItem(row, 2, QTableWidgetItem(str(a.get('photoCount') or 0)))
        self.hint.setText(f'共 {len(albums)} 个相册，请勾选后开始下载')

    def _set_all(self, checked: bool) -> None:
        for row in range(self.table.rowCount()):
            wrap = self.table.cellWidget(row, 0)
            if wrap:
                chk = wrap.findChild(QCheckBox)
                if chk:
                    chk.setChecked(checked)

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, '选择保存目录', self.save_edit.text())
        if path:
            self.save_edit.setText(path)

    def _on_download(self) -> None:
        selected = []
        for row in range(self.table.rowCount()):
            wrap = self.table.cellWidget(row, 0)
            chk = wrap.findChild(QCheckBox) if wrap else None
            if chk and chk.isChecked():
                selected.append(self._albums[row])
        save_dir = self.save_edit.text().strip()
        if not selected or not save_dir:
            return
        mode = 'photos' if self.mode_photos.isChecked() else 'zip'
        self.download_clicked.emit({
            'selected': selected,
            'mode': mode,
            'saveDir': save_dir,
            'allAlbums': self._albums,
        })
