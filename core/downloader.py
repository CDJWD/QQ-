"""下载引擎：ZIP / 照片 / 大相册分批，支持暂停与续传。"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlparse

import requests
import urllib3
from PySide6.QtCore import QObject, QThread, Signal

from . import state as state_mod

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
ID_SAFE = re.compile(r'[^A-Za-z0-9_-]+')
LARGE_ALBUM_THRESHOLD = 500
BATCH_SIZE = 20


def safe_filename(name: str) -> str:
    name = INVALID_CHARS.sub('_', (name or '').strip())
    # 去掉首尾点和空格，避免 Windows 非法名
    name = name.strip(' .')
    return name or ''


def safe_dirname(name: str) -> str:
    return safe_filename(name) or 'unnamed'


def html_unescape(url: str) -> str:
    return (url or '').replace('&amp;', '&').strip()


def unique_photo_basename(photo: dict[str, Any], index: int) -> str:
    """生成稳定且尽量唯一的文件名（不含扩展名）。"""
    pid = str(photo.get('id') or '')
    raw_name = (photo.get('name') or '').strip()
    if raw_name:
        base = safe_filename(raw_name)
        if base:
            return f'{index:05d}_{base}'[:80]
    # QQ 照片 id 含 !! * . 等，清洗后取尾部保证可区分
    safe_id = ID_SAFE.sub('', pid)[-28:] or f'img{index:05d}'
    return f'{index:05d}_{safe_id}'


def pick_media_url(photo: dict[str, Any]) -> str | None:
    if photo.get('videoflag') and photo.get('videourl'):
        return html_unescape(photo['videourl'])
    for key in ('rawurl', 'hdurl', 'burl', 'url'):
        val = photo.get(key)
        if isinstance(val, str) and val.startswith('http'):
            return html_unescape(val)
    return None


def media_ext(url: str, is_video: bool) -> str:
    path = urlparse(url).path
    suffix = Path(unquote(path)).suffix.lower()
    if suffix in {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.mp4', '.mov', '.avi'}:
        return suffix
    return '.mp4' if is_video else '.jpg'


class HttpDownloader:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://h5.qzone.qq.com/',
        })

    def download(self, url: str, dest: Path, min_size: int = 1024) -> None:
        url = html_unescape(url)
        candidates = [url]
        if url.startswith('https://'):
            candidates.append('http://' + url[len('https://'):])
        elif url.startswith('http://'):
            candidates.append('https://' + url[len('http://'):])

        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.stat().st_size >= min_size:
            return

        last_err: Exception | None = None
        for candidate in candidates:
            tmp = dest.with_suffix(dest.suffix + '.partial')
            try:
                with self.session.get(candidate, stream=True, timeout=900, verify=False) as resp:
                    if resp.status_code != 200:
                        body = resp.content[:120]
                        raise RuntimeError(f'HTTP {resp.status_code}: {body!r}')
                    total = 0
                    with open(tmp, 'wb') as f:
                        for chunk in resp.iter_content(256 * 1024):
                            if chunk:
                                f.write(chunk)
                                total += len(chunk)
                if total < min_size:
                    tmp.unlink(missing_ok=True)
                    raise RuntimeError(f'文件过小: {total}')
                for _ in range(8):
                    try:
                        if dest.exists():
                            dest.unlink()
                        tmp.replace(dest)
                        break
                    except PermissionError:
                        time.sleep(0.4)
                else:
                    import shutil
                    shutil.copy2(tmp, dest)
                    tmp.unlink(missing_ok=True)
                return
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                tmp.unlink(missing_ok=True)
                time.sleep(0.5)
        raise RuntimeError(str(last_err))

    def download_zip_with_retry(self, url: str, dest: Path, retries: int = 8) -> None:
        """ZIP 链接可能短暂 StoreKey 未就绪，短暂重试。"""
        url = html_unescape(url).replace('https://', 'http://')
        last_err: Exception | None = None
        for attempt in range(1, retries + 1):
            tmp = dest.with_suffix(dest.suffix + '.partial')
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                with self.session.get(url, stream=True, timeout=900, verify=False) as resp:
                    if resp.status_code == 400:
                        body = resp.content[:160]
                        if b'StoreKey' in body:
                            time.sleep(2 + attempt)
                            continue
                        raise RuntimeError(f'HTTP 400: {body!r}')
                    if resp.status_code != 200:
                        raise RuntimeError(f'HTTP {resp.status_code}')
                    total = 0
                    first = b''
                    with open(tmp, 'wb') as f:
                        for chunk in resp.iter_content(256 * 1024):
                            if not chunk:
                                continue
                            if not first:
                                first = chunk[:4]
                            f.write(chunk)
                            total += len(chunk)
                if total < 1024 or not first.startswith(b'PK'):
                    tmp.unlink(missing_ok=True)
                    raise RuntimeError(f'无效 ZIP (size={total})')
                for _ in range(8):
                    try:
                        if dest.exists():
                            dest.unlink()
                        tmp.replace(dest)
                        break
                    except PermissionError:
                        time.sleep(0.4)
                else:
                    import shutil
                    shutil.copy2(tmp, dest)
                    tmp.unlink(missing_ok=True)
                return
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                tmp.unlink(missing_ok=True)
                time.sleep(1)
        raise RuntimeError(str(last_err))


class DownloadWorker(QThread):
    """在后台线程执行 HTTP 下载；URL 获取通过主线程回调。"""

    progress = Signal(str)  # log line
    album_progress = Signal(str, str, int, int)  # album_id, status, done, total
    finished_ok = Signal()
    finished_err = Signal(str)

    def __init__(
        self,
        task_state: dict[str, Any],
        bridge_caller: Any,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.task_state = task_state
        self.bridge = bridge_caller  # object with sync-like request methods using wait
        self._pause = False
        self._stop = False
        self.http = HttpDownloader()

    def request_pause(self) -> None:
        self._pause = True

    def request_resume(self) -> None:
        self._pause = False

    def request_stop(self) -> None:
        self._stop = True
        self._pause = False

    def _wait_if_paused(self) -> None:
        while self._pause and not self._stop:
            time.sleep(0.2)

    def run(self) -> None:
        try:
            mode = self.task_state.get('mode') or 'zip'
            save_dir = Path(self.task_state['saveDir'])
            albums = self.task_state.get('albums') or {}
            selected = self.task_state.get('selectedAlbumIds') or list(albums.keys())
            total_albums = len(selected)
            for idx, album_id in enumerate(selected, 1):
                if self._stop:
                    break
                self._wait_if_paused()
                info = albums.get(album_id) or {}
                if info.get('status') == 'done':
                    self.progress.emit(f'[{idx}/{total_albums}] 跳过已完成: {info.get("title")}')
                    continue
                title = info.get('title') or album_id
                photo_count = int(info.get('photoCount') or 0)
                state_mod.update_album(self.task_state, album_id, status='downloading', error=None)
                self.album_progress.emit(album_id, 'downloading', idx, total_albums)
                self.progress.emit(f'[{idx}/{total_albums}] 开始: {title} ({photo_count})')
                try:
                    if mode == 'photos':
                        self._download_photos(album_id, title, info)
                    else:
                        self._download_zip(album_id, title, photo_count, info)
                    state_mod.update_album(self.task_state, album_id, status='done', error=None)
                    self.progress.emit(f'[{idx}/{total_albums}] 完成: {title}')
                    self.album_progress.emit(album_id, 'done', idx, total_albums)
                except Exception as exc:  # noqa: BLE001
                    state_mod.update_album(self.task_state, album_id, status='failed', error=str(exc))
                    self.progress.emit(f'[{idx}/{total_albums}] 失败: {title} -> {exc}')
                    self.album_progress.emit(album_id, 'failed', idx, total_albums)
            if self._stop:
                self.progress.emit('已停止（进度已保存，可继续）')
            else:
                self.progress.emit('全部任务结束')
            self.finished_ok.emit()
        except Exception as exc:  # noqa: BLE001
            self.finished_err.emit(str(exc))

    def _download_zip(self, album_id: str, title: str, photo_count: int, info: dict) -> None:
        save_dir = Path(self.task_state['saveDir'])
        safe = safe_dirname(title)
        # large albums or previous whole-album failure -> batch
        use_batch = photo_count >= LARGE_ALBUM_THRESHOLD or bool(info.get('forceBatch'))
        if not use_batch:
            try:
                result = self.bridge.call_get_album_zip(album_id, title)
                url = (result or {}).get('downloadUrl') or ''
                if not url or result.get('code') not in (0, None):
                    raise RuntimeError(result.get('message') or '无法获取整册链接')
                dest = save_dir / f'{safe}.zip'
                self.progress.emit(f'  下载整册 ZIP…')
                self.http.download_zip_with_retry(url, dest)
                # if StoreKey forever / too large empty, fall through
                if dest.exists() and dest.stat().st_size > 1024:
                    return
                raise RuntimeError('整册 ZIP 无效')
            except Exception as exc:  # noqa: BLE001
                self.progress.emit(f'  整册失败，改分批: {exc}')
                use_batch = True

        if use_batch:
            self._download_zip_batches(album_id, title, info)

    def _download_zip_batches(self, album_id: str, title: str, info: dict) -> None:
        save_dir = Path(self.task_state['saveDir'])
        safe = safe_dirname(title)
        parts_dir = save_dir / f'{safe}_parts'
        parts_dir.mkdir(parents=True, exist_ok=True)

        photos_result = self.bridge.call_list_photos(album_id)
        photos = (photos_result or {}).get('photos') or []
        ids = [p['id'] for p in photos if p.get('id')]
        if not ids:
            raise RuntimeError('相册无照片 ID')

        total_batches = (len(ids) + BATCH_SIZE - 1) // BATCH_SIZE
        done_parts = set(info.get('doneParts') or [])
        for i in range(total_batches):
            if self._stop:
                raise RuntimeError('用户停止')
            self._wait_if_paused()
            batch_no = i + 1
            dest = parts_dir / f'{safe}_{batch_no:03d}.zip'
            if batch_no in done_parts or (dest.exists() and dest.stat().st_size > 1024):
                done_parts.add(batch_no)
                continue
            batch_ids = ids[i * BATCH_SIZE:(i + 1) * BATCH_SIZE]
            self.progress.emit(f'  分批 {batch_no}/{total_batches}…')
            result = self.bridge.call_get_batch_zip(album_id, title, batch_ids)
            url = (result or {}).get('downloadUrl') or ''
            if not url:
                raise RuntimeError(result.get('message') or f'分批 {batch_no} 无链接')
            self.http.download_zip_with_retry(url, dest)
            done_parts.add(batch_no)
            state_mod.update_album(self.task_state, album_id, doneParts=sorted(done_parts), forceBatch=True)

    def _download_photos(self, album_id: str, title: str, info: dict) -> None:
        save_dir = Path(self.task_state['saveDir'])
        album_dir = save_dir / safe_dirname(title)
        album_dir.mkdir(parents=True, exist_ok=True)
        photos_result = self.bridge.call_list_photos(album_id)
        photos = (photos_result or {}).get('photos') or []
        done_ids = set(info.get('donePhotoIds') or [])
        total = len(photos)
        self.progress.emit(f'  共 {total} 个媒体，开始逐张下载…')
        ok_count = 0
        for i, photo in enumerate(photos, 1):
            if self._stop:
                raise RuntimeError('用户停止')
            self._wait_if_paused()
            pid = str(photo.get('id') or '')
            if pid and pid in done_ids:
                ok_count += 1
                continue
            url = pick_media_url(photo)
            if not url:
                self.progress.emit(f'  跳过 {i}/{total}: 无下载地址')
                continue
            ext = media_ext(url, bool(photo.get('videoflag')))
            base = unique_photo_basename(photo, i)
            dest = album_dir / f'{base}{ext}'
            if dest.exists():
                # 序号+id 仍冲突时再加后缀，绝不覆盖
                suffix_n = 1
                while True:
                    alt = album_dir / f'{base}_{suffix_n}{ext}'
                    if not alt.exists():
                        dest = alt
                        break
                    suffix_n += 1
            try:
                self.http.download(url, dest, min_size=512)
                if pid:
                    done_ids.add(pid)
                ok_count += 1
                if i % 10 == 0 or i == total:
                    state_mod.update_album(
                        self.task_state, album_id, donePhotoIds=sorted(done_ids)
                    )
                    self.progress.emit(f'  进度 {i}/{total}（成功 {ok_count}）')
            except Exception as exc:  # noqa: BLE001
                self.progress.emit(f'  跳过 {i}/{total}: {exc}')
        state_mod.update_album(self.task_state, album_id, donePhotoIds=sorted(done_ids))
        self.progress.emit(f'  相册完成：成功 {ok_count}/{total}')


class BridgeSyncCaller(QObject):
    """把异步 bridge 回调包装成线程可等待的同步调用（通过信号往返）。"""

    request = Signal(str, object)  # method, payload
    # responses delivered via set_result from main thread

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._event = None
        self._result: Any = None
        import threading
        self._cond = threading.Condition()

    def set_result(self, result: Any) -> None:
        with self._cond:
            self._result = result
            self._cond.notify_all()

    def _call(self, method: str, payload: dict, timeout: float = 180.0) -> Any:
        with self._cond:
            self._result = None
            self.request.emit(method, payload)
            ok = self._cond.wait(timeout=timeout)
            if not ok:
                raise TimeoutError(f'等待 {method} 超时')
            result = self._result
        if not result or not result.get('ok'):
            raise RuntimeError((result or {}).get('error') or f'{method} 失败')
        return result.get('data')

    def call_get_album_zip(self, album_id: str, title: str) -> dict:
        return self._call('get_album_zip', {'albumId': album_id, 'title': title})

    def call_get_batch_zip(self, album_id: str, title: str, photo_ids: list[str]) -> dict:
        return self._call('get_batch_zip', {
            'albumId': album_id, 'title': title, 'photoIds': photo_ids,
        }, timeout=180.0)

    def call_list_photos(self, album_id: str) -> dict:
        return self._call('list_photos', {'albumId': album_id}, timeout=600.0)
